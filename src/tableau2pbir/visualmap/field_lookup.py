"""Map FieldRef.column_id (Tableau pill slug) -> PBI field info for visual emission.

Tableau pill slugs use the format {prefix}_{body}_{2char_suffix} after slugification,
e.g. none_category_nk, usr_calculation_0390937790091264_qk.
DataModel column IDs use tbl__{ds}__col__{name}. We bridge them by extracting
the body slug from the pill and matching it against slug_id(col.name).
"""
from __future__ import annotations

import re

from tableau2pbir.ir.model import ColumnRole
from tableau2pbir.ir.workbook import Workbook
from tableau2pbir.util.ids import slug_id

# Matches Tableau pill slugs: {prefix}_{body}_{2_alpha_suffix}
# e.g. none_category_nk, usr_calculation_01_qk
# Does NOT match datasource markers like federated_17kv...8 (end in digit, not alpha)
_PILL_RE = re.compile(r'^([a-z]+)_(.+)_([a-z]{2})$')

# Aggregation prefixes that denote an implicit measure on a plain column.
# usr/none/yr/qr/mn/wk/dy/hr are dimension or user-calc prefixes — no display prefix.
_AGG_PREFIX_DISPLAY: dict[str, str] = {
    "sum":  "Sum",
    "avg":  "Avg",
    "min":  "Min",
    "max":  "Max",
    "cnt":  "Count",
    "cntd": "Count Distinct",
    "med":  "Median",
}

_MEASURE_SUFFIX = "qk"

_DATE_PART_PREFIX: dict[str, str] = {
    "yr": "Year",
    "qr": "Quarter",
    "mn": "Month",
    "wk": "Week",
    "dy": "Day",
    "hr": "Hour",
    "mi": "Minute",
    "sc": "Second",
}


def build_field_lookup(wb: Workbook) -> dict[str, dict]:
    """Return mapping: FieldRef.column_id -> {table_name, col_name, is_measure}."""
    col_by_id = {c.id: c for c in wb.data_model.columns}

    # base_slug -> {table_name, col_name, is_measure}
    # base_slug = slug_id(col.name), e.g. "category" or "calculation_0390937790091264"
    by_base: dict[str, dict] = {}
    for table in wb.data_model.tables:
        for col_id in table.column_ids:
            col = col_by_id.get(col_id)
            if col is None:
                continue
            by_base[slug_id(col.name)] = {
                "table_name": table.name,
                "col_name": col.name,
                "is_measure": col.role == ColumnRole.MEASURE,
                "datatype": col.datatype,
            }

    # For calculations, replace col_name with the user-facing display name.
    # Column.name stores the internal name (Calculation_0390937790091264),
    # Calculation.name stores what the user named it (DeltaOrder).
    for calc in wb.data_model.calculations:
        internal_slug = slug_id(calc.id.removeprefix("calc__"))
        if internal_slug in by_base:
            by_base[internal_slug] = {**by_base[internal_slug], "col_name": calc.name}

    # Also map direct column IDs (tbl__ds__col__name) → info, so slicer field_ids
    # (which are raw column IDs, not pill slugs) can be resolved correctly.
    col_id_lookup: dict[str, dict] = {}
    for table in wb.data_model.tables:
        for col_id in table.column_ids:
            col = col_by_id.get(col_id)
            if col is None:
                continue
            col_id_lookup[col_id] = {
                "table_name": table.name,
                "col_name": col.name,
                "is_measure": col.role == ColumnRole.MEASURE,
                "datatype": col.datatype,
                "measure_name": col.name,
            }

    # Resolve each FieldRef.column_id seen in sheet encodings and filters
    lookup: dict[str, dict] = dict(col_id_lookup)  # seed with direct col IDs
    for sheet in wb.sheets:
        enc = sheet.encoding
        refs = list(enc.rows) + list(enc.columns) + list(enc.detail)
        for opt in (enc.color, enc.size, enc.label, enc.tooltip, enc.shape, enc.angle, enc.text):
            if opt:
                refs.append(opt)
        # Also include filter fields so filter emission can resolve pill slugs.
        for f in sheet.filters:
            refs.append(f.field)
        # Include sort-by measure refs so computed-sort emission resolves correctly.
        for s in sheet.sort:
            if s.sort_by_field:
                refs.append(s.sort_by_field)
        for fr in refs:
            field_id = fr.column_id
            if field_id in lookup:
                continue
            m = _PILL_RE.match(field_id)
            if not m:
                continue
            prefix, body, suffix = m.group(1), m.group(2), m.group(3)
            if body not in by_base:
                continue
            base = by_base[body]

            # Route date-part derivation pills to the synthesized calculated column.
            # e.g. yr_order_date_ok → "Year order_date" column, not raw "order_date".
            if prefix in _DATE_PART_PREFIX and base.get("datatype") in ("date", "datetime"):
                part_label = _DATE_PART_PREFIX[prefix]
                derived_col_name = f"{part_label} {base['col_name']}"
                derived_body_slug = slug_id(derived_col_name)
                if derived_body_slug in by_base:
                    derived = by_base[derived_body_slug]
                    lookup[field_id] = {**derived, "measure_name": derived["col_name"]}
                    continue
                # Synthesized column not present (edge case) — fall through to raw column.

            col_name = base["col_name"]
            # For implicit aggregation pills (e.g. sum_profit_qk), build the
            # display measure name that PBI uses: "Sum profit", "Avg sales", etc.
            # User-calc pills (usr_) and dimension pills keep col_name as-is.
            if suffix == _MEASURE_SUFFIX and prefix in _AGG_PREFIX_DISPLAY:
                measure_name = f"{_AGG_PREFIX_DISPLAY[prefix]} {col_name}"
            else:
                measure_name = col_name
            lookup[field_id] = {**base, "measure_name": measure_name}

    return lookup
