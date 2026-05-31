"""PBIR filter emission — builds schema-valid FilterDefinition bodies."""
from __future__ import annotations

from tableau2pbir.ir.sheet import (
    CategoricalFilter, ConditionalFilter, ContextFilter, Filter,
    RangeFilter, TopNFilter,
)


# ---------------------------------------------------------------------------
# Literal formatting
# ---------------------------------------------------------------------------

def _format_literal(value: str | None) -> str:
    """Convert a raw Tableau filter value to a PBI QueryLiteralExpression.Value string.

    Official formats per semanticQuery schema:
      Integer → "24L"   Double → "2.4D"   String → "'value'"
      DateTime → "datetime'YYYY-MM-DDThh:mm:ss'"   Null → "null"
    """
    if not value:
        return "null"
    v = value.strip()
    # Tableau date literal: #2023-01-03# or #2023-01-03 12:30:00#
    if v.startswith("#") and v.endswith("#"):
        inner = v[1:-1].strip()
        if " " in inner:
            date_part, time_part = inner.split(" ", 1)
            return f"datetime'{date_part}T{time_part}'"
        return f"datetime'{inner}T00:00:00'"
    # Numeric
    try:
        int_val = int(v)
        return f"{int_val}L"
    except ValueError:
        pass
    try:
        float(v)
        return f"{v}D"
    except ValueError:
        pass
    # String — escape single quotes by doubling them (DAX convention)
    escaped = v.replace("'", "''")
    return f"'{escaped}'"


# ---------------------------------------------------------------------------
# Expression builders
# ---------------------------------------------------------------------------

def _entity_field(table_name: str, col_name: str, field_type: str = "Column") -> dict:
    """Top-level FilterContainer.field using StandaloneSourceRefExpression (Entity key)."""
    return {
        field_type: {
            "Expression": {"SourceRef": {"Entity": table_name}},
            "Property": col_name,
        }
    }


def _alias_col_expr(alias: str, col_name: str) -> dict:
    """Column expression inside From/Where using QuerySourceRefExpression (Source key)."""
    return {
        "Column": {
            "Expression": {"SourceRef": {"Source": alias}},
            "Property": col_name,
        }
    }


def _literal(value: str | None) -> dict:
    return {"Literal": {"Value": _format_literal(value)}}


# ---------------------------------------------------------------------------
# Per-kind emit (stubbed — completed in subsequent tasks)
# ---------------------------------------------------------------------------

def _filter_to_pbir(f: Filter) -> dict | None:
    """Return a FilterContainer dict, or None if this filter kind is deferred."""
    return None  # placeholder — implemented in Tasks 7–9


# ---------------------------------------------------------------------------
# Page filter collection
# ---------------------------------------------------------------------------

def collect_page_filters(per_sheet: list[tuple[tuple[str, ...], list]]) -> list[dict]:
    seen_keys: set[tuple] = set()
    out: list[dict] = []
    for _sheet_ids, filters in per_sheet:
        for f in filters:
            if isinstance(f, CategoricalFilter):
                key = (f.field.table_id, f.field.column_id, f.kind, tuple(f.include), tuple(f.exclude))
            elif isinstance(f, ContextFilter):
                key = (f.field.table_id, f.field.column_id, f.kind, tuple(f.include), tuple(f.exclude))
            elif isinstance(f, RangeFilter):
                key = (f.field.table_id, f.field.column_id, f.kind, f.min_val, f.max_val)
            else:
                key = (f.field.table_id, f.field.column_id, f.kind)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            result = _filter_to_pbir(f)
            if result is not None:
                out.append(result)
    return out
