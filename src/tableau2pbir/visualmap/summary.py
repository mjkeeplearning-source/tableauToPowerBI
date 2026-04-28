"""Stage 4 summary.md renderer."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VisualMapStats:
    total_sheets: int
    by_source: dict[str, int]
    visual_type_hist: dict[str, int]
    ai_low_confidence_sheet_ids: tuple[str, ...]
    unsupported_mark_types: dict[str, int]


def _hist(items: dict[str, int]) -> list[str]:
    if not items:
        return ["- (none)"]
    return [f"- {k}: {items[k]}" for k in sorted(items)]


def render_stage4_summary(stats: VisualMapStats) -> str:
    lines = [
        "# Stage 4 — map visuals",
        "",
        f"- total sheets: {stats.total_sheets}",
        "",
        "## Translation source",
        "",
        *_hist(stats.by_source),
        "",
        "## Visual type histogram",
        "",
        *_hist(stats.visual_type_hist),
        "",
        "## Low-confidence AI decisions",
        "",
    ]
    if stats.ai_low_confidence_sheet_ids:
        lines.extend(f"- {sid}" for sid in sorted(stats.ai_low_confidence_sheet_ids))
    else:
        lines.append("- (none)")
    lines.extend([
        "",
        "## Unsupported mark types",
        "",
        *_hist(stats.unsupported_mark_types),
        "",
    ])
    return "\n".join(lines) + "\n"
