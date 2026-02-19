# MemFinRobot Eval Report

- run_id: `20260219_101855`
- dataset: `D:\project\MemFinRobot\eval\datasets\MemFinConv.jsonl`
- counters: total=2, valid=2, skipped=0, failed=0

## m1_context_continuity

### Micro
- key_coverage: `0.333333`
- strict_key_hit_rate: `0.090909`
- contradiction_rate: `0.454545`
- short_term_hit_rate: `0.333333`
- long_term_hit_rate: `0.000000`
- profile_hit_rate: `0.000000`

### Macro
- key_coverage: `0.333333`
- strict_key_hit_rate: `0.090074`
- contradiction_rate: `0.454044`

### Counts
- eligible_count: `33`
- skipped_count: `4`
- failed_count: `0`
- required_key_total: `78`
- required_key_hit_total: `26`
- short_term_hit_total: `26`
- long_term_hit_total: `0`
- profile_hit_total: `0`

## m2_profile_accuracy

### Micro
- risk_level_acc: `0.000000`
- horizon_acc: `0.000000`
- liquidity_acc: `0.500000`
- constraints_f1: `0.200000`
- preferences_f1: `0.650000`
- profile_score: `0.270000`

### Macro
- risk_level_acc: `0.000000`
- horizon_acc: `0.000000`
- liquidity_acc: `0.500000`
- constraints_f1: `0.200000`
- preferences_f1: `0.650000`
- profile_score: `0.270000`

### Counts
- eligible_count: `2`
- skipped_count: `0`
- failed_count: `0`

## m3_risk_coverage

### Micro
- risk_coverage: `0.473684`
- strict_risk_coverage_rate: `0.151515`

### Macro
- risk_coverage: `0.476389`
- strict_risk_coverage_rate: `0.148897`

### Counts
- eligible_count: `33`
- skipped_count: `4`
- failed_count: `0`
- risk_required_total: `76`
- risk_hit_total: `36`

## m4_compliance

### Micro
- compliance_label_acc: `0.729730`
- severe_violation_rate: `0.270270`
- forbidden_hit_rate: `0.027027`

### Macro
- compliance_label_acc: `0.728070`
- severe_violation_rate: `0.271930`
- forbidden_hit_rate: `0.026316`

### Counts
- eligible_count: `37`
- skipped_count: `0`
- failed_count: `0`
- severe_count: `10`

## m5_explainability

### Micro
- rubric_hit_rate: `0.961240`
- judge_score_mean: `4.847027`

### Macro
- rubric_hit_rate: `0.961039`
- judge_score_mean: `4.848129`

### Counts
- eligible_count: `37`
- skipped_count: `0`
- failed_count: `0`
- rubric_required_total: `129`
- rubric_hit_total: `124`
- judge_scored_turns: `37`
