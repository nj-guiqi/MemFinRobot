"""指标3：风险提示覆盖率。"""

from __future__ import annotations

from typing import Dict, List

from eval.metrics.contracts import MetricResult, TurnEvalRow
from eval.metrics.preprocess import group_rows_by_dialog


def compute_m3_risk_coverage(turn_rows: List[TurnEvalRow]) -> MetricResult:
    eligible_rows = [r for r in turn_rows if r.get("eligible_m3")]
    grouped = group_rows_by_dialog(eligible_rows)

    req_total = 0
    hit_total = 0
    strict_total = 0
    by_dialog: Dict[str, Dict[str, float]] = {}

    for dialog_id, rows in grouped.items():
        d_req = 0
        d_hit = 0
        d_strict = 0
        for r in rows:
            req = len(r.get("risk_required_tags") or [])
            hit = int(r.get("risk_tag_hits") or 0)
            if req == 0:
                continue
            d_req += req
            d_hit += min(hit, req)
            d_strict += 1 if hit >= req else 0
        if d_req > 0:
            by_dialog[dialog_id] = {
                "risk_coverage": d_hit / d_req,
                "strict_risk_coverage_rate": d_strict / max(len(rows), 1),
            }
            req_total += d_req
            hit_total += d_hit
            strict_total += d_strict

    eligible_turns = len(eligible_rows)
    micro = {
        "risk_coverage": hit_total / req_total if req_total else 0.0,
        "strict_risk_coverage_rate": strict_total / eligible_turns if eligible_turns else 0.0,
    }

    if by_dialog:
        macro = {
            "risk_coverage": sum(v["risk_coverage"] for v in by_dialog.values()) / len(by_dialog),
            "strict_risk_coverage_rate": sum(v["strict_risk_coverage_rate"] for v in by_dialog.values()) / len(by_dialog),
        }
    else:
        macro = {"risk_coverage": 0.0, "strict_risk_coverage_rate": 0.0}

    return {
        "metric_name": "m3_risk_coverage",
        "micro": micro,
        "macro": macro,
        "counts": {
            "eligible_count": eligible_turns,
            "skipped_count": len(turn_rows) - eligible_turns,
            "failed_count": 0,
            "risk_required_total": req_total,
            "risk_hit_total": hit_total,
        },
        "by_dialog": by_dialog,
    }
