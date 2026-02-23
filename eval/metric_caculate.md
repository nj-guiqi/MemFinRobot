# MemFinRobot 指标计算方法说明（用于论文）

## 1. 评测目标与总体流程
本文评测的目标是从**上下文连续性、用户画像对齐、风险披露、合规性与可解释性**五个维度，对金融对话助手进行可复现量化评估。实现代码位于 `eval/metrics`。

整体流程如下：
1. 基于 `dialog_trace.jsonl`（或 `dialog_trace_mem0.jsonl` / `dialog_trace_llm.jsonl`）构建轮级中间表 `turn_eval`（函数：`build_turn_eval_rows`）。
2. 分别计算 M1~M5（`m1_context.py` 到 `m5_explainability.py`）。
3. 输出每个指标的 `micro`、`macro`、`counts` 与 `by_dialog`。

该流程的核心特点是：**先结构化，再统计**。即先把一轮对话映射为可计算字段，再执行统一统计，保证可解释性与可审计性。

---

## 2. 符号与数据定义
设对话集合为 $\mathcal{D}$，对话 $d\in\mathcal{D}$ 的轮集合为 $\mathcal{T}_d$。

对任意轮 $(d,t)$，记：
- $y_{d,t}$：模型回复文本（`pred_assistant_text`）
- $g_{d,t}$：对应 GT 标签（`gt_turn_tags`）
- $s_{d,t}\in\{\text{ok},\text{timeout},\text{error}\}$：轮状态（`turn_status`）
- $\mathbf{1}(\cdot)$：指示函数

中间表中，每个指标都有可评估标记 `eligible_m*`。仅 `eligible=True` 的样本进入该指标分母。

---

## 3. 指标定义

### 3.1 M1：上下文关联度 / 连续性（`m1_context.py`）

#### 3.1.1 轮级命中建模
对轮 $(d,t)$，GT 要求的记忆键集合为 $K_{d,t}$（来自 `memory_required_keys_gt`）。
通过 `resolve_memory_required_key` 将每个 key 解析为目标文本，得到可解析集合 $\tilde K_{d,t}\subseteq K_{d,t}$。

对每个 $k\in\tilde K_{d,t}$，定义命中指示：
$$
h_{d,t,k}=\mathbf{1}(\text{target}(k) \text{ 出现在 short\_term / long\_term / profile 任一来源})
$$
其中来源判断由 `detect_key_hits_from_memory_sources` 完成。

记：
$$
H_{d,t}=\sum_{k\in\tilde K_{d,t}} h_{d,t,k},\quad R_{d,t}=|\tilde K_{d,t}|
$$

轮级 key 覆盖率：
$$
\mathrm{KC}_{d,t}=\frac{H_{d,t}}{R_{d,t}}\quad (R_{d,t}>0)
$$

轮级 strict 命中：
$$
\mathrm{SKH}_{d,t}=\mathbf{1}(H_{d,t}=R_{d,t})
$$

轮级约束冲突：
$$
\mathrm{CONTRA}_{d,t}=\mathbf{1}(\text{回复与用户 constraints 存在规则冲突})
$$
（由 `detect_constraint_contradiction` 给出）。

#### 3.1.2 聚合统计
仅当 `eligible_m1=True`（即 $s_{d,t}=\text{ok}$ 且 $R_{d,t}>0$）才计入。

Micro：
$$
\mathrm{KC}^{micro}=\frac{\sum_{d,t} H_{d,t}}{\sum_{d,t} R_{d,t}},\qquad
\mathrm{SKH}^{micro}=\frac{\sum_{d,t}\mathrm{SKH}_{d,t}}{N_{m1}},\qquad
\mathrm{CR}^{micro}=\frac{\sum_{d,t}\mathrm{CONTRA}_{d,t}}{N_{m1}}
$$
其中 $N_{m1}$ 为可评估轮数。

Macro（先对话后平均）：
$$
\mathrm{KC}^{macro}=\frac{1}{|\mathcal{D}_{m1}|}\sum_{d\in\mathcal{D}_{m1}}\frac{\sum_t H_{d,t}}{\sum_t R_{d,t}}
$$
其余同理。

另外统计 short/long/profile 三路来源命中率：
$$
\mathrm{HitRate}_{src}=\frac{\text{src 命中总数}}{\sum_{d,t}R_{d,t}},\; src\in\{short,long,profile\}
$$

---

### 3.2 M2：画像提取准确率（`m2_profile.py`）
M2 以**对话级**为主。对每个对话 $d$：

1. 三个离散字段准确率：
- 风险等级（risk）
- 投资期限（horizon）
- 流动性需求（liquidity）

定义：
$$
\mathrm{Acc}^{(f)}_d=\mathbf{1}(\hat z^{(f)}_d=z^{(f)}_d),\quad f\in\{risk,horizon,liquidity\}
$$

2. 两个集合字段 F1：
- 约束集合 constraints
- 偏好集合 preferences

给定预测集合 $\hat S_d$ 与 GT 集合 $S_d$：
$$
P_d=\frac{|\hat S_d\cap S_d|}{|\hat S_d|},\quad
R_d=\frac{|\hat S_d\cap S_d|}{|S_d|},\quad
F1_d=\frac{2P_dR_d}{P_d+R_d}
$$
（代码对空集做边界处理）。

3. 对话级综合画像分：
$$
\mathrm{ProfileScore}_d=\frac{1}{5}\left(\mathrm{Acc}^{risk}_d+\mathrm{Acc}^{horizon}_d+\mathrm{Acc}^{liquidity}_d+F1^{constraints}_d+F1^{preferences}_d\right)
$$

全局 micro/macro 在当前实现中同口径（均为对话均值）。

注：若 `profile_snapshot` 缺失，代码会从全对话回复文本中进行关键词回退推断（`_infer_profile_from_text`）。

---

### 3.3 M3：风险提示覆盖率（`m3_risk.py`）
对轮 $(d,t)$，设 GT 风险标签集合为 $R_{d,t}$，预测标签集合为 $\hat R_{d,t}$。

轮级覆盖率：
$$
\mathrm{RC}_{d,t}=\frac{|R_{d,t}\cap \hat R_{d,t}|}{|R_{d,t}|}
$$

轮级严格覆盖：
$$
\mathrm{RStrict}_{d,t}=\mathbf{1}(R_{d,t}\subseteq \hat R_{d,t})
$$

仅当 `eligible_m3=True`（$s_{d,t}=ok$ 且 $|R_{d,t}|>0$）计入。

Micro：
$$
\mathrm{RC}^{micro}=\frac{\sum_{d,t}|R_{d,t}\cap \hat R_{d,t}|}{\sum_{d,t}|R_{d,t}|},
\qquad
\mathrm{RStrict}^{micro}=\frac{\sum_{d,t}\mathrm{RStrict}_{d,t}}{N_{m3}}
$$
Macro 为对话均值。

---

### 3.4 M4：内容合规率（`m4_compliance.py`）
M4 核心是标签一致性与严重违规率：

1. 合规标签准确率：
$$
\mathrm{CompAcc}=\frac{1}{N_{m4}}\sum_{d,t}\mathbf{1}(\hat c_{d,t}=c_{d,t})
$$
其中 $\hat c_{d,t}\in\{compliant,minor\_violation,severe\_violation\}$。

2. 严重违规率：
$$
\mathrm{SevereRate}=\frac{1}{N_{m4}}\sum_{d,t}\mathbf{1}(\hat c_{d,t}=severe\_violation)
$$

3. 禁区命中率：
$$
\mathrm{ForbiddenHitRate}=\frac{1}{N_{m4}}\sum_{d,t}\mathbf{1}(|\mathrm{forbidden\_hits}_{d,t}|>0)
$$

其中 $N_{m4}$ 为 `eligible_m4=True` 的轮数（当前即所有 $s_{d,t}=ok$ 的轮）。

---

### 3.5 M5：决策辅助解释度（`m5_explainability.py`）
对轮 $(d,t)$，设 GT 解释要素集合为 $E_{d,t}$，命中集合为 $\hat E_{d,t}$。

轮级 rubric 命中率：
$$
\mathrm{ER}_{d,t}=\frac{|E_{d,t}\cap \hat E_{d,t}|}{|E_{d,t}|}
$$

启发式评分（1~5）：
$$
\mathrm{Score}_{d,t}=1+4\cdot \frac{|E_{d,t}\cap \hat E_{d,t}|}{|E_{d,t}|}
$$
（对应代码 `heuristic_judge_score`）。

仅 `eligible_m5=True`（$s_{d,t}=ok$ 且 $|E_{d,t}|>0$）计入。

Micro：
$$
\mathrm{ER}^{micro}=\frac{\sum_{d,t}|E_{d,t}\cap \hat E_{d,t}|}{\sum_{d,t}|E_{d,t}|},
\qquad
\overline{\mathrm{Score}}=\frac{1}{N_{score}}\sum_{d,t}\mathrm{Score}_{d,t}
$$
Macro 为对话均值。

---

## 4. 可评估样本与分母控制
当前实现采用“按指标独立过滤”的设计：
- `eligible_m1`: `turn_status==ok` 且有可解析 key
- `eligible_m2`: 对话级（`valid_dialog` 且 `profile_gt` 可用）
- `eligible_m3`: `turn_status==ok` 且有风险标签需求
- `eligible_m4`: `turn_status==ok`
- `eligible_m5`: `turn_status==ok` 且有解释要素需求

因此，**不同指标分母不同**，论文中应避免直接横向比较原始分子/分母，而应比较各指标自身定义下的 micro/macro。

---

## 5. 方法分析（可写入论文讨论）

### 5.1 优点
1. **可解释性强**：每个指标都可追溯到轮级字段（`turn_eval`），便于误差分析与案例复盘。
2. **工程鲁棒性好**：通过 `eligible` 与 `counts` 机制，显式处理缺失、异常与不可评估样本。
3. **多粒度评估**：同时提供轮级、对话级、micro/macro，适用于模型迭代和系统对比。
4. **可迁移性高**：评估依赖 trace 契约，不强绑定具体 agent 实现，便于跨系统横评。

### 5.2 局限性
1. **规则匹配偏保守**：M1/M3/M5 部分依赖关键词或子串匹配，可能低估语义等价表达。
2. **M5 评分为启发式**：当前 `judge_score_1_5` 由命中率线性映射，不等同于真正 LLM-Judge 主观质量评分。
3. **M2 回退推断存在噪声**：当 `profile_snapshot` 缺失时，文本回退推断可能引入偏差。
4. **M4 依赖标签质量**：合规标签精度受 GT 标注规范与 forbidden 列表覆盖度影响。

### 5.3 对“无记忆基线”评测的含义
对于纯 LLM（无 memory）基线，M1 在方法上可能天然不适配。当前实践可采用“不可满足项忽略”（例如将 `memory_required_keys_gt` 置空）以避免不公平惩罚，并在 `manifest` 中显式记录该设置，保证结果可解释与可复现。

---

## 6. 结果报告建议（论文写作）
建议在正文表格中至少报告：
- M1: `key_coverage`, `strict_key_hit_rate`, `contradiction_rate`
- M2: `profile_score` 及 3 个字段准确率
- M3: `risk_coverage`, `strict_risk_coverage_rate`
- M4: `compliance_label_acc`, `severe_violation_rate`
- M5: `rubric_hit_rate`, `judge_score_mean`
- 附带 `eligible_count/skipped_count/failed_count`

并在附录给出代表性失败案例（从 `dialog_trace` 对齐到 `turn_eval`），以支撑定量结论。
