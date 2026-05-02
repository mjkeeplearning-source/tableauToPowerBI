import json
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
    col = Column(id="c1", name="Region", datatype="string", role=ColumnRole.DIMENSION,
                 kind=ColumnKind.RAW)
    return Workbook(
        ir_schema_version="1.1.0", source_path="x.twb", source_hash="a",
        tableau_version="2024.1", config={},
        data_model=DataModel(datasources=(ds,), tables=(table,)),
        sheets=(sheet,), dashboards=(dash,), unsupported=(),
    )


def test_render_writes_required_files(tmp_path: Path):
    wb = _wb_one_page_one_visual()
    render_report(wb, tmp_path)
    rd = tmp_path / "Report" / "definition"

    assert (rd / "report.json").is_file(), "report.json required"
    assert (rd / "version.json").is_file(), "version.json required"
    assert (rd / "pages" / "pages.json").is_file(), "pages/pages.json required by schema 3.2.0"


def test_version_json_is_2_0_0(tmp_path: Path):
    wb = _wb_one_page_one_visual()
    render_report(wb, tmp_path)
    rd = tmp_path / "Report" / "definition"
    ver = json.loads((rd / "version.json").read_text(encoding="utf-8"))
    assert ver["version"] == "2.0.0", f"version.json must be '2.0.0', got: {ver['version']}"


def test_pages_json_contains_page_id(tmp_path: Path):
    wb = _wb_one_page_one_visual()
    render_report(wb, tmp_path)
    rd = tmp_path / "Report" / "definition"
    pages_manifest = json.loads((rd / "pages" / "pages.json").read_text(encoding="utf-8"))
    assert len(pages_manifest["pageOrder"]) == 1
    assert pages_manifest["activePageName"] == pages_manifest["pageOrder"][0]


def test_page_folder_named_report_section(tmp_path: Path):
    wb = _wb_one_page_one_visual()
    render_report(wb, tmp_path)
    rd = tmp_path / "Report" / "definition"
    page_dirs = [p for p in (rd / "pages").iterdir() if p.is_dir()]
    assert len(page_dirs) == 1
    assert page_dirs[0].name == "ReportSection1", f"got: {page_dirs[0].name}"


def test_visual_folder_named_visual_1(tmp_path: Path):
    wb = _wb_one_page_one_visual()
    render_report(wb, tmp_path)
    rd = tmp_path / "Report" / "definition"
    page_dirs = [p for p in (rd / "pages").iterdir() if p.is_dir()]
    visual_dirs = list((page_dirs[0] / "visuals").iterdir())
    assert len(visual_dirs) == 1
    assert visual_dirs[0].name == "visual_1", f"got: {visual_dirs[0].name}"


def test_visual_projections_have_queryref(tmp_path: Path):
    """render_report must emit queryRef in every projection."""
    wb = _wb_one_page_one_visual()
    render_report(wb, tmp_path)
    rd = tmp_path / "Report" / "definition"
    page_dirs = [p for p in (rd / "pages").iterdir() if p.is_dir()]
    visual_json = json.loads(
        (page_dirs[0] / "visuals" / "visual_1" / "visual.json").read_text(encoding="utf-8")
    )
    projections = [
        p
        for ch in visual_json["visual"]["query"]["queryState"].values()
        for p in ch["projections"]
    ]
    assert all("queryRef" in p for p in projections), "every projection must have queryRef"
    assert all(p.get("active") is True for p in projections), "every projection must be active"


def test_render_writes_page_and_visual(tmp_path: Path):
    wb = _wb_one_page_one_visual()
    manifest = render_report(wb, tmp_path)
    rd = tmp_path / "Report" / "definition"
    pages = list((rd / "pages").iterdir())
    # pages/ has pages.json + one page folder
    page_dirs = [p for p in pages if p.is_dir()]
    assert len(page_dirs) == 1
    visuals = list((page_dirs[0] / "visuals").iterdir())
    assert len(visuals) == 1
    assert (visuals[0] / "visual.json").is_file()
    assert manifest["counts"]["pages"] == 1
    assert manifest["counts"]["visuals"] == 1
    assert manifest["blocked_visuals"] == []
