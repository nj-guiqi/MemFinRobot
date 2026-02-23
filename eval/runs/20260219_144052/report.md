# MemFinRobot Eval Report

- run_id: `20260219_144052`
- dataset: `D:\project\MemFinRobot\eval\datasets\MemFinConv.jsonl`
- counters: total=2, valid=2, skipped=0, failed=0

## m1_context_continuity

### Micro
- key_coverage: `0.307692`
- strict_key_hit_rate: `0.121212`
- contradiction_rate: `0.484848`
- short_term_hit_rate: `0.269231`
- long_term_hit_rate: `0.076923`
- profile_hit_rate: `0.025641`

### Macro
- key_coverage: `0.307692`
- strict_key_hit_rate: `0.119485`
- contradiction_rate: `0.485294`

### Counts
- eligible_count: `33`
- skipped_count: `4`
- failed_count: `0`
- required_key_total: `78`
- required_key_hit_total: `24`
- short_term_hit_total: `21`
- long_term_hit_total: `6`
- profile_hit_total: `2`

## m2_profile_accuracy

### Micro
- risk_level_acc: `0.000000`
- horizon_acc: `0.000000`
- liquidity_acc: `0.500000`
- constraints_f1: `0.342857`
- preferences_f1: `0.220238`
- profile_score: `0.212619`

### Macro
- risk_level_acc: `0.000000`
- horizon_acc: `0.000000`
- liquidity_acc: `0.500000`
- constraints_f1: `0.342857`
- preferences_f1: `0.220238`
- profile_score: `0.212619`

### Counts
- eligible_count: `2`
- skipped_count: `0`
- failed_count: `0`

## m3_risk_coverage

### Micro
- risk_coverage: `0.500000`
- strict_risk_coverage_rate: `0.212121`

### Macro
- risk_coverage: `0.500000`
- strict_risk_coverage_rate: `0.211397`

### Counts
- eligible_count: `33`
- skipped_count: `4`
- failed_count: `0`
- risk_required_total: `76`
- risk_hit_total: `38`

## m4_compliance

### Micro
- compliance_label_acc: `0.432432`
- severe_violation_rate: `0.405405`
- forbidden_hit_rate: `0.000000`

### Macro
- compliance_label_acc: `0.434211`
- severe_violation_rate: `0.406433`
- forbidden_hit_rate: `0.000000`

### Counts
- eligible_count: `37`
- skipped_count: `0`
- failed_count: `0`
- severe_count: `15`

## m5_explainability

### Micro
- rubric_hit_rate: `0.914729`
- judge_score_mean: `4.640000`

### Macro
- rubric_hit_rate: `0.914863`
- judge_score_mean: `4.639737`

### Counts
- eligible_count: `37`
- skipped_count: `0`
- failed_count: `0`
- rubric_required_total: `129`
- rubric_hit_total: `118`
- judge_scored_turns: `37`
