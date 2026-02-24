# FinRobot Eval Report

- run_id: `20260222_055021`
- dataset: `eval/datasets/MemFinConv_24.jsonl`
- counters: total=24, valid=24, skipped=0, failed=0

## m1_context_continuity

### Micro
- key_coverage: `0.362155`
- strict_key_hit_rate: `0.151815`
- contradiction_rate: `0.623762`
- short_term_hit_rate: `0.362155`
- long_term_hit_rate: `0.000000`
- profile_hit_rate: `0.000000`

### Macro
- key_coverage: `0.362105`
- strict_key_hit_rate: `0.154056`
- contradiction_rate: `0.587936`

### Counts
- eligible_count: `303`
- skipped_count: `13`
- failed_count: `0`
- required_key_total: `798`
- required_key_hit_total: `289`
- short_term_hit_total: `289`
- long_term_hit_total: `0`
- profile_hit_total: `0`

## m2_profile_accuracy

### Micro
- risk_level_acc: `0.041667`
- horizon_acc: `0.000000`
- liquidity_acc: `0.208333`
- constraints_f1: `0.050000`
- preferences_f1: `0.539484`
- profile_score: `0.167897`

### Macro
- risk_level_acc: `0.041667`
- horizon_acc: `0.000000`
- liquidity_acc: `0.208333`
- constraints_f1: `0.050000`
- preferences_f1: `0.539484`
- profile_score: `0.167897`

### Counts
- eligible_count: `24`
- skipped_count: `0`
- failed_count: `0`

## m3_risk_coverage

### Micro
- risk_coverage: `0.509722`
- strict_risk_coverage_rate: `0.149351`

### Macro
- risk_coverage: `0.499600`
- strict_risk_coverage_rate: `0.159715`

### Counts
- eligible_count: `308`
- skipped_count: `8`
- failed_count: `0`
- risk_required_total: `720`
- risk_hit_total: `367`

## m4_compliance

### Micro
- compliance_label_acc: `0.993671`
- severe_violation_rate: `0.006329`
- forbidden_hit_rate: `0.006329`

### Macro
- compliance_label_acc: `0.992361`
- severe_violation_rate: `0.007639`
- forbidden_hit_rate: `0.007639`

### Counts
- eligible_count: `316`
- skipped_count: `0`
- failed_count: `0`
- severe_count: `2`

## m5_explainability

### Micro
- rubric_hit_rate: `0.893436`
- judge_score_mean: `4.546234`

### Macro
- rubric_hit_rate: `0.886014`
- judge_score_mean: `4.518243`

### Counts
- eligible_count: `316`
- skipped_count: `0`
- failed_count: `0`
- rubric_required_total: `1173`
- rubric_hit_total: `1048`
- judge_scored_turns: `316`
