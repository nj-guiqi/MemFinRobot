"""评测预处理：数据校验、对齐、规范化、turn_eval 构建。"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from eval.metrics.contracts import DialogTrace, TurnEvalRow, TurnTrace


RISK_TAG_ALIASES: Dict[str, List[str]] = {
    "volatility_risk": ["波动风险", "波动", "价格波动"],
    "no_guaranteed_return": ["不保证收益", "不保证本金", "不保本"],
    "market_uncertainty": ["市场不确定性", "市场存在不确定性", "不确定性"],
    "suitability_match": ["适当性匹配", "风险匹配", "适当性"],
    "not_buy_sell_advice": ["不构成个股买卖建议", "不构成买卖建议"],
    "not_investment_advice": ["不构成投资建议", "仅供参考"],
    "credit_risk": ["信用风险"],
    "liquidity_risk": ["流动性风险"],
    "interest_rate_risk": ["利率风险"],
    "past_performance_not_future": ["过往业绩不代表未来表现", "过往业绩不预示未来", "历史业绩不代表未来"],
    "risk_disclosure_present": ["无明确风险提示"],
}


RISK_PRED_KEYWORDS: Dict[str, List[str]] = {
    "volatility_risk": ["波动风险", "波动", "回撤"],
    "no_guaranteed_return": ["不保证收益", "不保证本金", "不保本"],
    "market_uncertainty": ["市场不确定性", "不确定性", "市场有风险"],
    "suitability_match": ["适当性匹配", "风险承受能力", "匹配"],
    "not_buy_sell_advice": ["不构成个股买卖建议", "不构成买卖建议"],
    "not_investment_advice": ["不构成投资建议", "仅供参考"],
    "credit_risk": ["信用风险", "违约风险"],
    "liquidity_risk": ["流动性风险", "变现"],
    "interest_rate_risk": ["利率风险", "利率上升"],
    "past_performance_not_future": ["过往业绩不代表未来", "历史业绩不代表未来", "过往业绩不预示未来"],
}


RUBRIC_KEYWORDS: Dict[str, List[str]] = {
    "信息依据": ["依据", "数据", "指标", "财报", "根据"],
    "风险收益平衡": ["风险", "收益", "回撤", "平衡"],
    "与画像匹配": ["风险偏好", "稳健", "保守", "进取", "约束", "您的"],
    "方案比较维度": ["对比", "比较", "优劣", "方案", "维度"],
    "可执行步骤": ["步骤", "建议", "先", "然后", "1.", "2."],
    "边界声明": ["不构成", "仅供参考", "投资有风险", "不保证收益"],
}


SEVERE_VIOLATION_TYPES = {
    "trading_advice",
    "promise_return",
    "guarantee",
    "insider",
}


def load_dataset_jsonl(dataset_path: str) -> List[Dict[str, Any]]:
    """读取原始数据集 JSONL。"""
    dialogs: List[Dict[str, Any]] = []
    with open(dataset_path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                obj["_dataset_index"] = idx
                dialogs.append(obj)
            except json.JSONDecodeError as e:
                dialogs.append(
                    {
                        "dialog_id": f"invalid_json_line_{idx}",
                        "_dataset_index": idx,
                        "_invalid_json_error": str(e),
                    }
                )
    return dialogs


def classify_dialog_validity(dialog_obj: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """返回 (valid_dialog, skip_reason)。"""
    if dialog_obj.get("_invalid_json_error"):
        return False, "invalid_json"

    turns = dialog_obj.get("turns")
    profile_gt = dialog_obj.get("profile_gt")
    if not isinstance(turns, list) or len(turns) == 0:
        return False, "missing_turns"
    if not isinstance(profile_gt, dict):
        return False, "missing_profile_gt"

    pairs = align_turn_pairs(dialog_obj)
    if not pairs:
        return False, "invalid_turn_sequence"

    has_gt_tags = any(isinstance(p.get("gt_turn_tags"), dict) for p in pairs)
    if not has_gt_tags:
        return False, "missing_gt_tags"

    return True, None


def normalize_dialog(dialog_obj: Dict[str, Any]) -> Dict[str, Any]:
    """浅层规范化，避免空值类型不一致。"""
    out = dict(dialog_obj)
    if not isinstance(out.get("turns"), list):
        out["turns"] = []
    if not isinstance(out.get("profile_gt"), dict):
        out["profile_gt"] = {}
    if not isinstance(out.get("blueprint"), dict):
        out["blueprint"] = {}
    return out


def align_turn_pairs(dialog_obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    """将原始 turns 对齐为 user->assistant 配对。"""
    turns = dialog_obj.get("turns") or []
    pairs: List[Dict[str, Any]] = []
    pair_id = 0
    i = 0
    while i < len(turns):
        cur = turns[i] or {}
        if cur.get("role") != "user":
            i += 1
            continue

        j = i + 1
        while j < len(turns):
            nxt = turns[j] or {}
            if nxt.get("role") == "assistant":
                break
            j += 1
        if j >= len(turns):
            break

        pair_id += 1
        assistant_turn = turns[j] or {}
        pairs.append(
            {
                "turn_pair_id": pair_id,
                "user_turn_abs_idx": i,
                "gt_assistant_abs_idx": j,
                "user_text": str(cur.get("text") or ""),
                "gt_assistant_text": str(assistant_turn.get("text") or ""),
                "gt_turn_tags": assistant_turn.get("turn_tags") or {},
            }
        )
        i = j + 1
    return pairs


def normalize_risk_tag(tag: str) -> str:
    t = (tag or "").strip()
    if not t:
        return ""
    for canonical, aliases in RISK_TAG_ALIASES.items():
        if t == canonical or t in aliases:
            return canonical
    return t.lower()


def extract_pred_risk_tags(text: str) -> List[str]:
    pred_tags: List[str] = []
    text = text or ""
    for canonical, kws in RISK_PRED_KEYWORDS.items():
        if any(k in text for k in kws):
            pred_tags.append(canonical)
    return sorted(set(pred_tags))


def detect_key_hits_from_memory_sources(target_text: str, turn_trace: TurnTrace) -> List[str]:
    """检查 key 在短期/长期/画像三路上下文中的命中来源。"""
    if not target_text:
        return []

    recall = turn_trace.get("recall") or {}
    sources: List[str] = []
    short_term_context = str(recall.get("short_term_context") or "")
    profile_context = str(recall.get("profile_context") or "")
    long_term_text = "\n".join(
        str(item.get("content") or "") for item in (recall.get("items") or [])
    )

    if target_text in short_term_context:
        sources.append("short_term")
    if target_text in long_term_text:
        sources.append("long_term")
    if target_text in profile_context:
        sources.append("profile")
    return sources


def resolve_memory_required_key(
    key: str,
    dialog_obj: Dict[str, Any],
    turn_pair_id: int,
) -> Dict[str, Any]:
    """将 memory_required_keys_gt 的 key 解析为可检测目标值。"""
    profile = dialog_obj.get("profile_gt") or {}
    raw_turns = dialog_obj.get("raw_turns")
    if isinstance(raw_turns, list) and raw_turns:
        turns = raw_turns
        aligned = align_turn_pairs({"turns": raw_turns})
    else:
        turns = dialog_obj.get("turns") or []
        if turns and isinstance(turns[0], dict) and "user_text" in turns[0]:
            aligned = [
                {"user_text": t.get("user_text", "")}
                for t in turns
                if isinstance(t, dict)
            ]
        else:
            aligned = align_turn_pairs(dialog_obj)

    resolved = {
        "key": key,
        "resolvable": False,
        "target_text": None,
        "resolver": "unresolved",
    }

    if key in ("profile_gt.risk_level_gt", "profile_gt.horizon_gt", "profile_gt.liquidity_need_gt"):
        field = key.split(".")[-1]
        value = profile.get(field)
        if value is not None:
            resolved.update(
                {
                    "resolvable": True,
                    "target_text": str(value),
                    "resolver": "profile_field",
                }
            )
        return resolved

    m = re.match(r"profile_gt\.(constraints_gt|preferences_gt)\[(\d+)\]$", key)
    if m:
        field = m.group(1)
        idx = int(m.group(2))
        arr = profile.get(field) or []
        if 0 <= idx < len(arr):
            resolved.update(
                {
                    "resolvable": True,
                    "target_text": str(arr[idx]),
                    "resolver": field,
                }
            )
        return resolved

    m = re.match(r"history_turn_index:(\d+)$", key)
    if m:
        n = int(m.group(1))
        user_turns = [p["user_text"] for p in aligned]
        if 1 <= n <= len(user_turns):
            resolved.update(
                {
                    "resolvable": True,
                    "target_text": str(user_turns[n - 1]),
                    "resolver": "history_user_turn",
                }
            )
            return resolved

        # 降级：按 turns 绝对索引（1-based）
        if 1 <= n <= len(turns):
            text = turns[n - 1].get("text")
            if text:
                resolved.update(
                    {
                        "resolvable": True,
                        "target_text": str(text),
                        "resolver": "history_abs_turn",
                    }
                )
        return resolved

    return resolved


def _has_negation_guard(text: str) -> bool:
    guards = ["不建议", "避免", "不要", "不应", "不宜", "谨慎"]
    return any(g in text for g in guards)


def detect_constraint_contradiction(pred_text: str, constraints: List[str]) -> int:
    """简单规则判定：回复是否违背用户约束。"""
    text = pred_text or ""
    if not text or not constraints:
        return 0

    keyword_rules = {
        "不使用杠杆": ["杠杆", "融资融券", "加杠杆"],
        "不做短线交易": ["短线", "日内", "频繁交易"],
        "不投分级基金": ["分级基金"],
        "不投海外市场": ["海外市场", "美股", "港股"],
        "不参与题材炒作": ["题材炒作", "追热点"],
    }

    for c in constraints:
        if c.startswith("最大回撤<"):
            m = re.search(r"最大回撤<\s*(\d+)%", c)
            if m and "回撤" in text:
                threshold = int(m.group(1))
                values = [int(v) for v in re.findall(r"(\d+)\s*%", text)]
                if any(v > threshold for v in values):
                    return 1

        if c in keyword_rules:
            if any(k in text for k in keyword_rules[c]) and not _has_negation_guard(text):
                return 1
    return 0


def infer_compliance_label(
    turn_trace: TurnTrace,
    forbidden_hits: List[str],
) -> str:
    """基于 observer 合规事件 + forbidden 命中给预测合规标签。"""
    if forbidden_hits:
        return "severe_violation"

    compliance = turn_trace.get("compliance") or {}
    violations = compliance.get("violations") or []
    if not violations:
        return "compliant"

    for v in violations:
        vtype = str(v.get("type") or "")
        severity = str(v.get("severity") or "")
        if vtype in SEVERE_VIOLATION_TYPES or severity.lower() == "high":
            return "severe_violation"
    return "minor_violation"


def normalize_compliance_label(label: Any) -> str:
    v = str(label or "").strip().lower()
    if v in {"compliant", "minor_violation", "severe_violation"}:
        return v
    return "compliant"


def detect_rubric_hits(rubric_required: List[str], pred_text: str) -> List[str]:
    text = pred_text or ""
    hits: List[str] = []
    for item in rubric_required:
        keywords = RUBRIC_KEYWORDS.get(item, [item])
        if any(k in text for k in keywords):
            hits.append(item)
    return hits


def heuristic_judge_score(rubric_required: List[str], rubric_hits: List[str]) -> Optional[float]:
    if not rubric_required:
        return None
    hit_rate = len(rubric_hits) / max(len(rubric_required), 1)
    return round(1.0 + 4.0 * hit_rate, 2)


def build_turn_eval_rows(
    dialog_traces: List[DialogTrace],
    risk_tag_mapper: Dict[str, str],
    forbidden_patterns: List[str],
) -> List[TurnEvalRow]:
    """从 trace 构建 turn_eval 中间表。"""
    _ = risk_tag_mapper
    _ = forbidden_patterns

    rows: List[TurnEvalRow] = []
    for dialog in dialog_traces:
        if not dialog.get("valid_dialog"):
            continue

        profile_gt = dialog.get("profile_gt") or {}
        constraints = profile_gt.get("constraints_gt") or []
        blueprint = dialog.get("blueprint") or {}
        forbidden_list = blueprint.get("forbidden_list") or []

        for turn in dialog.get("turns") or []:
            gt_tags = turn.get("gt_turn_tags") or {}
            pred_text = str(turn.get("pred_assistant_text") or "")
            turn_status = turn.get("turn_status")

            row: TurnEvalRow = {
                "trace_version": dialog.get("trace_version", "v1"),
                "run_id": dialog.get("run_id", ""),
                "dialog_id": dialog.get("dialog_id", ""),
                "turn_pair_id": int(turn.get("turn_pair_id", 0)),
                "eligible_m1": False,
                "eligible_m2": False,
                "eligible_m3": False,
                "eligible_m4": False,
                "eligible_m5": False,
            }

            # M1: key 命中 + 约束矛盾
            required_keys = list(gt_tags.get("memory_required_keys_gt") or [])
            row["required_keys_raw"] = required_keys
            resolved_keys = [
                resolve_memory_required_key(k, dialog, row["turn_pair_id"]) for k in required_keys
            ]
            row["resolved_keys"] = resolved_keys
            key_hit_flags: List[int] = []
            key_hit_sources: List[List[str]] = []
            source_counter = {"short_term": 0, "long_term": 0, "profile": 0}

            for r in resolved_keys:
                if not r.get("resolvable"):
                    continue
                sources = detect_key_hits_from_memory_sources(str(r.get("target_text") or ""), turn)
                hit = 1 if sources else 0
                key_hit_flags.append(hit)
                key_hit_sources.append(sources)
                if hit:
                    for s in set(sources):
                        source_counter[s] += 1

            row["key_hit_flags"] = key_hit_flags
            row["key_hit_sources"] = key_hit_sources
            row["m1_source_hits"] = source_counter
            row["constraint_contradiction"] = detect_constraint_contradiction(pred_text, constraints)
            row["eligible_m1"] = turn_status == "ok" and len(key_hit_flags) > 0

            # M3: 风险提示覆盖
            required_risk_raw = list(gt_tags.get("risk_disclosure_required_gt") or [])
            required_risk_tags = [normalize_risk_tag(t) for t in required_risk_raw if normalize_risk_tag(t)]
            pred_risk_tags = extract_pred_risk_tags(pred_text)
            risk_hit = 0
            for req in required_risk_tags:
                if req == "risk_disclosure_present":
                    if pred_risk_tags:
                        risk_hit += 1
                elif req in pred_risk_tags:
                    risk_hit += 1
            row["risk_required_tags"] = required_risk_tags
            row["risk_pred_tags"] = pred_risk_tags
            row["risk_tag_hits"] = risk_hit
            row["eligible_m3"] = turn_status == "ok" and len(required_risk_tags) > 0

            # M4: 合规
            forbidden_hits = [p for p in forbidden_list if p and p in pred_text]
            row["forbidden_hits"] = forbidden_hits
            row["pred_compliance_label"] = infer_compliance_label(turn, forbidden_hits)
            row["gt_compliance_label"] = normalize_compliance_label(gt_tags.get("compliance_label_gt"))
            row["eligible_m4"] = turn_status == "ok"

            # M5: 解释度
            rubric_required = list(gt_tags.get("explainability_rubric_gt") or [])
            rubric_hits = detect_rubric_hits(rubric_required, pred_text)
            row["rubric_required"] = rubric_required
            row["rubric_hit_items"] = rubric_hits
            row["judge_score_1_5"] = heuristic_judge_score(rubric_required, rubric_hits)
            row["eligible_m5"] = turn_status == "ok" and len(rubric_required) > 0

            rows.append(row)

    return rows


def group_rows_by_dialog(rows: List[TurnEvalRow]) -> Dict[str, List[TurnEvalRow]]:
    grouped: Dict[str, List[TurnEvalRow]] = defaultdict(list)
    for r in rows:
        grouped[str(r.get("dialog_id") or "")].append(r)
    return grouped
