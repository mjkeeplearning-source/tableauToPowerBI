"""Stage 7 summary.md."""
from __future__ import annotations


def render_summary(manifest: dict) -> str:
    c = manifest.get("counts", {})
    blocked = manifest.get("blocked_visuals", [])
    inter = manifest.get("visual_interactions", [])
    return (
        "# Stage 7 — build report PBIR\n\n"
        f"- pages: {c.get('pages', 0)}\n"
        f"- visuals: {c.get('visuals', 0)}\n"
        f"- slicers: {c.get('slicers', 0)}\n"
        f"- visual_interactions: {len(inter)}\n"
        f"- blocked_visuals: {len(blocked)}\n"
    )
