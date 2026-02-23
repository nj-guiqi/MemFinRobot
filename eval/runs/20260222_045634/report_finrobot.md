# MemFinRobot Eval Report

- run_id: `20260222_045634`
- dataset: `eval/datasets/MemFinConv_24.jsonl`
- counters: total=24, valid=24, skipped=0, failed=0

## m1_context_continuity

### Micro
- key_coverage: `0.141604`
- strict_key_hit_rate: `0.036304`
- contradiction_rate: `0.009901`
- short_term_hit_rate: `0.141604`
- long_term_hit_rate: `0.000000`
- profile_hit_rate: `0.000000`

### Macro
- key_coverage: `0.144963`
- strict_key_hit_rate: `0.041827`
- contradiction_rate: `0.009882`

### Counts
- eligible_count: `303`
- skipped_count: `13`
- failed_count: `0`
- required_key_total: `798`
- required_key_hit_total: `113`
- short_term_hit_total: `113`
- long_term_hit_total: `0`
- profile_hit_total: `0`

## m2_profile_accuracy

### Micro
- risk_level_acc: `0.458333`
- horizon_acc: `0.416667`
- liquidity_acc: `0.041667`
- constraints_f1: `0.066667`
- preferences_f1: `0.231944`
- profile_score: `0.243056`

### Macro
- risk_level_acc: `0.458333`
- horizon_acc: `0.416667`
- liquidity_acc: `0.041667`
- constraints_f1: `0.066667`
- preferences_f1: `0.231944`
- profile_score: `0.243056`

### Counts
- eligible_count: `24`
- skipped_count: `0`
- failed_count: `0`

## m3_risk_coverage

### Micro
- risk_coverage: `0.072222`
- strict_risk_coverage_rate: `0.000000`

### Macro
- risk_coverage: `0.071669`
- strict_risk_coverage_rate: `0.000000`

### Counts
- eligible_count: `308`
- skipped_count: `8`
- failed_count: `0`
- risk_required_total: `720`
- risk_hit_total: `52`

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
- eligible_count: `316`
- skipped_count: `0`
- failed_count: `0`
- severe_count: `0`

## m5_explainability

### Micro
- rubric_hit_rate: `0.144928`
- judge_score_mean: `1.569494`

### Macro
- rubric_hit_rate: `0.151277`
- judge_score_mean: `1.592980`

### Counts
- eligible_count: `316`
- skipped_count: `0`
- failed_count: `0`
- rubric_required_total: `1173`
- rubric_hit_total: `170`
- judge_scored_turns: `316`
