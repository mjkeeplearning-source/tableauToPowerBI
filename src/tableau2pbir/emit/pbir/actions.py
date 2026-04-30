"""Action → visualInteractions."""
from __future__ import annotations

from tableau2pbir.ir.dashboard import Action, ActionKind


def render_visual_interactions(actions: list[Action], sheet_to_visual: dict[str, str]) -> list[dict]:
    out: list[dict] = []
    for a in actions:
        if a.kind not in (ActionKind.FILTER, ActionKind.HIGHLIGHT):
            continue  # URL + PARAMETER deferred
        for src in a.source_sheet_ids:
            for tgt in a.target_sheet_ids:
                if src not in sheet_to_visual or tgt not in sheet_to_visual:
                    continue
                out.append({
                    "source": sheet_to_visual[src],
                    "target": sheet_to_visual[tgt],
                    "type": "filter" if a.kind == ActionKind.FILTER else "highlight",
                })
    return out
