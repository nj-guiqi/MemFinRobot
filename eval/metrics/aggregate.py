"""指标聚合与结果落盘。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from eval.metrics.contracts import DialogTrace, EvalSummary, MetricResult, TurnEvalRow


def aggregate_all_metrics(
    run_id: str,
    dataset_path: str,
    metrics: Dict[str, MetricResult],
    counters: Dict[str, int],
) -> EvalSummary:
    return {
        "run_id": run_id,
        "trace_version": "v1",
        "dataset_path": dataset_path,
        "metrics": metrics,
        "counters": counters,
    }


def write_eval_outputs(
    output_dir: str,
    manifest: Dict[str, Any],
    dialog_traces: List[DialogTrace],
    turn_rows: List[TurnEvalRow],
    summary: EvalSummary,
) -> None:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    manifest_path = out / "run_manifest.json"
    dialog_trace_path = out / "dialog_trace.jsonl"
    turn_eval_path = out / "turn_eval.jsonl"
    summary_path = out / "metrics_summary.json"

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    with open(dialog_trace_path, "w", encoding="utf-8") as f:
        for row in dialog_traces:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    with open(turn_eval_path, "w", encoding="utf-8") as f:
        for row in turn_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

