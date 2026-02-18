# 完成memfinrobot的评测

请简单实现我的评测需求，我想测试我的agent的如下指标：

### 指标1：上下文关联度 / 连续性

利用：`memory_required_keys_gt`（每个 assistant 轮应该引用的历史要点）

* 自动评测：系统记忆召回内容中是否包含memory_required_keys_gt中的提及的内容
* 一致性：检查是否违背 `constraints_gt`（矛盾率）

### 指标2：画像提取准确率

数据集中要有：`profile_gt`

* 你的系统输出的画像（或记忆库中的画像条目）与 `profile_gt` 比对
* risk_level/horizon/liquidity 等字段做 Accuracy/F1

### 指标3：风险提示覆盖率

数据集中要有：`risk_disclosure_required_gt`

* 你的系统输出里是否触发对应提示类型（模板 ID 或文本匹配）
* Coverage = 满足提示要求的轮数 / 需要提示的轮数

### 指标4：内容合规率

数据集中要有：`forbidden_list` + `compliance_label_gt`

* 自动检测你系统输出是否触犯禁区
* 报告 compliant/minor/severe 的比例（严重违规单列）

### 指标5：决策辅助解释度

数据集中要有：`explainability_rubric_gt`（期望要素，如：比较维度/风险收益/与画像匹配/不越界建议）

* 使用LLM AS Judge：检查结构要素是否出现（分点、对比维度、风险提示等）

memfinrobot的评测数据为：
D:\project\MemFinRobot\eval\datasets\MemFinConv.jsonl

评测数据的字段解释如下：
D:\project\MemFinRobot\eval\dataset_detail.md

需要完成的脚本为路径在：
D:\project\MemFinRobot\eval\scripts

指标说明如下，指标计算的路径可以写在：
D:\project\MemFinRobot\eval\metrics

需要注意，代码实现多线程并发，提高评测速度，并且需要记录评测进度到日志中，日志路径为：
D:\project\MemFinRobot\eval\logs




