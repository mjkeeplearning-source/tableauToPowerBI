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
