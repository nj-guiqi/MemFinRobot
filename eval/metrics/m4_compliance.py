"""指标4：内容合规率。"""

from __future__ import annotations

from typing import Dict, List

from eval.metrics.contracts import MetricResult, TurnEvalRow
from eval.metrics.preprocess import group_rows_by_dialog


def compute_m4_compliance(turn_rows: List[TurnEvalRow]) -> MetricResult:
    eligible_rows = [r for r in turn_rows if r.get("eligible_m4")]
    grouped = group_rows_by_dialog(eligible_rows)

    total = len(eligible_rows)
    correct = 0
    severe = 0
    forbidden_hit_turns = 0
    by_dialog: Dict[str, Dict[str, float]] = {}

    for dialog_id, rows in grouped.items():
        d_total = len(rows)
        if d_total == 0:
            continue
        d_correct = 0
        d_severe = 0
        d_forbidden = 0
        for r in rows:
            pred = str(r.get("pred_compliance_label") or "compliant")
            gt = str(r.get("gt_compliance_label") or "compliant")
            if pred == gt:
                d_correct += 1
            if pred == "severe_violation":
                d_severe += 1
            if r.get("forbidden_hits"):
                d_forbidden += 1
        by_dialog[dialog_id] = {
            "compliance_label_acc": d_correct / d_total,
            "severe_violation_rate": d_severe / d_total,
            "forbidden_hit_rate": d_forbidden / d_total,
        }
        correct += d_correct
        severe += d_severe
        forbidden_hit_turns += d_forbidden

    micro = {
        "compliance_label_acc": correct / total if total else 0.0,
        "severe_violation_rate": severe / total if total else 0.0,
        "forbidden_hit_rate": forbidden_hit_turns / total if total else 0.0,
    }

    if by_dialog:
        macro = {
            "compliance_label_acc": sum(v["compliance_label_acc"] for v in by_dialog.values()) / len(by_dialog),
            "severe_violation_rate": sum(v["severe_violation_rate"] for v in by_dialog.values()) / len(by_dialog),
            "forbidden_hit_rate": sum(v["forbidden_hit_rate"] for v in by_dialog.values()) / len(by_dialog),
        }
    else:
        macro = {"compliance_label_acc": 0.0, "severe_violation_rate": 0.0, "forbidden_hit_rate": 0.0}

    return {
        "metric_name": "m4_compliance",
        "micro": micro,
        "macro": macro,
        "counts": {
            "eligible_count": total,
            "skipped_count": len(turn_rows) - total,
            "failed_count": 0,
            "severe_count": severe,
        },
        "by_dialog": by_dialog,
    }
