
## 实验结果汇总

MemFinRobot:/Users/nijian.15/projects/MemFinRobot/eval/runs/20260220_082913/report.md

mem0:/Users/nijian.15/projects/MemFinRobot/eval/runs/20260220_155804/report_mem0.md

LLM:/Users/nijian.15/projects/MemFinRobot/eval/runs/20260221_085707/report_llm.md

FinRobot:/Users/nijian.15/projects/MemFinRobot/eval/runs/20260222_055021/report_finrobot.md

LangMem:/Users/nijian.15/projects/MemFinRobot/eval/runs/20260222_072551/report_langmem.md

## 汇总结果

注：带 `↓` 表示越低越好；`LLM` 的 `m1_*` 因 `eligible_count=0` 记为 `-`；`mem0/LLM/FinRobot/LangMem` 的 `m4_*` 已用 `ComplianceGuard` 基于 `pred_assistant_text` 重新计算（替代适配器硬编码合规）。

| Method | run_id | m1_key_cov | m1_strict_hit | m1_contra↓ | m1_short_hit | m1_long_hit | m1_profile_hit | m2_profile_score | m3_risk_cov | m3_strict_risk | m4_acc | m4_severe↓ | m5_rubric_hit | m5_judge_mean |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MemFinRobot | 20260220_082913 | 0.2686 | 0.1339 | 0.4812 | 0.2370 | 0.0790 | 0.0174 | 0.1853 | 0.4780 | 0.1270 | 0.5458 | 0.4024 | 0.9209 | 4.6769 |
| mem0 | 20260220_155804 | 0.3440 | 0.1520 | 0.6858 | 0.3427 | 0.0539 | 0.0000 | 0.1716 | 0.5412 | 0.1495 | 0.3204 | 0.6634 | 0.9085 | 4.6372 |
| LLM | 20260221_085707 | - | - | - | - | - | - | 0.1625 | 0.5361 | 0.1494 | 0.5380 | 0.4241 | 0.8704 | 4.4683 |
| FinRobot | 20260222_055021 | 0.3622 | 0.1518 | 0.6238 | 0.3622 | 0.0000 | 0.0000 | 0.1679 | 0.5097 | 0.1494 | 0.5443 | 0.4525 | 0.8934 | 4.5462 |
| LangMem | 20260222_072551 | 0.3697 | 0.1551 | 0.7525 | 0.3672 | 0.0539 | 0.0000 | 0.1865 | 0.4500 | 0.1364 | 0.4652 | 0.5285 | 0.8593 | 4.4102 |
