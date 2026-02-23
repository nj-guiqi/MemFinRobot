"""Simple LLM 对话回放与 trace 生成（对齐现有 replay 格式）。"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
import time
from typing import Any, Callable, Dict, Optional

from eval.metrics.contracts import DialogTrace, TurnStatus
from eval.metrics.preprocess import align_turn_pairs, classify_dialog_validity, normalize_dialog
from eval.scripts.replay import EvalTurnObserver, build_turn_trace


ProgressCallback = Optional[Callable[[str, Dict[str, Any]], None]]


def _emit_progress(callback: ProgressCallback, event: str, payload: Dict[str, Any]) -> None:
    if not callback:
        return
    try:
        callback(event, payload)
    except Exception:
        pass


def run_dialog_replay_llm(
    dialog_obj: Dict[str, Any],
    run_id: str,
    dataset_index: int,
    agent_factory: Any,
    observer_factory: Any,
    timeout_sec: int = 120,
    turn_heartbeat_sec: int = 20,
    progress_callback: ProgressCallback = None,
) -> DialogTrace:
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
        error = None

        _emit_progress(
            progress_callback,
            "turn_started",
            {"dialog_id": dialog_id, "turn_pair_id": turn_id},
        )

        turn_executor = ThreadPoolExecutor(max_workers=1)
        future = turn_executor.submit(
            agent.handle_turn,
            user_message=pair["user_text"],
            session_id=trace["session_id"],
            user_id=trace["user_id"],
            turn_pair=pair,
        )
        next_heartbeat_sec = float(max(1, turn_heartbeat_sec))

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
                "turn_status": status,
                "latency_ms": round(latency_ms, 3),
                "error": error,
            },
        )

    if any(t.get("turn_status") != "ok" for t in trace["turns"]):
        trace["dialog_status"] = "partial"
    return trace


def evaluate_dialog_task_llm(
    dialog_obj: Dict[str, Any],
    dataset_index: int,
    run_id: str,
    agent_factory: Any,
    observer_factory: Any,
    timeout_sec: int = 120,
    turn_heartbeat_sec: int = 20,
    progress_callback: ProgressCallback = None,
) -> DialogTrace:
    return run_dialog_replay_llm(
        dialog_obj=dialog_obj,
        run_id=run_id,
        dataset_index=dataset_index,
        agent_factory=agent_factory,
        observer_factory=observer_factory,
        timeout_sec=timeout_sec,
        turn_heartbeat_sec=turn_heartbeat_sec,
        progress_callback=progress_callback,
    )
