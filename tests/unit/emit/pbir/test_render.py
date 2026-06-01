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


def _make_sheet(sheet_id: str, name: str, visual_type: str = "columnChart") -> Sheet:
    return Sheet(
        id=sheet_id, name=name, datasource_refs=("d1",), mark_type="bar",
        encoding=Encoding(), filters=(), sort=(), dual_axis=False, reference_lines=(),
        uses_calculations=(),
        pbir_visual=PbirVisual(
            visual_type=visual_type,
            encoding_bindings=(
                EncodingBinding(channel="Category", source_field_id="Sales.Region"),
                EncodingBinding(channel="Y", source_field_id="Total Sales"),
            ),
        ),
    )


def _wb_two_sheets_one_dashboard() -> Workbook:
    """Two worksheets + one dashboard containing both (mirrors simple_join_dashboard.twb)."""
    s1 = _make_sheet("s1", "Category average orders", "columnChart")
    s2 = _make_sheet("s2", "Category by Margin", "barChart")
    leaf1 = Leaf(kind=LeafKind.SHEET, payload={"sheet_id": "s1"},
                 position=Position(x=0, y=0, w=1000, h=400))
    leaf2 = Leaf(kind=LeafKind.SHEET, payload={"sheet_id": "s2"},
                 position=Position(x=0, y=400, w=1000, h=400))
    dash = Dashboard(
        id="d1", name="Company Dashboard",
        size=DashboardSize(w=1000, h=800, kind="exact"),
        layout_tree=Container(kind=ContainerKind.FLOATING, children=(leaf1, leaf2)),
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
        ir_schema_version="1.1.0", source_path="x.twb", source_hash="b",
        tableau_version="2024.1", config={},
        data_model=DataModel(datasources=(ds,), tables=(table,)),
        sheets=(s1, s2), dashboards=(dash,), unsupported=(),
    )


def test_each_worksheet_gets_its_own_page(tmp_path: Path):
    """Each Tableau worksheet must become an independent PBI page."""
    wb = _wb_two_sheets_one_dashboard()
    manifest = render_report(wb, tmp_path)
    # 2 sheets + 1 dashboard = 3 pages
    assert manifest["counts"]["pages"] == 3


def test_worksheet_pages_are_numbered_before_dashboard_pages(tmp_path: Path):
    """Sheet pages come first in pageOrder; dashboard page(s) follow."""
    wb = _wb_two_sheets_one_dashboard()
    render_report(wb, tmp_path)
    rd = tmp_path / "Report" / "definition"
    pages = json.loads((rd / "pages" / "pages.json").read_text(encoding="utf-8"))
    assert len(pages["pageOrder"]) == 3
    # First two pages are the sheets
    page1_json = json.loads(
        (rd / "pages" / pages["pageOrder"][0] / "page.json").read_text(encoding="utf-8")
    )
    page2_json = json.loads(
        (rd / "pages" / pages["pageOrder"][1] / "page.json").read_text(encoding="utf-8")
    )
    assert page1_json["displayName"] == "Category average orders"
    assert page2_json["displayName"] == "Category by Margin"


def test_worksheet_page_has_one_full_canvas_visual(tmp_path: Path):
    """Each worksheet page must contain exactly one visual covering the full page."""
    wb = _wb_two_sheets_one_dashboard()
    render_report(wb, tmp_path)
    rd = tmp_path / "Report" / "definition"
    pages = json.loads((rd / "pages" / "pages.json").read_text(encoding="utf-8"))
    sheet_page_dir = rd / "pages" / pages["pageOrder"][0]
    visuals = list((sheet_page_dir / "visuals").iterdir())
    assert len(visuals) == 1
    v = json.loads((visuals[0] / "visual.json").read_text(encoding="utf-8"))
    pos = v["position"]
    assert pos["x"] == 0 and pos["y"] == 0


def test_dashboard_page_still_has_both_sheet_visuals(tmp_path: Path):
    """The dashboard page must contain one visual per referenced worksheet."""
    wb = _wb_two_sheets_one_dashboard()
    manifest = render_report(wb, tmp_path)
    rd = tmp_path / "Report" / "definition"
    pages = json.loads((rd / "pages" / "pages.json").read_text(encoding="utf-8"))
    dash_page_dir = rd / "pages" / pages["pageOrder"][2]  # 3rd page = dashboard
    visuals = list((dash_page_dir / "visuals").iterdir())
    assert len(visuals) == 2
    assert manifest["counts"]["visuals"] == 4  # 2 sheet pages + 2 dashboard visuals


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
    # 1 sheet + 1 dashboard = 2 pages
    assert len(pages_manifest["pageOrder"]) == 2
    assert pages_manifest["activePageName"] == pages_manifest["pageOrder"][0]


def test_page_folder_named_report_section(tmp_path: Path):
    wb = _wb_one_page_one_visual()
    render_report(wb, tmp_path)
    rd = tmp_path / "Report" / "definition"
    page_dirs = sorted([p for p in (rd / "pages").iterdir() if p.is_dir()])
    # 1 sheet page + 1 dashboard page
    assert len(page_dirs) == 2
    assert page_dirs[0].name == "ReportSection1", f"got: {page_dirs[0].name}"
    assert page_dirs[1].name == "ReportSection2", f"got: {page_dirs[1].name}"


def test_visual_folder_named_visual_1(tmp_path: Path):
    wb = _wb_one_page_one_visual()
    render_report(wb, tmp_path)
    rd = tmp_path / "Report" / "definition"
    page_dirs = sorted([p for p in (rd / "pages").iterdir() if p.is_dir()])
    # ReportSection1 is the sheet page; its visual is visual_1
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
    # pages/ has pages.json + 1 sheet page + 1 dashboard page
    page_dirs = sorted([p for p in pages if p.is_dir()])
    assert len(page_dirs) == 2
    # sheet page has visual_1, dashboard page has visual_2
    assert (page_dirs[0] / "visuals" / "visual_1" / "visual.json").is_file()
    assert (page_dirs[1] / "visuals" / "visual_2" / "visual.json").is_file()
    assert manifest["counts"]["pages"] == 2
    assert manifest["counts"]["visuals"] == 2
    assert manifest["blocked_visuals"] == []
