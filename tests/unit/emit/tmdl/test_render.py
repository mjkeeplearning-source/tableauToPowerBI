from pathlib import Path

from tableau2pbir.emit.tmdl.render import render_semantic_model
from tableau2pbir.ir.calculation import Calculation, CalculationKind, CalculationPhase, CalculationScope
from tableau2pbir.ir.datasource import ConnectorTier, Datasource
from tableau2pbir.ir.model import Table
from tableau2pbir.ir.workbook import DataModel, Workbook


def _wb_with_one_table_and_one_measure() -> Workbook:
    ds = Datasource(
        id="d1", name="DS", tableau_kind="csv", connector_tier=ConnectorTier.TIER_1,
        pbi_m_connector="Csv.Document", connection_params={"filename": "C:/x.csv"},
        user_action_required=(), table_ids=("t1",), extract_ignored=False,
    )
    table = Table(id="t1", name="Sales", datasource_id="d1", column_ids=("c1",))
    calc = Calculation(
        id="m1", name="Total Sales", scope=CalculationScope.MEASURE,
        tableau_expr="SUM([X])", dax_expr="SUM('Sales'[X])",
        kind=CalculationKind.AGGREGATE, phase=CalculationPhase.AGGREGATE,
    )
    dm = DataModel(datasources=(ds,), tables=(table,), calculations=(calc,))
    return Workbook(
        ir_schema_version="1.1.0", source_path="x.twb", source_hash="a",
        tableau_version="2024.1", config={},
        data_model=dm, sheets=(), dashboards=(), unsupported=(),
    )


def test_render_writes_files(tmp_path: Path):
    wb = _wb_with_one_table_and_one_measure()
    manifest = render_semantic_model(wb, tmp_path)
    sm = tmp_path / "SemanticModel"
    assert (sm / "database.tmdl").is_file()
    assert (sm / "model.tmdl").is_file()
    assert (sm / "tables" / "Sales.tmdl").is_file()
    assert "tables/Sales.tmdl" in manifest["files"]
    assert manifest["counts"]["tables"] == 1
    assert manifest["counts"]["measures"] == 1
