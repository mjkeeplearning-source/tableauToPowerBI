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
    if not v:
        return "null"
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
# Per-kind emit
# ---------------------------------------------------------------------------

def _emit_categorical(f: CategoricalFilter | ContextFilter) -> dict | None:
    table = f.field.table_id
    col = f.field.column_id
    alias = "f"

    include_vals = list(f.include)
    exclude_vals = list(f.exclude)

    if not include_vals and not exclude_vals:
        return None

    def _in_expr(values: list[str]) -> dict:
        return {
            "In": {
                "Expressions": [_alias_col_expr(alias, col)],
                "Values": [[_literal(v)] for v in values],
            }
        }

    if include_vals and not exclude_vals:
        condition = _in_expr(include_vals)
    elif exclude_vals and not include_vals:
        condition = {"Not": {"Expression": _in_expr(exclude_vals)}}
    else:
        condition = {
            "And": {
                "Left": _in_expr(include_vals),
                "Right": {"Not": {"Expression": _in_expr(exclude_vals)}},
            }
        }

    return {
        "name": f.id,
        "field": _entity_field(table, col, "Column"),
        "type": "Categorical",
        "filter": {
            "Version": 2,
            "From": [{"Name": alias, "Entity": table, "Type": 0}],
            "Where": [{"Condition": condition}],
        },
        "howCreated": "User",
        "isHiddenInViewMode": False,
    }


_AGG_PREFIX_TO_FUNC: dict[str, int] = {
    "sum": 0, "avg": 1, "average": 1, "cntd": 2, "ctd": 2,
    "min": 3, "max": 4, "cnt": 5, "median": 6,
}


def _emit_range(f: RangeFilter) -> dict | None:
    table = f.field.table_id
    col = f.field.column_id
    alias = "f"

    has_min = f.min_val is not None
    has_max = f.max_val is not None
    if not has_min and not has_max:
        return None

    if f.agg_prefix is not None:
        func_code = _AGG_PREFIX_TO_FUNC.get(f.agg_prefix.lower())
        if func_code is None:
            return None  # unknown prefix — skip

        agg_alias_expr = {
            "Aggregation": {
                "Function": func_code,
                "Expression": _alias_col_expr(alias, col),
            }
        }
        agg_entity_expr = {
            "Aggregation": {
                "Function": func_code,
                "Expression": {
                    "Column": {
                        "Expression": {"SourceRef": {"Entity": table}},
                        "Property": col,
                    }
                },
            }
        }
        where_conditions = []
        if has_min:
            where_conditions.append({"Condition": {"Comparison": {
                "ComparisonKind": 2,
                "Left": agg_alias_expr,
                "Right": _literal(f.min_val),
            }}})
        if has_max:
            where_conditions.append({"Condition": {"Comparison": {
                "ComparisonKind": 4,
                "Left": agg_alias_expr,
                "Right": _literal(f.max_val),
            }}})
        return {
            "name": f.id,
            "field": agg_entity_expr,
            "type": "Advanced",
            "filter": {
                "Version": 2,
                "From": [{"Name": alias, "Entity": table, "Type": 0}],
                "Where": where_conditions,
            },
            "howCreated": "User",
            "isHiddenInViewMode": False,
        }

    # Row-level range filter
    alias_col = _alias_col_expr(alias, col)
    if has_min and has_max:
        condition = {
            "Between": {
                "Expression": alias_col,
                "LowerBound": _literal(f.min_val),
                "UpperBound": _literal(f.max_val),
            }
        }
    elif has_min:
        condition = {"Comparison": {"ComparisonKind": 2, "Left": alias_col, "Right": _literal(f.min_val)}}
    else:
        condition = {"Comparison": {"ComparisonKind": 4, "Left": alias_col, "Right": _literal(f.max_val)}}

    return {
        "name": f.id,
        "field": _entity_field(table, col, "Column"),
        "type": "Range",
        "filter": {
            "Version": 2,
            "From": [{"Name": alias, "Entity": table, "Type": 0}],
            "Where": [{"Condition": condition}],
        },
        "howCreated": "User",
        "isHiddenInViewMode": False,
    }


def _filter_to_pbir(f: Filter) -> dict | None:
    """Return a FilterContainer dict, or None if this filter kind is deferred."""
    if isinstance(f, (CategoricalFilter, ContextFilter)):
        return _emit_categorical(f)
    if isinstance(f, RangeFilter):
        return _emit_range(f)
    # TopNFilter, ConditionalFilter — deferred
    return None


# ---------------------------------------------------------------------------
# Page filter collection
# ---------------------------------------------------------------------------

def collect_page_filters(per_sheet: list[tuple[tuple[str, ...], list]]) -> list[dict]:
    seen_keys: set[tuple] = set()
    out: list[dict] = []
    for _sheet_ids, filters in per_sheet:
        for f in filters:
            if isinstance(f, (CategoricalFilter, ContextFilter)):
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
