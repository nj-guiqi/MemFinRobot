# MemFin Eval Metrics Contract v1

本文档定义评测实现的函数级输入输出签名，确保：

- 评测代码与 `memfinrobot` 解耦；
- 指标实现可并行执行；
- 后续替换模型/agent 时最小改动。

## 1. Module Layout (Recommended)

- `eval/scripts/run_eval.py`：运行入口、并发调度、落盘
- `eval/scripts/replay.py`：对话回放与 trace 生成
- `eval/metrics/contracts.py`：TypedDict / dataclass 契约
- `eval/metrics/preprocess.py`：数据校验、对齐、规范化
- `eval/metrics/m1_context.py`
- `eval/metrics/m2_profile.py`
- `eval/metrics/m3_risk.py`
- `eval/metrics/m4_compliance.py`
- `eval/metrics/m5_explainability.py`
- `eval/metrics/aggregate.py`
- `eval/metrics/report.py`

## 2. Core Type Signatures

以下为 Python typing 契约（建议）。

```python
from typing import Any, Dict, List, Literal, Optional, Tuple, TypedDict

ComplianceLabel = Literal["compliant", "minor_violation", "severe_violation"]
TurnStatus = Literal["ok", "timeout", "error"]
DialogStatus = Literal["ok", "partial", "failed", "skipped"]

class RecallItem(TypedDict, total=False):
    rank: int
    item_id: str
    content: str
    score: float
    source: str
    turn_index: int
    session_id: str

class RecallTrace(TypedDict, total=False):
    query: str
    short_term_context: str
    short_term_turns: List[Dict[str, str]]
    profile_context: str
    packed_context: str
    token_count: int
    items: List[RecallItem]

class ToolTrace(TypedDict, total=False):
    tool_name: str
    args: Dict[str, Any]
    result_excerpt: str
    latency_ms: float
    error: Optional[str]

class ComplianceTrace(TypedDict, total=False):
    needs_modification: bool
    is_compliant: bool
    violations: List[Dict[str, Any]]
    risk_disclaimer_added: bool
    suitability_warning: Optional[str]

class TurnTrace(TypedDict, total=False):
    turn_pair_id: int
    user_turn_abs_idx: int
    gt_assistant_abs_idx: int
    user_text: str
    gt_assistant_text: str
    gt_turn_tags: Dict[str, Any]
    pred_assistant_text: str
    latency_ms: float
    turn_status: TurnStatus
    error: Optional[str]
    recall: Optional[RecallTrace]
    tools: List[ToolTrace]
    compliance: Optional[ComplianceTrace]
    profile_snapshot: Optional[Dict[str, Any]]

class DialogTrace(TypedDict, total=False):
    trace_version: str
    run_id: str
    dialog_id: str
    dataset_index: int
    scenario_type: Optional[str]
    difficulty: Optional[str]
    dialog_status: DialogStatus
    valid_dialog: bool
    skip_reason: Optional[str]
    worker_id: Optional[int]
    session_id: Optional[str]
    user_id: Optional[str]
    turns: List[TurnTrace]
    dialog_error: Optional[str]

class TurnEvalRow(TypedDict, total=False):
    trace_version: str
    run_id: str
    dialog_id: str
    turn_pair_id: int
    eligible_m1: bool
    eligible_m2: bool
    eligible_m3: bool
    eligible_m4: bool
    eligible_m5: bool
    required_keys_raw: List[str]
    resolved_keys: List[Dict[str, Any]]
    key_hit_flags: List[int]
    key_hit_sources: List[List[str]]
    m1_source_hits: Dict[str, int]
    constraint_contradiction: int
    risk_required_tags: List[str]
    risk_pred_tags: List[str]
    risk_tag_hits: int
    forbidden_hits: List[str]
    pred_compliance_label: ComplianceLabel
    gt_compliance_label: ComplianceLabel
    rubric_required: List[str]
    rubric_hit_items: List[str]
    judge_score_1_5: Optional[float]

class MetricResult(TypedDict, total=False):
    metric_name: str
    micro: Dict[str, float]
    macro: Dict[str, float]
    counts: Dict[str, int]
    by_dialog: Dict[str, Dict[str, float]]

class EvalSummary(TypedDict, total=False):
    run_id: str
    trace_version: str
    dataset_path: str
    metrics: Dict[str, MetricResult]
    counters: Dict[str, int]
```

## 3. Data Loading & Validation

```python
def load_dataset_jsonl(dataset_path: str) -> List[Dict[str, Any]]:
    """读取原始数据集 JSONL。异常: IOError/JSONDecodeError。"""

def classify_dialog_validity(dialog_obj: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    返回 (valid_dialog, skip_reason)。
    skip_reason 例如:
    - missing_turns
    - missing_profile_gt
    - invalid_turn_sequence
    - missing_gt_tags
    """

def normalize_dialog(dialog_obj: Dict[str, Any]) -> Dict[str, Any]:
    """对标签、枚举、文本做规范化，输出统一字典。"""

def align_turn_pairs(dialog_obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    将原始 turns 对齐成 user->assistant pair 列表。
    每个元素包含:
    - turn_pair_id
    - user_turn_abs_idx
    - gt_assistant_abs_idx
    - user_text
    - gt_assistant_text
    - gt_turn_tags
    """
```

## 4. Replay & Trace Building

```python
def run_dialog_replay(
    dialog_obj: Dict[str, Any],
    run_id: str,
    dataset_index: int,
    agent_factory: Any,
    observer_factory: Any,
    timeout_sec: int = 120,
) -> DialogTrace:
    """
    单对话回放（串行 turn），产出 DialogTrace。
    不抛出异常到上层，异常写入 dialog_error/turn.error。
    """

def build_turn_trace(
    turn_pair: Dict[str, Any],
    pred_text: str,
    observer_payload: Dict[str, Any],
    latency_ms: float,
    turn_status: TurnStatus = "ok",
    error: Optional[str] = None,
) -> TurnTrace:
    """组装标准 TurnTrace。"""
```

## 5. Preprocess for Metrics

```python
def build_turn_eval_rows(
    dialog_traces: List[DialogTrace],
    risk_tag_mapper: Dict[str, str],
    forbidden_patterns: List[str],
) -> List[TurnEvalRow]:
    """
    从 trace 构建指标中间表 turn_eval。
    负责:
    - eligibility 判定
    - key resolver
    - key 命中来源归因（short_term/long_term/profile）
    - 风险标签规范化
    - 初步命中统计
    """

def detect_key_hits_from_memory_sources(
    target_text: str,
    turn_trace: TurnTrace,
) -> List[str]:
    """
    返回命中来源列表，取值子集:
    - short_term
    - long_term
    - profile
    """

def resolve_memory_required_key(
    key: str,
    dialog_obj: Dict[str, Any],
    turn_pair_id: int,
) -> Dict[str, Any]:
    """
    返回:
    {
      "key": str,
      "resolvable": bool,
      "target_text": Optional[str],
      "resolver": str
    }
    """
```

## 6. Metric Function Signatures

### 6.1 M1 上下文关联/连续性

```python
def compute_m1_context_continuity(
    turn_rows: List[TurnEvalRow],
) -> MetricResult:
    """
    输出至少包含:
    micro:
      - key_coverage
      - strict_key_hit_rate
      - contradiction_rate
      - short_term_hit_rate
      - long_term_hit_rate
      - profile_hit_rate
    counts:
      - eligible_turns
      - required_key_total
      - required_key_hit_total
      - short_term_hit_total
      - long_term_hit_total
      - profile_hit_total
    """
```

### 6.2 M2 画像提取准确率

```python
def compute_m2_profile_accuracy(
    dialog_traces: List[DialogTrace],
    dialog_objs: Dict[str, Dict[str, Any]],
) -> MetricResult:
    """
    主口径 dialog 级:
    micro:
      - risk_level_acc
      - horizon_acc
      - liquidity_acc
      - constraints_f1
      - preferences_f1
      - profile_score
    """
```

### 6.3 M3 风险提示覆盖率

```python
def compute_m3_risk_coverage(
    turn_rows: List[TurnEvalRow],
) -> MetricResult:
    """
    micro:
      - risk_coverage
      - strict_risk_coverage_rate
    counts:
      - risk_required_total
      - risk_hit_total
      - eligible_turns
    """
```

### 6.4 M4 内容合规率

```python
def compute_m4_compliance(
    turn_rows: List[TurnEvalRow],
) -> MetricResult:
    """
    micro:
      - compliance_label_acc
      - severe_violation_rate
      - forbidden_hit_rate
    counts:
      - eligible_turns
      - severe_count
    """
```

### 6.5 M5 决策辅助解释度

```python
def compute_m5_explainability(
    turn_rows: List[TurnEvalRow],
) -> MetricResult:
    """
    micro:
      - rubric_hit_rate
      - judge_score_mean
    counts:
      - rubric_required_total
      - rubric_hit_total
      - judge_scored_turns
    """
```

## 7. Aggregation & Reporting

```python
def aggregate_all_metrics(
    run_id: str,
    dataset_path: str,
    metrics: Dict[str, MetricResult],
    counters: Dict[str, int],
) -> EvalSummary:
    """汇总五类指标。"""

def write_eval_outputs(
    output_dir: str,
    manifest: Dict[str, Any],
    dialog_traces: List[DialogTrace],
    turn_rows: List[TurnEvalRow],
    summary: EvalSummary,
) -> None:
    """统一写文件输出。"""

def render_markdown_report(summary: EvalSummary) -> str:
    """生成 Markdown 报告文本。"""
```

## 8. Concurrency Signatures

```python
def run_eval_parallel(
    dataset_path: str,
    run_id: str,
    max_workers_dialog: int,
    max_workers_judge: int,
    agent_factory: Any,
    observer_factory: Any,
) -> EvalSummary:
    """
    对话内串行、对话间并发。
    返回 EvalSummary。
    """

def evaluate_dialog_task(
    dialog_obj: Dict[str, Any],
    dataset_index: int,
    run_id: str,
    agent_factory: Any,
    observer_factory: Any,
) -> DialogTrace:
    """线程池任务函数。"""
```

## 9. Error-handling Contract

- 函数 `compute_m*` 不应抛异常中断全局流程。
- 单条样本错误写入 `turn_status/error` 或 `dialog_error`。
- 所有 metric result 必须包含 `counts`：
  - `eligible_count`
  - `skipped_count`
  - `failed_count`
- 分母为 0 时，指标值统一返回 `0.0`，并在 counts 标记 `eligible_count=0`。

## 10. Determinism Contract (Optional but Recommended)

- 同一 `run_id` 固定:
  - 数据顺序
  - 并发配置
  - LLM Judge temperature/seed
- 允许重跑比较时输出 `config_fingerprint`（模型、提示词版本、映射词表 hash）。
