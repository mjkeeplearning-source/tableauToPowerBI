"""Stage 2 sheet builder. Produces IR Sheets from raw extract worksheets
and surfaces quick-table-calc pill modifiers as deferred-feature
UnsupportedItems (v1 defers table_calc kinds per §16)."""
from __future__ import annotations

from typing import Any

from tableau2pbir.ir.common import FieldRef, UnsupportedItem
from tableau2pbir.ir.sheet import Encoding, Filter, ReferenceLine, Sheet, SortSpec
from tableau2pbir.util.ids import stable_id


def _ref(column_name: str, table_id: str) -> FieldRef:
    return FieldRef(table_id=table_id, column_id=stable_id("", column_name).lstrip("_"))


def _build_encoding(raw_enc: dict[str, Any], table_id: str) -> Encoding:
    def r(name: str | None) -> FieldRef | None:
        return _ref(name, table_id) if name else None
    return Encoding(
        rows=tuple(_ref(n, table_id) for n in raw_enc.get("rows", ())),
        columns=tuple(_ref(n, table_id) for n in raw_enc.get("columns", ())),
        color=r(raw_enc.get("color")),
        size=r(raw_enc.get("size")),
        label=r(raw_enc.get("label")),
        tooltip=r(raw_enc.get("tooltip")),
        detail=tuple(_ref(n, table_id) for n in raw_enc.get("detail", ())),
        shape=r(raw_enc.get("shape")),
        angle=r(raw_enc.get("angle")),
    )


def _build_filter(raw_f: dict[str, Any], sheet_idx: int, filter_idx: int, table_id: str) -> Filter:
    return Filter(
        id=f"filter__s{sheet_idx}_{filter_idx}",
        kind=raw_f["kind"],
        field=_ref(raw_f["column"], table_id),
        include=tuple(raw_f.get("include", ())),
        exclude=tuple(raw_f.get("exclude", ())),
        expr=raw_f.get("expr"),
    )


def _build_sort(raw_sorts: list[dict[str, Any]], table_id: str) -> tuple[SortSpec, ...]:
    return tuple(
        SortSpec(field=_ref(s["column"], table_id), direction=s["direction"])
        for s in raw_sorts
    )


def _build_reference_lines(
    raw_rls: list[dict[str, Any]], sheet_idx: int, table_id: str,
) -> tuple[ReferenceLine, ...]:
    out: list[ReferenceLine] = []
    for idx, rl in enumerate(raw_rls):
        scope = rl.get("scope_column") or ""
        if not scope:
            continue
        value_str = rl.get("value")
        try:
            value_num: float | None = float(value_str) if value_str is not None else None
        except ValueError:
            value_num = None
        out.append(ReferenceLine(
            id=f"refline__s{sheet_idx}_{idx}",
            scope_field=_ref(scope, table_id),
            kind=rl["kind"],
            value=value_num,
            lod_expr=None,
        ))
    return tuple(out)


def build_sheets(
    raw_worksheets: list[dict[str, Any]],
    calc_names: set[str],
    table_id_for_ref: dict[str, str],
) -> tuple[tuple[Sheet, ...], tuple[UnsupportedItem, ...]]:
    sheets: list[Sheet] = []
    qtc_unsupported: list[UnsupportedItem] = []

    for idx, raw in enumerate(raw_worksheets):
        ds_refs = raw["datasource_refs"]
        table_id = table_id_for_ref.get(ds_refs[0]) if ds_refs else "tbl__unknown"
        if table_id is None:
            table_id = "tbl__unknown"

        used_names: list[str] = []
        for channel in ("rows", "columns", "detail"):
            for name in raw["encodings"].get(channel, ()):
                if name in calc_names and name not in used_names:
                    used_names.append(name)
        for channel in ("color", "size", "label", "tooltip", "shape", "angle"):
            name = raw["encodings"].get(channel)
            if name and name in calc_names and name not in used_names:
                used_names.append(name)
        uses_calculations = tuple(stable_id("calc", n) for n in used_names)

        filters = tuple(
            _build_filter(f, idx, fi, table_id)
            for fi, f in enumerate(raw["filters"])
        )
        sheet_id = stable_id("sheet", raw["name"])
        sheets.append(Sheet(
            id=sheet_id,
            name=raw["name"],
            datasource_refs=tuple(stable_id("ds", d) for d in ds_refs),
            mark_type=raw["mark_type"],
            encoding=_build_encoding(raw["encodings"], table_id),
            filters=filters,
            sort=_build_sort(raw["sort"], table_id),
            dual_axis=raw["dual_axis"],
            reference_lines=_build_reference_lines(raw["reference_lines"], idx, table_id),
            format=None,
            uses_calculations=uses_calculations,
        ))

        for qtc in raw.get("quick_table_calcs", []):
            qtc_unsupported.append(UnsupportedItem(
                object_kind="calc",
                object_id=f"{sheet_id}__qtc__{qtc['type']}__{stable_id('', qtc['column'])}",
                source_excerpt=f"sheet={raw['name']!r} column={qtc['column']!r} type={qtc['type']!r}",
                reason="Quick table calculation — deferred to v1.1 behind --with-table-calcs.",
                code="deferred_feature_table_calcs",
            ))

    return tuple(sheets), tuple(qtc_unsupported)
