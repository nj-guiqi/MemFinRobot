"""指标5：决策辅助解释度。"""

from __future__ import annotations

from typing import Dict, List

from eval.metrics.contracts import MetricResult, TurnEvalRow
from eval.metrics.preprocess import group_rows_by_dialog


def compute_m5_explainability(turn_rows: List[TurnEvalRow]) -> MetricResult:
    eligible_rows = [r for r in turn_rows if r.get("eligible_m5")]
    grouped = group_rows_by_dialog(eligible_rows)

    req_total = 0
    hit_total = 0
    score_values: List[float] = []
    by_dialog: Dict[str, Dict[str, float]] = {}

    for dialog_id, rows in grouped.items():
        d_req = 0
        d_hit = 0
        d_scores: List[float] = []
        for r in rows:
            req = len(r.get("rubric_required") or [])
            hit = len(r.get("rubric_hit_items") or [])
            if req == 0:
                continue
            d_req += req
            d_hit += min(hit, req)
            score = r.get("judge_score_1_5")
            if score is not None:
                d_scores.append(float(score))
                score_values.append(float(score))
        if d_req > 0:
            by_dialog[dialog_id] = {
                "rubric_hit_rate": d_hit / d_req,
                "judge_score_mean": sum(d_scores) / len(d_scores) if d_scores else 0.0,
            }
            req_total += d_req
            hit_total += d_hit

    micro = {
        "rubric_hit_rate": hit_total / req_total if req_total else 0.0,
        "judge_score_mean": sum(score_values) / len(score_values) if score_values else 0.0,
    }

    if by_dialog:
        macro = {
            "rubric_hit_rate": sum(v["rubric_hit_rate"] for v in by_dialog.values()) / len(by_dialog),
            "judge_score_mean": sum(v["judge_score_mean"] for v in by_dialog.values()) / len(by_dialog),
        }
    else:
        macro = {"rubric_hit_rate": 0.0, "judge_score_mean": 0.0}

    return {
        "metric_name": "m5_explainability",
        "micro": micro,
        "macro": macro,
        "counts": {
            "eligible_count": len(eligible_rows),
            "skipped_count": len(turn_rows) - len(eligible_rows),
            "failed_count": 0,
            "rubric_required_total": req_total,
            "rubric_hit_total": hit_total,
            "judge_scored_turns": len(score_values),
        },
        "by_dialog": by_dialog,
    }
