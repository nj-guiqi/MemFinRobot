# MemFinRobot

面向证券投资的记忆增强型智能理财顾问智能体

## 项目简介

MemFinRobot 是一个基于 qwen-agent 框架的智能理财顾问系统，通过多层次记忆机制（短期对话记忆 / 长期对话记忆 / 用户画像记忆）提升对话连续性、个性化服务能力和合规性。

### 核心特性

- **记忆增强**：基于动态窗口选择的长期对话记忆表征与检索
- **个性化服务**：用户画像管理，提供适当性匹配的建议
- **合规审校**：禁语检测、风险提示强制添加、适当性检查
- **工具调用**：行情查询、产品信息、知识库检索、风险计算等

## 项目结构

```
MemFinRobot/
├── memfinrobot/           # 核心代码
│   ├── agent/            # 智能体决策层
│   ├── memory/           # 记忆管理（核心模块）
│   │   ├── schemas.py    # 数据结构定义
│   │   ├── embedding.py  # 向量嵌入（BGE-M3）
│   │   ├── window_selector.py  # 动态窗口选择
│   │   ├── window_refiner.py   # 窗口内容精炼
│   │   ├── memory_writer.py    # 记忆写入
│   │   ├── recall.py     # 多路召回
│   │   ├── rerank.py     # 重排序
│   │   └── manager.py    # 记忆管理器
│   ├── tools/            # qwen-agent工具实现
│   ├── compliance/       # 合规与风险控制
│   ├── llm/             # LLM适配层
│   ├── config/          # 配置管理
│   ├── prompts/         # 提示词模板
│   ├── telemetry/       # 可观测日志
│   └── utils/           # 工具函数
├── apps/
│   └── cli/             # 命令行入口
├── tests/               # 单元测试
├── data/                # 数据目录
└── docs/                # 文档
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置

复制配置文件并修改：

```bash
cp config.example.json config.json
```

设置环境变量（或在配置文件中设置）：

```bash
export DASHSCOPE_API_KEY="your-api-key"
```

### 3. 运行CLI

```bash
python -m apps.cli.main
```

或指定配置文件：

```bash
python -m apps.cli.main -c config.json
```

### 4. 运行测试

```bash
pytest tests/ -v
```

## 核心模块说明

### 记忆层 (memory/)

记忆层是本项目的核心，实现了"长期对话记忆的表征与检索"：

1. **WindowSelector**: 基于LLM的动态窗口选择，通过多次采样投票降低不确定性
2. **WindowRefiner**: 对选中的历史片段进行精炼，提取关键信息
3. **MemoryWriter**: 将精炼后的记忆写入存储（支持向量索引）
4. **MemoryRecall**: 多路召回（语义/关键词/画像规则）
5. **MemoryReranker**: 召回结果重排序

### 智能体层 (agent/)

基于 qwen-agent 的 FnCallAgent 扩展：

- 在LLM调用前注入记忆上下文
- 在输出前执行合规审校
- 在对话结束后更新长期记忆

### 合规层 (compliance/)

确保输出符合金融监管要求：

- 禁语检测与过滤
- 风险提示强制添加
- 用户适当性匹配检查

## 配置说明

```json
{
  "llm": {
    "model": "qwen-plus",       // 模型名称
    "model_server": "dashscope", // 服务提供商
    "temperature": 0.7          // 采样温度
  },
  "embedding": {
    "model_path": "path/to/bge-m3",  // 向量模型路径
    "device": "cuda"                  // 运行设备
  },
  "memory": {
    "max_window_size": 15,      // 最大窗口大小
    "vote_times": 5,            // 投票次数
    "confidence_threshold": 0.6 // 置信度阈值
  }
}
```

## 开发计划

- [x] V0: 基础框架搭建，核心模块实现
- [ ] V1: 动态窗口算法工程化，可观测日志完善
- [ ] V2: 向量库（FAISS）集成，多用户支持
- [ ] V3: 真实数据源接入，合规策略细化

## 许可证

MIT License
