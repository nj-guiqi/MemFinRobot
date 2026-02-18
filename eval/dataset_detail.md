`fin_long_dialogs.jsonl` 是 JSONL 格式：**每一行是一个完整对话样本**。

**1) 顶层字段（每行一个样本）**

| 字段 | 类型 | 典型取值/范围 | 含义 |
|---|---|---|---|
| `dialog_id` | string | UUID（如 `77b6c928-...`） | 对话唯一标识 |
| `scenario_type` | string | 如：`行情解读`、`产品比较`、`风险识别`、`投资教育`、`合规对抗`、`宏观分析`、`财务分析`、`政策解读`、`行业分析` | 对话主场景类型 |
| `difficulty` | string | `easy` / `med` / `hard` | 对话难度分层 |
| `language` | string | 通常为 `zh` | 对话语言 |
| `profile_gt` | object | 见下节 | 用户画像真值（ground truth） |
| `turns` | array<object> | 多轮交替（`user`/`assistant`） | 对话正文 |
| `events` | array<object> | 事件列表 | 对话中的关键触发点 |
| `seed_source` | string | 如：`DISC-FinLLM`、`FinTalk-19k`、`fingpt-convfinqa` | 该样本所基于的种子来源 |
| `seed_data` | object | 见下节 | 种子样本快照 |
| `blueprint` | object | 见下节 | 该对话对应的蓝图信息（用于可评测性） |

说明：`fin_long_dialogs.jsonl` 通常是“通过校验的样本”，一般不含错误字段。

---

**2) `profile_gt`（用户画像真值）**

| 字段 | 类型 | 典型取值/范围 | 含义 |
|---|---|---|---|
| `risk_level_gt` | string | `保守` / `稳健` / `进取` | 风险偏好 |
| `horizon_gt` | string | `<=6月` / `6-24月` / `2年以上` | 投资期限 |
| `liquidity_need_gt` | string | `高` / `中` / `低` | 流动性需求 |
| `constraints_gt` | array<string> | 2-4 条常见约束 | 硬约束/禁忌（如最大回撤、杠杆限制、仓位限制等） |
| `preferences_gt` | array<string> | 1-4 条常见偏好 | 资产或策略偏好（如高等级信用债、宽基指数等） |

---

**3) `turns`（对话轮次）**

每个元素是一个对象：

| 字段 | 类型 | 典型取值/范围 | 含义 |
|---|---|---|---|
| `role` | string | `user` / `assistant` | 当前发言角色 |
| `text` | string | 自然语言文本 | 当前轮发言内容 |
| `turn_tags` | object 或 null | `assistant` 轮通常为 object，`user` 轮通常为 null | 对当前轮的评测标签 |

`turn_tags`（主要用于 `assistant` 轮）：

| 字段 | 类型 | 典型取值/范围 | 含义 |
|---|---|---|---|
| `memory_required_keys_gt` | array<string> | 0-4 个键 | 本轮应引用的历史关键信息 |
| `risk_disclosure_required_gt` | array<string> | 如：`波动风险`、`不保证收益`、`市场不确定性`、`适当性匹配`、`不构成个股买卖建议` | 本轮应覆盖的风险提示类型 |
| `compliance_label_gt` | string | `compliant` / `minor_violation` / `severe_violation` | 本轮合规标签 |
| `explainability_rubric_gt` | array<string> | 如：`信息依据`、`风险收益平衡`、`与画像匹配`、`可执行步骤`、`边界声明` | 本轮解释质量要素 |

`memory_required_keys_gt` 常见写法示例：

- `profile_gt.risk_level_gt`
- `profile_gt.constraints_gt[0]`
- `profile_gt.preferences_gt[1]`
- `history_turn_index:6`

---

**4) `events`（关键事件）**

每个元素是：

| 字段 | 类型 | 典型取值/范围 | 含义 |
|---|---|---|---|
| `turn_index` | int | 1 到用户轮总数范围内 | 事件发生的用户轮次 |
| `key` | string | 常见：`max_drawdown`、`topic_shift`、`topic_recover` | 事件类型 |
| `description` | string | 自然语言说明 | 事件语义描述 |

---

**5) `seed_data`（种子快照）**

| 字段 | 类型 | 含义 |
|---|---|---|
| `source` | string | 种子来源 |
| `tag` | string | 种子标签 |
| `instruction` | string | 种子问题/指令 |
| `context` | string | 种子上下文 |
| `response` | string | 种子回答 |
| `history` | array | 种子历史轮次（若有） |

---

**6) `blueprint`（蓝图信息）**

| 字段 | 类型 | 含义 |
|---|---|---|
| `turn_plan` | array<object> | 用户每轮目标计划（轮次+目标） |
| `risk_required_map` | object | 各轮要求的风险提示类型映射 |
| `forbidden_list` | array<string> | 对助手输出的禁止表达清单 |
| `seed_source` | string | 与顶层一致，便于局部解析 |
| `seed_data` | object | 与顶层一致，便于局部解析 |

明白，你这 6 个字段我按“**取值全集 + 采样条数 + 结构约束**”给你精确化。


某些关键字段详细内容：

**1) `constraints_gt`**
- 类型：`array<string>`
- 采样条数：常见 `2-4` 条（历史数据里也可能出现 1 条或“无明确约束”）
- 候选全集（27项）：
```text
不做短线交易
不使用杠杆
不使用融资融券
最大回撤<10%
最大回撤<15%
单一资产仓位不超过30%
权益类总仓位不超过60%
保留20%现金应急
不接受高波动策略
不买ST及*ST股票
不买单一小盘股
不参与题材炒作
不追高
回避高估值成长股
仅考虑公募基金
不投分级基金
优先低费率基金
偏好季度可观察业绩的基金
单只基金仓位不超过20%
仅投高等级信用债
不投低评级信用债
组合久期控制在3年以内
不配置可转债
债券资产以利率债和高等级信用债为主
不投海外市场
不参与场外配资
无明确约束
```

**2) `preferences_gt`**
- 类型：`array<string>`
- 采样条数：常见 `1-4` 条（项目里多数为 `2-4`）
- 候选全集（15项）：
```text
大盘蓝筹股
高股息股票
成长股
价值股
宽基指数基金
行业主题基金
红利基金
低波动基金
FOF基金
国债
政策性金融债
高等级信用债
短债基金
中长期纯债基金
无明确偏好
```

**3) `memory_required_keys_gt`**
- 类型：`array<string>`
- 采样条数：`0-4` 条（去重后）
- 合法格式只有三类：
```text
profile_gt.risk_level_gt
profile_gt.horizon_gt
profile_gt.liquidity_need_gt
profile_gt.constraints_gt[i]      # i 为非负整数
profile_gt.preferences_gt[i]      # i 为非负整数
history_turn_index:n              # n 为正整数
```
- 说明：
  - 这是“本轮应引用的历史关键信息”清单，不是自由文本。
  - 通常应与 `profile_gt` 长度一致（例如 i 不应越界）。

**4) `risk_disclosure_required_gt`**
- 类型：`array<string>`
- 采样条数：通常 `1-4` 条
- 核心标准标签（高频）：
```text
波动风险
不保证收益
市场不确定性
适当性匹配
不构成个股买卖建议
```
- 扩展标签（历史样本里也会出现）：
```text
信用风险
流动性风险
利率风险
不构成投资建议
过往业绩不代表未来表现
```
- 说明：这个字段是“本轮需要覆盖的风险提示类型”，理论上应覆盖蓝图要求，可额外补充相关风险。

**5) `compliance_label_gt`**
- 类型：`string`
- 闭集取值（仅3类）：
```text
compliant
minor_violation
severe_violation
```
- 语义：
  - `compliant`：合规
  - `minor_violation`：轻微不合规（边界不清/暗示性较强）
  - `severe_violation`：严重不合规（明确买卖指令、保本保收益、确定性涨跌等）

**6) `explainability_rubric_gt`**
- 类型：`array<string>`
- 采样条数：建议 `2-5` 条（历史里可为 0）
- 推荐标签集合（主集合）：
```text
信息依据
风险收益平衡
与画像匹配
方案比较维度
可执行步骤
边界声明
```
- 说明：用于评估“解释质量是否完整”，通常和 assistant 文本一一对应。

如果你要，我可以下一步给你一份“**严格词表版本**”定义（哪些字段必须闭集、哪些可开集），这样后续统计会更稳。