# MemFinRobot Eval Report

- run_id: `debug_finrobot_one2`
- dataset: `eval/datasets/_debug_one_dialog.jsonl`
- counters: total=1, valid=1, skipped=0, failed=0

## m1_context_continuity

### Micro
- key_coverage: `0.000000`
- strict_key_hit_rate: `0.000000`
- contradiction_rate: `0.000000`
- short_term_hit_rate: `0.000000`
- long_term_hit_rate: `0.000000`
- profile_hit_rate: `0.000000`

### Macro
- key_coverage: `0.000000`
- strict_key_hit_rate: `0.000000`
- contradiction_rate: `0.000000`

### Counts
- eligible_count: `3`
- skipped_count: `10`
- failed_count: `0`
- required_key_total: `5`
- required_key_hit_total: `0`
- short_term_hit_total: `0`
- long_term_hit_total: `0`
- profile_hit_total: `0`

## m2_profile_accuracy

### Micro
- risk_level_acc: `1.000000`
- horizon_acc: `0.000000`
- liquidity_acc: `0.000000`
- constraints_f1: `0.000000`
- preferences_f1: `0.000000`
- profile_score: `0.200000`

### Macro
- risk_level_acc: `1.000000`
- horizon_acc: `0.000000`
- liquidity_acc: `0.000000`
- constraints_f1: `0.000000`
- preferences_f1: `0.000000`
- profile_score: `0.200000`

### Counts
- eligible_count: `1`
- skipped_count: `0`
- failed_count: `0`

## m3_risk_coverage

### Micro
- risk_coverage: `0.250000`
- strict_risk_coverage_rate: `0.000000`

### Macro
- risk_coverage: `0.250000`
- strict_risk_coverage_rate: `0.000000`

### Counts
- eligible_count: `2`
- skipped_count: `11`
- failed_count: `0`
- risk_required_total: `4`
- risk_hit_total: `1`

## m4_compliance

### Micro
- compliance_label_acc: `1.000000`
- severe_violation_rate: `0.000000`
- forbidden_hit_rate: `0.000000`

### Macro
- compliance_label_acc: `1.000000`
- severe_violation_rate: `0.000000`
- forbidden_hit_rate: `0.000000`

### Counts
- eligible_count: `3`
- skipped_count: `10`
- failed_count: `0`
- severe_count: `0`

## m5_explainability

### Micro
- rubric_hit_rate: `0.272727`
- judge_score_mean: `2.000000`

### Macro
- rubric_hit_rate: `0.272727`
- judge_score_mean: `2.000000`

### Counts
- eligible_count: `3`
- skipped_count: `10`
- failed_count: `0`
- rubric_required_total: `11`
- rubric_hit_total: `3`
- judge_scored_turns: `3`
