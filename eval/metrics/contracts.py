"""评测契约类型定义（Trace/Metric）。"""

from typing import Any, Dict, List, Literal, Optional, TypedDict

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
    profile_gt: Optional[Dict[str, Any]]
    blueprint: Optional[Dict[str, Any]]
    raw_turns: Optional[List[Dict[str, Any]]]


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

