"""Stage 4 — map visuals. See spec §6 Stage 4 + §16 v1 mark scope."""
from __future__ import annotations

from typing import Any

from tableau2pbir.ir.common import UnsupportedItem
from tableau2pbir.ir.workbook import Workbook
from tableau2pbir.llm.client import LLMClient
from tableau2pbir.pipeline import StageContext, StageResult
from tableau2pbir.visualmap.ai_fallback import map_visual_via_ai
from tableau2pbir.visualmap.dispatch import dispatch_visual
from tableau2pbir.visualmap.summary import VisualMapStats, render_stage4_summary
from tableau2pbir.visualmap.validator import validate_visual

_AI_FALLBACK_MARKS = frozenset({
    "bar", "line", "area", "circle", "shape", "scatter",
    "pie", "text", "map", "automatic",
})


def _make_client(ctx: StageContext) -> LLMClient:
    return LLMClient(cache_dir=ctx.output_dir / ".llm-cache")


def _known_field_ids(wb: Workbook) -> frozenset[str]:
    fids: set[str] = set()
    for tbl in wb.data_model.tables:
        fids.update(tbl.column_ids)
    fids.update(c.id for c in wb.data_model.calculations)
    # Encoding FieldRef.column_ids use a different slug format than
    # table.column_ids; include them so dispatch-generated bindings validate.
    for sheet in wb.sheets:
        enc = sheet.encoding
        for fr in (*enc.rows, *enc.columns, *enc.detail):
            fids.add(fr.column_id)
        for opt in (enc.color, enc.size, enc.label, enc.tooltip, enc.shape, enc.angle):
            if opt:
                fids.add(opt.column_id)
    return frozenset(fids)


def run(input_json: dict[str, Any], ctx: StageContext) -> StageResult:
    wb = Workbook.model_validate(input_json)
    known_fids = _known_field_ids(wb)

    by_source: dict[str, int] = {}
    visual_hist: dict[str, int] = {}
    low_conf: list[str] = []
    unsupported_marks: dict[str, int] = {}
    new_unsupported: list[UnsupportedItem] = list(wb.unsupported)
    new_sheets = []

    client: LLMClient | None = None
    for sheet in wb.sheets:
        pv = dispatch_visual(sheet)
        chose_source = "rule" if pv is not None else None

        if pv is None and sheet.mark_type in _AI_FALLBACK_MARKS:
            if client is None:
                client = _make_client(ctx)
            pv = map_visual_via_ai(
                sheet, fixture=None, client=client,
                known_field_ids=known_fids,
            )
            chose_source = "ai" if pv is not None else None

        if pv is None:
            mt = sheet.mark_type
            unsupported_marks[mt] = unsupported_marks.get(mt, 0) + 1
            new_unsupported.append(UnsupportedItem(
                object_kind="mark", object_id=sheet.id,
                source_excerpt=mt,
                reason=f"Mark type {mt!r} not in v1 visual catalog",
                code=f"unsupported_mark_{mt}",
            ))
            new_sheets.append(sheet)
            by_source["skip"] = by_source.get("skip", 0) + 1
            continue

        errors = validate_visual(pv, known_field_ids=known_fids)
        if errors:
            new_unsupported.append(UnsupportedItem(
                object_kind="mark", object_id=sheet.id,
                source_excerpt="; ".join(errors)[:200],
                reason="visual binding validation failed",
                code="visual_binding_invalid",
            ))
            new_sheets.append(sheet)
            by_source["skip"] = by_source.get("skip", 0) + 1
            continue

        new_sheets.append(sheet.model_copy(update={"pbir_visual": pv}))
        src = chose_source or "rule"
        by_source[src] = by_source.get(src, 0) + 1
        visual_hist[pv.visual_type] = visual_hist.get(pv.visual_type, 0) + 1

    new_wb = wb.model_copy(update={
        "sheets": tuple(new_sheets),
        "unsupported": tuple(new_unsupported),
    })
    stats = VisualMapStats(
        total_sheets=len(wb.sheets), by_source=by_source,
        visual_type_hist=visual_hist,
        ai_low_confidence_sheet_ids=tuple(low_conf),
        unsupported_mark_types=unsupported_marks,
    )
    return StageResult(
        output=new_wb.model_dump(mode="json"),
        summary_md=render_stage4_summary(stats),
        errors=(),
    )
