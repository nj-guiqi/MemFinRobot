# MemFin Eval Trace Schema v1

本文档定义评测侧的稳定数据契约。评测实现只依赖该契约，不直接依赖 `memfinrobot` 内部对象结构。

## 1. Scope

- schema version: `v1`
- encoding: `UTF-8`
- timestamp: ISO8601（建议 UTC）
- line format: JSONL（逐行 JSON 对象）

## 2. Output Artifacts

一次评测运行建议落地以下文件：

- `eval/runs/{run_id}/run_manifest.json`
- `eval/runs/{run_id}/dialog_trace.jsonl`
- `eval/runs/{run_id}/turn_eval.jsonl`
- `eval/runs/{run_id}/metrics_summary.json`
- `eval/logs/progress_{run_id}.jsonl`

## 3. Enum Conventions

### 3.1 通用状态

- `turn_status`: `ok | timeout | error`
- `dialog_status`: `ok | partial | failed | skipped`

### 3.2 合规标签

- `compliance_label`: `compliant | minor_violation | severe_violation`

### 3.3 风险标签 canonical set

建议在预处理时统一到以下集合（可扩展）：

- `volatility_risk`（波动风险）
- `no_guaranteed_return`（不保证收益）
- `market_uncertainty`（市场不确定性）
- `suitability_match`（适当性匹配）
- `not_buy_sell_advice`（不构成个股买卖建议）
- `not_investment_advice`（不构成投资建议）
- `credit_risk`（信用风险）
- `liquidity_risk`（流动性风险）
- `interest_rate_risk`（利率风险）
- `past_performance_not_future`（过往业绩不代表未来表现）
- `risk_disclosure_present`（用于处理“无明确风险提示”类要求）

## 4. Top-level Models

### 4.1 RunManifest

```json
{
  "trace_version": "v1",
  "run_id": "20260217_210500_abc123",
  "dataset_path": "eval/datasets/MemFinConv.jsonl",
  "started_at": "2026-02-17T13:05:00Z",
  "ended_at": "2026-02-17T13:21:42Z",
  "model_name": "qwen-plus",
  "workers_dialog": 4,
  "workers_judge": 2,
  "counters": {
    "total_dialogs": 8,
    "valid_dialogs": 4,
    "skipped_dialogs": 4,
    "failed_dialogs": 0,
    "total_turn_pairs": 81
  },
  "notes": "test run"
}
```

字段要求：

- required:
  - `trace_version`
  - `run_id`
  - `dataset_path`
  - `started_at`
  - `model_name`
  - `workers_dialog`
  - `workers_judge`
  - `counters`
- optional:
  - `ended_at`
  - `notes`

### 4.2 DialogTrace（`dialog_trace.jsonl` 每行一个）

```json
{
  "trace_version": "v1",
  "run_id": "20260217_210500_abc123",
  "dialog_id": "3e53acb5-c444-4640-8ac4-78ce4d26a104",
  "dataset_index": 1,
  "scenario_type": "投资教育",
  "difficulty": "hard",
  "dialog_status": "ok",
  "valid_dialog": true,
  "skip_reason": null,
  "worker_id": 2,
  "session_id": "session_3e53acb5",
  "user_id": "eval_user_3e53acb5",
  "turns": [],
  "dialog_error": null
}
```

字段要求：

- required:
  - `trace_version`
  - `run_id`
  - `dialog_id`
  - `dataset_index`
  - `dialog_status`
  - `valid_dialog`
- optional:
  - `scenario_type`
  - `difficulty`
  - `skip_reason`
  - `worker_id`
  - `session_id`
  - `user_id`
  - `turns`
  - `dialog_error`

### 4.3 TurnTrace（`DialogTrace.turns[]`）

```json
{
  "turn_pair_id": 1,
  "user_turn_abs_idx": 0,
  "gt_assistant_abs_idx": 1,
  "user_text": "我想先了解一下...",
  "gt_assistant_text": "理解资本主义市场经济...",
  "gt_turn_tags": {
    "memory_required_keys_gt": ["profile_gt.risk_level_gt"],
    "risk_disclosure_required_gt": ["市场不确定性"],
    "compliance_label_gt": "compliant",
    "explainability_rubric_gt": ["信息依据", "边界声明"]
  },
  "pred_assistant_text": "......",
  "latency_ms": 1820.5,
  "turn_status": "ok",
  "error": null,
  "recall": {
    "query": "我想先了解一下...",
    "short_term_context": "user: ...\nassistant: ...",
    "short_term_turns": [
      {"role": "user", "content": "..."},
      {"role": "assistant", "content": "..."}
    ],
    "profile_context": "",
    "packed_context": "...",
    "token_count": 302,
    "items": [
      {
        "rank": 1,
        "item_id": "8e4c...",
        "content": "用户: ...",
        "score": 0.73,
        "source": "semantic+keyword",
        "turn_index": 3,
        "session_id": "session_3e53acb5"
      }
    ]
  },
  "tools": [
    {
      "tool_name": "risk_template",
      "args": {"product_type": "fund"},
      "result_excerpt": "{\"success\":true,...}",
      "latency_ms": 55.0,
      "error": null
    }
  ],
  "compliance": {
    "needs_modification": false,
    "is_compliant": true,
    "violations": [],
    "risk_disclaimer_added": true,
    "suitability_warning": null
  },
  "profile_snapshot": {
    "risk_level": "medium",
    "investment_horizon": "long",
    "liquidity_need": "medium",
    "investment_goal": "stable_growth",
    "preferred_topics": ["基金", "债券"],
    "forbidden_assets": [],
    "max_acceptable_loss": 0.1
  }
}
```

字段要求：

- required:
  - `turn_pair_id`
  - `user_turn_abs_idx`
  - `gt_assistant_abs_idx`
  - `user_text`
  - `gt_assistant_text`
  - `gt_turn_tags`
  - `turn_status`
- optional:
  - `pred_assistant_text`
  - `latency_ms`
  - `error`
  - `recall`
  - `tools`
  - `compliance`
  - `profile_snapshot`

说明：

- `recall.items` 表示长期记忆召回条目（long-term）。
- `recall.short_term_context/short_term_turns` 表示短期窗口（近期对话）。
- 指标1命中判定使用三路并集：`short_term + long_term + profile_context`。

## 5. TurnEval Row Schema（`turn_eval.jsonl`）

每行是一个已对齐 turn pair 的指标中间结果。

```json
{
  "trace_version": "v1",
  "run_id": "20260217_210500_abc123",
  "dialog_id": "3e53acb5-c444-4640-8ac4-78ce4d26a104",
  "turn_pair_id": 1,
  "eligible_m1": true,
  "eligible_m2": false,
  "eligible_m3": true,
  "eligible_m4": true,
  "eligible_m5": true,
  "required_keys_raw": ["profile_gt.risk_level_gt"],
  "resolved_keys": [
    {
      "key": "profile_gt.risk_level_gt",
      "resolvable": true,
      "target_text": "稳健",
      "resolver": "profile_field"
    }
  ],
  "key_hit_flags": [1],
  "key_hit_sources": [["short_term"]],
  "m1_source_hits": {
    "short_term": 1,
    "long_term": 0,
    "profile": 0
  },
  "constraint_contradiction": 0,
  "risk_required_tags": ["market_uncertainty"],
  "risk_pred_tags": ["market_uncertainty", "not_buy_sell_advice"],
  "risk_tag_hits": 1,
  "forbidden_hits": [],
  "pred_compliance_label": "compliant",
  "gt_compliance_label": "compliant",
  "rubric_required": ["信息依据", "边界声明"],
  "rubric_hit_items": ["信息依据", "边界声明"],
  "judge_score_1_5": 4.0
}
```

字段要求：

- required:
  - `trace_version`
  - `run_id`
  - `dialog_id`
  - `turn_pair_id`
  - `eligible_m1`
  - `eligible_m2`
  - `eligible_m3`
  - `eligible_m4`
  - `eligible_m5`
- optional:
  - 其余指标中间字段（可按指标逐步补齐）

建议新增（用于指标1来源归因）：

- `key_hit_sources`: `List[List[str]]`，与 `key_hit_flags` 按索引对齐。
  - 每个 key 可由多个来源命中，如 `["short_term", "long_term"]`。
- `m1_source_hits`:
  - `short_term`: int
  - `long_term`: int
  - `profile`: int

## 6. Resolver Contract（memory_required_keys_gt）

`memory_required_keys_gt` 必须解析为可检验目标：

- `profile_gt.risk_level_gt`
- `profile_gt.horizon_gt`
- `profile_gt.liquidity_need_gt`
- `profile_gt.constraints_gt[i]`
- `profile_gt.preferences_gt[i]`
- `history_turn_index:n`

解析规则：

1. `profile_gt.*` 直接取 `dialog.profile_gt` 对应值。
2. `constraints/preferences` 检查索引越界。
3. `history_turn_index:n` 默认解释为第 `n` 个 user 轮（1-based）。
4. 若 user-轮解释失败，再降级尝试 turns 绝对索引（1-based）。
5. 两次都失败标记 `resolvable=false`，不进入分母。

命中判定规则（M1）：

1. 先在 `recall.short_term_context` 中检索目标值；
2. 再在 `recall.items[*].content` 中检索目标值；
3. 最后在 `recall.profile_context` 中检索目标值（若已实现画像注入）；
4. 任一来源命中即该 key 命中；
5. 同时记录命中来源用于来源归因统计。

## 7. Missing/Failure Rules

- `valid_dialog=false` 的对话不写入 `turn_eval.jsonl`。
- `turn_status != ok` 的轮可以写入 turn_eval，但默认 `eligible_m* = false`。
- 对于空数组要求：
  - `memory_required_keys_gt=[]` -> `eligible_m1=false`
  - `risk_disclosure_required_gt=[]` -> `eligible_m3=false`
  - `explainability_rubric_gt=[]` -> `eligible_m5=false`
- 必须在最终 summary 报告 `eligible_count`、`skipped_count`、`failed_count`。

## 8. Backward Compatibility

- 新版本字段只能新增，不能重命名或删除 `v1` 既有 required 字段。
- 若扩展，建议 `trace_version=v1.1` 并保持 `v1` reader 可降级读取。
