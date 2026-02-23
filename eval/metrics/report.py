"""评测报告渲染。"""

from __future__ import annotations

from typing import Any, Dict

from eval.metrics.contracts import EvalSummary


def render_markdown_report(summary: EvalSummary) -> str:
    lines = []
    lines.append("# MemFinRobot Eval Report")
    lines.append("")
    lines.append(f"- run_id: `{summary.get('run_id', '')}`")
    lines.append(f"- dataset: `{summary.get('dataset_path', '')}`")
    counters = summary.get("counters", {})
    lines.append(
        f"- counters: total={counters.get('total_dialogs', 0)}, "
        f"valid={counters.get('valid_dialogs', 0)}, "
        f"skipped={counters.get('skipped_dialogs', 0)}, "
        f"failed={counters.get('failed_dialogs', 0)}"
    )
    lines.append("")

    metrics = summary.get("metrics", {})
    for name, result in metrics.items():
        lines.append(f"## {name}")
        micro = result.get("micro", {})
        macro = result.get("macro", {})
        counts = result.get("counts", {})

        lines.append("")
        lines.append("### Micro")
        for k, v in micro.items():
            lines.append(f"- {k}: `{_fmt(v)}`")

        lines.append("")
        lines.append("### Macro")
        for k, v in macro.items():
            lines.append(f"- {k}: `{_fmt(v)}`")

        lines.append("")
        lines.append("### Counts")
        for k, v in counts.items():
            lines.append(f"- {k}: `{v}`")
        lines.append("")

    return "\n".join(lines)


def _fmt(v: Any) -> str:
    if isinstance(v, float):
        return f"{v:.6f}"
    return str(v)

