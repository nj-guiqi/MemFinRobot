"""指标1：上下文关联度 / 连续性。"""

from __future__ import annotations

from typing import Dict, List

from eval.metrics.contracts import MetricResult, TurnEvalRow
from eval.metrics.preprocess import group_rows_by_dialog


def compute_m1_context_continuity(turn_rows: List[TurnEvalRow]) -> MetricResult:
    eligible_rows = [r for r in turn_rows if r.get("eligible_m1")]
    grouped = group_rows_by_dialog(eligible_rows)

    total_required = 0
    total_hits = 0
    strict_hits = 0
    contra_total = 0
    source_totals = {"short_term": 0, "long_term": 0, "profile": 0}

    by_dialog: Dict[str, Dict[str, float]] = {}

    for dialog_id, rows in grouped.items():
        d_required = 0
        d_hits = 0
        d_strict = 0
        d_contra = 0
        for r in rows:
            flags = list(r.get("key_hit_flags") or [])
            required = len(flags)
            hits = sum(flags)
            if required == 0:
                continue
            d_required += required
            d_hits += hits
            d_strict += 1 if hits == required else 0
            d_contra += int(r.get("constraint_contradiction") or 0)
            src = r.get("m1_source_hits") or {}
            for k in source_totals:
                source_totals[k] += int(src.get(k) or 0)

        if d_required > 0:
            by_dialog[dialog_id] = {
                "key_coverage": d_hits / d_required,
                "strict_key_hit_rate": d_strict / max(len(rows), 1),
                "contradiction_rate": d_contra / max(len(rows), 1),
            }
            total_required += d_required
            total_hits += d_hits
            strict_hits += d_strict
            contra_total += d_contra

    eligible_turns = len(eligible_rows)
    micro = {
        "key_coverage": total_hits / total_required if total_required else 0.0,
        "strict_key_hit_rate": strict_hits / eligible_turns if eligible_turns else 0.0,
        "contradiction_rate": contra_total / eligible_turns if eligible_turns else 0.0,
        "short_term_hit_rate": source_totals["short_term"] / total_required if total_required else 0.0,
        "long_term_hit_rate": source_totals["long_term"] / total_required if total_required else 0.0,
        "profile_hit_rate": source_totals["profile"] / total_required if total_required else 0.0,
    }

    if by_dialog:
        macro = {
            "key_coverage": sum(v["key_coverage"] for v in by_dialog.values()) / len(by_dialog),
            "strict_key_hit_rate": sum(v["strict_key_hit_rate"] for v in by_dialog.values()) / len(by_dialog),
            "contradiction_rate": sum(v["contradiction_rate"] for v in by_dialog.values()) / len(by_dialog),
        }
    else:
        macro = {"key_coverage": 0.0, "strict_key_hit_rate": 0.0, "contradiction_rate": 0.0}

    return {
        "metric_name": "m1_context_continuity",
        "micro": micro,
        "macro": macro,
        "counts": {
            "eligible_count": eligible_turns,
            "skipped_count": len(turn_rows) - eligible_turns,
            "failed_count": 0,
            "required_key_total": total_required,
            "required_key_hit_total": total_hits,
            "short_term_hit_total": source_totals["short_term"],
            "long_term_hit_total": source_totals["long_term"],
            "profile_hit_total": source_totals["profile"],
        },
        "by_dialog": by_dialog,
    }
