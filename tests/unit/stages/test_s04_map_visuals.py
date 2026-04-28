"""Stage 4 orchestrator. Reads stage-3 IR, attaches PbirVisual to every
sheet whose mark is in the v1 catalog; routes the rest to unsupported[]."""
from __future__ import annotations

from pathlib import Path

from tableau2pbir.pipeline import StageContext
from tableau2pbir.stages.s04_map_visuals import run


def _ir_one_bar_sheet() -> dict:
    return {
        "ir_schema_version": "1.1.0",
        "source_path": "x.twb", "source_hash": "0" * 64,
        "tableau_version": "18.1", "config": {},
        "data_model": {
            "datasources": [], "tables": [{
                "id": "t", "name": "Sales", "datasource_id": "ds",
                "column_ids": ("t__col__region", "t__col__sales"),
                "primary_key": None,
            }], "relationships": [],
            "calculations": [], "parameters": [],
            "hierarchies": [], "sets": [],
        },
        "sheets": [{
            "id": "s1", "name": "Bars",
            "datasource_refs": ("ds",), "mark_type": "bar",
            "encoding": {
                "rows": [{"table_id": "t", "column_id": "t__col__region"}],
                "columns": [{"table_id": "t", "column_id": "t__col__sales"}],
                "color": None, "size": None, "label": None,
                "tooltip": None, "detail": [],
                "shape": None, "angle": None,
            },
            "filters": [], "sort": [], "dual_axis": False,
            "reference_lines": [], "uses_calculations": [],
            "pbir_visual": None,
        }],
        "dashboards": [], "unsupported": [],
    }


def test_stage4_attaches_pbir_visual_for_bar(tmp_path: Path):
    ctx = StageContext(workbook_id="w", output_dir=tmp_path,
                       config={}, stage_number=4)
    out = run(_ir_one_bar_sheet(), ctx).output
    [sh] = out["sheets"]
    pv = sh["pbir_visual"]
    assert pv is not None
    assert pv["visual_type"] == "clusteredBarChart"


def test_stage4_routes_unsupported_mark(tmp_path: Path):
    ir = _ir_one_bar_sheet()
    ir["sheets"][0]["mark_type"] = "polygon"
    ctx = StageContext(workbook_id="w", output_dir=tmp_path,
                       config={}, stage_number=4)
    out = run(ir, ctx).output
    [sh] = out["sheets"]
    assert sh["pbir_visual"] is None
    codes = [u["code"] for u in out["unsupported"]]
    assert "unsupported_mark_polygon" in codes
