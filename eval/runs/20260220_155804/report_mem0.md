# MemFinRobot Eval Report

- run_id: `20260220_155804`
- dataset: `eval/datasets/MemFinConv_24.jsonl`
- counters: total=24, valid=24, skipped=0, failed=0

## m1_context_continuity

### Micro
- key_coverage: `0.344031`
- strict_key_hit_rate: `0.152027`
- contradiction_rate: `0.685811`
- short_term_hit_rate: `0.342747`
- long_term_hit_rate: `0.053915`
- profile_hit_rate: `0.000000`

### Macro
- key_coverage: `0.353922`
- strict_key_hit_rate: `0.169343`
- contradiction_rate: `0.672741`

### Counts
- eligible_count: `296`
- skipped_count: `20`
- failed_count: `0`
- required_key_total: `779`
- required_key_hit_total: `268`
- short_term_hit_total: `267`
- long_term_hit_total: `42`
- profile_hit_total: `0`

## m2_profile_accuracy

### Micro
- risk_level_acc: `0.041667`
- horizon_acc: `0.000000`
- liquidity_acc: `0.250000`
- constraints_f1: `0.066667`
- preferences_f1: `0.499603`
- profile_score: `0.171587`

### Macro
- risk_level_acc: `0.041667`
- horizon_acc: `0.000000`
- liquidity_acc: `0.250000`
- constraints_f1: `0.066667`
- preferences_f1: `0.499603`
- profile_score: `0.171587`

### Counts
- eligible_count: `24`
- skipped_count: `0`
- failed_count: `0`

## m3_risk_coverage

### Micro
- risk_coverage: `0.541193`
- strict_risk_coverage_rate: `0.149502`

### Macro
- risk_coverage: `0.537919`
- strict_risk_coverage_rate: `0.167438`

### Counts
- eligible_count: `301`
- skipped_count: `15`
- failed_count: `0`
- risk_required_total: `704`
- risk_hit_total: `381`

## m4_compliance

### Micro
- compliance_label_acc: `0.996764`
- severe_violation_rate: `0.003236`
- forbidden_hit_rate: `0.003236`

### Macro
- compliance_label_acc: `0.995833`
- severe_violation_rate: `0.004167`
- forbidden_hit_rate: `0.004167`

### Counts
- eligible_count: `309`
- skipped_count: `7`
- failed_count: `0`
- severe_count: `1`

## m5_explainability

### Micro
- rubric_hit_rate: `0.908457`
- judge_score_mean: `4.637217`

### Macro
- rubric_hit_rate: `0.907305`
- judge_score_mean: `4.629102`

### Counts
- eligible_count: `309`
- skipped_count: `7`
- failed_count: `0`
- rubric_required_total: `1147`
- rubric_hit_total: `1042`
- judge_scored_turns: `309`
