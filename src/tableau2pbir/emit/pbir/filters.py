"""Workbook + page filter promotion."""
from __future__ import annotations

from tableau2pbir.ir.sheet import Filter


def collect_page_filters(per_sheet: list[tuple[tuple[str, ...], list[Filter]]]) -> list[dict]:
    seen_keys: set[tuple] = set()
    out: list[dict] = []
    for _sheet_ids, filters in per_sheet:
        for f in filters:
            key = (f.field.table_id, f.field.column_id, f.kind, tuple(f.include), tuple(f.exclude))
            if key in seen_keys:
                continue
            seen_keys.add(key)
            out.append(_filter_to_pbir(f))
    return out


def _filter_to_pbir(f: Filter) -> dict:
    obj: dict = {
        "name": f.id,
        "type": f.kind,
        "field": {
            "Column": {
                "Expression": {"SourceRef": {"Source": f.field.table_id}},
                "Property": f.field.column_id,
            },
        },
    }
    if f.kind == "categorical":
        obj["filter"] = {"include": list(f.include), "exclude": list(f.exclude)}
    return obj
