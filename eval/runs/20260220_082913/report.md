# MemFinRobot Eval Report

- run_id: `20260220_082913`
- dataset: `D:\project\MemFinRobot\eval\datasets\MemFinConv_24.jsonl`
- counters: total=24, valid=24, skipped=0, failed=0

## m1_context_continuity

### Micro
- key_coverage: `0.268562`
- strict_key_hit_rate: `0.133891`
- contradiction_rate: `0.481172`
- short_term_hit_rate: `0.236967`
- long_term_hit_rate: `0.078989`
- profile_hit_rate: `0.017378`

### Macro
- key_coverage: `0.232147`
- strict_key_hit_rate: `0.116815`
- contradiction_rate: `0.504439`

### Counts
- eligible_count: `239`
- skipped_count: `77`
- failed_count: `0`
- required_key_total: `633`
- required_key_hit_total: `170`
- short_term_hit_total: `150`
- long_term_hit_total: `50`
- profile_hit_total: `11`

## m2_profile_accuracy

### Micro
- risk_level_acc: `0.416667`
- horizon_acc: `0.125000`
- liquidity_acc: `0.166667`
- constraints_f1: `0.044444`
- preferences_f1: `0.173911`
- profile_score: `0.185338`

### Macro
- risk_level_acc: `0.416667`
- horizon_acc: `0.125000`
- liquidity_acc: `0.166667`
- constraints_f1: `0.044444`
- preferences_f1: `0.173911`
- profile_score: `0.185338`

### Counts
- eligible_count: `24`
- skipped_count: `0`
- failed_count: `0`

## m3_risk_coverage

### Micro
- risk_coverage: `0.478032`
- strict_risk_coverage_rate: `0.127049`

### Macro
- risk_coverage: `0.486903`
- strict_risk_coverage_rate: `0.136698`

### Counts
- eligible_count: `244`
- skipped_count: `72`
- failed_count: `0`
- risk_required_total: `569`
- risk_hit_total: `272`

## m4_compliance

### Micro
- compliance_label_acc: `0.545817`
- severe_violation_rate: `0.402390`
- forbidden_hit_rate: `0.007968`

### Macro
- compliance_label_acc: `0.601605`
- severe_violation_rate: `0.347057`
- forbidden_hit_rate: `0.007639`

### Counts
- eligible_count: `251`
- skipped_count: `65`
- failed_count: `0`
- severe_count: `101`

## m5_explainability

### Micro
- rubric_hit_rate: `0.920940`
- judge_score_mean: `4.676932`

### Macro
- rubric_hit_rate: `0.926510`
- judge_score_mean: `4.702601`

### Counts
- eligible_count: `251`
- skipped_count: `65`
- failed_count: `0`
- rubric_required_total: `936`
- rubric_hit_total: `862`
- judge_scored_turns: `251`
