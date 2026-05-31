"""Stage 2 sheet builder. Produces IR Sheets from raw extract worksheets
and surfaces quick-table-calc pill modifiers as deferred-feature
UnsupportedItems (v1 defers table_calc kinds per §16)."""
from __future__ import annotations

from typing import Any

from tableau2pbir.ir.common import FieldRef, UnsupportedItem
from tableau2pbir.ir.sheet import (
    CategoricalFilter, ConditionalFilter, ContextFilter, Encoding, Filter,
    MarkStyle, RangeFilter, ReferenceLine, Sheet, SortSpec, TopNFilter,
)
from tableau2pbir.util.ids import stable_id


def _ref(column_name: str, table_id: str) -> FieldRef:
    return FieldRef(table_id=table_id, column_id=stable_id("", column_name).lstrip("_"))


def _is_datasource_marker(name: str) -> bool:
    """Tableau datasource markers use 'class.hash' format: contains '.' but no ':'."""
    return "." in name and ":" not in name


def _build_encoding(raw_enc: dict[str, Any], table_id: str) -> Encoding:
    def r(name: str | None) -> FieldRef | None:
        if not name or _is_datasource_marker(name):
            return None
        return _ref(name, table_id)
    return Encoding(
        rows=tuple(_ref(n, table_id) for n in raw_enc.get("rows", ()) if not _is_datasource_marker(n)),
        columns=tuple(_ref(n, table_id) for n in raw_enc.get("columns", ()) if not _is_datasource_marker(n)),
        color=r(raw_enc.get("color")),
        size=r(raw_enc.get("size")),
        label=r(raw_enc.get("label")),
        tooltip=r(raw_enc.get("tooltip")),
        detail=tuple(_ref(n, table_id) for n in raw_enc.get("detail", ()) if not _is_datasource_marker(n)),
        shape=r(raw_enc.get("shape")),
        angle=r(raw_enc.get("angle")),
    )


def _build_filter(raw_f: dict[str, Any], sheet_idx: int, filter_idx: int, table_id: str) -> Filter:
    fid = f"filter__s{sheet_idx}_{filter_idx}"
    field = _ref(raw_f["column"], table_id)
    kind = raw_f["kind"]
    if kind == "categorical":
        return CategoricalFilter(
            id=fid, field=field,
            include=tuple(raw_f.get("include", ())),
            exclude=tuple(raw_f.get("exclude", ())),
        )
    if kind == "range":
        return RangeFilter(
            id=fid, field=field,
            min_val=raw_f.get("min_val"),
            max_val=raw_f.get("max_val"),
            agg_prefix=raw_f.get("agg_prefix"),
        )
    if kind == "top_n":
        by_col = raw_f.get("by_column")
        return TopNFilter(
            id=fid, field=field,
            n=int(raw_f.get("n", 10)),
            direction=raw_f.get("direction", "Top"),
            by_field=_ref(by_col, table_id) if by_col else None,
            by_agg=raw_f.get("by_agg"),
        )
    if kind == "conditional":
        return ConditionalFilter(
            id=fid, field=field,
            expr=raw_f.get("expr"),
        )
    if kind == "context":
        return ContextFilter(
            id=fid, field=field,
            include=tuple(raw_f.get("include", ())),
            exclude=tuple(raw_f.get("exclude", ())),
        )
    # categorical + any unrecognised kind → CategoricalFilter
    return CategoricalFilter(
        id=fid, field=field,
        include=tuple(raw_f.get("include", ())),
        exclude=tuple(raw_f.get("exclude", ())),
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


def _build_mark_style(raw_style: dict[str, Any] | None) -> MarkStyle | None:
    if raw_style is None:
        return None
    return MarkStyle(
        mark_color=raw_style.get("mark_color"),
        labels_show=bool(raw_style.get("labels_show", False)),
    )


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
        for fi, fobj in enumerate(filters):
            if isinstance(fobj, TopNFilter):
                qtc_unsupported.append(UnsupportedItem(
                    object_kind="filter",
                    object_id=fobj.id,
                    source_excerpt=f"sheet={raw['name']!r} column={raw['filters'][fi]['column']!r} kind=top_n",
                    reason="TopN filter emission deferred to v1.1.",
                    code="deferred_feature_topn_filter",
                ))
            elif isinstance(fobj, ConditionalFilter):
                qtc_unsupported.append(UnsupportedItem(
                    object_kind="filter",
                    object_id=fobj.id,
                    source_excerpt=f"sheet={raw['name']!r} column={raw['filters'][fi]['column']!r} kind=conditional",
                    reason="Conditional filter emission deferred to v1.1.",
                    code="deferred_feature_conditional_filter",
                ))
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
            mark_style=_build_mark_style(raw.get("mark_style")),
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
