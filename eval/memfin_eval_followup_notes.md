# MemFin 评测问题定位与改动需求（简版）

## 1. 目标

- 暂不改动业务逻辑（记忆、工具、合规）。
- 仅补齐与 `mem0` 评测类似的“简单超时重试”能力，降低 `turn_status=error`。
- 明确 `MemFinRobot` 的 `m3` 低分主要原因，便于后续定向优化提示词/规则。

## 2. 简易改动需求（不做复杂策略）

### 2.1 范围

- 文件：`eval/scripts/run_eval.py`
- 文件：`eval/scripts/replay.py`
- 可选：`run_manifest.json` 增加超时参数落盘字段（与 `mem0/langmem` 对齐）

### 2.2 需求点

1. 对每个 turn 增加“单轮超时 + 心跳日志”
- 参考 `mem0/langmem` 的 replay 风格：用 `ThreadPoolExecutor(max_workers=1)` 包一层 `agent.handle_turn`。
- 支持参数：
  - `--turn-timeout-sec`（建议默认 `1800` 或 `3600`）
  - `--turn-heartbeat-sec`（建议默认 `60` 或 `200`）
- 超时后把该轮记为 error，`error` 字段写明 `turn_timeout`。

2. 对每个 turn 增加“简单重试”
- 只对网络类错误重试，最多 `--turn-retries` 次（建议默认 `2`）。
- 可重试关键字（最小集合）：
  - `Request timed out.`
  - `Connection error.`
  - `incomplete chunked read`
- 每次重试前固定 sleep（例如 `1s`），无需指数退避。

3. 命令行参数与 manifest 对齐
- `run_eval.py` 增加参数：
  - `--turn-timeout-sec`
  - `--turn-heartbeat-sec`
  - `--turn-retries`
- `run_manifest.json` 增加字段：
  - `turn_timeout_sec`
  - `turn_heartbeat_sec`
  - `turn_retries`

### 2.3 非目标（本次不做）

- 不改 `MemFinFnCallAgent` 内部工具/记忆/合规模块。
- 不改模型、提示词和温度参数。
- 不引入复杂重试策略（指数退避、熔断、请求级重放队列等）。

## 3. 当前错误轮定位结论（MemFin run_id=20260220_082913）

数据源：`eval/runs/20260220_082913/dialog_trace.jsonl`

- 总 turn：`316`
- `turn_status=error`：`65`
- 错误类型分布：
  - `Request timed out.`：`52`
  - `Connection error.`：`11`
  - `incomplete chunked read`：`2`

结论：错误轮主因是请求超时/连接中断，且当前链路缺少 turn 级超时控制与重试。

## 4. m3 低分定位（MemFin）

数据源：`eval/runs/20260220_082913/turn_eval.jsonl`

- `m3_eligible`: `244`
- `risk_required_total`: `569`
- `risk_hit_total`: `272`
- `risk_coverage`: `0.478032`

### 4.1 主要缺口标签

- `no_guaranteed_return`: `13 / 172`（命中率 `0.076`）
- `not_buy_sell_advice`: `0 / 31`（命中率 `0.000`）
- `market_uncertainty`: `76 / 146`（命中率 `0.521`）

### 4.2 已有较好命中标签

- `volatility_risk`: `137 / 143`（命中率 `0.958`）
- `suitability_match`: `32 / 36`（命中率 `0.889`）

### 4.3 回合命中形态

- `full_hit`: `31` turns
- `partial_hit`: `161` turns
- `0_hit`: `52` turns

### 4.4 场景维度（覆盖率较低）

- 投资教育：`0.409`
- 宏观分析：`0.450`
- 其余场景多在 `0.48~0.60`

## 5. 解读

- `m3` 低分不是单一由“短期窗口”导致。
- 主要是风险提示表达与评测标签词表不一致，尤其是：
  - 缺少“不保证收益”类表达；
  - 缺少“非买卖建议”类表达；
  - 对“市场不确定性”表达不稳定。
- 因此建议优先先做“超时重试”保证样本完整，再做风险表达模板对齐。

## 6. 风险表达模板优化需求（用于提升 m3）

### 6.1 目标

- 在不改 `m3` 评测逻辑前提下，提升回答中的风险表达覆盖率。
- 优先补齐 `no_guaranteed_return`、`not_buy_sell_advice`、`market_uncertainty` 三类表达。
- 保持合规语气和可读性，避免机械堆叠风险短语。

### 6.2 范围

- 文件：`memfinrobot/agent/memfin_agent.py`（生成回复后、合规审校前）
- 文件：`memfinrobot/prompts/*`（系统提示词或回复规范）
- 可选：新增 `memfinrobot/compliance/risk_phrase_template.py`（集中管理风险表达模板）

### 6.3 需求点

1. 增加“风险表达规范块”
- 在最终回复中保证至少包含以下三类表达（可同句出现）：
  - 不保证收益类：例如“收益不确定/不保证收益/不保本”
  - 非买卖建议类：例如“不构成买卖建议/不构成个股买卖建议”
  - 市场不确定性类：例如“市场存在不确定性/市场波动可能导致偏离预期”

2. 模板化但不固定句式
- 每类风险表达提供 3 到 5 个可替换短句，按轮次或随机选择，避免输出同质化。
- 模板应兼容中文自然表达，不使用生硬拼接。

3. 触发策略（简化版）
- 默认在涉及产品、配置、收益/回撤判断时附加风险表达规范块。
- 对纯事实问答（如术语定义）可降级为最短风险提示版本。
- 本次不引入复杂分类器，使用关键词触发即可。

4. 与合规模块协同
- 优先在生成阶段补足风险表达，减少后置 `ComplianceGuard` 被动改写。
- 不删除现有 `risk_disclaimer` 机制，保持双保险。

### 6.4 验收口径

- 以当前数据集重跑后，`m3` 至少达到以下方向性目标：
  - `risk_coverage` 较当前 `0.478` 有显著提升（建议目标 `>=0.55`）
  - `no_guaranteed_return` 命中率显著提升（建议目标 `>=0.40`）
  - `not_buy_sell_advice` 命中率显著提升（建议目标 `>=0.40`）
  - `market_uncertainty` 命中率提升（建议目标 `>=0.65`）
- `m4` 不出现明显回退（`severe_violation_rate` 不升高）。

### 6.5 非目标

- 不为“刷分”硬编码与 `gt_tag` 一一对应的模板注入。
- 不修改 `eval/metrics/m3_risk.py` 的计算规则。
- 不引入复杂 NLU/分类模型，仅做模板与触发规则优化。
