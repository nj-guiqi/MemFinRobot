# MemFinRobot Eval Report

- run_id: `20260224_085203`
- dataset: `eval/datasets/MemFinConv_24.jsonl`
- counters: total=24, valid=24, skipped=0, failed=0

## m1_context_continuity

### Micro
- key_coverage: `0.307018`
- strict_key_hit_rate: `0.128713`
- contradiction_rate: `0.501650`
- short_term_hit_rate: `0.295739`
- long_term_hit_rate: `0.066416`
- profile_hit_rate: `0.003759`

### Macro
- key_coverage: `0.295936`
- strict_key_hit_rate: `0.124224`
- contradiction_rate: `0.502387`

### Counts
- eligible_count: `303`
- skipped_count: `13`
- failed_count: `0`
- required_key_total: `798`
- required_key_hit_total: `245`
- short_term_hit_total: `236`
- long_term_hit_total: `53`
- profile_hit_total: `3`

## m2_profile_accuracy

### Micro
- risk_level_acc: `0.416667`
- horizon_acc: `0.291667`
- liquidity_acc: `0.250000`
- constraints_f1: `0.050000`
- preferences_f1: `0.132056`
- profile_score: `0.228078`

### Macro
- risk_level_acc: `0.416667`
- horizon_acc: `0.291667`
- liquidity_acc: `0.250000`
- constraints_f1: `0.050000`
- preferences_f1: `0.132056`
- profile_score: `0.228078`

### Counts
- eligible_count: `24`
- skipped_count: `0`
- failed_count: `0`

## m3_risk_coverage

### Micro
- risk_coverage: `0.836111`
- strict_risk_coverage_rate: `0.665584`

### Macro
- risk_coverage: `0.837813`
- strict_risk_coverage_rate: `0.667207`

### Counts
- eligible_count: `308`
- skipped_count: `8`
- failed_count: `0`
- risk_required_total: `720`
- risk_hit_total: `602`

## m4_compliance

### Micro
- compliance_label_acc: `0.352381`
- severe_violation_rate: `0.549206`
- forbidden_hit_rate: `0.006349`

### Macro
- compliance_label_acc: `0.367188`
- severe_violation_rate: `0.544042`
- forbidden_hit_rate: `0.006410`

### Counts
- eligible_count: `315`
- skipped_count: `1`
- failed_count: `0`
- severe_count: `173`

## m5_explainability

### Micro
- rubric_hit_rate: `0.958155`
- judge_score_mean: `4.837079`

### Macro
- rubric_hit_rate: `0.952700`
- judge_score_mean: `4.811510`

### Counts
- eligible_count: `315`
- skipped_count: `1`
- failed_count: `0`
- rubric_required_total: `1171`
- rubric_hit_total: `1122`
- judge_scored_turns: `315`
