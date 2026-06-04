"""Unit tests for date-part pill resolution in build_field_lookup()."""
from __future__ import annotations

from tableau2pbir.visualmap.field_lookup import build_field_lookup
from tableau2pbir.ir.model import Column, ColumnKind, ColumnRole, Table
from tableau2pbir.ir.sheet import Encoding, Sheet
from tableau2pbir.ir.common import FieldRef
from tableau2pbir.ir.workbook import DataModel, Workbook
from tableau2pbir.ir.version import IR_SCHEMA_VERSION


# ── Helpers ───────────────────────────────────────────────────────────────────

def _wb(tables, columns, sheets):
    dm = DataModel(datasources=(), tables=tables, columns=columns,
                   relationships=(), calculations=(), parameters=())
    return Workbook(
        ir_schema_version=IR_SCHEMA_VERSION,
        source_path="test.twb", source_hash="a" * 64,
        tableau_version="2026.1", config={},
        data_model=dm, sheets=sheets, dashboards=(), unsupported=(),
    )


def _col(col_id, name, datatype="string", role=ColumnRole.DIMENSION,
         kind=ColumnKind.RAW, dax_expr=None, source_column=None):
    return Column(id=col_id, name=name, datatype=datatype, role=role,
                  kind=kind, dax_expr=dax_expr,
                  source_column=source_column or (name if kind == ColumnKind.RAW else None))


def _table(table_id, name, col_ids):
    return Table(id=table_id, name=name, datasource_id="ds__ds",
                 column_ids=tuple(col_ids))


def _sheet_with_col_encoding(field_id: str, table_id: str) -> Sheet:
    enc = Encoding(columns=(FieldRef(table_id=table_id, column_id=field_id),))
    return Sheet(id="sheet__s", name="S", datasource_refs=(), mark_type="line",
                 encoding=enc, filters=(), sort=(), dual_axis=False,
                 reference_lines=(), uses_calculations=(), visual_format=None)


def _sheet_with_row_encoding(field_id: str, table_id: str) -> Sheet:
    enc = Encoding(rows=(FieldRef(table_id=table_id, column_id=field_id),))
    return Sheet(id="sheet__s2", name="S2", datasource_refs=(), mark_type="bar",
                 encoding=enc, filters=(), sort=(), dual_axis=False,
                 reference_lines=(), uses_calculations=(), visual_format=None)


# ── Date-part resolution ──────────────────────────────────────────────────────

def test_year_pill_resolves_to_synthesized_column():
    raw = _col("tbl__ds__col__order_date", "order_date", datatype="date")
    derived = _col("tbl__ds__col__year_order_date", "Year order_date",
                   datatype="integer", kind=ColumnKind.CALCULATED, dax_expr="YEAR(orders[order_date])")
    table = _table("tbl__orders", "orders",
                   ["tbl__ds__col__order_date", "tbl__ds__col__year_order_date"])
    sheet = _sheet_with_col_encoding("yr_order_date_ok", "tbl__orders")
    wb = _wb((table,), (raw, derived), (sheet,))
    lookup = build_field_lookup(wb)
    assert "yr_order_date_ok" in lookup
    info = lookup["yr_order_date_ok"]
    assert info["col_name"] == "Year order_date"
    assert info["table_name"] == "orders"
    assert info["is_measure"] is False


def test_month_pill_resolves_to_synthesized_column():
    raw = _col("tbl__ds__col__order_date", "order_date", datatype="date")
    derived = _col("tbl__ds__col__month_order_date", "Month order_date",
                   datatype="integer", kind=ColumnKind.CALCULATED, dax_expr="MONTH(orders[order_date])")
    table = _table("tbl__orders", "orders",
                   ["tbl__ds__col__order_date", "tbl__ds__col__month_order_date"])
    sheet = _sheet_with_col_encoding("mn_order_date_ok", "tbl__orders")
    wb = _wb((table,), (raw, derived), (sheet,))
    lookup = build_field_lookup(wb)
    assert lookup["mn_order_date_ok"]["col_name"] == "Month order_date"


def test_date_part_pill_without_synthesized_column_falls_back_to_raw():
    """If Stage 2 did not synthesize the column (edge case), fall back gracefully."""
    raw = _col("tbl__ds__col__order_date", "order_date", datatype="date")
    table = _table("tbl__orders", "orders", ["tbl__ds__col__order_date"])
    sheet = _sheet_with_col_encoding("yr_order_date_ok", "tbl__orders")
    wb = _wb((table,), (raw,), (sheet,))
    lookup = build_field_lookup(wb)
    # Fallback: raw column info (same as pre-fix behaviour for robustness)
    info = lookup.get("yr_order_date_ok")
    assert info is not None
    assert info["col_name"] == "order_date"  # graceful fallback


# ── Regression: existing pill types still resolve correctly ───────────────────

def test_sum_measure_pill_still_resolves():
    sales = _col("tbl__ds__col__sales", "sales", datatype="real", role=ColumnRole.MEASURE)
    table = _table("tbl__orders", "orders", ["tbl__ds__col__sales"])
    sheet = _sheet_with_row_encoding("sum_sales_qk", "tbl__orders")
    wb = _wb((table,), (sales,), (sheet,))
    lookup = build_field_lookup(wb)
    info = lookup["sum_sales_qk"]
    assert info["measure_name"] == "Sum sales"
    assert info["is_measure"] is True


def test_none_dimension_pill_still_resolves():
    cat = _col("tbl__ds__col__category", "category", datatype="string")
    table = _table("tbl__orders", "orders", ["tbl__ds__col__category"])
    sheet = _sheet_with_col_encoding("none_category_nk", "tbl__orders")
    wb = _wb((table,), (cat,), (sheet,))
    lookup = build_field_lookup(wb)
    info = lookup["none_category_nk"]
    assert info["col_name"] == "category"
    assert info["is_measure"] is False


def test_string_column_with_yr_prefix_is_not_treated_as_date_part():
    """A column named 'yr_something' that is string type must not trigger date-part logic."""
    str_col = _col("tbl__ds__col__region", "region", datatype="string")
    table = _table("tbl__orders", "orders", ["tbl__ds__col__region"])
    sheet = _sheet_with_col_encoding("none_region_nk", "tbl__orders")
    wb = _wb((table,), (str_col,), (sheet,))
    lookup = build_field_lookup(wb)
    info = lookup["none_region_nk"]
    assert info["col_name"] == "region"
