# MemFinRobot Eval Report

- run_id: `20260222_071516`
- dataset: `eval/datasets/MemFinConv_24.jsonl`
- counters: total=24, valid=24, skipped=0, failed=0

## m1_context_continuity

### Micro
- key_coverage: `0.218519`
- strict_key_hit_rate: `0.074766`
- contradiction_rate: `0.233645`
- short_term_hit_rate: `0.218519`
- long_term_hit_rate: `0.000000`
- profile_hit_rate: `0.000000`

### Macro
- key_coverage: `0.195190`
- strict_key_hit_rate: `0.071406`
- contradiction_rate: `0.231360`

### Counts
- eligible_count: `107`
- skipped_count: `209`
- failed_count: `0`
- required_key_total: `270`
- required_key_hit_total: `59`
- short_term_hit_total: `59`
- long_term_hit_total: `0`
- profile_hit_total: `0`

## m2_profile_accuracy

### Micro
- risk_level_acc: `0.250000`
- horizon_acc: `0.041667`
- liquidity_acc: `0.041667`
- constraints_f1: `0.016667`
- preferences_f1: `0.198611`
- profile_score: `0.109722`

### Macro
- risk_level_acc: `0.250000`
- horizon_acc: `0.041667`
- liquidity_acc: `0.041667`
- constraints_f1: `0.016667`
- preferences_f1: `0.198611`
- profile_score: `0.109722`

### Counts
- eligible_count: `24`
- skipped_count: `0`
- failed_count: `0`

## m3_risk_coverage

### Micro
- risk_coverage: `0.436214`
- strict_risk_coverage_rate: `0.118182`

### Macro
- risk_coverage: `0.429422`
- strict_risk_coverage_rate: `0.143333`

### Counts
- eligible_count: `110`
- skipped_count: `206`
- failed_count: `0`
- risk_required_total: `243`
- risk_hit_total: `106`

## m4_compliance

### Micro
- compliance_label_acc: `0.983051`
- severe_violation_rate: `0.016949`
- forbidden_hit_rate: `0.016949`

### Macro
- compliance_label_acc: `0.982857`
- severe_violation_rate: `0.017143`
- forbidden_hit_rate: `0.017143`

### Counts
- eligible_count: `118`
- skipped_count: `198`
- failed_count: `0`
- severe_count: `2`

## m5_explainability

### Micro
- rubric_hit_rate: `0.792271`
- judge_score_mean: `4.131949`

### Macro
- rubric_hit_rate: `0.757537`
- judge_score_mean: `4.010087`

### Counts
- eligible_count: `118`
- skipped_count: `198`
- failed_count: `0`
- rubric_required_total: `414`
- rubric_hit_total: `328`
- judge_scored_turns: `118`
