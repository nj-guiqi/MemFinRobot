"""评测主入口：并发回放 + 指标计算 + 报告落盘。"""

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

# 允许直接 `python eval/scripts/run_eval.py` 运行
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval.metrics.aggregate import aggregate_all_metrics, write_eval_outputs
from eval.metrics.m1_context import compute_m1_context_continuity
from eval.metrics.m2_profile import compute_m2_profile_accuracy
from eval.metrics.m3_risk import compute_m3_risk_coverage
from eval.metrics.m4_compliance import compute_m4_compliance
from eval.metrics.m5_explainability import compute_m5_explainability
from eval.metrics.preprocess import build_turn_eval_rows, load_dataset_jsonl
from eval.metrics.report import render_markdown_report
from eval.scripts.replay import EvalTurnObserver, evaluate_dialog_task
from memfinrobot.agent.memfin_agent import MemFinFnCallAgent
from memfinrobot.config.settings import Settings
from memfinrobot.tools import get_default_tools


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


def build_agent_factory(base_settings: Settings, run_dir: Path):
    """创建 per-dialog agent 工厂。"""

    def _factory(dialog_id: str, observer: Any) -> MemFinFnCallAgent:
        settings = copy.deepcopy(base_settings)
        settings.memory.storage_path = str(run_dir / "memstore" / dialog_id)
        tools = get_default_tools()
        return MemFinFnCallAgent(
            function_list=tools,
            llm=settings.llm.to_dict(),
            settings=settings,
            observer=observer,
        )

    return _factory


def run_eval_parallel(
    dataset_path: str,
    run_id: str,
    max_workers_dialog: int,
    max_workers_judge: int,
    agent_factory: Any,
    observer_factory: Any,
) -> Dict[str, Any]:
    """对话内串行、对话间并发。"""
    _ = max_workers_judge  # 当前实现采用启发式解释评分，未调用外部 Judge
    dialogs = load_dataset_jsonl(dataset_path)

    progress_path = PROJECT_ROOT / "eval" / "logs" / f"progress_{run_id}.jsonl"
    progress = ProgressLogger(progress_path)
    progress.log("run_started", {"run_id": run_id, "dataset_path": dataset_path, "dialogs": len(dialogs)})

    dialog_traces: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max_workers_dialog) as executor:
        futures = []
        for obj in dialogs:
            idx = int(obj.get("_dataset_index", 0))
            dialog_id = str(obj.get("dialog_id") or f"dialog_{idx}")
            progress.log("dialog_started", {"dialog_id": dialog_id, "dataset_index": idx})
            futures.append(
                executor.submit(
                    evaluate_dialog_task,
                    obj,
                    idx,
                    run_id,
                    agent_factory,
                    observer_factory,
                )
            )

        for fut in as_completed(futures):
            trace = fut.result()
            dialog_traces.append(trace)
            progress.log(
                "dialog_done",
                {
                    "dialog_id": trace.get("dialog_id"),
                    "status": trace.get("dialog_status"),
                    "turns": len(trace.get("turns") or []),
                },
            )
    dialog_traces.sort(key=lambda x: int(x.get("dataset_index") or 0))

    # 指标计算
    turn_rows = build_turn_eval_rows(dialog_traces, risk_tag_mapper={}, forbidden_patterns=[])
    m1 = compute_m1_context_continuity(turn_rows)
    m2 = compute_m2_profile_accuracy(dialog_traces, dialog_objs={})
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
    parser = argparse.ArgumentParser(description="MemFinRobot evaluation runner")
    parser.add_argument("--dataset", type=str, default=str(PROJECT_ROOT / "eval" / "datasets" / "MemFinConv.jsonl"))
    parser.add_argument("--config", type=str, default=None, help="config.json path")
    parser.add_argument("--output-root", type=str, default=str(PROJECT_ROOT / "eval" / "runs"))
    parser.add_argument("--workers-dialog", type=int, default=max(1, min(4, os.cpu_count() or 1)))
    parser.add_argument("--workers-judge", type=int, default=1)
    args = parser.parse_args()

    run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    run_dir = Path(args.output_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    base_settings = Settings.from_file(args.config) if args.config else Settings()
    agent_factory = build_agent_factory(base_settings, run_dir)

    started_at = datetime.utcnow().isoformat() + "Z"
    result = run_eval_parallel(
        dataset_path=args.dataset,
        run_id=run_id,
        max_workers_dialog=args.workers_dialog,
        max_workers_judge=args.workers_judge,
        agent_factory=agent_factory,
        observer_factory=EvalTurnObserver,
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
        "model_name": base_settings.llm.model,
        "workers_dialog": args.workers_dialog,
        "workers_judge": args.workers_judge,
        "counters": result["counters"],
    }

    write_eval_outputs(
        output_dir=str(run_dir),
        manifest=manifest,
        dialog_traces=result["dialog_traces"],
        turn_rows=result["turn_rows"],
        summary=summary,
    )

    report_md = render_markdown_report(summary)
    report_path = run_dir / "report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_md)

    print(f"[Eval Done] run_id={run_id}")
    print(f"- output: {run_dir}")
    print(f"- report: {report_path}")


if __name__ == "__main__":
    main()
