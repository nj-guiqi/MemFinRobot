"""对话回放与 trace 生成。"""

from __future__ import annotations

import copy
import time
from threading import Lock
from typing import Any, Dict, List, Optional

from eval.metrics.contracts import DialogTrace, TurnStatus, TurnTrace
from eval.metrics.preprocess import align_turn_pairs, classify_dialog_validity, normalize_dialog


class EvalTurnObserver:
    """收集 agent 事件并按 turn_pair_id 聚合。"""

    def __init__(self) -> None:
        self._lock = Lock()
        self._turn_payload: Dict[int, Dict[str, Any]] = {}

    def on_event(self, event: str, payload: Dict[str, Any]) -> None:
        turn_id = int(payload.get("turn_pair_id") or 0)
        if turn_id <= 0:
            return

        with self._lock:
            bucket = self._turn_payload.setdefault(turn_id, {"tools": []})
            if event == "turn_start":
                bucket["query"] = payload.get("query", "")
            elif event == "recall_done":
                bucket["recall"] = {
                    "query": payload.get("query", ""),
                    "short_term_context": payload.get("short_term_context", ""),
                    "short_term_turns": payload.get("short_term_turns", []),
                    "profile_context": payload.get("profile_context", ""),
                    "packed_context": payload.get("packed_context", ""),
                    "token_count": payload.get("token_count", 0),
                    "items": [
                        {
                            "rank": idx + 1,
                            "item_id": it.get("id", ""),
                            "content": it.get("content", ""),
                            "score": it.get("score", 0.0),
                            "source": it.get("source", ""),
                            "turn_index": it.get("turn_index", 0),
                            "session_id": it.get("session_id", ""),
                        }
                        for idx, it in enumerate(payload.get("recalled_items") or [])
                    ],
                }
            elif event == "tool_called":
                bucket["tools"].append(
                    {
                        "tool_name": payload.get("tool_name", ""),
                        "args": payload.get("tool_args", {}),
                        "result_excerpt": payload.get("tool_result", ""),
                        "latency_ms": payload.get("latency_ms", 0.0),
                        "error": None,
                    }
                )
            elif event == "compliance_done":
                bucket["compliance"] = {
                    "needs_modification": payload.get("needs_modification", False),
                    "is_compliant": payload.get("is_compliant", True),
                    "violations": payload.get("violations", []),
                    "risk_disclaimer_added": payload.get("risk_disclaimer_added", False),
                    "suitability_warning": payload.get("suitability_warning"),
                }
            elif event == "profile_snapshot":
                bucket["profile_snapshot"] = payload.get("profile", {})
            elif event == "turn_end":
                bucket["turn_end"] = {
                    "latency_ms": payload.get("latency_ms", 0.0),
                    "final_content": payload.get("final_content", ""),
                }

    def get_turn_payload(self, turn_pair_id: int) -> Dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._turn_payload.get(turn_pair_id, {}))


def build_turn_trace(
    turn_pair: Dict[str, Any],
    pred_text: str,
    observer_payload: Dict[str, Any],
    latency_ms: float,
    turn_status: TurnStatus = "ok",
    error: Optional[str] = None,
) -> TurnTrace:
    return {
        "turn_pair_id": int(turn_pair["turn_pair_id"]),
        "user_turn_abs_idx": int(turn_pair["user_turn_abs_idx"]),
        "gt_assistant_abs_idx": int(turn_pair["gt_assistant_abs_idx"]),
        "user_text": str(turn_pair.get("user_text", "")),
        "gt_assistant_text": str(turn_pair.get("gt_assistant_text", "")),
        "gt_turn_tags": turn_pair.get("gt_turn_tags") or {},
        "pred_assistant_text": pred_text or "",
        "latency_ms": float(latency_ms),
        "turn_status": turn_status,
        "error": error,
        "recall": observer_payload.get("recall"),
        "tools": observer_payload.get("tools", []),
        "compliance": observer_payload.get("compliance"),
        "profile_snapshot": observer_payload.get("profile_snapshot"),
    }


def run_dialog_replay(
    dialog_obj: Dict[str, Any],
    run_id: str,
    dataset_index: int,
    agent_factory: Any,
    observer_factory: Any,
    timeout_sec: int = 120,
) -> DialogTrace:
    """单对话回放，产出 DialogTrace。"""
    _ = timeout_sec
    dialog_obj = normalize_dialog(dialog_obj)
    dialog_id = str(dialog_obj.get("dialog_id") or f"dialog_{dataset_index}")
    valid_dialog, skip_reason = classify_dialog_validity(dialog_obj)

    trace: DialogTrace = {
        "trace_version": "v1",
        "run_id": run_id,
        "dialog_id": dialog_id,
        "dataset_index": dataset_index,
        "scenario_type": dialog_obj.get("scenario_type"),
        "difficulty": dialog_obj.get("difficulty"),
        "dialog_status": "ok" if valid_dialog else "skipped",
        "valid_dialog": valid_dialog,
        "skip_reason": skip_reason,
        "session_id": f"eval_session_{dialog_id}",
        "user_id": f"eval_user_{dialog_id}",
        "turns": [],
        "dialog_error": None,
        "profile_gt": dialog_obj.get("profile_gt"),
        "blueprint": dialog_obj.get("blueprint"),
        "raw_turns": dialog_obj.get("turns"),
    }
    if not valid_dialog:
        return trace

    turn_pairs = align_turn_pairs(dialog_obj)
    observer = observer_factory() if observer_factory else EvalTurnObserver()

    try:
        agent = agent_factory(dialog_id=dialog_id, observer=observer)
    except Exception as e:
        trace["dialog_status"] = "failed"
        trace["dialog_error"] = f"create_agent_failed: {e}"
        return trace

    for pair in turn_pairs:
        turn_id = int(pair["turn_pair_id"])
        start_ts = time.perf_counter()
        pred_text = ""
        status: TurnStatus = "ok"
        error: Optional[str] = None
        try:
            pred_text = agent.handle_turn(
                user_message=pair["user_text"],
                session_id=trace["session_id"],
                user_id=trace["user_id"],
            )
        except Exception as e:
            status = "error"
            error = str(e)
        latency_ms = (time.perf_counter() - start_ts) * 1000
        observed = observer.get_turn_payload(turn_id)
        if observed.get("turn_end", {}).get("latency_ms"):
            latency_ms = float(observed["turn_end"]["latency_ms"])
        trace["turns"].append(
            build_turn_trace(
                turn_pair=pair,
                pred_text=pred_text,
                observer_payload=observed,
                latency_ms=latency_ms,
                turn_status=status,
                error=error,
            )
        )

    if any(t.get("turn_status") != "ok" for t in trace["turns"]):
        trace["dialog_status"] = "partial"
    return trace


def evaluate_dialog_task(
    dialog_obj: Dict[str, Any],
    dataset_index: int,
    run_id: str,
    agent_factory: Any,
    observer_factory: Any,
) -> DialogTrace:
    """线程池任务函数。"""
    return run_dialog_replay(
        dialog_obj=dialog_obj,
        run_id=run_id,
        dataset_index=dataset_index,
        agent_factory=agent_factory,
        observer_factory=observer_factory,
    )

