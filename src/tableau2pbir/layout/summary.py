"""Stage 5 summary.md renderer."""
from __future__ import annotations


def render_summary(per_dashboard: list[dict]) -> str:
    lines = ["# Stage 5 — compute layout", ""]
    if not per_dashboard:
        lines.append("_no dashboards in workbook_")
        return "\n".join(lines) + "\n"
    lines.append("| dashboard | canvas | leaves | clamped | dropped | placeholder_ratio |")
    lines.append("|---|---|---|---|---|---|")
    for d in per_dashboard:
        ratio = f"{d['placeholder_ratio']:.2f}" if d["leaves"] else "n/a"
        lines.append(
            f"| {d['name']} | {d['canvas_w']}x{d['canvas_h']} (scale {d['scale']:.2f}) "
            f"| {d['leaves']} | {d['clamped']} | {d['dropped']} | {ratio} |"
        )
    return "\n".join(lines) + "\n"
