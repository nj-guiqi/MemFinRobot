**Trace Schema v1（字段级）**

建议产出 4 类文件，评测只依赖它们，不直接依赖 `memfinrobot` 内部对象。

### 1) `run_manifest.json`（一次评测运行）
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `trace_version` | string | 是 | 固定 `v1` |
| `run_id` | string | 是 | 唯一运行ID |
| `dataset_path` | string | 是 | 数据集路径 |
| `started_at` | string(datetime) | 是 | 开始时间 |
| `ended_at` | string(datetime) | 否 | 结束时间 |
| `model_name` | string | 是 | 被测模型 |
| `workers_dialog` | int | 是 | 对话并发数 |
| `workers_judge` | int | 是 | LLM-Judge并发数 |
| `counters` | object | 是 | `total_dialogs/valid_dialogs/skipped_dialogs/failed_dialogs/total_turn_pairs` |
| `notes` | string | 否 | 备注 |

### 2) `dialog_trace.jsonl`（每行一个对话）
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `run_id` | string | 是 | 关联运行 |
| `dialog_id` | string | 是 | 数据集对话ID |
| `dataset_index` | int | 是 | 行号 |
| `scenario_type` | string/null | 否 | 场景 |
| `difficulty` | string/null | 否 | 难度 |
| `valid_dialog` | bool | 是 | 是否可评测 |
| `skip_reason` | string/null | 否 | 跳过原因 |
| `session_id` | string | 否 | 会话ID |
| `user_id` | string | 否 | 用户ID |
| `worker_id` | int | 否 | 执行worker |
| `turns` | array[`TurnTrace`] | 否 | 回放轮次 |
| `dialog_error` | string/null | 否 | 对话级错误 |

### 3) `TurnTrace`（`dialog_trace.turns[]`）
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `turn_pair_id` | int | 是 | 第k个 user->assistant 配对 |
| `user_turn_abs_idx` | int | 是 | 原始 turns 绝对索引 |
| `gt_assistant_abs_idx` | int | 是 | GT assistant 绝对索引 |
| `user_text` | string | 是 | 输入给agent的用户文本 |
| `gt_assistant_text` | string | 是 | GT assistant 文本 |
| `gt_turn_tags` | object | 是 | 原始GT标签（四类） |
| `pred_assistant_text` | string | 否 | 模型输出 |
| `latency_ms` | number | 否 | 该轮耗时 |
| `status` | string | 是 | `ok/error/timeout` |
| `error` | string/null | 否 | 异常信息 |
| `recall` | object/null | 否 | 召回观测 |
| `tools` | array | 否 | 工具调用轨迹 |
| `compliance` | object/null | 否 | 合规观测 |
| `profile_snapshot` | object/null | 否 | 本轮后画像快照（建议） |

### 4) `recall/tools/compliance` 子结构
`recall`：
- `query`: string  
- `packed_context`: string  
- `token_count`: int  
- `items`: array of `{rank:int,item_id:string,content:string,score:number,source:string,turn_index:int}`

`tools[]`：
- `{tool_name:string,args:object,result_excerpt:string,latency_ms:number,error:string/null}`

`compliance`：
- `{needs_modification:bool,is_compliant:bool,violations:array,risk_disclaimer_added:bool,suitability_warning:string/null}`

---

**评测中间表（建议）`turn_eval.jsonl`**

用于指标计算，避免每次重解析文本。

| 字段 | 类型 | 说明 |
|---|---|---|
| `run_id/dialog_id/turn_pair_id` | string/int | 主键 |
| `eligible_m1..eligible_m5` | bool | 各指标是否纳入分母 |
| `required_keys_raw` | array[string] | GT原始keys |
| `resolved_keys` | array[object] | `{key,resolvable,target_text}` |
| `key_hit_flags` | array[0/1] | 与 `resolved_keys` 对齐 |
| `constraint_contradiction` | 0/1 | 是否违反任一约束 |
| `risk_required_tags` | array[string] | 规范化后GT风险标签 |
| `risk_pred_tags` | array[string] | 规范化后预测标签 |
| `risk_tag_hits` | int | 命中数量 |
| `forbidden_hits` | array[string] | 命中的禁区项 |
| `pred_compliance_label` | string | `compliant/minor/severe` |
| `gt_compliance_label` | string | GT标签 |
| `rubric_required` | array[string] | GT解释要素 |
| `rubric_hit_items` | array[string] | 预测命中要素 |
| `judge_score_1_5` | number/null | LLM Judge分 |

---

## 指标公式清单（含分母定义）

记：
- 对话集合为 `D`
- 对话 `d` 的可评测轮集合为 `T_d`
- `I(·)` 为指示函数

### 指标1：上下文关联度 / 连续性
1. 轮级 Key Coverage  
`KC_{d,t} = hits_{d,t} / req_{d,t}`，仅当 `req_{d,t} > 0` 才计入分母。
2. 轮级 Strict Key Hit  
`SKH_{d,t} = I(hits_{d,t} = req_{d,t})`，同样仅在 `req_{d,t}>0` 计。
3. 轮级 约束矛盾  
`CONTRA_{d,t} = I(存在 constraints_gt 与 pred_assistant_text 冲突)`

对话级：
- `KC_d = Σ hits_{d,t} / Σ req_{d,t}`
- `SKH_d = 平均(SKH_{d,t})`
- `CR_d = 平均(CONTRA_{d,t})`

全局：
- `KC_micro = Σ_d Σ_t hits / Σ_d Σ_t req`
- `KC_macro = 平均_d KC_d`
- `CR_micro = Σ_d Σ_t CONTRA / Σ_d |T_d(eligible)|`

### 指标2：画像提取准确率
字段：`risk_level/horizon/liquidity`（分类），`constraints/preferences`（集合）

1. 分类字段 Accuracy  
`Acc_f = 正确对话数 / 可评测对话数`
2. 集合字段 Precision/Recall/F1（对话级后可全局平均）  
`P = |Pred∩GT|/|Pred|`  
`R = |Pred∩GT|/|GT|`  
`F1 = 2PR/(P+R)`
3. 全局画像分（可选）  
`ProfileScore = 平均(Acc_risk, Acc_horizon, Acc_liquidity, F1_constraints, F1_preferences)`

分母：仅 `valid_dialog 且 profile_gt 完整` 的对话。

### 指标3：风险提示覆盖率
轮级（仅 `|R_{d,t}|>0`）：
- `RC_{d,t} = |R_{d,t} ∩ P_{d,t}| / |R_{d,t}|`
- `RStrict_{d,t} = I(R_{d,t} ⊆ P_{d,t})`

全局：
- `RC_micro = Σ |R∩P| / Σ |R|`
- `RC_macro = 平均_d (Σ|R∩P| / Σ|R|)_d`
- `RStrict_rate = 平均(RStrict_{d,t})`

### 指标4：内容合规率
1. 标签准确率  
`CompAcc = Σ I(pred_label = gt_label) / N_eligible`
2. 严重违规率  
`SevereRate = Σ I(pred_label = severe) / N_eligible`
3. 禁区命中率  
`ForbiddenHitRate = Σ I(|forbidden_hits|>0) / N_eligible`

`N_eligible`：有预测assistant文本且有GT合规标签的轮。

### 指标5：决策辅助解释度
轮级（仅 `|E_{d,t}|>0`）：
- `ER_{d,t} = |E_{d,t} ∩ H_{d,t}| / |E_{d,t}|`
- `Score_{d,t} = judge_score_1_5`

全局：
- `ER_micro = Σ |E∩H| / Σ |E|`
- `ER_macro = 平均_d ER_d`
- `JudgeScore_mean = 平均(Score_{d,t})`

---

## 分母与缺失值规则（必须固定）
1. `req=0` 的轮不计入该子指标分母。  
2. `key` 无法解析（越界、坏格式）记 `unresolvable_key`，不计入 `req`。  
3. 对话级失败（超时/异常）标记 `failed_dialog`，不混入有效分母。  
4. 所有结果必须输出 `eligible_count`、`skipped_count`、`failed_count`。  

如果你愿意，我下一步可以直接给你一份 `trace_schema_v1.json`（JSON Schema草案）和 `metrics_contract.md`（函数输入输出签名），你可以直接照着实现。