# 评测设置（论文撰写版）

## 1. 评测目标

本节用于比较不同方法在多轮金融对话任务上的表现，重点关注：

- 多轮上下文连续性（是否正确利用历史对话/记忆）
- 用户画像理解能力
- 风险提示与合规表达
- 解释性与可读性

## 2. 统一实验设置

### 2.1 数据与评测流程

- 数据集：`eval/datasets/MemFinConv_24.jsonl`（24 个对话，316 个 user-assistant turn pair）
- 统一评测管线：replay -> trace -> metric（M1~M5）-> summary/report
- 所有方法都通过 `eval/scripts/replay_*.py` 生成统一格式 trace，再进入同一套指标计算逻辑

### 2.2 Backbone LLM（公平对比）

- 统一主对话模型：`qwen3.5-plus`
- 统一接口：DashScope OpenAI-compatible endpoint
- 统一生成参数主范围：`temperature=0.7`, `max_tokens=2048`

说明：
- `run_eval_finrobot.py` 的代码默认值是 `qwen-plus`，但本项目实际评测脚本与历史运行清单使用的是 `qwen3.5-plus`，以保证横向可比性。

### 2.3 Prompt 与可比性控制

- `LLM / Mem0 / LangMem / FinRobot` 适配器都对齐使用同一金融顾问系统提示（`MEMFIN_SYSTEM_PROMPT`）
- 区别主要来自“记忆机制、工具机制、合规模块、工作流框架”，而不是系统提示词差异

## 3. 对比方法说明

### 3.1 Ours: MemFinRobot

- 框架：基于 `qwen-agent` 的 `FnCallAgent` 扩展
- 核心模块：
  - `MemoryManager`：短期上下文 + 长期记忆召回 + 用户画像更新
  - 工具链：行情、产品检索、风险模板、组合计算、网页检索/访问、Python 执行等
  - `ComplianceGuard`：合规检查与风险表达约束
- 运行入口：`eval/scripts/run_eval.py`

该方法是“记忆 + 工具 + 合规”三者耦合的完整金融咨询 agent。

### 3.2 Baseline A: 纯 LLM（无记忆、无工具）

- 适配器：`eval/scripts/llm_agent_adapter.py`
- 每轮仅输入 `system + 当前 user message`，不保留会话历史
- 不使用外部工具，不执行显式记忆读写，不做画像建模
- 作为“最小能力”参考下界

额外处理：
- 该基线天然不具备记忆召回能力，评测时对 M1 的 `memory_required_keys` 做忽略处理，避免将“无记忆结构”重复惩罚。

### 3.3 Baseline B: FinRobot（金融 agent 框架）

- 项目：<https://github.com/AI4Finance-Foundation/FinRobot>
- 适配器：`eval/scripts/finrobot_agent_adapter.py`
- 工作流：`SingleAssistant`（`Market_Analyst` 配置）
- 记忆形态：主要为短期对话窗口注入；无独立长期记忆库/画像模块
- 工具能力：依赖 FinRobot toolkit（受 API key 与运行环境影响）

该基线代表“通用金融 agent workflow”在本任务上的表现。

### 3.4 Baseline C: Mem0（记忆增强）

- 项目：<https://github.com/mem0ai/mem0>
- 适配器：`eval/scripts/mem0_agent_adapter.py`
- 机制：
  - 每轮先 `memory.search` 召回长期记忆
  - 拼接短期历史 + 召回结果后再调用 LLM 生成回答
  - turn 结束后将对话写回记忆
- 向量配置（当前实验）：`text-embedding-v4`, `1024 dims`, `qdrant`

该基线代表“外挂长期记忆层”的主流方案。

### 3.5 Baseline D: LangMem（LangGraph + memory tools）

- 项目：<https://github.com/langchain-ai/langmem>
- 适配器：`eval/scripts/langmem_agent_adapter.py`
- 机制：
  - 基于 `LangGraph ReAct agent`
  - 通过 `manage_memory` / `search_memory` 工具维护记忆
  - `InMemoryStore + OpenAIEmbeddings` 做召回
  - 短期历史与召回结果一起注入当前轮上下文

该基线代表“agentic memory tool”路线。

## 4. 本仓库当前已跑实验（用于论文复现说明）

- MemFinRobot：`run_manifest.json`（如 `run_id=20260220_082913`）
- 纯 LLM：`run_manifest_llm.json`（`run_id=20260221_085707`）
- Mem0：`run_manifest_mem0.json`（`run_id=20260220_155804`）
- FinRobot：`run_manifest_finrobot.json`（`run_id=20260222_055021`）
- LangMem：`run_manifest_langmem.json`（`run_id=20260222_071516`）

上述 run 清单中，主对话模型均记录为 `qwen3.5-plus`，并统一在 `MemFinConv_24` 上评测。
