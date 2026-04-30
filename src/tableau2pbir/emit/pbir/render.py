"""Stage 7 orchestrator. §6 Stage 7."""
from __future__ import annotations

from pathlib import Path

from tableau2pbir.emit._io import write_text
from tableau2pbir.emit.pbir.actions import render_visual_interactions
from tableau2pbir.emit.pbir.blocked import compute_blocked_visuals
from tableau2pbir.emit.pbir.filters import collect_page_filters
from tableau2pbir.emit.pbir.ids import stable_id
from tableau2pbir.emit.pbir.page import render_page
from tableau2pbir.emit.pbir.report import render_report as render_report_json
from tableau2pbir.emit.pbir.slicer import render_filter_slicer, render_parameter_slicer
from tableau2pbir.emit.pbir.visual import render_visual
from tableau2pbir.ir.dashboard import Container, Leaf, LeafKind
from tableau2pbir.ir.workbook import Workbook
from tableau2pbir.layout.leaf_types import PbiObjectKind, map_leaf_kind


def render_report(wb: Workbook, out_dir: Path) -> dict:
    rd = out_dir / "Report" / "definition"
    sheet_by_id = {s.id: s for s in wb.sheets}
    parameter_by_id = {p.id: p for p in wb.data_model.parameters}
    column_to_tier: dict[str, int] = _column_tier_index(wb)

    page_ids: list[str] = []
    rendered_visuals: list[dict] = []
    sheet_to_visual: dict[str, str] = {}
    visual_count = 0
    slicer_count = 0

    for ordinal, dash in enumerate(wb.dashboards):
        page_id = stable_id("page", dash.id)
        page_ids.append(page_id)
        page_dir = rd / "pages" / page_id

        leaves = list(_iter_leaves(dash.layout_tree))
        per_sheet_filters: list[tuple[tuple[str, ...], list]] = []

        for z, leaf in enumerate(leaves):
            if leaf.position is None or leaf.position.w == 0 or leaf.position.h == 0:
                continue
            obj_kind = map_leaf_kind(leaf.kind)
            if obj_kind == PbiObjectKind.DROP:
                continue

            visual_id = stable_id("visual", page_id, str(z))
            v_dir = page_dir / "visuals" / visual_id

            if obj_kind == PbiObjectKind.VISUAL:
                sheet_id = leaf.payload.get("sheet_id")
                sheet = sheet_by_id.get(sheet_id)
                if sheet is None or sheet.pbir_visual is None:
                    continue
                write_text(v_dir / "visual.json",
                           render_visual(visual_id, sheet.pbir_visual, leaf.position, z))
                sheet_to_visual[sheet.id] = visual_id
                field_ids = tuple(b.source_field_id for b in sheet.pbir_visual.encoding_bindings)
                rendered_visuals.append({
                    "page_id": page_id, "visual_id": visual_id, "sheet_id": sheet.id,
                    "field_ids": field_ids,
                })
                per_sheet_filters.append(((sheet.id,), list(sheet.filters)))
                visual_count += 1

            elif obj_kind == PbiObjectKind.SLICER_FILTER:
                source_field_id = leaf.payload.get("field_id", "")
                write_text(v_dir / "visual.json",
                           render_filter_slicer(visual_id, source_field_id, leaf.position, z))
                slicer_count += 1

            elif obj_kind == PbiObjectKind.SLICER_PARAMETER:
                pid = leaf.payload.get("parameter_id", "")
                p = parameter_by_id.get(pid)
                if p is None:
                    continue
                write_text(v_dir / "visual.json",
                           render_parameter_slicer(visual_id, p.name, p.intent.value,
                                                   leaf.position, z))
                slicer_count += 1
            # TEXTBOX / IMAGE / NAV_BUTTON / PLACEHOLDER / LEGEND_SUPPRESS — v1 skips emission

        page_filters = collect_page_filters(per_sheet_filters)
        write_text(page_dir / "page.json",
                   render_page(page_id, dash.name, ordinal,
                               width=dash.size.w or 1280, height=dash.size.h or 720,
                               filters=page_filters))

    write_text(rd / "report.json",
               render_report_json(report_name=Path(wb.source_path).stem, page_order=page_ids))

    interactions: list[dict] = []
    for dash in wb.dashboards:
        interactions.extend(render_visual_interactions(list(dash.actions), sheet_to_visual))

    blocked = compute_blocked_visuals(rendered_visuals, wb.unsupported, column_to_tier)

    return {
        "counts": {
            "pages": len(page_ids),
            "visuals": visual_count,
            "slicers": slicer_count,
        },
        "blocked_visuals": blocked,
        "visual_interactions": interactions,
    }


def _iter_leaves(node):
    if isinstance(node, Leaf):
        yield node
        return
    if isinstance(node, Container):
        for c in node.children:
            yield from _iter_leaves(c)


def _column_tier_index(wb: Workbook) -> dict[str, int]:
    """Map every IR column id (and 'Table.Column' tag) → backing datasource connector_tier."""
    out: dict[str, int] = {}
    ds_by_id = {d.id: d for d in wb.data_model.datasources}
    for t in wb.data_model.tables:
        ds = ds_by_id.get(t.datasource_id)
        if ds is None:
            continue
        tier = int(ds.connector_tier)
        for col_id in t.column_ids:
            out[col_id] = tier
            out[f"{t.name}.{col_id}"] = tier
    return out
