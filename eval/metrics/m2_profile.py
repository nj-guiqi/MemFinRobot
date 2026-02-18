"""指标2：画像提取准确率（以 dialog 级为主）。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from eval.metrics.contracts import DialogTrace, MetricResult


RISK_MAP = {
    "保守": "low",
    "稳健": "medium",
    "进取": "high",
    "low": "low",
    "medium": "medium",
    "high": "high",
}

HORIZON_MAP = {
    "<=6月": "short",
    "6-24月": "medium",
    "2年以上": "long",
    "短期": "short",
    "中期": "medium",
    "长期": "long",
    "short": "short",
    "medium": "medium",
    "long": "long",
}

LIQUIDITY_MAP = {
    "高": "high",
    "中": "medium",
    "低": "low",
    "high": "high",
    "medium": "medium",
    "low": "low",
}


def _normalize_value(v: Any, mapping: Dict[str, str]) -> str:
    return mapping.get(str(v or "").strip(), "unknown")


def _set_f1(pred: Set[str], gt: Set[str]) -> float:
    if not gt and not pred:
        return 1.0
    if not gt:
        return 0.0
    inter = len(pred & gt)
    p = inter / len(pred) if pred else 0.0
    r = inter / len(gt) if gt else 0.0
    if p + r == 0:
        return 0.0
    return 2 * p * r / (p + r)


def _find_last_profile_snapshot(dialog: DialogTrace) -> Optional[Dict[str, Any]]:
    snapshot = None
    for turn in dialog.get("turns") or []:
        s = turn.get("profile_snapshot")
        if isinstance(s, dict):
            snapshot = s
    return snapshot


def _infer_profile_from_text(text: str) -> Tuple[str, str, str]:
    risk = "unknown"
    horizon = "unknown"
    liquidity = "unknown"

    if any(k in text for k in ["保守", "低风险"]):
        risk = "low"
    elif any(k in text for k in ["稳健", "中风险"]):
        risk = "medium"
    elif any(k in text for k in ["进取", "高风险", "激进"]):
        risk = "high"

    if any(k in text for k in ["6月", "短期"]):
        horizon = "short"
    elif any(k in text for k in ["6-24月", "1年", "2年内"]):
        horizon = "medium"
    elif any(k in text for k in ["2年以上", "长期"]):
        horizon = "long"

    if any(k in text for k in ["高流动性", "随时需要用钱", "保留现金"]):
        liquidity = "high"
    elif any(k in text for k in ["流动性中等"]):
        liquidity = "medium"
    elif any(k in text for k in ["低流动性"]):
        liquidity = "low"

    return risk, horizon, liquidity


def compute_m2_profile_accuracy(
    dialog_traces: List[DialogTrace],
    dialog_objs: Dict[str, Dict[str, Any]],
) -> MetricResult:
    _ = dialog_objs
    by_dialog: Dict[str, Dict[str, float]] = {}
    eligible_dialogs = 0

    risk_correct = 0
    horizon_correct = 0
    liquidity_correct = 0
    constraints_f1_total = 0.0
    preferences_f1_total = 0.0

    for dialog in dialog_traces:
        if not dialog.get("valid_dialog"):
            continue
        profile_gt = dialog.get("profile_gt") or {}
        if not profile_gt:
            continue
        eligible_dialogs += 1

        gt_risk = _normalize_value(profile_gt.get("risk_level_gt"), RISK_MAP)
        gt_horizon = _normalize_value(profile_gt.get("horizon_gt"), HORIZON_MAP)
        gt_liquidity = _normalize_value(profile_gt.get("liquidity_need_gt"), LIQUIDITY_MAP)
        gt_constraints = set(profile_gt.get("constraints_gt") or [])
        gt_preferences = set(profile_gt.get("preferences_gt") or [])

        snapshot = _find_last_profile_snapshot(dialog)
        pred_risk = "unknown"
        pred_horizon = "unknown"
        pred_liquidity = "unknown"
        pred_constraints: Set[str] = set()
        pred_preferences: Set[str] = set()

        if snapshot:
            pred_risk = _normalize_value(snapshot.get("risk_level"), RISK_MAP)
            pred_horizon = _normalize_value(snapshot.get("investment_horizon"), HORIZON_MAP)
            pred_liquidity = _normalize_value(snapshot.get("liquidity_need"), LIQUIDITY_MAP)
            pred_preferences |= set(snapshot.get("preferred_topics") or [])
            pred_constraints |= set(snapshot.get("forbidden_assets") or [])

        all_pred_text = "\n".join(str(t.get("pred_assistant_text") or "") for t in (dialog.get("turns") or []))
        if pred_risk == "unknown" or pred_horizon == "unknown" or pred_liquidity == "unknown":
            txt_risk, txt_horizon, txt_liquidity = _infer_profile_from_text(all_pred_text)
            if pred_risk == "unknown":
                pred_risk = txt_risk
            if pred_horizon == "unknown":
                pred_horizon = txt_horizon
            if pred_liquidity == "unknown":
                pred_liquidity = txt_liquidity

        # 为了简化可解释性：只统计“是否提及了 GT 约束/偏好”
        pred_constraints |= {c for c in gt_constraints if c in all_pred_text}
        pred_preferences |= {p for p in gt_preferences if p in all_pred_text}

        risk_acc = 1.0 if pred_risk == gt_risk and gt_risk != "unknown" else 0.0
        horizon_acc = 1.0 if pred_horizon == gt_horizon and gt_horizon != "unknown" else 0.0
        liquidity_acc = 1.0 if pred_liquidity == gt_liquidity and gt_liquidity != "unknown" else 0.0
        c_f1 = _set_f1(pred_constraints, gt_constraints)
        p_f1 = _set_f1(pred_preferences, gt_preferences)

        risk_correct += int(risk_acc)
        horizon_correct += int(horizon_acc)
        liquidity_correct += int(liquidity_acc)
        constraints_f1_total += c_f1
        preferences_f1_total += p_f1

        by_dialog[str(dialog.get("dialog_id"))] = {
            "risk_level_acc": risk_acc,
            "horizon_acc": horizon_acc,
            "liquidity_acc": liquidity_acc,
            "constraints_f1": c_f1,
            "preferences_f1": p_f1,
            "profile_score": (risk_acc + horizon_acc + liquidity_acc + c_f1 + p_f1) / 5.0,
        }

    if eligible_dialogs > 0:
        micro = {
            "risk_level_acc": risk_correct / eligible_dialogs,
            "horizon_acc": horizon_correct / eligible_dialogs,
            "liquidity_acc": liquidity_correct / eligible_dialogs,
            "constraints_f1": constraints_f1_total / eligible_dialogs,
            "preferences_f1": preferences_f1_total / eligible_dialogs,
            "profile_score": (
                (risk_correct / eligible_dialogs)
                + (horizon_correct / eligible_dialogs)
                + (liquidity_correct / eligible_dialogs)
                + (constraints_f1_total / eligible_dialogs)
                + (preferences_f1_total / eligible_dialogs)
            )
            / 5.0,
        }
    else:
        micro = {
            "risk_level_acc": 0.0,
            "horizon_acc": 0.0,
            "liquidity_acc": 0.0,
            "constraints_f1": 0.0,
            "preferences_f1": 0.0,
            "profile_score": 0.0,
        }

    # M2 是 dialog 粒度，macro 与 micro 同口径
    macro = dict(micro)

    return {
        "metric_name": "m2_profile_accuracy",
        "micro": micro,
        "macro": macro,
        "counts": {
            "eligible_count": eligible_dialogs,
            "skipped_count": len(dialog_traces) - eligible_dialogs,
            "failed_count": len([d for d in dialog_traces if not d.get("valid_dialog")]),
        },
        "by_dialog": by_dialog,
    }
