"""AI fallback for stage 4. Calls LLMClient.map_visual, builds a PbirVisual,
runs the validator, returns None on failure (caller routes to unsupported[])."""
from __future__ import annotations

from typing import Any

from tableau2pbir.ir.sheet import EncodingBinding, PbirVisual, Sheet
from tableau2pbir.llm.client import LLMClient
from tableau2pbir.visualmap.validator import validate_visual


def _sheet_subset(sheet: Sheet, fixture: str | None) -> dict[str, Any]:
    enc = sheet.encoding
    payload: dict[str, Any] = {
        "id": sheet.id,
        "mark_type": sheet.mark_type,
        "dual_axis": sheet.dual_axis,
        "shelves": {
            "rows":    [_ref(f) for f in enc.rows],
            "columns": [_ref(f) for f in enc.columns],
            "color":   [_ref(enc.color)] if enc.color else [],
            "size":    [_ref(enc.size)]  if enc.size  else [],
            "label":   [_ref(enc.label)] if enc.label else [],
            "tooltip": [_ref(enc.tooltip)] if enc.tooltip else [],
            "detail":  [_ref(f) for f in enc.detail],
            "shape":   [_ref(enc.shape)] if enc.shape else [],
            "angle":   [_ref(enc.angle)] if enc.angle else [],
        },
    }
    if fixture is not None:
        payload["fixture"] = fixture
    return payload


def _ref(fr: Any) -> dict[str, str]:
    return {"table_id": fr.table_id, "column_id": fr.column_id}


def map_visual_via_ai(
    sheet: Sheet, *, fixture: str | None, client: LLMClient,
    known_field_ids: frozenset[str],
) -> PbirVisual | None:
    response = client.map_visual(_sheet_subset(sheet, fixture))
    bindings = tuple(
        EncodingBinding(
            channel=str(b["channel"]),
            source_field_id=str(b["field_ref"]),
        )
        for b in response.get("encoding_bindings", [])
    )
    pv = PbirVisual(
        visual_type=str(response.get("visual_type", "")),
        encoding_bindings=bindings,
        format={},
    )
    if validate_visual(pv, known_field_ids=known_field_ids):
        return None
    return pv
