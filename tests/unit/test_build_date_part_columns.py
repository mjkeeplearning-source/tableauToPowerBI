"""Unit tests for build_date_part_columns() in _build_data_model.py."""
from __future__ import annotations

import pytest

from tableau2pbir.stages._build_data_model import build_date_part_columns
from tableau2pbir.ir.model import Column, ColumnKind, ColumnRole, Table


# ── Test fixtures ─────────────────────────────────────────────────────────────

def _date_col(name: str = "order_date", table_prefix: str = "tbl__ds1") -> Column:
    return Column(
        id=f"{table_prefix}__col__{name}",
        name=name,
        datatype="date",
        role=ColumnRole.DIMENSION,
        kind=ColumnKind.RAW,
        source_column=name,
    )


def _real_col(name: str = "sales", table_prefix: str = "tbl__ds1") -> Column:
    return Column(
        id=f"{table_prefix}__col__{name}",
        name=name,
        datatype="real",
        role=ColumnRole.MEASURE,
        kind=ColumnKind.RAW,
        source_column=name,
    )


def _string_col(name: str = "category", table_prefix: str = "tbl__ds1") -> Column:
    return Column(
        id=f"{table_prefix}__col__{name}",
        name=name,
        datatype="string",
        role=ColumnRole.DIMENSION,
        kind=ColumnKind.RAW,
        source_column=name,
    )


def _orders_table(col_ids: tuple[str, ...]) -> Table:
    return Table(
        id="tbl__orders",
        name="orders",
        datasource_id="ds__ds1",
        column_ids=col_ids,
    )


def _raw_ds(col_map: dict | None = None) -> list[dict]:
    return [{"name": "ds1", "col_map": col_map or {"order_date": ["orders", "order_date"]}}]


def _raw_ws(*column_instances) -> list[dict]:
    return [{"column_instances": list(column_instances)}]


def _ci(base: str, derivation: str, slug: str | None = None) -> dict:
    return {
        "slug": slug or f"x:{base}:ok",
        "base_column": base,
        "derivation": derivation,
    }


# ── Core behaviour ────────────────────────────────────────────────────────────

def test_year_creates_dax_column():
    col = _date_col()
    table = _orders_table((col.id,))
    new_cols, updated_tables = build_date_part_columns(
        _raw_ws(_ci("order_date", "Year")), _raw_ds(), (table,), (col,)
    )
    assert len(new_cols) == 1
    c = new_cols[0]
    assert c.name == "Year order_date"
    assert c.datatype == "integer"
    assert c.kind == ColumnKind.CALCULATED
    assert c.dax_expr == "YEAR(orders[order_date])"
    assert c.role == ColumnRole.DIMENSION
    assert c.source_column is None


def test_all_derivations_produce_correct_dax_function():
    expected = {
        "Year":    "YEAR",
        "Quarter": "QUARTER",
        "Month":   "MONTH",
        "Week":    "WEEKNUM",
        "Day":     "DAY",
        "Hour":    "HOUR",
        "Minute":  "MINUTE",
        "Second":  "SECOND",
    }
    col = _date_col()
    table = _orders_table((col.id,))
    for derivation, dax_fn in expected.items():
        new_cols, _ = build_date_part_columns(
            [{"column_instances": [_ci("order_date", derivation)]}],
            _raw_ds(), (table,), (col,),
        )
        assert len(new_cols) == 1
        assert new_cols[0].dax_expr == f"{dax_fn}(orders[order_date])", (
            f"Wrong DAX for {derivation}: got {new_cols[0].dax_expr!r}"
        )


def test_duplicate_across_two_worksheets_creates_one_column():
    col = _date_col()
    table = _orders_table((col.id,))
    raw_ws = [
        {"column_instances": [_ci("order_date", "Year")]},
        {"column_instances": [_ci("order_date", "Year")]},
    ]
    new_cols, _ = build_date_part_columns(raw_ws, _raw_ds(), (table,), (col,))
    assert len(new_cols) == 1


def test_non_date_base_column_is_skipped():
    col = _string_col("category")
    table = _orders_table((col.id,))
    raw_ds = [{"name": "ds1", "col_map": {"category": ["orders", "category"]}}]
    new_cols, _ = build_date_part_columns(
        _raw_ws(_ci("category", "Year")), raw_ds, (table,), (col,)
    )
    assert len(new_cols) == 0


def test_real_type_base_column_is_skipped():
    col = _real_col("sales")
    table = _orders_table((col.id,))
    raw_ds = [{"name": "ds1", "col_map": {"sales": ["orders", "sales"]}}]
    new_cols, _ = build_date_part_columns(
        _raw_ws(_ci("sales", "Year")), raw_ds, (table,), (col,)
    )
    assert len(new_cols) == 0


def test_unknown_base_column_in_col_map_is_skipped():
    col = _date_col()
    table = _orders_table((col.id,))
    # col_map has a different name — base_column "no_such" not in col_map
    raw_ds = [{"name": "ds1", "col_map": {"order_date": ["orders", "order_date"]}}]
    new_cols, _ = build_date_part_columns(
        _raw_ws(_ci("no_such", "Year")), raw_ds, (table,), (col,)
    )
    assert len(new_cols) == 0


def test_empty_column_instances_list():
    col = _date_col()
    table = _orders_table((col.id,))
    new_cols, updated_tables = build_date_part_columns(
        [{"column_instances": []}], _raw_ds(), (table,), (col,)
    )
    assert len(new_cols) == 0
    assert updated_tables[0].column_ids == table.column_ids


def test_synthesized_column_id_appended_to_table():
    col = _date_col()
    table = _orders_table((col.id,))
    _, updated_tables = build_date_part_columns(
        _raw_ws(_ci("order_date", "Year")), _raw_ds(), (table,), (col,)
    )
    orders = next(t for t in updated_tables if t.name == "orders")
    assert any("year_order_date" in cid for cid in orders.column_ids)
    assert len(orders.column_ids) == len(table.column_ids) + 1


def test_original_table_not_mutated():
    col = _date_col()
    table = _orders_table((col.id,))
    original_ids = table.column_ids
    _, updated_tables = build_date_part_columns(
        _raw_ws(_ci("order_date", "Year")), _raw_ds(), (table,), (col,)
    )
    assert table.column_ids == original_ids  # pydantic immutable, original unchanged


def test_no_col_map_falls_back_to_table_scan():
    """Plain (non-federated) datasource with empty col_map."""
    col = _date_col("order_date", "tbl__ds1")
    table = _orders_table((col.id,))
    raw_ds = [{"name": "ds1", "col_map": {}}]  # empty col_map
    new_cols, _ = build_date_part_columns(
        _raw_ws(_ci("order_date", "Year")), raw_ds, (table,), (col,)
    )
    assert len(new_cols) == 1
    assert new_cols[0].dax_expr == "YEAR(orders[order_date])"


def test_dax_uses_physical_col_name_from_col_map():
    """Physical column name in DB differs from logical Tableau name."""
    col = Column(
        id="tbl__ds1__col__order_date",
        name="order_date",
        datatype="date",
        role=ColumnRole.DIMENSION,
        kind=ColumnKind.RAW,
        source_column="OrderDate",  # different physical name
    )
    table = _orders_table((col.id,))
    raw_ds = [{"name": "ds1", "col_map": {"order_date": ["orders", "OrderDate"]}}]
    new_cols, _ = build_date_part_columns(
        _raw_ws(_ci("order_date", "Year")), raw_ds, (table,), (col,)
    )
    assert len(new_cols) == 1
    assert new_cols[0].dax_expr == "YEAR(orders[OrderDate])"


def test_col_map_physical_name_takes_precedence_over_source_column():
    """col_map physical name is used in DAX, not Column.source_column."""
    col = Column(
        id="tbl__ds1__col__order_date",
        name="order_date",
        datatype="date",
        role=ColumnRole.DIMENSION,
        kind=ColumnKind.RAW,
        source_column="ord_dt",  # different from col_map physical name
    )
    table = _orders_table((col.id,))
    raw_ds = [{"name": "ds1", "col_map": {"order_date": ["orders", "OrderDate"]}}]
    new_cols, _ = build_date_part_columns(
        _raw_ws(_ci("order_date", "Year")), raw_ds, (table,), (col,)
    )
    assert len(new_cols) == 1
    assert new_cols[0].dax_expr == "YEAR(orders[OrderDate])"  # col_map wins, not "ord_dt"


def test_two_different_derivations_of_same_column():
    col = _date_col()
    table = _orders_table((col.id,))
    raw_ws = [{"column_instances": [
        _ci("order_date", "Year"),
        _ci("order_date", "Month"),
    ]}]
    new_cols, updated_tables = build_date_part_columns(raw_ws, _raw_ds(), (table,), (col,))
    assert len(new_cols) == 2
    names = {c.name for c in new_cols}
    assert names == {"Year order_date", "Month order_date"}
    orders = next(t for t in updated_tables if t.name == "orders")
    assert len(orders.column_ids) == len(table.column_ids) + 2
