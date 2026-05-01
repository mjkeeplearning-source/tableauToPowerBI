from pathlib import Path

from tableau2pbir.emit.tmdl.render import render_semantic_model
from tableau2pbir.ir.calculation import Calculation, CalculationKind, CalculationPhase, CalculationScope
from tableau2pbir.ir.common import FieldRef
from tableau2pbir.ir.datasource import ConnectorTier, Datasource
from tableau2pbir.ir.model import Relationship, RelationshipSource, Table
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
    defn = sm / "definition"
    assert (sm / "definition.pbism").is_file(), "definition.pbism missing"
    assert (defn / "database.tmdl").is_file()
    assert (defn / "model.tmdl").is_file()
    assert (defn / "tables" / "Sales.tmdl").is_file()
    assert "tables/Sales.tmdl" in manifest["files"]
    assert manifest["counts"]["tables"] == 1
    assert manifest["counts"]["measures"] == 1


def _wb_with_two_tables_and_relationship() -> Workbook:
    ds = Datasource(
        id="d1", name="DS", tableau_kind="postgres", connector_tier=ConnectorTier.TIER_1,
        pbi_m_connector="PostgreSQL.Database",
        connection_params={"server": "srv", "dbname": "db"},
        user_action_required=(), table_ids=("t1", "t2"), extract_ignored=False,
    )
    orders = Table(id="t1", name="orders", datasource_id="d1", column_ids=())
    returns = Table(id="t2", name="returns", datasource_id="d1", column_ids=())
    rel = Relationship(
        id="rel__orders_returns",
        from_ref=FieldRef(table_id="t1", column_id="order_id"),
        to_ref=FieldRef(table_id="t2", column_id="order_id"),
        cardinality="many_to_one", cross_filter="single",
        source=RelationshipSource.TABLEAU_JOIN,
    )
    dm = DataModel(datasources=(ds,), tables=(orders, returns), relationships=(rel,))
    return Workbook(
        ir_schema_version="1.1.0", source_path="x.twb", source_hash="a",
        tableau_version="2024.1", config={},
        data_model=dm, sheets=(), dashboards=(), unsupported=(),
    )


def test_relationships_written_to_single_relationships_tmdl(tmp_path: Path):
    wb = _wb_with_two_tables_and_relationship()
    manifest = render_semantic_model(wb, tmp_path)
    defn = tmp_path / "SemanticModel" / "definition"
    # Must be a single file alongside model.tmdl — NOT per-relationship under relationships/
    assert (defn / "relationships.tmdl").is_file(), "relationships.tmdl missing"
    assert not (defn / "relationships").is_dir(), "relationships/ subdirectory must not exist"
    assert "relationships.tmdl" in manifest["files"]
    assert manifest["counts"]["relationships"] == 1


def test_relationships_tmdl_content_uses_dot_notation(tmp_path: Path):
    wb = _wb_with_two_tables_and_relationship()
    render_semantic_model(wb, tmp_path)
    text = (tmp_path / "SemanticModel" / "definition" / "relationships.tmdl").read_text(encoding="utf-8")
    assert "relationship rel__orders_returns" in text
    assert "fromColumn: orders.order_id" in text
    assert "toColumn: returns.order_id" in text


def test_definition_pbism_has_version_4(tmp_path: Path):
    import json
    wb = _wb_with_one_table_and_one_measure()
    render_semantic_model(wb, tmp_path)
    data = json.loads((tmp_path / "SemanticModel" / "definition.pbism").read_text(encoding="utf-8"))
    assert data["version"] == "4.0"
    assert "$schema" in data
