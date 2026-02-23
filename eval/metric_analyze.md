下面给你一版**完整可直接放入毕业论文**的章节文本：整体以**严谨定义与公式**为主（每个指标都给出轮级/对话级定义、eligible 条件、micro/macro 聚合），并在每个小节末尾用段落补充“解释与分析（优势/局限）”。你可以直接粘贴进论文的方法章节；若你后续需要“与实验章节的衔接段”“表格呈现建议”“案例分析段落”，我也可以继续补。

---

# X.X 经济金融领域多轮对话体验指标（MemFinRobot Metrics）

## X.X.1 评测目标与总体流程

本文的评测目标是从**上下文连续性（M1）、用户画像对齐（M2）、风险披露覆盖（M3）、内容合规性（M4）与决策辅助解释度（M5）**五个维度，对经济金融领域多轮对话助手进行可复现的量化评估。评测输入为对话执行轨迹 `dialog_trace.jsonl`（或不同系统变体的 trace），评测过程遵循“**先结构化，再统计**”的范式：首先将每轮对话映射为轮级中间表 `turn_eval`，再在此基础上计算各项指标并聚合得到 micro/macro 等统计。

设对话集合为 (\mathcal{D})，对话 (d\in\mathcal{D}) 的轮集合为 (\mathcal{T}_d)。对任意轮 ((d,t))，定义：

* (y_{d,t})：模型回复文本（`pred_assistant_text`）
* (g_{d,t})：该轮 GT 标签/要素（`gt_turn_tags`）
* (s_{d,t}\in{\text{ok},\text{timeout},\text{error}})：轮状态（`turn_status`）
* (\mathbf{1}(\cdot))：指示函数

为保证统计鲁棒性，本文为每个指标 (M_i) 定义独立的可评估标记 `eligible_mi`，仅当 `eligible=True` 时样本进入该指标分母。不同指标的分母集合因此可能不同，论文结果呈现需同时报告各指标的有效样本数（eligible counts），以保证可解释性与可比性。

---

## X.X.2 M1：上下文关联度与连续性（Contextual Continuity）

### X.X.2.1 轮级命中建模（Key Hit Modeling）

金融多轮对话的连续性主要体现为：模型能否在后续轮次**引用并遵循**先前给出的关键条件，并避免与用户硬约束冲突。为将该能力操作化为可计算信号，本文以 GT 给出的“记忆键需求”为锚点。

对轮 ((d,t))，设 GT 要求的记忆键集合为
[
K_{d,t} \quad (\text{来自 } \texttt{memory_required_keys_gt})
]
通过解析函数将 key 映射为目标文本证据，得到可解析集合
[
\tilde{K}*{d,t}\subseteq K*{d,t}
]
对每个 (k\in \tilde{K}*{d,t})，定义命中指示变量：
[
h*{d,t,k}=\mathbf{1}\Big(\text{target}(k)\ \text{出现在}\ \text{short_term} \ \lor\ \text{long_term}\ \lor\ \text{profile}\Big)
]
其中 `short_term/long_term/profile` 分别对应短期上下文、长期记忆与用户画像注入来源。

令
[
H_{d,t}=\sum_{k\in \tilde{K}*{d,t}} h*{d,t,k},\qquad R_{d,t}=|\tilde{K}*{d,t}|
]
则轮级关键条件覆盖率（Key Coverage）定义为：
[
\mathrm{KC}*{d,t}=\frac{H_{d,t}}{R_{d,t}}\quad (R_{d,t}>0)
]
轮级严格命中（Strict Key Hit）定义为：
[
\mathrm{SKH}*{d,t}=\mathbf{1}(H*{d,t}=R_{d,t})
]

此外，为刻画“引用了条件但违反约束”的情况，本文定义轮级约束冲突指示变量：
[
\mathrm{CONTRA}*{d,t}=\mathbf{1}\big(y*{d,t}\ \text{与用户 constraints 存在规则冲突}\big)
]

### X.X.2.2 可评估条件与聚合统计（Eligibility & Aggregation）

M1 的可评估条件为：
[
\texttt{eligible_m1}=\mathbf{1}(s_{d,t}=\text{ok}\ \land\ R_{d,t}>0)
]
记可评估轮集合为 (\Omega_{m1})，其大小为 (N_{m1}=|\Omega_{m1}|)。

**Micro 口径：**
[
\mathrm{KC}^{micro}=\frac{\sum_{(d,t)\in\Omega_{m1}} H_{d,t}}{\sum_{(d,t)\in\Omega_{m1}} R_{d,t}},\qquad
\mathrm{SKH}^{micro}=\frac{1}{N_{m1}}\sum_{(d,t)\in\Omega_{m1}}\mathrm{SKH}*{d,t},\qquad
\mathrm{CR}^{micro}=\frac{1}{N*{m1}}\sum_{(d,t)\in\Omega_{m1}}\mathrm{CONTRA}_{d,t}
]

**Macro 口径（先对话后平均）：** 记 (\mathcal{D}*{m1}) 为至少含一个可评估轮的对话集合，则
[
\mathrm{KC}^{macro}=\frac{1}{|\mathcal{D}*{m1}|}\sum_{d\in\mathcal{D}*{m1}}
\frac{\sum*{t:(d,t)\in\Omega_{m1}} H_{d,t}}{\sum_{t:(d,t)\in\Omega_{m1}} R_{d,t}}
]
其余 (\mathrm{SKH}^{macro})、(\mathrm{CR}^{macro}) 同理定义为对话级均值的跨对话平均。

为支持组件级归因，本文进一步统计三路来源的命中率：
[
\mathrm{HitRate}*{src}=\frac{\text{src 命中总数}}{\sum*{(d,t)\in\Omega_{m1}} R_{d,t}},\quad src\in{short,long,profile}
]

### X.X.2.3 指标解释与分析

M1 将连续性拆解为“**覆盖（有没有用到）**”与“**一致性（有没有用错）**”。覆盖率衡量模型是否正确调取关键条件；冲突率直接刻画回复是否违反用户硬约束，从而避免仅凭关键词出现而高估连续性。其局限在于命中判定较多依赖字符串/关键词匹配，可能低估语义等价表达；约束冲突检测为启发式规则，可能存在漏检与误检。因此，本文在结果呈现中建议同时报告 (\mathrm{KC})、(\mathrm{SKH}) 与 (\mathrm{CR}) 并结合案例复核。

---

## X.X.3 M2：用户画像对齐度（Profile Alignment）

### X.X.3.1 对话级定义（Dialog-level Formulation）

金融建议的适当性依赖用户画像（风险等级、期限、流动性）以及约束/偏好要素。由于画像常跨多轮逐步显露，M2 采用**对话级**评估。对每个对话 (d)，设 GT 离散画像字段为 (z_d^{(f)})，预测为 (\hat z_d^{(f)})，其中
[
f\in{risk,horizon,liquidity}
]
离散字段准确率定义为：
[
\mathrm{Acc}_d^{(f)}=\mathbf{1}(\hat z_d^{(f)}=z_d^{(f)})
]

对集合字段（约束/偏好），设 GT 集合为 (S_d)，预测集合为 (\hat S_d)。精确率与召回率分别为：
[
P_d=\frac{|\hat S_d\cap S_d|}{|\hat S_d|},\quad
R_d=\frac{|\hat S_d\cap S_d|}{|S_d|}
]
F1 定义为：
[
F1_d=\frac{2P_dR_d}{P_d+R_d}
]
（实现中对空集情况做边界处理以避免分母为零。）

综合画像得分定义为：
[
\mathrm{ProfileScore}_d=\frac{1}{5}\left(
\mathrm{Acc}_d^{risk}+\mathrm{Acc}_d^{horizon}+\mathrm{Acc}_d^{liquidity}+F1_d^{constraints}+F1_d^{preferences}
\right)
]

### X.X.3.2 可评估条件与聚合统计

记满足画像标注可用、对话有效的集合为 (\mathcal{D}*{m2})。M2 的统计以对话均值为主，因此 micro/macro 在当前实现中同口径（均为对话均值）：
[
\overline{\mathrm{ProfileScore}}=\frac{1}{|\mathcal{D}*{m2}|}\sum_{d\in\mathcal{D}*{m2}}\mathrm{ProfileScore}*d
]
并拆分报告各子项均值：
[
\overline{\mathrm{Acc}^{(f)}}=\frac{1}{|\mathcal{D}*{m2}|}\sum*{d}\mathrm{Acc}*d^{(f)},\qquad
\overline{F1^{(s)}}=\frac{1}{|\mathcal{D}*{m2}|}\sum_{d}F1_d^{(s)}
]
其中 (s\in{constraints,preferences})。

当系统缺失结构化 `profile_snapshot` 时，评测实现会从全对话回复文本进行关键词回退推断，以提升评测覆盖面。

### X.X.3.3 指标解释与分析

M2 同时约束“关键画像方向是否正确”（离散准确率）与“画像要素是否充分且不过度泛化”（集合 F1），因此更贴近金融适当性评价。其主要局限在于回退推断可能引入噪声；同时模型可通过频繁复述画像字段获得更高的集合命中，存在一定策略性空间。因此本文建议在实验报告中除综合分外，必须拆分呈现三类准确率与两类 F1，以定位系统性偏差来源。

---

## X.X.4 M3：风险提示覆盖率（Risk Disclosure Coverage）

### X.X.4.1 轮级定义（Turn-level Formulation）

金融对话需要充分的风险披露。M3 将披露质量定义为“应披露风险标签”的覆盖程度。对轮 ((d,t))，设 GT 风险标签集合为 (R_{d,t})，预测集合为 (\hat R_{d,t})。

轮级风险覆盖率定义为：
[
\mathrm{RC}*{d,t}=\frac{|R*{d,t}\cap \hat R_{d,t}|}{|R_{d,t}|}\quad (|R_{d,t}|>0)
]
轮级严格覆盖指示变量定义为：
[
\mathrm{RStrict}*{d,t}=\mathbf{1}(R*{d,t}\subseteq \hat R_{d,t})
]

### X.X.4.2 可评估条件与聚合统计

M3 的可评估条件为：
[
\texttt{eligible_m3}=\mathbf{1}(s_{d,t}=\text{ok}\ \land\ |R_{d,t}|>0)
]
记可评估轮集合为 (\Omega_{m3})，大小为 (N_{m3})。

**Micro 口径：**
[
\mathrm{RC}^{micro}=\frac{\sum_{(d,t)\in\Omega_{m3}} |R_{d,t}\cap \hat R_{d,t}|}{\sum_{(d,t)\in\Omega_{m3}} |R_{d,t}|},\qquad
\mathrm{RStrict}^{micro}=\frac{1}{N_{m3}}\sum_{(d,t)\in\Omega_{m3}}\mathrm{RStrict}_{d,t}
]

**Macro 口径：** 先对话内求均值/比例，再跨对话平均（定义同 M1 的 macro 形式）。

### X.X.4.3 指标解释与分析

M3 的优势是与金融合规实践直接对应：GT 风险标签可视为“应披露清单”，覆盖率反映披露是否全面，严格覆盖率对“缺项”更敏感。其局限在于风险标签抽取与命中常依赖关键词或规则触发，可能低估隐式披露，也可能将模板化披露视为高覆盖。因此本文建议结合严格覆盖率与样例检查，避免对高覆盖分数做过度解释。

---

## X.X.5 M4：内容合规性（Compliance）

### X.X.5.1 指标定义（Label Consistency & Red-line Monitoring）

合规性不仅体现在整体等级一致，也体现在是否触碰红线表达。M4 设计为三项互补指标。对可评估轮 ((d,t)\in\Omega_{m4})，设 GT 合规标签为 (c_{d,t})，预测为 (\hat c_{d,t})，其中
[
\hat c_{d,t},c_{d,t}\in{compliant,\ minor_violation,\ severe_violation}
]

合规标签准确率定义为：
[
\mathrm{CompAcc}=\frac{1}{N_{m4}}\sum_{(d,t)\in\Omega_{m4}}\mathbf{1}(\hat c_{d,t}=c_{d,t})
]

严重违规率定义为：
[
\mathrm{SevereRate}=\frac{1}{N_{m4}}\sum_{(d,t)\in\Omega_{m4}}\mathbf{1}(\hat c_{d,t}=severe_violation)
]

禁区命中率定义为：
[
\mathrm{ForbiddenHitRate}=\frac{1}{N_{m4}}\sum_{(d,t)\in\Omega_{m4}}\mathbf{1}(|forbidden_hits_{d,t}|>0)
]

### X.X.5.2 可评估条件与统计口径

M4 的可评估条件通常设为所有正常轮：
[
\texttt{eligible_m4}=\mathbf{1}(s_{d,t}=\text{ok})
]
因此 (N_{m4}) 为所有 ok 轮数量。M4 以轮级 micro 为主要口径；若需要 macro，可按对话分组计算再平均。

### X.X.5.3 指标解释与分析

(\mathrm{CompAcc}) 反映整体合规等级一致性，但可能掩盖少量极端风险事件；因此本文强调 (\mathrm{SevereRate}) 作为核心安全指标，用于重点惩罚严重违规。同时，(\mathrm{ForbiddenHitRate}) 提供审计友好特性：禁区命中可定位到触发短语以支持人工复核。其局限在于：若 GT 合规标签存在噪声，会影响准确率；禁区列表若覆盖不足或对同义改写不敏感，可能漏检。

---

## X.X.6 M5：决策辅助解释度（Explainability）

### X.X.6.1 轮级 rubric 命中（Rubric-based Coverage）

金融对话的高质量解释应包含依据、风险收益权衡、可执行步骤与边界声明等要素。M5 以 GT rubric 要素集合为锚点，评估模型解释要素的覆盖情况。对轮 ((d,t))，设 GT 要素集合为 (E_{d,t})，命中集合为 (\hat E_{d,t})。

轮级要素命中率定义为：
[
\mathrm{ER}*{d,t}=\frac{|E*{d,t}\cap \hat E_{d,t}|}{|E_{d,t}|}\quad (|E_{d,t}|>0)
]

为便于与人工评分尺度对齐，本文定义启发式 1–5 分映射：
[
\mathrm{Score}*{d,t}=1+4\cdot \mathrm{ER}*{d,t}
]

### X.X.6.2 可评估条件与聚合统计

M5 的可评估条件为：
[
\texttt{eligible_m5}=\mathbf{1}(s_{d,t}=\text{ok}\ \land\ |E_{d,t}|>0)
]
记可评估轮集合为 (\Omega_{m5})，大小为 (N_{m5})。

**Micro 口径：**
[
\mathrm{ER}^{micro}=\frac{\sum_{(d,t)\in\Omega_{m5}} |E_{d,t}\cap \hat E_{d,t}|}{\sum_{(d,t)\in\Omega_{m5}} |E_{d,t}|}
]
启发式均分：
[
\overline{\mathrm{Score}}=\frac{1}{N_{m5}}\sum_{(d,t)\in\Omega_{m5}} \mathrm{Score}_{d,t}
]
Macro 口径同理可先对话聚合再平均。

### X.X.6.3 指标解释与分析

M5 的优势在于其解释性评估可复现、可审计：rubric 要素将“解释度”拆解为具体可计算单元，便于系统迭代与对比。然而，需要注意 (\mathrm{ER}) 衡量的是“要素覆盖”而非“解释质量”，高命中并不必然意味着信息充分或推理严谨；同时模型可能通过模板化结构提高命中率。因此本文建议在实验章节中结合案例分析，展示命中高但内容空泛的反例，以防读者将高分等同于高质量解释。

---

## X.X.7 分母控制与对无记忆基线的处理（Denominator Control & Memory-free Baselines）

由于五个指标评估对象不同，本文采用“按指标独立过滤”的 eligible 设计：M1 仅在存在可解析 key 的轮上评估；M3/M5 仅在存在风险披露或解释要素需求的轮上评估；M4 覆盖所有正常轮；M2 在对话级、且画像 GT 可用时评估。该设计保证每个指标的分母仅包含“具备可评估条件”的样本，从而减少缺失与异常造成的偏差。

对于无记忆（memory-free）的纯 LLM 基线，M1 在方法上可能不完全适配：若仍使用“必须命中记忆键”的要求，会对不具备该能力的系统产生结构性不公平。为保证对比的可解释性，本文实践中可采用“不可满足项忽略”的策略（例如将该基线的 `memory_required_keys_gt` 置空或在 manifest 中显式声明忽略记忆 key 需求），并在论文中说明该选择与其合理性，以保证可复现与公平比较。

---

###（本节小结）
本文提出的 MemFinRobot 指标体系以结构化对话轨迹为基础，提供了从连续性、画像对齐、风险披露、合规性到解释度的多维评估。各指标均给出明确的轮级/对话级定义与 micro/macro 聚合口径，并通过 eligible 机制实现分母控制，从而在保证可解释性与可审计性的同时，提高统计鲁棒性并支持系统消融分析。

---

如果你希望这章更像“毕业论文”常见结构，我还可以顺手帮你补两段（不改变公式严谨性）：

1. **“指标与实验表格如何对应”**：每个指标在实验表中的列名与解释；
2. **“Threats to Validity”** 小节：把你列的 construct validity、gaming、规则覆盖不足等整理成论文常规写法。
