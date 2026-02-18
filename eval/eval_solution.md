

**1) 评测粒度设计（先定规则）**
建议统一采用“**按轮计算，按对话聚合，最后全局汇总**”。

| 指标 | 主计算粒度 | 对话级聚合 | 全局汇总 |
|---|---|---|---|
| 指标1 上下文关联/连续性 | assistant-turn | 对话均值 + 严格通过率 | micro + macro |
| 指标2 画像提取准确率 | dialog（主）+ turn（可选） | 每对话一份画像快照 | 字段级 Accuracy/F1 |
| 指标3 风险提示覆盖率 | assistant-turn | 覆盖率（命中标签/应命中标签） | micro + macro |
| 指标4 合规率 | assistant-turn | 合规比例与严重违规率 | micro + macro |
| 指标5 解释度 | assistant-turn | 平均解释分/要素命中率 | micro + macro |

**建议结论口径**
- 论文主结果用全局 `micro`。
- 稳定性补充 `macro`（每个对话先算分再平均）。
- 所有指标保留 `eligible_count`（有效样本数）避免分母不一致。

---

**2) 评测集对齐方案（最关键）**
你的数据 `eval/datasets/MemFinConv.jsonl` 需要先做“对齐预处理”，否则指标会漂。

**2.1 样本有效性分层**
- `valid_dialog`：有 `profile_gt`、`turns` 为数组、可抽出 user/assistant 配对。
- `partial_dialog`：只有 `seed_*`，无完整 `turns`/标签。
- `invalid_dialog`：JSON结构异常。

当前你这份数据里，`partial_dialog` 比例不低（你本地文件后几条是 seed-only 样式），所以默认只评 `valid_dialog`，并把跳过原因写入日志。

**2.2 回放对齐规则**
- 只把 `user` 轮送进 agent。
- 每送一轮 user，拿到一个模型 assistant 输出，记为预测轮 `pred_assistant_k`。
- 用同一位置的 GT assistant 轮 `gt_assistant_k` 对齐评分（不是按文本匹配，是按顺序匹配）。
- 统一保存索引：
  - `turn_pair_id`（1..N）
  - `user_turn_abs_idx`（原 turns 绝对位置）
  - `gt_assistant_abs_idx`

**2.3 `memory_required_keys_gt` 对齐**
你这个字段是 DSL，必须先解析成“可检测目标值”：
- `profile_gt.risk_level_gt` -> 目标值 = `profile_gt.risk_level_gt`
- `profile_gt.constraints_gt[i]` -> 目标值 = `constraints_gt[i]`
- `profile_gt.preferences_gt[i]` -> 目标值 = `preferences_gt[i]`
- `history_turn_index:n` -> 目标文本 = 第 n 个历史 user 轮（默认按 user-turn 1-based）
- 若 `n` 越界，降级尝试“绝对turn索引1-based”；再不行标记 `unresolvable_key`，不计入分母

补充：`history_turn_index:n` 与短期记忆天然相关。评测时需要把短期窗口（近期对话）作为独立命中源统计，避免“只看长期召回”导致漏计。

**2.4 标签标准化（避免同义词导致误判）**
做一层 canonical 映射（评测侧完成，不改业务逻辑）：
- 风险提示标签标准化：`不构成个股买卖建议`、`不构成投资建议`、`过往业绩不预示未来`、`波动风险` 等映射到固定 tag set。
- 画像字段标准化：`保守/稳健/进取` 映射到 `low/medium/high`。
- 特殊值 `无明确风险提示`：建议映射为 `risk_disclosure_presence_required=true`（因为它在蓝图里更像“不能缺风险提示”而不是“要输出这句话”）。

---

**3) 五个指标的精细计算逻辑**
**指标1：上下文关联度 / 连续性**
- 轮级1A（召回命中）：  
  `turn_key_hit_rate = hit_required_keys / required_keys`  
  检测对象用 observer 采集的三路上下文并集：`short_term_context + long_term_recalled_items + profile_context(未来可选)`，不是只看最终回复。
- 轮级1B（严格命中）：  
  `turn_strict = 1 if 所有required_keys命中 else 0`
- 轮级1C（连续性矛盾）：  
  检测 assistant 回复是否违反 `constraints_gt`（规则库+LLM兜底二级判定）。
- 轮级1D（来源归因）：  
  对每个命中的 key 记录来源：`short_term | long_term | profile`。  
  评测结果额外输出 `short_term_hit_rate / long_term_hit_rate / profile_hit_rate`（profile 在你后续实现前通常为 0）。
- 对话级：  
  `dialog_key_coverage = Σhit / Σrequired`  
  `dialog_contradiction_rate = contradiction_turns / eligible_turns`
- 全局：micro/macro 同时给。

**指标2：画像提取准确率**
- 主口径建议用 dialog 级（最终快照）：
  - `risk_level`、`horizon`、`liquidity` 算 Accuracy。
  - `constraints/preferences` 算集合F1（或 Jaccard）。
- 若你接受小改业务代码，observer每轮记录 `profile_snapshot`，再补充“收敛曲线”（第几轮画像稳定）。

**指标3：风险提示覆盖率**
- 轮级：对每个 required 风险标签判命中（规则词典 + 模板词 + LLM兜底）。
- `turn_coverage = matched_required / len(required)`
- 对话级/全局：  
  `coverage = Σmatched_required / Σrequired`

**指标4：内容合规率**
- 轮级先判预测标签 `pred_label in {compliant, minor, severe}`（规则优先，LLM补判边界样本）。
- 统计：
  - `label_accuracy`（与 `compliance_label_gt`）
  - `severe_rate`
  - `forbidden_hit_rate`（命中 `forbidden_list`）
- 对话级输出“是否出现 severe”。

**指标5：解释度**
- 轮级要素命中：`rubric_hit = hit_rubric_items / required_rubric_items`
- LLM Judge 给 `1-5` 分（仅在有 `explainability_rubric_gt` 的轮）
- 对话级：平均分 + 命中率；全局做 micro/macro。

---

**4) Observer 方案（与你的想法一致）**
建议在 `memfinrobot/agent/memfin_agent.py` 增加可选 observer，不破坏现有 CLI 用法。

**最小事件集合**
- `on_turn_start`
- `on_recall_done`
- `on_tool_called`
- `on_compliance_done`
- `on_turn_end`
- `on_profile_snapshot`（可选但强烈建议）

**`on_recall_done` 必含字段**
- `query`
- `short_term_context`: 近期对话窗口文本（建议同时记录 `short_term_turns`）
- `recalled_items`(long-term): `[{id, content, score, source, turn_index, session_id}]`
- `profile_context`（可选，后续画像直接注入时启用）
- `packed_context`（最终注入LLM的拼接文本）
- `token_count`

这样指标1能直接按来源对齐 `memory_required_keys_gt`，并区分是短期命中还是长期命中，不需要猜内部状态。

---

**5) 并发执行方案（细到可实现）**
评测是“对话内顺序、对话间并发”。

**5.1 并发模型**
- 任务单元：`dialog`
- 执行器：`ThreadPoolExecutor(max_workers=K)`
- 每个 worker 内：该 dialog 的 user turns 串行回放（保证会话状态正确）

**5.2 线程隔离（必须做）**
- 每个 dialog 单独 agent 实例
- 每个 dialog 独立 `session_id/user_id`
- 每个 dialog 独立 memory 存储目录（避免 `memory_index.json` 竞争写）
  - 例如：`eval/runs/{run_id}/memstore/{dialog_id}`
- 不用全局 telemetry 单例，改成每 dialog 独立 observer 实例

**5.3 两阶段并发（推荐）**
- 阶段A：对话回放并发（产生 trace）
- 阶段B：指标计算并发
  - 规则指标可本地并行
  - LLM Judge 独立线程池 + 全局限流（避免429）

**5.4 限流与重试**
- 全局信号量控制同时在飞请求数
- 失败重试：指数退避 + jitter
- 超时后记录 `turn_failed`，不中断全局 run

**5.5 进度日志**
- `eval/logs/progress_{run_id}.jsonl` 按事件写：
  - `dialog_started`
  - `turn_done`
  - `dialog_done`
  - `metric_done`
- 最终汇总：
  - `eval/metrics/results_{run_id}.json`
  - `eval/metrics/report_{run_id}.md`

---

**6) 对 memfinrobot 的“最小改动清单”**
只改少量点，保证你说的“评测代码独立”：
- `memfinrobot/agent/memfin_agent.py`
  - 增加 `observer` 参数（可空）
  - 在 recall/compliance/tool/turn 完成处发事件
- 可选：暴露 `handle_turn_with_trace`（返回 `{response, trace}`）
- 可选：在每轮结束时附带 `profile_snapshot`（`memory_manager.get_profile`）

评测侧只依赖 observer 输出的 `trace schema`，以后你内部逻辑改了，适配层最多改一处。

