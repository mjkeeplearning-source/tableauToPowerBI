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


def test_empty_datasources_returns_empty():
    tables, columns = build_tables([])
    assert tables == ()
    assert columns == ()
