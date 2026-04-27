"""Tableau (mark_type, shelf_signature) → PBIR (visual_type, bindings).

v1 dispatch table. Mark types not covered return None so the caller falls
back to AI or routes to unsupported[]."""
from __future__ import annotations

from tableau2pbir.ir.common import FieldRef
from tableau2pbir.ir.sheet import EncodingBinding, PbirVisual, Sheet


def _bind(channel: str, fr: FieldRef) -> EncodingBinding:
    return EncodingBinding(channel=channel, source_field_id=fr.column_id)


def _has(rows: tuple[FieldRef, ...]) -> FieldRef | None:
    return rows[0] if rows else None


def dispatch_visual(sheet: Sheet) -> PbirVisual | None:
    mark = sheet.mark_type
    enc = sheet.encoding
    rows = enc.rows
    cols = enc.columns
    color = enc.color

    if mark in ("bar", "automatic") and rows and cols:
        bindings = [_bind("category", rows[0]), _bind("value", cols[0])]
        if color:
            bindings.append(_bind("series", color))
        return PbirVisual(
            visual_type="clusteredBarChart",
            encoding_bindings=tuple(bindings),
            format={},
        )

    if mark == "line" and rows and cols:
        bindings = [_bind("category", cols[0]), _bind("value", rows[0])]
        if color:
            bindings.append(_bind("series", color))
        return PbirVisual(
            visual_type="lineChart",
            encoding_bindings=tuple(bindings),
            format={},
        )

    if mark == "area" and rows and cols:
        return PbirVisual(
            visual_type="areaChart",
            encoding_bindings=(
                _bind("category", cols[0]), _bind("value", rows[0]),
            ),
            format={},
        )

    if mark in ("circle", "shape", "scatter") and rows and cols:
        bindings = [_bind("x", cols[0]), _bind("y", rows[0])]
        if enc.size:
            bindings.append(_bind("size", enc.size))
        if color:
            bindings.append(_bind("color", color))
        return PbirVisual(
            visual_type="scatterChart",
            encoding_bindings=tuple(bindings),
            format={},
        )

    if mark == "pie" and rows:
        bindings = [_bind("value", rows[0])]
        if color:
            bindings.insert(0, _bind("category", color))
        return PbirVisual(
            visual_type="pieChart",
            encoding_bindings=tuple(bindings),
            format={},
        )

    if mark == "text":
        bindings = []
        for r in rows:
            bindings.append(_bind("values", r))
        for c in cols:
            bindings.append(_bind("values", c))
        if not bindings:
            return None
        return PbirVisual(
            visual_type="tableEx",
            encoding_bindings=tuple(bindings),
            format={},
        )

    if mark == "map" and rows and cols:
        return PbirVisual(
            visual_type="filledMap",
            encoding_bindings=(
                _bind("location", cols[0]), _bind("value", rows[0]),
            ),
            format={},
        )

    return None
