from tableau2pbir.emit.tmdl.table import render_table
from tableau2pbir.ir.calculation import Calculation, CalculationKind, CalculationPhase, CalculationScope
from tableau2pbir.ir.datasource import ConnectorTier, Datasource
from tableau2pbir.ir.model import Column, ColumnKind, ColumnRole


def test_table_with_one_column_one_measure_csv_partition():
    ds = Datasource(
        id="d1", name="DS", tableau_kind="csv", connector_tier=ConnectorTier.TIER_1,
        pbi_m_connector="Csv.Document",
        connection_params={"filename": "C:/data.csv"},
        user_action_required=(), table_ids=("t1",), extract_ignored=False,
    )
    cols = [Column(id="c1", name="Region", datatype="string", role=ColumnRole.DIMENSION, kind=ColumnKind.RAW)]
    measures = [Calculation(
        id="m1", name="Total", scope=CalculationScope.MEASURE,
        tableau_expr="SUM([X])", dax_expr="SUM('Sales'[X])",
        kind=CalculationKind.AGGREGATE, phase=CalculationPhase.AGGREGATE,
    )]
    out = render_table(name="Sales", columns=cols, measures=measures, datasource=ds)
    assert out.startswith("table Sales")
    assert "column Region" in out
    assert "measure Total" in out
    assert "partition Sales = m" in out
    assert "Csv.Document" in out


def test_db_table_uses_direct_query_mode():
    ds = Datasource(
        id="d2", name="PG", tableau_kind="postgres", connector_tier=ConnectorTier.TIER_2,
        pbi_m_connector="PostgreSQL.Database",
        connection_params={"server": "localhost", "dbname": "sales", "schema": "public", "table": "orders"},
        user_action_required=("enter credentials",), table_ids=("t2",), extract_ignored=False,
    )
    out = render_table(name="orders", columns=[], measures=[], datasource=ds)
    assert "mode: directQuery" in out, "DB-backed tables must use directQuery partition mode"


def test_csv_table_uses_import_mode():
    ds = Datasource(
        id="d1", name="DS", tableau_kind="csv", connector_tier=ConnectorTier.TIER_1,
        pbi_m_connector="Csv.Document",
        connection_params={"filename": "C:/data.csv"},
        user_action_required=(), table_ids=("t1",), extract_ignored=False,
    )
    out = render_table(name="Sales", columns=[], measures=[], datasource=ds)
    assert "mode: import" in out, "File-based tables must use import partition mode"


def test_render_table_emits_column_blocks():
    ds = Datasource(
        id="ds1", name="orders",
        tableau_kind="postgres",
        connector_tier=ConnectorTier.TIER_1,
        pbi_m_connector="PostgreSQL.Database",
        connection_params={"server": "srv", "dbname": "db"},
        user_action_required=(),
        table_ids=(),
        extract_ignored=False,
    )
    cols = [
        Column(id="c1", name="order_id", datatype="string",  role=ColumnRole.DIMENSION,
               kind=ColumnKind.RAW, source_column="order_id"),
        Column(id="c2", name="sales",    datatype="real",    role=ColumnRole.MEASURE,
               kind=ColumnKind.RAW, source_column="sales"),
    ]
    out = render_table(name="orders", columns=cols, measures=[], datasource=ds)
    assert "column order_id" in out
    assert "dataType: string" in out
    assert "sourceColumn: order_id" in out
    assert "column sales" in out
    assert "dataType: double" in out
    assert "sourceColumn: sales" in out
