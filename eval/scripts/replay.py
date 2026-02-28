"""对话回放与 trace 生成。"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
import copy
import time
from threading import Lock
from typing import Any, Callable, Dict, List, Optional

from eval.metrics.contracts import DialogTrace, TurnStatus, TurnTrace
from eval.metrics.preprocess import align_turn_pairs, classify_dialog_validity, normalize_dialog

RETRYABLE_ERROR_KEYWORDS = (
    "Request timed out.",
    "Connection error.",
    "incomplete chunked read",
)
RETRY_BACKOFF_SEC = 1.0
ProgressCallback = Optional[Callable[[str, Dict[str, Any]], None]]


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


def _emit_progress(callback: ProgressCallback, event: str, payload: Dict[str, Any]) -> None:
    if not callback:
        return
    try:
        callback(event, payload)
    except Exception:
        pass


def _is_retryable_error(error: Optional[str]) -> bool:
    if not error:
        return False
    lowered = error.lower()
    return any(keyword.lower() in lowered for keyword in RETRYABLE_ERROR_KEYWORDS)


def run_dialog_replay(
    dialog_obj: Dict[str, Any],
    run_id: str,
    dataset_index: int,
    agent_factory: Any,
    observer_factory: Any,
    timeout_sec: int = 120,
    turn_heartbeat_sec: int = 20,
    turn_retries: int = 0,
    progress_callback: ProgressCallback = None,
) -> DialogTrace:
    """单对话回放，产出 DialogTrace。"""
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
        pred_text = ""
        status: TurnStatus = "ok"
        error: Optional[str] = None

        attempts_used = 0
        latency_ms = 0.0
        max_attempts = max(1, int(turn_retries) + 1)

        for attempt in range(1, max_attempts + 1):
            attempts_used = attempt
            start_ts = time.perf_counter()

            _emit_progress(
                progress_callback,
                "turn_started",
                {"dialog_id": dialog_id, "turn_pair_id": turn_id, "attempt": attempt},
            )

            turn_executor = ThreadPoolExecutor(max_workers=1)
            future = turn_executor.submit(
                agent.handle_turn,
                user_message=pair["user_text"],
                session_id=trace["session_id"],
                user_id=trace["user_id"],
            )
            next_heartbeat_sec = float(max(1, turn_heartbeat_sec))

            pred_text = ""
            status = "ok"
            error = None
            try:
                while True:
                    elapsed_sec = time.perf_counter() - start_ts
                    if timeout_sec > 0 and elapsed_sec >= float(timeout_sec):
                        status = "error"
                        error = f"turn_timeout: exceeded {timeout_sec}s"
                        future.cancel()
                        _emit_progress(
                            progress_callback,
                            "turn_timeout",
                            {
                                "dialog_id": dialog_id,
                                "turn_pair_id": turn_id,
                                "attempt": attempt,
                                "elapsed_sec": round(elapsed_sec, 3),
                                "timeout_sec": timeout_sec,
                            },
                        )
                        break

                    wait_timeout = 1.0
                    if timeout_sec > 0:
                        wait_timeout = min(wait_timeout, float(timeout_sec) - elapsed_sec)

                    try:
                        pred_text = future.result(timeout=max(wait_timeout, 0.1))
                        break
                    except FutureTimeoutError:
                        elapsed_sec = time.perf_counter() - start_ts
                        if turn_heartbeat_sec > 0 and elapsed_sec >= next_heartbeat_sec:
                            _emit_progress(
                                progress_callback,
                                "turn_heartbeat",
                                {
                                    "dialog_id": dialog_id,
                                    "turn_pair_id": turn_id,
                                    "attempt": attempt,
                                    "elapsed_sec": round(elapsed_sec, 3),
                                },
                            )
                            next_heartbeat_sec += float(max(1, turn_heartbeat_sec))
                        continue
                    except Exception as e:
                        status = "error"
                        error = str(e)
                        break
            finally:
                turn_executor.shutdown(wait=False, cancel_futures=True)

            latency_ms = (time.perf_counter() - start_ts) * 1000
            should_retry = (
                status == "error"
                and attempt < max_attempts
                and _is_retryable_error(error)
            )
            if not should_retry:
                break

            _emit_progress(
                progress_callback,
                "turn_retry",
                {
                    "dialog_id": dialog_id,
                    "turn_pair_id": turn_id,
                    "attempt": attempt,
                    "next_attempt": attempt + 1,
                    "max_attempts": max_attempts,
                    "error": error,
                },
            )
            time.sleep(RETRY_BACKOFF_SEC)

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
        _emit_progress(
            progress_callback,
            "turn_done",
            {
                "dialog_id": dialog_id,
                "turn_pair_id": turn_id,
                "attempts_used": attempts_used,
                "turn_status": status,
                "latency_ms": round(latency_ms, 3),
                "error": error,
            },
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
    timeout_sec: int = 120,
    turn_heartbeat_sec: int = 20,
    turn_retries: int = 0,
    progress_callback: ProgressCallback = None,
) -> DialogTrace:
    """线程池任务函数。"""
    return run_dialog_replay(
        dialog_obj=dialog_obj,
        run_id=run_id,
        dataset_index=dataset_index,
        agent_factory=agent_factory,
        observer_factory=observer_factory,
        timeout_sec=timeout_sec,
        turn_heartbeat_sec=turn_heartbeat_sec,
        turn_retries=turn_retries,
        progress_callback=progress_callback,
    )
