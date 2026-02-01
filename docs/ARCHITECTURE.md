# MemFinRobot 项目架构设计（可扩展初版）

本文档基于开题报告《面向证券投资的记忆增强型智能理财顾问智能体》（产品设计方向），并结合你已完成的“长期对话记忆的表征与检索”核心实现（参考 `D:\project\ChatSeeker\dynamic_win\dynamic_win_multi_reduce_uncertanty.py`），以及 qwen-agent 的 agent/tool 组织方式（参考 `D:\project\Qwen-Agent\qwen_agent` 与示例 `D:\project\Qwen-Agent\examples`、`D:\project\DeepResearch\inference\react_agent.py`），给出 MemFinRobot 的可落地、可迭代的工程架构。

---

## 1. 产品目标与边界

### 1.1 目标（What）
- 面向证券投资（基金/股票/债券等）的智能理财顾问“陪伴式咨询”智能体。
- 通过多层次记忆机制（短期对话记忆 / 长期对话记忆 / 用户画像记忆）提升：
  - 对话连续性（跨轮次依赖、长周期跟踪）
  - 个性化（风险承受能力、偏好主题、投资期限）
  - 可解释性与可追溯性（记忆来源、引用片段）
  - 合规性（风险提示一致、避免承诺收益/交易指令）

### 1.2 边界（What NOT）
- 不做“直接买卖指令/收益承诺/确定性预测”的输出；定位为“决策辅助”。
- 不把外部数据源视为绝对真理：需要来源、时间戳、失败回退、风险提示。

---

## 2. 总体分层架构（四层）

对应开题报告的四层设计，工程上固定“层间接口”，便于后续替换实现：

1) 用户交互层（UI）
- CLI / WebUI / API（对接前端或 IM）

2) 智能体决策层（Agent Orchestration）
- 意图识别 → 记忆召回 → 计划/推理（ReAct/函数调用）→ 工具调用 → 合规审校 → 回复生成

3) 知识与记忆层（Knowledge & Memory）
- 短期：窗口化上下文（可控长度、可解释）
- 长期：流式写入 + 检索召回（向量 + 结构化元数据）
- 用户画像：结构化 profile（风险等级、期限、主题偏好、禁忌）
- 领域知识库：监管/产品规则/投教材料/研报摘要（RAG）

4) 工具与服务层（Tools & Services）
- 行情/指标/产品信息/公告/宏观数据
- 组合与风险计算器（波动、回撤、久期等可扩展）
- 合规模板与审核工具

---

## 3. 核心对话闭环（数据流）

```mermaid
flowchart TD
  U[User Input] --> P[Preprocess\n(清洗/脱敏/语言检测)]
  P --> I[Intent & Task Router\n(意图识别/任务类型)]
  I --> MR[Memory Recall\n(短期/长期/画像/知识库)]
  MR --> PL[Plan/Reason\n(ReAct or FnCall)]
  PL -->|tool call| T[Tools/Services]
  T --> PL
  PL --> C[Compliance & Risk Guard\n(适当性/禁语/模板)]
  C --> R[Response Compose\n(结构化解释+风险提示)]
  R --> MU[Memory Update\n(写入长期/更新画像)]
  MU --> UO[Output to UI]
```

工程关键点：
- “记忆召回 MR”与“记忆更新 MU”必须是显式模块：可单测、可替换、可观测。
- “合规与风险 C”必须在最终输出前强制执行：即使工具/模型给出激进建议，也要拦截。

---

## 4. 目录结构（初版骨架）

以下目录是“可扩展最小架构”：先把边界和接口立起来，后续往里填实现。

```text
MemFinRobot/
  docs/
    ARCHITECTURE.md
    adr/                        # 架构决策记录（可选）
  apps/
    cli/                        # 命令行交互入口
    api/                        # HTTP API（可选）
    webui/                      # 简单前端/可视化（可选）
  memfinrobot/
    agent/                      # 智能体决策层
    memory/                     # 长短期记忆与画像
    knowledge/                  # 领域知识库/RAG
    tools/                      # qwen-agent 工具实现
    compliance/                 # 合规与风险控制
    llm/                        # 模型适配与调用（qwen-agent 封装）
    prompts/                    # 系统提示词/模板
    config/                     # 配置（YAML/JSON/ENV）
    telemetry/                  # 日志/trace/可解释记录
    utils/
  data/
    kb/                         # 领域知识库原始资料（可选）
    profiles/                   # 用户画像样例/调试数据
    conversations/              # 对话样例/评测集
  eval/
    datasets/
    metrics/
    scripts/
  tests/
  scripts/
```

---

## 5. 各模块职责与“复杂功能”说明

### 5.1 `memfinrobot/agent/`（智能体决策层）
职责：把“用户问题 → 决策辅助回答”变成可控的流水线。

复杂功能（必须模块化）：
- 意图识别与任务分解：
  - 将问题分类：行情信息 / 产品比较 / 风险识别 / 资产配置思路 / 投资教育
  - 识别是否需要工具：行情/产品库/计算器/知识库
  - 识别是否需要更新画像：用户透露了风险偏好、期限、目标等
- 推理与工具调用（ReAct / Function Calling）：
  - 使用 qwen-agent 的 `FnCallAgent` 风格：LLM 产出工具调用 JSON → 执行工具 → 把结果回填给 LLM
  - 强制最大调用次数、超时、失败回退（避免“工具死循环”）
  - 对工具结果做“证据化封装”：来源、时间、字段解释，供后续合规与引用
- 上下文组装（Context Packing）：
  - 把记忆召回结果按优先级拼接：画像 > 长期关键记忆 > 短期窗口 > 知识库引用 > 工具结果
  - 控制 token 预算：分配给各段落的预算、截断策略、引用粒度

对外接口（建议）：
- `agent.run(messages) -> iterator[messages]`（与 qwen-agent 风格一致）
- `agent.handle_turn(user_msg, session_state) -> assistant_msg + updated_state`

### 5.2 `memfinrobot/memory/`（记忆层：短期/长期/画像）
职责：让智能体“记得住、找得到、用得稳、说得清”。

子模块建议：
- `stream/`：对话流式处理（你已完成的核心点）
- `stores/`：存储（向量库/结构化库/文件）
- `retrieval/`：召回（多路召回 + 重排 + 去噪）
- `schemas.py`：统一数据结构（MemoryItem、UserProfile、RecallResult）

复杂功能（重点）：
1) 长期对话记忆的表征与检索（你现有实现的工程化落点）
   - 流式写入（Streaming Ingestion）：
     - 每轮对话到达时，不等整段结束，增量处理并写入长期记忆
     - 为每条记忆生成：文本表征 + 向量表征 + 元数据（时间、主题、风险、来源轮次）
   - 动态窗口选择（Dynamic Window Selection）：
     - 参考 `dynamic_win_multi_reduce_uncertanty.py`：LLM 选择“与当前 query 最相关的历史片段索引”
     - 多次采样+投票以降低不确定性（vote/confidence）
     - 低置信度回退到固定窗口/摘要（保证鲁棒性）
   - 选择片段精炼（Refine Selected Window）：
     - 对选中的窗口内容再进行“指令化/要点化”提炼，减少噪声、提升可复用性
     - 产物应可解释：保留“原文片段引用 + 精炼后的记忆条目”
   - 分层表征（Hierarchical Representation）：
     - 将“精炼记忆 | [context] | 当前轮内容”拼接为层级文本，作为长期记忆写入的稳定表征
     - 使后续检索既能命中“过去关键点”，也能回溯“当时上下文”
2) 多路召回与重排（Multi-Recall & Rerank）
   - 召回通道（可并行）：
     - 向量相似度召回（semantic）
     - 关键词/实体召回（ticker、基金代码、行业、宏观事件）
     - 画像规则召回（风险等级相关条款、禁忌提醒）
   - 重排：
     - 可选 BGE reranker（你代码中已有接口位），或者 LLM rerank
   - 去重与冲突处理：
     - 相同事实多条命中时合并（保留最可信来源/最新时间）
     - 冲突记忆标注为“需要澄清”并引导追问
3) 用户画像记忆（Profile Memory）
   - 结构化字段（建议最小集合）：
     - 风险承受能力（低/中/高 + 证据轮次）
     - 投资期限（短/中/长）
     - 目标（稳健增值/现金流/行业主题/学习投教）
     - 约束（不碰某类资产、不可接受亏损阈值）
   - 更新策略：
     - 只有当用户明确表达/多次出现一致信号时才更新（避免单轮误判）
     - 记录“置信度”和“证据来源”（合规与可解释）

### 5.3 `memfinrobot/knowledge/`（领域知识库/RAG）
职责：提供“可引用的金融知识与规则”，支撑解释与合规。

复杂功能：
- 知识来源治理：每条知识要能追溯（文件/链接/发布时间/版本）
- RAG 检索与引用：输出要包含引用片段（必要时给出原文节选）
- 与对话记忆区分：知识库是“公共事实/规则”，记忆是“用户个体偏好/历史对话”

实现建议：
- 初版可直接复用 qwen-agent 自带 `Memory`（文档检索工具链：doc_parser + retrieval）
- 后续再替换为更强的向量库/检索器，但对 agent 暴露接口保持不变

### 5.4 `memfinrobot/tools/`（工具与服务层，qwen-agent Tool）
职责：把外部能力“封装为可调用、可审计”的工具。

复杂功能（建议工具化）：
- 行情/指标工具：价格、涨跌幅、波动、估值等（需时间戳与来源）
- 产品信息工具：基金/债券要素、费用、风险等级、历史区间表现（尽量避免预测）
- 计算器工具：收益回撤解释、久期/利率敏感性、仓位与风险暴露（可解释输出）
- 合规模板工具：根据意图/资产类别/风险等级返回标准化提示语块

工具接口建议：
- 每个工具实现 qwen-agent `BaseTool.call(params)`，并返回结构化 JSON（便于审计与拼装）
- 工具输出统一包一层 `ToolResult`：`{data, source, asof, errors, warnings}`

### 5.5 `memfinrobot/compliance/`（合规与风险控制）
职责：强制把输出控制在“决策辅助 + 风险提示 + 适当性匹配”的范围内。

复杂功能：
- 适当性检查：用户风险等级 vs 建议内容风险等级（不匹配则转为教育/提醒/建议澄清）
- 禁语/高风险表达过滤：
  - “保证收益”“必涨”“内幕/荐股”“具体买卖点位指令”等
  - 发现后：改写为中性表达 + 风险提示 + 建议咨询持牌机构
- 输出结构化：固定包含
  - 信息来源/时效性说明（如果有工具数据）
  - 风险提示（模板化）
  - 建议的下一步澄清问题（当画像不全/冲突时）

### 5.6 `memfinrobot/llm/`（模型适配层）
职责：屏蔽“具体模型/调用方式”的差异，便于后续切换 qwen 系列、vLLM、本地模型等。

复杂功能：
- 统一生成参数（temperature/top_p/max_tokens/seed）
- 统一超时/重试/限流
- 统一 token 预算估计（避免上下文爆炸）

### 5.7 `memfinrobot/telemetry/`（可观测与可解释）
职责：为实验验证与产品合规提供“可追溯链路”。

复杂功能：
- 每轮对话记录：
  - 意图分类结果
  - 召回的记忆条目（含分数、来源、时间）
  - 工具调用（入参/出参/耗时/错误）
  - 合规审校命中规则与改写结果
- 产出可用于论文评测的指标日志：
  - 上下文关联度、画像提取准确率、风险提示覆盖率、内容合规率、解释度

---

## 6. “长期对话记忆表征与检索”在本项目中的工程落点

你现有实现的关键思想建议在 MemFinRobot 中拆成 3 个可替换组件（保持接口稳定）：

1) `WindowSelector`（选择“哪些历史轮次值得看”）
- 输入：`dialogue_history: list[str]`、`current_query: str`
- 输出：`selected_indices: list[int]`、`confidence: float`、`debug: {...}`
- 初版实现：复用动态窗口 + 多次投票（参考 `dynamic_win_multi_reduce_uncertanty.py`）
- 扩展：可替换为 embedding 召回、规则召回、或多路融合

2) `WindowRefiner`（把窗口内容变成“可写入长期记忆的干净条目”）
- 输入：`selected_texts: list[str]`、`current_query: str`
- 输出：`refined_items: list[str]` + `citations`（可选）

3) `MemoryWriter`（写入长期记忆库）
- 输入：`refined_items`、`current_turn`、`metadata`
- 输出：`memory_ids`（便于后续引用与回溯）

检索侧拆成：
- `Recall`：多路召回（向量/关键词/画像规则）→ 合并去重
- `Rerank`：重排与阈值过滤
- `Pack`：按 token 预算打包为“可给 LLM 用的上下文块”

这样做的好处：
- 你的“动态窗口算法”不会与“存储方案（FAISS/SQLite/云）”耦死
- 后续做消融实验时只替换某个组件即可（论文验证友好）

---

## 7. 基于 qwen-agent 的集成方式（建议）

### 7.1 为什么选 `FnCallAgent`
- qwen-agent 已提供“LLM + tool calling + loop”的通用框架（参考 `qwen_agent/agents/fncall_agent.py`）。
- 你只需要在“每轮调用 LLM 之前”注入记忆上下文、在“最终输出前”做合规审校即可。

### 7.2 推荐的主 Agent 形态
- `MemFinFnCallAgent(FnCallAgent)`：
  - override/包装 `_run()`：
    1) 读取 session_state（画像、对话历史索引、记忆库句柄）
    2) 调用 `MemoryRecall` 生成 `memory_context`
    3) 组装 system/user prompt（含合规边界、风险提示要求、引用要求）
    4) 进入 FnCallAgent 的工具循环
    5) 出口前调用 `ComplianceGuard`：必要时改写/追加风险提示/追问
    6) 调用 `MemoryUpdate`：把本轮信息写入长期记忆并更新画像

### 7.3 工具集（初版）
- `market_quote`：行情与指标（可先 mock）
- `product_lookup`：基金/债券/股票基础信息（可先 mock）
- `knowledge_retrieval`：监管/投教/产品规则（可复用 qwen-agent Memory 或自建）
- `risk_template`：输出标准风险提示块
- `portfolio_calc`：解释性计算（可先实现最小集）

---

## 8. 评测与实验（与论文可对齐）

建议在 `eval/` 固化三类评测脚手架，便于写论文与做消融：
- 连续性：上下文关联度、跨轮一致性（是否沿用历史偏好/决策路径）
- 画像：风险等级/期限/主题偏好提取准确率（与标注对比）
- 合规：风险提示覆盖率、禁语命中率、违规输出率

消融实验建议开关：
- 无长期记忆 / 无动态窗口 / 无 refine / 无重排 / 无模板风险提示

---

## 9. 迭代路线（建议从简到强）

1) V0（现在）：搭骨架 + 接入 qwen-agent FnCallAgent + 记忆召回/更新接口打通（可先用本地文件存储）
2) V1：把你的动态窗口算法工程化为 `WindowSelector/Refiner`，并加上可观测日志与最小评测脚本
3) V2：引入向量库（FAISS/Chroma 等）+ 画像结构化存储（SQLite），支持多用户/多会话
4) V3：工具接真实数据源 + 合规策略更细化（不同资产/不同意图的模板体系）

