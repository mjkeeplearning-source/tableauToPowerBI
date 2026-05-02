"""Collect implicit DAX measures for raw columns aggregated in Tableau visuals.

When Tableau uses SUM([profit]) on a shelf it creates a pill slug sum_profit_qk.
The column 'profit' exists in the TMDL as a plain column, not a named measure.
Power BI visual.json references it as a Measure, so a named DAX measure must exist.
This module derives those measures from the pill slug prefixes in visual bindings.
"""
from __future__ import annotations

import re

from tableau2pbir.ir.workbook import Workbook
from tableau2pbir.visualmap.field_lookup import build_field_lookup

_PILL_RE = re.compile(r'^([a-z]+)_(.+)_([a-z]{2})$')

_PREFIX_TO_DAX: dict[str, str] = {
    "sum":  "SUM",
    "avg":  "AVERAGE",
    "min":  "MIN",
    "max":  "MAX",
    "cnt":  "COUNT",
    "cntd": "DISTINCTCOUNT",
    "med":  "MEDIAN",
}

_MEASURE_SUFFIX = "qk"


def collect_implicit_measures(wb: Workbook) -> dict[str, list[tuple[str, str]]]:
    """Return {table_name: [(measure_name, dax_expr), ...]} for all measure-pill
    fields in visual bindings that lack an explicit Calculation entry.

    Only pills with the quantitative suffix ('qk') and a known aggregation prefix
    are included. Ordinal ('ok') and nominal ('nk') pills are skipped.
    """
    existing_calc_names = {c.name for c in wb.data_model.calculations}
    field_lookup = build_field_lookup(wb)

    result: dict[str, list[tuple[str, str]]] = {}
    seen: set[tuple[str, str]] = set()  # (table_name, measure_name)

    for sheet in wb.sheets:
        if sheet.pbir_visual is None:
            continue
        for binding in sheet.pbir_visual.encoding_bindings:
            field_id = binding.source_field_id
            m = _PILL_RE.match(field_id)
            if not m:
                continue
            prefix, suffix = m.group(1), m.group(3)
            if suffix != _MEASURE_SUFFIX:
                continue
            dax_func = _PREFIX_TO_DAX.get(prefix)
            if dax_func is None:
                continue
            info = field_lookup.get(field_id)
            if info is None:
                continue
            table_name: str = info["table_name"]
            col_name: str = info["col_name"]
            if col_name in existing_calc_names:
                continue
            key = (table_name, col_name)
            if key in seen:
                continue
            seen.add(key)
            dax_expr = f"{dax_func}('{table_name}'[{col_name}])"
            result.setdefault(table_name, []).append((col_name, dax_expr))

    return result
