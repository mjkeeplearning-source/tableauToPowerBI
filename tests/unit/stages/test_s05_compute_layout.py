from pathlib import Path

from tableau2pbir.ir.common import UnsupportedItem
from tableau2pbir.ir.dashboard import (
    Container, ContainerKind, Dashboard, DashboardSize, Leaf, LeafKind, Position,
)
from tableau2pbir.ir.workbook import DataModel, Workbook
from tableau2pbir.pipeline import StageContext
from tableau2pbir.stages import s05_compute_layout


def _make_ir_dict(dashboard: Dashboard) -> dict:
    wb = Workbook(
        ir_schema_version="1.1.0", source_path="x.twb", source_hash="abc",
        tableau_version="2024.1", config={},
        data_model=DataModel(), sheets=(), dashboards=(dashboard,), unsupported=(),
    )
    return wb.model_dump(mode="json")


def test_stage5_resolves_leaf_positions(tmp_path: Path):
    leaf = Leaf(kind=LeafKind.SHEET, payload={"sheet_id": "s1"})
    dash = Dashboard(
        id="d1", name="Page1",
        size=DashboardSize(w=1280, h=720, kind="exact"),
        layout_tree=Container(kind=ContainerKind.H, children=(leaf,)),
    )
    ctx = StageContext(workbook_id="wb", output_dir=tmp_path, config={}, stage_number=5)
    result = s05_compute_layout.run(_make_ir_dict(dash), ctx)
    pos = result.output["dashboards"][0]["layout_tree"]["children"][0]["position"]
    assert pos == {"x": 0, "y": 0, "w": 1280, "h": 720}
    assert "Stage 5" in result.summary_md


def test_stage5_warns_on_clamp(tmp_path: Path):
    leaf = Leaf(
        kind=LeafKind.SHEET, payload={"sheet_id": "s1"},
        position=Position(x=900, y=500, w=500, h=400),
    )
    dash = Dashboard(
        id="d1", name="Page1",
        size=DashboardSize(w=1000, h=600, kind="exact"),
        layout_tree=Container(kind=ContainerKind.FLOATING, children=(leaf,)),
    )
    ctx = StageContext(workbook_id="wb", output_dir=tmp_path, config={}, stage_number=5)
    result = s05_compute_layout.run(_make_ir_dict(dash), ctx)
    codes = [e.code for e in result.errors]
    assert "layout.leaf_clamped" in codes


def test_stage5_output_passthrough_has_ir_keys(tmp_path: Path):
    leaf = Leaf(kind=LeafKind.BLANK, payload={})
    dash = Dashboard(
        id="d1", name="P1",
        size=DashboardSize(w=800, h=600, kind="exact"),
        layout_tree=Container(kind=ContainerKind.V, children=(leaf,)),
    )
    ctx = StageContext(workbook_id="wb", output_dir=tmp_path, config={}, stage_number=5)
    result = s05_compute_layout.run(_make_ir_dict(dash), ctx)
    assert "ir_schema_version" in result.output
    assert "dashboards" in result.output
