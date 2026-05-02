"""Tests for translate/col_qualifier — column reference mapping and qualification."""
from __future__ import annotations

import pytest

from tableau2pbir.ir.model import Column, ColumnKind, ColumnRole, Table
from tableau2pbir.ir.workbook import DataModel
from tableau2pbir.translate.col_qualifier import build_col_context, qualify_bracket_refs


def _col(id: str, name: str, kind: ColumnKind = ColumnKind.RAW) -> Column:
    return Column(
        id=id, name=name, datatype="string",
        role=ColumnRole.DIMENSION, kind=kind,
    )


def _table(id: str, name: str, col_ids: list[str]) -> Table:
    return Table(id=id, name=name, datasource_id="ds1", column_ids=tuple(col_ids))


# ---------------------------------------------------------------------------
# qualify_bracket_refs
# ---------------------------------------------------------------------------

def test_qualify_simple_column_ref():
    col_ref_map = {"order_id": ("orders", "order_id")}
    result = qualify_bracket_refs("[order_id]", col_ref_map)
    assert result == "'orders'[order_id]"


def test_qualify_disambiguation_suffix_ref():
    col_ref_map = {"order_id (returns)": ("returns", "order_id")}
    result = qualify_bracket_refs("[order_id (returns)]", col_ref_map)
    assert result == "'returns'[order_id]"


def test_qualify_ref_inside_aggregate():
    col_ref_map = {"order_id": ("orders", "order_id")}
    result = qualify_bracket_refs("DISTINCTCOUNT([order_id])", col_ref_map)
    assert result == "DISTINCTCOUNT('orders'[order_id])"


def test_qualify_compound_expression_both_refs():
    col_ref_map = {
        "order_id": ("orders", "order_id"),
        "order_id (returns)": ("returns", "order_id"),
    }
    result = qualify_bracket_refs(
        "DISTINCTCOUNT([order_id]) - DISTINCTCOUNT([order_id (returns)])",
        col_ref_map,
    )
    assert result == "DISTINCTCOUNT('orders'[order_id]) - DISTINCTCOUNT('returns'[order_id])"


def test_leaves_unknown_ref_unchanged():
    col_ref_map = {"other_col": ("t", "other_col")}
    result = qualify_bracket_refs("[SomeMeasure]", col_ref_map)
    assert result == "[SomeMeasure]"


def test_leaves_already_qualified_ref_unchanged():
    col_ref_map = {"profit": ("orders", "profit")}
    result = qualify_bracket_refs("SUM('orders'[profit])", col_ref_map)
    assert result == "SUM('orders'[profit])"


def test_empty_col_ref_map_returns_expr_unchanged():
    result = qualify_bracket_refs("DISTINCTCOUNT([order_id])", {})
    assert result == "DISTINCTCOUNT([order_id])"


# ---------------------------------------------------------------------------
# build_col_context
# ---------------------------------------------------------------------------

def test_build_col_context_single_table():
    c1 = _col("c1", "order_id")
    c2 = _col("c2", "profit")
    t1 = _table("t1", "orders", ["c1", "c2"])
    dm = DataModel(tables=(t1,), columns=(c1, c2))

    col_ref_map, columns_by_table = build_col_context(dm)

    assert col_ref_map["order_id"] == ("orders", "order_id")
    assert col_ref_map["profit"] == ("orders", "profit")
    assert columns_by_table["orders"] == ["order_id", "profit"]


def test_build_col_context_disambiguation_variant_created():
    c1 = _col("c1", "order_id")
    t1 = _table("t1", "orders", ["c1"])
    dm = DataModel(tables=(t1,), columns=(c1,))

    col_ref_map, _ = build_col_context(dm)

    assert col_ref_map["order_id (orders)"] == ("orders", "order_id")


def test_build_col_context_multi_table_first_table_wins_for_simple_ref():
    c_orders = _col("c1", "order_id")
    c_returns = _col("c2", "order_id")
    t_orders = _table("t1", "orders", ["c1"])
    t_returns = _table("t2", "returns", ["c2"])
    dm = DataModel(tables=(t_orders, t_returns), columns=(c_orders, c_returns))

    col_ref_map, _ = build_col_context(dm)

    assert col_ref_map["order_id"] == ("orders", "order_id")
    assert col_ref_map["order_id (orders)"] == ("orders", "order_id")
    assert col_ref_map["order_id (returns)"] == ("returns", "order_id")


def test_build_col_context_columns_by_table_multi_table():
    c1 = _col("c1", "order_id")
    c2 = _col("c2", "returned")
    t1 = _table("t1", "orders", ["c1"])
    t2 = _table("t2", "returns", ["c2"])
    dm = DataModel(tables=(t1, t2), columns=(c1, c2))

    _, columns_by_table = build_col_context(dm)

    assert columns_by_table["orders"] == ["order_id"]
    assert columns_by_table["returns"] == ["returned"]


def test_build_col_context_excludes_calculated_columns():
    c_raw = _col("c1", "profit", ColumnKind.RAW)
    c_calc = _col("c2", "Margin", ColumnKind.CALCULATED)
    t1 = _table("t1", "orders", ["c1", "c2"])
    dm = DataModel(tables=(t1,), columns=(c_raw, c_calc))

    col_ref_map, columns_by_table = build_col_context(dm)

    assert "profit" in col_ref_map
    assert "Margin" not in col_ref_map
    assert "profit" in columns_by_table["orders"]
    assert "Margin" not in columns_by_table["orders"]


def test_build_col_context_real_ir_disambiguation_col():
    """Stage 2 sets col.name='order_id (returns)', source_column='order_id' for
    cross-table columns.  build_col_context must use source_column as the DAX name."""
    c_orders = _col("c1", "order_id")
    c_returns = Column(
        id="c2", name="order_id (returns)", datatype="string",
        role=ColumnRole.DIMENSION, kind=ColumnKind.RAW,
        source_column="order_id",
    )
    t_orders = _table("t1", "orders", ["c1"])
    t_returns = _table("t2", "returns", ["c2"])
    dm = DataModel(tables=(t_orders, t_returns), columns=(c_orders, c_returns))

    col_ref_map, columns_by_table = build_col_context(dm)

    assert col_ref_map["order_id"] == ("orders", "order_id")
    assert col_ref_map["order_id (returns)"] == ("returns", "order_id")
    assert columns_by_table["returns"] == ["order_id"]


def test_build_col_context_empty_data_model():
    dm = DataModel()
    col_ref_map, columns_by_table = build_col_context(dm)
    assert col_ref_map == {}
    assert columns_by_table == {}
