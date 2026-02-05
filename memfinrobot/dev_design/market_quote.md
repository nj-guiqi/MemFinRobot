**可用的免费行情数据方案（适合毕业设计/原型）**

国内的股票、基金、指数数据

1) **AkShare（推荐作为“统一入口”库）**
- 形式：Python库，底层对接东方财富/新浪/腾讯等公开数据（多为网页/接口抓取），你只用关心函数调用与字段映射。
- 覆盖：A股现货、ETF、指数、基金净值/估值等（取决于具体函数）。
- 优点：上手快、品类多、社区常用；对你现在的工具化封装最省事。
- 风险：非官方数据源，字段/接口可能变；需要做降级与异常兜底。
- 参考：AkShare 的东方财富A股实时行情函数示例（`stock_zh_a_spot_em`）与用法介绍。 citeturn0search0

2) **腾讯行情 `qt.gtimg.cn`（推荐作为“默认实时源”实现一个轻量Provider）**
- 形式：HTTP GET，返回 `~` 分隔的字符串；免Key，速度快。
- 覆盖：A股/ETF/指数现货常用字段（价格、昨收、今开、成交量额等，需按字段下标解析）。
- 优点：依赖少（标准库即可）、实时性好。
- 风险：非官方，字段下标可能变化；需要写健壮解析与监控。
- 参考：返回格式与字段示例说明（非官方文档/经验总结）。 citeturn0search3

---

## `market_quote.py` 接入真实行情的数据“细节方案”（不改现有框架的前提）

### 1) 总体架构：Provider抽象 + 统一返回结构
- 在 `MarketQuoteTool` 内部引入“数据源选择”逻辑：`provider = params.provider || ENV || 默认值`
- 设计一个内部接口（不一定要单独文件，原型阶段放同文件也行）：
  - `get_quote(symbol, market) -> ToolResult`
- Tool 层只做：
  - 参数校验 → 调 Provider → **字段归一化** → `ToolResult` 输出

### 2) Provider选择策略（推荐）
- **默认**：`tencent`（A股/ETF/指数实时）
- **备选/降级**：`sina`
- **统一库模式**：`akshare`（当你希望“基金/指数/ETF/股票都一个库解决”时作为默认也可）
- **海外**：`yfinance`
- **离线测试**：`mock`（保留现有mock用于单测稳定性）

建议支持：
- `params.provider` 显式指定（优先级最高）
- 环境变量：`MEMFIN_MARKET_QUOTE_PROVIDER`
- `config.json` 增加可选段：`market_data: { provider, timeout_s, fallback_provider }`（你项目已有settings加载机制，便于工程化）

### 3) 标的代码与市场识别（A股最关键）
- 输入 `symbol` 允许：
  - `000001`（默认按规则推断交易所）
  - `sh600000 / sz000001`（显式前缀）
  - 海外如 `AAPL / 0700.HK / 000001.SZ`（给 yfinance） 暂时不考虑海外数据
- A股推断规则（工程常用、够用）：
  - `6/5/9` 开头多为 `SH`
  - `0/3/1/2` 开头多为 `SZ`
- `market` 参数用于语义标签（stock/fund/index），真实数据源通常不严格区分，你可以：
  - 仍保留 `market` 字段原样返回
  - 但在选择 akshare 函数时用它分流（例如ETF走ETF现货接口）

### 4) 字段归一化（你工具层对外的“稳定契约”）
统一返回（建议最小稳定集合）：
- `name`
- `symbol`
- `type`（沿用 market）
- `price`
- `prev_close`
- `open`
- `high`
- `low`
- `change`（price-prev_close）
- `change_pct`（%）
- `volume`
- `amount`
- `asof`（解析到时间就用解析值，否则用抓取时间）

Provider侧做“尽量取到”，取不到就置 `None`，ToolResult里加 `warnings` 说明口径/缺失。

### 5) 工程细节：健壮性与合规/可用性
- **超时**：5–8s；失败重试1次（可选）
- **限频**：简单QPS限制（例如同symbol 1–2秒内走内存缓存），避免被封
- **降级**：tencent失败 → akshare → mock（最后兜底，保证agent不中断）
- **可观测**：在 `ToolResult.source` 写清楚 `tencent/sina/akshare/mock`，方便你在论文/答辩展示“数据来源与降级策略”
- **免责声明**：`warnings` 增加“来自公开接口、口径可能变化”

### 6) 测试策略（保证你现有 `tests/tools/test_tools.py` 不被真实网络拖垮）
- 单测默认使用 `provider=mock`（或环境变量全局强制mock）
- 另加一组“可选集成测试”（手动跑）：`provider=tencent`，只断言字段存在/类型合理，不断言具体价格

---

## 推荐你最终选型（最省心、答辩也好讲）
- **主实时源**：`tencent`（轻量、免Key）
- **统一增强**：引入 `akshare` 作为补充（基金/ETF/指数更全）
- **工程保障**：mock兜底 + 限频 + source标注 + warnings

---

## 实现状态（已完成）

### 已实现功能

1. **Provider 抽象架构**
   - `TencentProvider`: 腾讯行情接口（主数据源）
   - `AkShareProvider`: AkShare 库（备选数据源）
   - `MockProvider`: Mock 数据（测试/兜底）

2. **配置支持**
   - `settings.py` 新增 `MarketDataConfig`
   - 支持环境变量 `MEMFIN_MARKET_QUOTE_PROVIDER`
   - 支持参数显式指定 `provider`

3. **工程特性**
   - 内存缓存限频（默认2秒）
   - 自动降级机制
   - 数据来源标注（source字段）
   - 字段归一化

### 使用示例

```python
from memfinrobot.tools.market_quote import MarketQuoteTool

tool = MarketQuoteTool()

# 使用默认数据源（tencent）
result = tool.call({"symbol": "000001"})

# 显式指定数据源
result = tool.call({"symbol": "000001", "provider": "tencent"})
result = tool.call({"symbol": "000001", "provider": "akshare"})
result = tool.call({"symbol": "000001", "provider": "mock"})

# 查询指数
result = tool.call({"symbol": "000300", "market": "index"})

# 查询ETF
result = tool.call({"symbol": "510300", "market": "fund"})
```

### 配置文件示例

在 `config.json` 中添加：

```json
{
  "market_data": {
    "provider": "tencent",
    "fallback_provider": "mock",
    "timeout_seconds": 8.0,
    "rate_limit_seconds": 1.0
  }
}
```

### 测试说明

- 单元测试默认使用 `provider=mock` 保证稳定性
- 集成测试可手动指定 `provider=tencent` 验证真实数据
