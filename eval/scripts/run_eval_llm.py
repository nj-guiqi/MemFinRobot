"""Simple LLM 评测入口：并发回放 + 指标计算 + 断点续跑 + llm 后缀落盘。"""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval.metrics.aggregate import aggregate_all_metrics
from eval.metrics.m1_context import compute_m1_context_continuity
from eval.metrics.m2_profile import compute_m2_profile_accuracy
from eval.metrics.m3_risk import compute_m3_risk_coverage
from eval.metrics.m4_compliance import compute_m4_compliance
from eval.metrics.m5_explainability import compute_m5_explainability
from eval.metrics.preprocess import build_turn_eval_rows, load_dataset_jsonl
from eval.metrics.report import render_markdown_report
from eval.scripts.llm_agent_adapter import LlmAgentAdapter
from eval.scripts.replay_llm import EvalTurnObserver, evaluate_dialog_task_llm


class ProgressLogger:
    """线程安全进度日志（JSONL）。"""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def log(self, event: str, payload: Dict[str, Any]) -> None:
        row = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "event": event,
            **payload,
        }
        with self._lock:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _load_existing_dialog_traces(dialog_trace_path: Path) -> Dict[str, Dict[str, Any]]:
    traces_by_dialog: Dict[str, Dict[str, Any]] = {}
    if not dialog_trace_path.exists():
        return traces_by_dialog
    with open(dialog_trace_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            dialog_id = str(row.get("dialog_id") or "")
            if dialog_id:
                traces_by_dialog[dialog_id] = row
    return traces_by_dialog


def _append_dialog_trace(dialog_trace_path: Path, trace: Dict[str, Any]) -> None:
    dialog_trace_path.parent.mkdir(parents=True, exist_ok=True)
    with open(dialog_trace_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(trace, ensure_ascii=False) + "\n")


def _build_failed_trace(
    run_id: str,
    dataset_index: int,
    dialog_id: str,
    dialog_obj: Dict[str, Any],
    error: str,
) -> Dict[str, Any]:
    return {
        "trace_version": "v1",
        "run_id": run_id,
        "dialog_id": dialog_id,
        "dataset_index": dataset_index,
        "scenario_type": dialog_obj.get("scenario_type"),
        "difficulty": dialog_obj.get("difficulty"),
        "dialog_status": "failed",
        "valid_dialog": False,
        "skip_reason": None,
        "session_id": f"eval_session_{dialog_id}",
        "user_id": f"eval_user_{dialog_id}",
        "turns": [],
        "dialog_error": error,
        "profile_gt": dialog_obj.get("profile_gt"),
        "blueprint": dialog_obj.get("blueprint"),
        "raw_turns": dialog_obj.get("turns"),
    }


def _write_eval_outputs_llm(
    output_dir: Path,
    manifest: Dict[str, Any],
    dialog_traces: List[Dict[str, Any]],
    turn_rows: List[Dict[str, Any]],
    summary: Dict[str, Any],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_dir / "run_manifest_llm.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    with open(output_dir / "dialog_trace_llm.jsonl", "w", encoding="utf-8") as f:
        for row in dialog_traces:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    with open(output_dir / "turn_eval_llm.jsonl", "w", encoding="utf-8") as f:
        for row in turn_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    with open(output_dir / "metrics_summary_llm.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


def _drop_m1_required_keys_for_llm(dialog_traces: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """简单 LLM 基线不具备记忆召回能力，忽略 m1 所需 key。"""
    traces = copy.deepcopy(dialog_traces)
    for dialog in traces:
        for turn in dialog.get("turns") or []:
            gt_tags = turn.get("gt_turn_tags")
            if isinstance(gt_tags, dict):
                gt_tags["memory_required_keys_gt"] = []
    return traces


def build_llm_agent_factory(args: argparse.Namespace):
    """创建 per-dialog 的 simple llm agent 工厂。"""

    def _factory(dialog_id: str, observer: Any) -> LlmAgentAdapter:
        return LlmAgentAdapter(
            dialog_id=dialog_id,
            observer=observer,
            base_url=args.base_url,
            chat_model=args.chat_model,
            api_key_env=args.api_key_env,
            api_key=args.api_key,
            enable_thinking=args.enable_thinking,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            request_timeout_sec=args.request_timeout_sec,
        )

    return _factory


def run_eval_parallel_llm(
    dataset_path: str,
    run_id: str,
    run_dir: Path,
    max_workers_dialog: int,
    max_workers_judge: int,
    agent_factory: Any,
    observer_factory: Any,
    turn_timeout_sec: int,
    turn_heartbeat_sec: int,
) -> Dict[str, Any]:
    """对话内串行、对话间并发。"""
    _ = max_workers_judge
    dialogs = load_dataset_jsonl(dataset_path)

    progress_path = PROJECT_ROOT / "eval" / "logs" / f"progress_llm_{run_id}.jsonl"
    progress = ProgressLogger(progress_path)

    dialog_trace_path = run_dir / "dialog_trace_llm.jsonl"
    dialog_traces_by_id = _load_existing_dialog_traces(dialog_trace_path)
    completed_dialog_ids = set(dialog_traces_by_id.keys())
    progress.log(
        "run_started",
        {
            "run_id": run_id,
            "dataset_path": dataset_path,
            "dialogs": len(dialogs),
            "resumed_completed_dialogs": len(completed_dialog_ids),
        },
    )

    with ThreadPoolExecutor(max_workers=max_workers_dialog) as executor:
        futures: Dict[Any, Dict[str, Any]] = {}
        for obj in dialogs:
            idx = int(obj.get("_dataset_index", 0))
            dialog_id = str(obj.get("dialog_id") or f"dialog_{idx}")
            if dialog_id in completed_dialog_ids:
                progress.log("dialog_skipped_resume", {"dialog_id": dialog_id, "dataset_index": idx})
                continue

            progress.log("dialog_started", {"dialog_id": dialog_id, "dataset_index": idx})
            progress_callback = (
                lambda event, payload, _dialog_id=dialog_id, _idx=idx: progress.log(
                    event,
                    {"dialog_id": _dialog_id, "dataset_index": _idx, **(payload or {})},
                )
            )
            fut = executor.submit(
                evaluate_dialog_task_llm,
                obj,
                idx,
                run_id,
                agent_factory,
                observer_factory,
                turn_timeout_sec,
                turn_heartbeat_sec,
                progress_callback,
            )
            futures[fut] = {"dialog_obj": obj, "dataset_index": idx, "dialog_id": dialog_id}

        for fut in as_completed(futures):
            meta = futures[fut]
            dialog_id = str(meta["dialog_id"])
            dataset_index = int(meta["dataset_index"])
            dialog_obj = meta["dialog_obj"]

            try:
                trace = fut.result()
            except Exception as e:
                trace = _build_failed_trace(
                    run_id=run_id,
                    dataset_index=dataset_index,
                    dialog_id=dialog_id,
                    dialog_obj=dialog_obj,
                    error=f"unhandled_dialog_exception: {type(e).__name__}: {e}",
                )
                progress.log(
                    "dialog_failed",
                    {
                        "dialog_id": dialog_id,
                        "dataset_index": dataset_index,
                        "error": str(e),
                    },
                )

            dialog_traces_by_id[dialog_id] = trace
            _append_dialog_trace(dialog_trace_path, trace)
            progress.log(
                "dialog_done",
                {
                    "dialog_id": trace.get("dialog_id"),
                    "status": trace.get("dialog_status"),
                    "turns": len(trace.get("turns") or []),
                },
            )

    dialog_traces: List[Dict[str, Any]] = list(dialog_traces_by_id.values())
    dialog_traces.sort(key=lambda x: int(x.get("dataset_index") or 0))

    # LLM baseline: 忽略 m1 memory key 需求，避免将无记忆能力误算为 m1 失败。
    metric_traces = _drop_m1_required_keys_for_llm(dialog_traces)

    turn_rows = build_turn_eval_rows(metric_traces, risk_tag_mapper={}, forbidden_patterns=[])
    m1 = compute_m1_context_continuity(turn_rows)
    m2 = compute_m2_profile_accuracy(metric_traces, dialog_objs={})
    m3 = compute_m3_risk_coverage(turn_rows)
    m4 = compute_m4_compliance(turn_rows)
    m5 = compute_m5_explainability(turn_rows)
    metrics = {
        "m1_context_continuity": m1,
        "m2_profile_accuracy": m2,
        "m3_risk_coverage": m3,
        "m4_compliance": m4,
        "m5_explainability": m5,
    }

    valid_dialogs = len([d for d in dialog_traces if d.get("valid_dialog")])
    skipped_dialogs = len([d for d in dialog_traces if d.get("dialog_status") == "skipped"])
    failed_dialogs = len([d for d in dialog_traces if d.get("dialog_status") == "failed"])
    total_turn_pairs = sum(len(d.get("turns") or []) for d in dialog_traces)
    counters = {
        "total_dialogs": len(dialog_traces),
        "valid_dialogs": valid_dialogs,
        "skipped_dialogs": skipped_dialogs,
        "failed_dialogs": failed_dialogs,
        "total_turn_pairs": total_turn_pairs,
    }
    progress.log("metrics_done", {"run_id": run_id, "turn_rows": len(turn_rows)})
    progress.log("run_finished", {"run_id": run_id, **counters})
    return {"dialog_traces": dialog_traces, "turn_rows": turn_rows, "metrics": metrics, "counters": counters}


def main() -> None:
    parser = argparse.ArgumentParser(description="Simple LLM evaluation runner")
    parser.add_argument("--dataset", type=str, default=str(PROJECT_ROOT / "eval" / "datasets" / "MemFinConv.jsonl"))
    parser.add_argument("--output-root", type=str, default=str(PROJECT_ROOT / "eval" / "runs"))
    parser.add_argument("--run-id", type=str, default=None, help="resume with existing run_id")
    parser.add_argument("--workers-dialog", type=int, default=max(1, min(4, os.cpu_count() or 1)))
    parser.add_argument("--workers-judge", type=int, default=1)

    parser.add_argument("--chat-model", type=str, default="qwen3.5-plus")
    parser.add_argument("--base-url", type=str, default="https://dashscope.aliyuncs.com/compatible-mode/v1")
    parser.add_argument("--api-key-env", type=str, default="DASHSCOPE_API_KEY")
    parser.add_argument("--api-key", type=str, default=None)
    parser.add_argument("--enable-thinking", action="store_true", help="enable extra_body.enable_thinking")
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--max-tokens", type=int, default=2048)
    parser.add_argument("--request-timeout-sec", type=float, default=120.0)
    parser.add_argument("--turn-timeout-sec", type=int, default=300)
    parser.add_argument("--turn-heartbeat-sec", type=int, default=20)

    args = parser.parse_args()

    run_id = args.run_id or datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    run_dir = Path(args.output_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    agent_factory = build_llm_agent_factory(args=args)
    started_at = datetime.utcnow().isoformat() + "Z"
    result = run_eval_parallel_llm(
        dataset_path=args.dataset,
        run_id=run_id,
        run_dir=run_dir,
        max_workers_dialog=args.workers_dialog,
        max_workers_judge=args.workers_judge,
        agent_factory=agent_factory,
        observer_factory=EvalTurnObserver,
        turn_timeout_sec=args.turn_timeout_sec,
        turn_heartbeat_sec=args.turn_heartbeat_sec,
    )
    ended_at = datetime.utcnow().isoformat() + "Z"

    summary = aggregate_all_metrics(
        run_id=run_id,
        dataset_path=args.dataset,
        metrics=result["metrics"],
        counters=result["counters"],
    )
    manifest = {
        "trace_version": "v1",
        "run_id": run_id,
        "dataset_path": args.dataset,
        "started_at": started_at,
        "ended_at": ended_at,
        "model_name": args.chat_model,
        "workers_dialog": args.workers_dialog,
        "workers_judge": args.workers_judge,
        "request_timeout_sec": args.request_timeout_sec,
        "turn_timeout_sec": args.turn_timeout_sec,
        "turn_heartbeat_sec": args.turn_heartbeat_sec,
        "counters": result["counters"],
        "runner": "llm",
        "m1_handling": "ignored_memory_required_keys",
    }

    _write_eval_outputs_llm(
        output_dir=run_dir,
        manifest=manifest,
        dialog_traces=result["dialog_traces"],
        turn_rows=result["turn_rows"],
        summary=summary,
    )

    report_md = render_markdown_report(summary)
    report_path = run_dir / "report_llm.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_md)

    print(f"[Eval LLM Done] run_id={run_id}")
    print(f"- output: {run_dir}")
    print(f"- report: {report_path}")


if __name__ == "__main__":
    main()
