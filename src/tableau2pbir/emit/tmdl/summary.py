"""Stage 6 summary.md."""
from __future__ import annotations


def render_summary(manifest: dict) -> str:
    c = manifest.get("counts", {})
    return (
        "# Stage 6 — build TMDL\n\n"
        f"- files: {len(manifest.get('files', []))}\n"
        f"- tables: {c.get('tables', 0)}\n"
        f"- measures: {c.get('measures', 0)}\n"
        f"- relationships: {c.get('relationships', 0)}\n"
        f"- parameters emitted: {c.get('parameters', 0)}\n"
    )
