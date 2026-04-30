from pathlib import Path

from tableau2pbir.ir.calculation import Calculation, CalculationKind, CalculationPhase, CalculationScope
from tableau2pbir.ir.datasource import ConnectorTier, Datasource
from tableau2pbir.ir.model import Table
from tableau2pbir.ir.workbook import DataModel, Workbook
from tableau2pbir.pipeline import StageContext
from tableau2pbir.stages import s06_build_tmdl


def _wb() -> dict:
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
    return Workbook(
        ir_schema_version="1.1.0", source_path="x.twb", source_hash="a",
        tableau_version="2024.1", config={},
        data_model=DataModel(datasources=(ds,), tables=(table,), calculations=(calc,)),
        sheets=(), dashboards=(), unsupported=(),
    ).model_dump(mode="json")


def test_stage6_writes_files_and_returns_manifest(tmp_path: Path):
    ctx = StageContext(workbook_id="wb", output_dir=tmp_path, config={}, stage_number=6)
    result = s06_build_tmdl.run(_wb(), ctx)
    sm = tmp_path / "SemanticModel"
    assert (sm / "database.tmdl").is_file()
    assert (sm / "tables" / "Sales.tmdl").is_file()
    assert "Stage 6" in result.summary_md
    # Stage 6 passes the Workbook IR through so Stage 7 can consume it.
    assert "data_model" in result.output
