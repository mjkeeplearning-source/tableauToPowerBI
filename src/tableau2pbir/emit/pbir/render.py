"""Stage 7 orchestrator. §6 Stage 7."""
from __future__ import annotations

import json
from pathlib import Path

from tableau2pbir.emit._io import write_text
from tableau2pbir.emit.pbir.actions import render_visual_interactions
from tableau2pbir.emit.pbir.blocked import compute_blocked_visuals
from tableau2pbir.emit.pbir.filters import collect_page_filters
from tableau2pbir.emit.pbir.ids import stable_id
from tableau2pbir.emit.pbir.page import render_page
from tableau2pbir.emit.pbir.report import render_pages_manifest, render_report as render_report_json
from tableau2pbir.emit.pbir.slicer import render_filter_slicer, render_parameter_slicer
from tableau2pbir.emit.pbir.visual import render_visual
from tableau2pbir.ir.dashboard import Container, Leaf, LeafKind, Position
from tableau2pbir.ir.workbook import Workbook
from tableau2pbir.layout.leaf_types import PbiObjectKind, map_leaf_kind
from tableau2pbir.visualmap.field_lookup import build_field_lookup


def render_report(wb: Workbook, out_dir: Path) -> dict:
    rd = out_dir / "Report" / "definition"
    sheet_by_id = {s.id: s for s in wb.sheets}
    parameter_by_id = {p.id: p for p in wb.data_model.parameters}
    column_to_tier: dict[str, int] = _column_tier_index(wb)

    field_lookup = build_field_lookup(wb)
    page_ids: list[str] = []
    rendered_visuals: list[dict] = []
    sheet_to_visual: dict[str, str] = {}
    visual_count = 0
    slicer_count = 0

    # Emit one full-canvas page per worksheet (mirrors Tableau's per-sheet tab model).
    _SHEET_PAGE_W, _SHEET_PAGE_H = 1280, 720
    sheet_ids_with_page: set[str] = set()
    for sheet in wb.sheets:
        if sheet.pbir_visual is None:
            continue
        page_id = f"ReportSection{len(page_ids) + 1}"
        page_ids.append(page_id)
        page_dir = rd / "pages" / page_id
        visual_count += 1
        visual_id = f"visual_{visual_count}"
        full_pos = Position(x=0, y=0, w=_SHEET_PAGE_W, h=_SHEET_PAGE_H)
        write_text(page_dir / "visuals" / visual_id / "visual.json",
                   render_visual(visual_id, sheet.pbir_visual, full_pos, 0, field_lookup))
        rendered_visuals.append({
            "page_id": page_id, "visual_id": visual_id, "sheet_id": sheet.id,
            "field_ids": tuple(b.source_field_id for b in sheet.pbir_visual.encoding_bindings),
        })
        page_filters = collect_page_filters([((sheet.id,), list(sheet.filters))], field_lookup)
        write_text(page_dir / "page.json",
                   render_page(page_id, sheet.name,
                               width=_SHEET_PAGE_W, height=_SHEET_PAGE_H,
                               filters=page_filters))
        sheet_ids_with_page.add(sheet.id)

    for ordinal, dash in enumerate(wb.dashboards):
        # Skip synthetic dashboards — they wrap a single standalone sheet that Loop 1
        # already rendered as a full-canvas page.
        if dash.is_synthetic and _sheet_already_paged(dash, sheet_ids_with_page):
            continue

        page_id = f"ReportSection{len(page_ids) + 1}"
        page_dir = rd / "pages" / page_id

        leaves = list(_iter_leaves(dash.layout_tree))
        per_sheet_filters: list[tuple[tuple[str, ...], list]] = []
        page_content_count = 0

        for z, leaf in enumerate(leaves):
            if leaf.position is None or leaf.position.w == 0 or leaf.position.h == 0:
                continue
            obj_kind = map_leaf_kind(leaf.kind)
            if obj_kind == PbiObjectKind.DROP:
                continue

            if obj_kind == PbiObjectKind.VISUAL:
                sheet_id = leaf.payload.get("sheet_id")
                sheet = sheet_by_id.get(sheet_id)
                if sheet is None or sheet.pbir_visual is None:
                    continue
                visual_count += 1
                visual_id = f"visual_{visual_count}"
                v_dir = page_dir / "visuals" / visual_id
                write_text(v_dir / "visual.json",
                           render_visual(visual_id, sheet.pbir_visual, leaf.position, z,
                                         field_lookup))
                sheet_to_visual[sheet.id] = visual_id
                field_ids = tuple(b.source_field_id for b in sheet.pbir_visual.encoding_bindings)
                rendered_visuals.append({
                    "page_id": page_id, "visual_id": visual_id, "sheet_id": sheet.id,
                    "field_ids": field_ids,
                })
                per_sheet_filters.append(((sheet.id,), list(sheet.filters)))
                page_content_count += 1

            elif obj_kind == PbiObjectKind.SLICER_FILTER:
                slicer_count += 1
                slicer_id = f"slicer_{slicer_count}"
                s_dir = page_dir / "visuals" / slicer_id
                source_field_id = leaf.payload.get("field_id", "")
                write_text(s_dir / "visual.json",
                           render_filter_slicer(slicer_id, source_field_id, leaf.position, z,
                                                field_lookup))
                page_content_count += 1

            elif obj_kind == PbiObjectKind.SLICER_PARAMETER:
                pid = leaf.payload.get("parameter_id", "")
                p = parameter_by_id.get(pid)
                if p is None:
                    continue
                slicer_count += 1
                slicer_id = f"slicer_{slicer_count}"
                s_dir = page_dir / "visuals" / slicer_id
                write_text(s_dir / "visual.json",
                           render_parameter_slicer(slicer_id, p.name, p.intent.value,
                                                   leaf.position, z))
                page_content_count += 1
            # TEXTBOX / IMAGE / NAV_BUTTON / PLACEHOLDER / LEGEND_SUPPRESS — v1 skips emission

        if page_content_count == 0:
            continue  # No renderable content — skip writing page.json and adding to pageOrder

        page_ids.append(page_id)
        page_filters = collect_page_filters(per_sheet_filters, field_lookup)
        write_text(page_dir / "page.json",
                   render_page(page_id, dash.name,
                               width=dash.size.w or 1280, height=dash.size.h or 720,
                               filters=page_filters))

    write_text(rd / "pages" / "pages.json",
               render_pages_manifest(page_order=page_ids))
    write_text(rd / "report.json", render_report_json())
    write_text(rd / "version.json", json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
        "version": "2.0.0",
    }, indent=2))

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


def _sheet_already_paged(dash, sheet_ids_with_page: set[str]) -> bool:
    """Return True if every sheet leaf in this dashboard already has a full-canvas page."""
    sheet_leaves = [
        l for l in _iter_leaves(dash.layout_tree) if l.kind == LeafKind.SHEET
    ]
    return bool(sheet_leaves) and all(
        l.payload.get("sheet_id") in sheet_ids_with_page for l in sheet_leaves
    )


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
