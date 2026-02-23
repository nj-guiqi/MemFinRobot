# MemFinRobot Eval Report

- run_id: `20260221_085707`
- dataset: `eval/datasets/MemFinConv_24.jsonl`
- counters: total=24, valid=24, skipped=0, failed=0

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
- eligible_count: `0`
- skipped_count: `316`
- failed_count: `0`
- required_key_total: `0`
- required_key_hit_total: `0`
- short_term_hit_total: `0`
- long_term_hit_total: `0`
- profile_hit_total: `0`

## m2_profile_accuracy

### Micro
- risk_level_acc: `0.041667`
- horizon_acc: `0.000000`
- liquidity_acc: `0.208333`
- constraints_f1: `0.033333`
- preferences_f1: `0.529167`
- profile_score: `0.162500`

### Macro
- risk_level_acc: `0.041667`
- horizon_acc: `0.000000`
- liquidity_acc: `0.208333`
- constraints_f1: `0.033333`
- preferences_f1: `0.529167`
- profile_score: `0.162500`

### Counts
- eligible_count: `24`
- skipped_count: `0`
- failed_count: `0`

## m3_risk_coverage

### Micro
- risk_coverage: `0.536111`
- strict_risk_coverage_rate: `0.149351`

### Macro
- risk_coverage: `0.525769`
- strict_risk_coverage_rate: `0.151034`

### Counts
- eligible_count: `308`
- skipped_count: `8`
- failed_count: `0`
- risk_required_total: `720`
- risk_hit_total: `386`

## m4_compliance

### Micro
- compliance_label_acc: `0.977848`
- severe_violation_rate: `0.022152`
- forbidden_hit_rate: `0.022152`

### Macro
- compliance_label_acc: `0.974966`
- severe_violation_rate: `0.025034`
- forbidden_hit_rate: `0.025034`

### Counts
- eligible_count: `316`
- skipped_count: `0`
- failed_count: `0`
- severe_count: `7`

## m5_explainability

### Micro
- rubric_hit_rate: `0.870418`
- judge_score_mean: `4.468323`

### Macro
- rubric_hit_rate: `0.870447`
- judge_score_mean: `4.464826`

### Counts
- eligible_count: `316`
- skipped_count: `0`
- failed_count: `0`
- rubric_required_total: `1173`
- rubric_hit_total: `1021`
- judge_scored_turns: `316`
