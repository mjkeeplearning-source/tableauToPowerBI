"""Stage 5 — compute layout (pure python). §6 Stage 5."""
from __future__ import annotations

from typing import Any

from tableau2pbir.ir.dashboard import Container, Leaf
from tableau2pbir.ir.workbook import Workbook
from tableau2pbir.layout.canvas import select_canvas
from tableau2pbir.layout.leaf_types import PbiObjectKind, map_leaf_kind
from tableau2pbir.layout.summary import render_summary
from tableau2pbir.layout.walker import walk_layout
from tableau2pbir.pipeline import StageContext, StageError, StageResult


def run(input_json: dict[str, Any], ctx: StageContext) -> StageResult:
    wb = Workbook.model_validate(input_json)
    per_dashboard: list[dict] = []
    errors: list[StageError] = []

    new_dashboards = []
    for dash in wb.dashboards:
        canvas_w, canvas_h, scale = select_canvas(dash.size, ctx.config or {})
        resolved = walk_layout(dash.layout_tree, canvas_w, canvas_h, scale)

        positions_iter = iter(resolved)
        new_tree = _rebuild_tree(dash.layout_tree, positions_iter)
        new_dash = dash.model_copy(update={"layout_tree": new_tree})
        new_dashboards.append(new_dash)

        clamped = sum(1 for r in resolved if r.clamped)
        dropped = sum(1 for r in resolved if r.dropped)
        placeholders = sum(
            1 for r in resolved
            if map_leaf_kind(r.kind) in (PbiObjectKind.PLACEHOLDER, PbiObjectKind.DROP)
        )
        leaves = len(resolved) or 1
        per_dashboard.append({
            "name": dash.name,
            "canvas_w": canvas_w,
            "canvas_h": canvas_h,
            "scale": scale,
            "leaves": len(resolved),
            "clamped": clamped,
            "dropped": dropped,
            "placeholder_ratio": placeholders / leaves,
        })
        for r in resolved:
            if r.clamped:
                errors.append(StageError(
                    severity="warn", code="layout.leaf_clamped",
                    object_id=dash.id,
                    message=f"Leaf in dashboard '{dash.name}' clamped to canvas.",
                    fix_hint=None,
                ))
            if r.dropped:
                errors.append(StageError(
                    severity="warn", code="layout.leaf_dropped",
                    object_id=dash.id,
                    message=f"Leaf in dashboard '{dash.name}' completely off-canvas; dropped.",
                    fix_hint=None,
                ))

    new_wb = wb.model_copy(update={"dashboards": tuple(new_dashboards)})
    return StageResult(
        output=new_wb.model_dump(mode="json"),
        summary_md=render_summary(per_dashboard),
        errors=tuple(errors),
    )


def _rebuild_tree(node: Container | Leaf, positions_iter) -> Container | Leaf:
    if isinstance(node, Leaf):
        resolved = next(positions_iter)
        return node.model_copy(update={"position": resolved.position})
    new_children = tuple(_rebuild_tree(c, positions_iter) for c in node.children)
    return node.model_copy(update={"children": new_children})
