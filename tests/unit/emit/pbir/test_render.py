from pathlib import Path

from tableau2pbir.emit.pbir.render import render_report
from tableau2pbir.ir.dashboard import (
    Container, ContainerKind, Dashboard, DashboardSize, Leaf, LeafKind, Position,
)
from tableau2pbir.ir.datasource import ConnectorTier, Datasource
from tableau2pbir.ir.model import Column, ColumnKind, ColumnRole, Table
from tableau2pbir.ir.sheet import EncodingBinding, Encoding, PbirVisual, Sheet
from tableau2pbir.ir.workbook import DataModel, Workbook


def _wb_one_page_one_visual() -> Workbook:
    sheet = Sheet(
        id="s1", name="Bars", datasource_refs=("d1",), mark_type="bar",
        encoding=Encoding(), filters=(), sort=(), dual_axis=False, reference_lines=(),
        uses_calculations=(),
        pbir_visual=PbirVisual(
            visual_type="clusteredBarChart",
            encoding_bindings=(
                EncodingBinding(channel="Category", source_field_id="Sales.Region"),
                EncodingBinding(channel="Y", source_field_id="Total Sales"),
            ),
        ),
    )
    leaf = Leaf(kind=LeafKind.SHEET, payload={"sheet_id": "s1"},
                position=Position(x=0, y=0, w=1280, h=720))
    dash = Dashboard(
        id="d1", name="Page 1",
        size=DashboardSize(w=1280, h=720, kind="exact"),
        layout_tree=Container(kind=ContainerKind.H, children=(leaf,)),
    )
    ds = Datasource(
        id="d1", name="DS", tableau_kind="csv", connector_tier=ConnectorTier.TIER_1,
        pbi_m_connector="Csv.Document", connection_params={"filename": "C:/x.csv"},
        user_action_required=(), table_ids=("t1",), extract_ignored=False,
    )
    table = Table(id="t1", name="Sales", datasource_id="d1", column_ids=("c1",))
    col = Column(id="c1", name="Region", datatype="string", role=ColumnRole.DIMENSION, kind=ColumnKind.RAW)
    return Workbook(
        ir_schema_version="1.1.0", source_path="x.twb", source_hash="a",
        tableau_version="2024.1", config={},
        data_model=DataModel(datasources=(ds,), tables=(table,)),
        sheets=(sheet,), dashboards=(dash,), unsupported=(),
    )


def test_render_writes_page_and_visual(tmp_path: Path):
    wb = _wb_one_page_one_visual()
    manifest = render_report(wb, tmp_path)
    rd = tmp_path / "Report" / "definition"
    assert (rd / "report.json").is_file()
    pages = list((rd / "pages").iterdir())
    assert len(pages) == 1
    visuals = list((pages[0] / "visuals").iterdir())
    assert len(visuals) == 1
    assert (visuals[0] / "visual.json").is_file()
    assert manifest["counts"]["pages"] == 1
    assert manifest["counts"]["visuals"] == 1
    assert manifest["blocked_visuals"] == []
