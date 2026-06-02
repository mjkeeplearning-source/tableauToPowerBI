"""Tableau (mark_type, shelf_signature) → PBIR (visual_type, bindings).

v1 dispatch table. Mark types not covered return None so the caller falls
back to AI or routes to unsupported[]."""
from __future__ import annotations

from tableau2pbir.ir.common import FieldRef
from tableau2pbir.ir.sheet import EncodingBinding, MarkStyle, PbirVisual, Sheet, VisualSortEntry


def _bind(channel: str, fr: FieldRef) -> EncodingBinding:
    return EncodingBinding(channel=channel, source_field_id=fr.column_id)


def _is_measure(fr: FieldRef) -> bool:
    """Infer measure role from the _qk suffix embedded by stable_id in the column_id."""
    return fr.column_id.endswith("_qk")


def _build_format_objects(mark_style: MarkStyle | None) -> dict[str, list[dict]]:
    if mark_style is None:
        return {}
    objects: dict[str, list[dict]] = {}
    if mark_style.labels_show:
        objects["labels"] = [
            {"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}
        ]
    if mark_style.mark_color:
        objects["dataPoint"] = [
            {"properties": {"fill": {"solid": {"color": {
                "expr": {"Literal": {"Value": f"'{mark_style.mark_color}'"}}
            }}}}}
        ]
    return objects


def _build_sort_entries(
    sheet: Sheet,
    existing_bindings: list[EncodingBinding],
) -> tuple[tuple[EncodingBinding, ...], tuple[VisualSortEntry, ...]]:
    """Return (extra_bindings, sort_entries) from computed sorts.

    Extra bindings add the sort-by measure to Values if not already present.
    """
    extra: list[EncodingBinding] = []
    entries: list[VisualSortEntry] = []
    existing_ids = {b.source_field_id for b in existing_bindings}
    for s in sheet.sort:
        if s.sort_by_field is None:
            continue
        fid = s.sort_by_field.column_id
        if fid not in existing_ids and not any(b.source_field_id == fid for b in extra):
            extra.append(_bind("Values", s.sort_by_field))
        entries.append(VisualSortEntry(field_id=fid, direction=s.direction))
    return tuple(extra), tuple(entries)


def dispatch_visual(sheet: Sheet) -> PbirVisual | None:
    mark = sheet.mark_type
    enc = sheet.encoding
    rows = enc.rows
    cols = enc.columns
    color = enc.color
    fmt = _build_format_objects(sheet.mark_style)

    if mark in ("bar", "automatic") and rows and not cols:
        # Dimension-only rows (Tableau nested-header / cross-tab): map to Table visual.
        if all(not _is_measure(r) for r in rows):
            bindings = [_bind("Values", r) for r in rows]
            existing_ids = {r.column_id for r in rows}
            if enc.text and enc.text.column_id not in existing_ids:
                bindings.append(_bind("Values", enc.text))
            extra_sort, sort_entries = _build_sort_entries(sheet, bindings)
            bindings.extend(extra_sort)
            return PbirVisual(
                visual_type="tableEx",
                encoding_bindings=tuple(bindings),
                format=fmt,
                sort_by=sort_entries,
            )

    if mark in ("bar", "automatic") and rows and cols:
        # Horizontal bar: Tableau places measure on COLUMNS shelf, dimension on ROWS
        if _is_measure(cols[0]) and not _is_measure(rows[0]):
            bindings = [_bind("Category", rows[0])] + [_bind("Y", c) for c in cols]
            if color:
                bindings.append(_bind("Series", color))
            return PbirVisual(visual_type="barChart", encoding_bindings=tuple(bindings), format=fmt)
        # Vertical bar (default): COLUMNS=dimension→Category, ROWS=measure(s)→Y
        bindings = [_bind("Category", cols[0])] + [_bind("Y", r) for r in rows]
        if color:
            bindings.append(_bind("Series", color))
        return PbirVisual(visual_type="columnChart", encoding_bindings=tuple(bindings), format=fmt)

    if mark == "line" and rows and cols:
        bindings = [_bind("Category", cols[0])] + [_bind("Y", r) for r in rows]
        if color:
            bindings.append(_bind("Series", color))
        return PbirVisual(visual_type="lineChart", encoding_bindings=tuple(bindings), format=fmt)

    if mark == "area" and rows and cols:
        return PbirVisual(
            visual_type="areaChart",
            encoding_bindings=(_bind("Category", cols[0]), _bind("Y", rows[0])),
            format=fmt,
        )

    if mark in ("circle", "shape", "scatter") and rows and cols:
        bindings = [_bind("X", cols[0]), _bind("Y", rows[0])]
        if enc.size:
            bindings.append(_bind("Size", enc.size))
        if color:
            bindings.append(_bind("Color", color))
        return PbirVisual(visual_type="scatterChart", encoding_bindings=tuple(bindings), format=fmt)

    if mark == "pie" and rows:
        bindings = [_bind("Y", rows[0])]
        if color:
            bindings.insert(0, _bind("Category", color))
        return PbirVisual(visual_type="pieChart", encoding_bindings=tuple(bindings), format=fmt)

    if mark == "text":
        bindings = [_bind("Values", r) for r in rows] + [_bind("Values", c) for c in cols]
        existing_ids = {f.column_id for f in rows} | {f.column_id for f in cols}
        if enc.text and enc.text.column_id not in existing_ids:
            bindings.append(_bind("Values", enc.text))
        extra_sort, sort_entries = _build_sort_entries(sheet, bindings)
        bindings.extend(extra_sort)
        if not bindings:
            return None
        return PbirVisual(
            visual_type="tableEx",
            encoding_bindings=tuple(bindings),
            format=fmt,
            sort_by=sort_entries,
        )

    if mark == "map" and rows and cols:
        return PbirVisual(
            visual_type="filledMap",
            encoding_bindings=(_bind("Location", cols[0]), _bind("Y", rows[0])),
            format=fmt,
        )

    return None
