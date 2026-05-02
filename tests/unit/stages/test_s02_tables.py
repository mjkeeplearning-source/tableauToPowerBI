from __future__ import annotations

from tableau2pbir.ir.model import ColumnKind, ColumnRole
from tableau2pbir.stages._build_data_model import build_tables


def test_one_table_per_datasource():
    raw = [{
        "name": "sample.csv", "caption": "Sample",
        "connection": {"class": "textscan"}, "named_connections": [], "extract": None,
        "columns": [
            {"name": "id", "datatype": "integer", "role": "dimension", "type": "ordinal"},
            {"name": "amount", "datatype": "integer", "role": "measure", "type": "quantitative"},
        ],
        "calculations": [],
    }]
    tables, columns = build_tables(raw)
    assert len(tables) == 1
    assert tables[0].name == "sample.csv"
    assert tables[0].datasource_id == "ds__sample_csv"
    assert len(columns) == 2
    amount = next(c for c in columns if c.name == "amount")
    assert amount.role == ColumnRole.MEASURE
    assert amount.kind == ColumnKind.RAW
    assert amount.datatype == "integer"


def test_calculated_column_has_tableau_expr_and_kind_calculated():
    raw = [{
        "name": "orders", "caption": None,
        "connection": {"class": "sqlserver"}, "named_connections": [], "extract": None,
        "columns": [
            {"name": "Revenue", "datatype": "real", "role": "measure", "type": None},
            {"name": "Profit Margin", "datatype": "real", "role": "measure", "type": None},
        ],
        "calculations": [
            {"host_column_name": "Profit Margin", "tableau_expr": "SUM([Profit])/SUM([Revenue])",
             "datatype": "real", "role": "measure"},
        ],
    }]
    _, columns = build_tables(raw)
    margin = next(c for c in columns if c.name == "Profit Margin")
    assert margin.kind == ColumnKind.CALCULATED
    assert margin.tableau_expr == "SUM([Profit])/SUM([Revenue])"
    assert margin.dax_expr is None          # Populated in Plan 3 (stage 3).


def test_table_column_ids_reference_columns():
    raw = [{
        "name": "sample.csv", "caption": None,
        "connection": {"class": "textscan"}, "named_connections": [], "extract": None,
        "columns": [
            {"name": "id", "datatype": "integer", "role": "dimension", "type": None},
            {"name": "amount", "datatype": "integer", "role": "measure", "type": None},
        ],
        "calculations": [],
    }]
    tables, columns = build_tables(raw)
    column_ids = {c.id for c in columns}
    assert set(tables[0].column_ids) == column_ids


def test_federated_join_emits_one_table_per_relation():
    raw = [{
        "name": "federated.abc",
        "connection": {"class": "federated"},
        "named_connections": [
            {"name": "pg.xyz", "caption": "srv",
             "connection": {"class": "postgres", "server": "srv", "dbname": "db"}},
        ],
        "extract": None,
        "relations": [
            {"name": "orders",  "table": "[public].[orders]",  "connection": "pg.xyz"},
            {"name": "returns", "table": "[public].[returns]", "connection": "pg.xyz"},
        ],
        "col_map": {
            "category": ("orders",  "category"),
            "returned": ("returns", "returned"),
        },
        "columns": [
            {"name": "category", "datatype": "string", "role": "dimension", "type": "nominal"},
            {"name": "returned", "datatype": "string", "role": "dimension", "type": "nominal"},
        ],
        "calculations": [],
    }]
    tables, columns = build_tables(raw)
    assert len(tables) == 2
    names = {t.name for t in tables}
    assert names == {"orders", "returns"}

    orders_t = next(t for t in tables if t.name == "orders")
    returns_t = next(t for t in tables if t.name == "returns")

    assert orders_t.physical_schema == "public"
    assert orders_t.physical_table  == "orders"
    assert returns_t.physical_schema == "public"
    assert returns_t.physical_table  == "returns"

    # category column → orders table; returned column → returns table
    cat_col = next(c for c in columns if c.name == "category")
    ret_col = next(c for c in columns if c.name == "returned")
    assert cat_col.id in orders_t.column_ids
    assert ret_col.id in returns_t.column_ids


def test_empty_datasources_returns_empty():
    tables, columns = build_tables([])
    assert tables == ()
    assert columns == ()


def test_source_column_populated_from_col_map():
    """Federated col_map physical name flows into Column.source_column."""
    raw = [{
        "name": "federated.abc",
        "connection": {"class": "federated"},
        "named_connections": [
            {"name": "pg", "caption": None,
             "connection": {"class": "postgres", "server": "srv", "dbname": "db"}},
        ],
        "extract": None,
        "relations": [
            {"name": "orders",  "table": "[public].[orders]",  "connection": "pg"},
            {"name": "returns", "table": "[public].[returns]", "connection": "pg"},
        ],
        "col_map": {
            "order_id":           ("orders",  "order_id"),
            "order_id (returns)": ("returns", "order_id"),   # Tableau alias → physical "order_id"
        },
        "columns": [
            {"name": "order_id",           "datatype": "string", "role": "dimension", "type": "nominal"},
            {"name": "order_id (returns)", "datatype": "string", "role": "dimension", "type": "nominal"},
        ],
        "calculations": [],
    }]
    _, columns = build_tables(raw)
    orders_col  = next(c for c in columns if c.name == "order_id")
    returns_col = next(c for c in columns if c.name == "order_id (returns)")
    assert orders_col.source_column == "order_id"
    assert returns_col.source_column == "order_id"   # physical name, not the alias


def test_plain_datasource_source_column_equals_name():
    """Plain datasource: source_column = column name (no col_map)."""
    raw = [{
        "name": "sales", "caption": None,
        "connection": {"class": "sqlserver"}, "named_connections": [], "extract": None,
        "columns": [
            {"name": "profit", "datatype": "real", "role": "measure", "type": "quantitative"},
        ],
        "calculations": [],
    }]
    _, columns = build_tables(raw)
    assert columns[0].source_column == "profit"
