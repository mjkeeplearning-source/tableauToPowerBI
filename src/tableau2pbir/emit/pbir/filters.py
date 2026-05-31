"""Workbook + page filter promotion."""
from __future__ import annotations

from tableau2pbir.ir.sheet import (
    CategoricalFilter, ContextFilter, Filter, RangeFilter, TopNFilter, ConditionalFilter,
)


def collect_page_filters(per_sheet: list[tuple[tuple[str, ...], list[Filter]]]) -> list[dict]:
    seen_keys: set[tuple] = set()
    out: list[dict] = []
    for _sheet_ids, filters in per_sheet:
        for f in filters:
            if isinstance(f, (CategoricalFilter, ContextFilter)):
                key = (f.field.table_id, f.field.column_id, f.kind, tuple(f.include), tuple(f.exclude))
            elif isinstance(f, RangeFilter):
                key = (f.field.table_id, f.field.column_id, f.kind, f.min_val, f.max_val, f.agg_prefix)
            else:
                key = (f.field.table_id, f.field.column_id, f.kind)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            result = _filter_to_pbir(f)
            if result is not None:
                out.append(result)
    return out


def _filter_to_pbir(f: Filter) -> dict | None:
    # Categorical/context emit is a temporary placeholder (schema-invalid structure).
    # Full schema-valid emit (correct type casing, FilterDefinition body, Entity SourceRef)
    # is implemented in Tasks 7-8.
    if isinstance(f, (CategoricalFilter, ContextFilter)):
        obj: dict = {
            "name": f.id,
            "type": f.kind,
            "field": {
                "Column": {
                    "Expression": {"SourceRef": {"Source": f.field.table_id}},
                    "Property": f.field.column_id,
                },
            },
            "filter": {"include": list(f.include), "exclude": list(f.exclude)},
        }
        return obj
    # All other kinds (RangeFilter, TopNFilter, ConditionalFilter) — not yet implemented
    return None
