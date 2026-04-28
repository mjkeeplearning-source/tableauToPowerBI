"""Contract: every Sheet either has pbir_visual set OR an UnsupportedItem
with a stage-4 code."""
from __future__ import annotations

from pathlib import Path

from tableau2pbir.pipeline import StageContext
from tableau2pbir.stages.s04_map_visuals import run

_STAGE4_CODES_PREFIXES = ("unsupported_mark_", "visual_binding_invalid")


def test_every_sheet_has_visual_or_unsupported(tmp_path: Path):
    ir = {
        "ir_schema_version": "1.1.0",
        "source_path": "x.twb", "source_hash": "0" * 64,
        "tableau_version": "18.1", "config": {},
        "data_model": {
            "datasources": [], "tables": [{
                "id": "t", "name": "T", "datasource_id": "ds",
                "column_ids": ("t__col__a",), "primary_key": None,
            }], "relationships": [],
            "calculations": [], "parameters": [],
            "hierarchies": [], "sets": [],
        },
        "sheets": [{
            "id": "s1", "name": "Polly",
            "datasource_refs": ("ds",), "mark_type": "polygon",
            "encoding": {
                "rows": [], "columns": [],
                "color": None, "size": None, "label": None,
                "tooltip": None, "detail": [], "shape": None, "angle": None,
            },
            "filters": [], "sort": [], "dual_axis": False,
            "reference_lines": [], "uses_calculations": [],
            "pbir_visual": None,
        }],
        "dashboards": [], "unsupported": [],
    }
    out = run(ir, StageContext(workbook_id="w", output_dir=tmp_path,
                               config={}, stage_number=4)).output
    unsupported_sheet_ids = {
        u["object_id"] for u in out["unsupported"]
        if any(u["code"].startswith(p) or u["code"] == p
               for p in _STAGE4_CODES_PREFIXES)
    }
    for sh in out["sheets"]:
        assert sh["pbir_visual"] is not None or sh["id"] in unsupported_sheet_ids
