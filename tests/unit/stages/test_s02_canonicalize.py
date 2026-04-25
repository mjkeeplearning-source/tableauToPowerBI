"""Stage 2 wiring test. Built incrementally: this task covers only the
skeleton (version stamp + top-level Workbook assembly). Subsequent tasks
add datasource/table/calc/parameter/sheet/dashboard coverage."""
from __future__ import annotations

from pathlib import Path

from tableau2pbir.ir.version import IR_SCHEMA_VERSION
from tableau2pbir.pipeline import StageContext
from tableau2pbir.stages import s02_canonicalize


def _ctx(tmp_path: Path) -> StageContext:
    return StageContext(workbook_id="wb", output_dir=tmp_path, config={}, stage_number=2)


_MIN_EXTRACT: dict = {
    "source_path": "/fake/trivial.twb",
    "source_hash": "0" * 64,
    "tableau_version": "2024.1",
    "datasources": [],
    "parameters": [],
    "worksheets": [],
    "dashboards": [],
    "actions": [],
    "unsupported": [],
}


def test_stage2_stamps_schema_version(tmp_path: Path):
    result = s02_canonicalize.run(_MIN_EXTRACT, _ctx(tmp_path))
    assert result.output["ir_schema_version"] == IR_SCHEMA_VERSION


def test_stage2_preserves_source_metadata(tmp_path: Path):
    result = s02_canonicalize.run(_MIN_EXTRACT, _ctx(tmp_path))
    out = result.output
    assert out["source_path"] == "/fake/trivial.twb"
    assert out["source_hash"] == "0" * 64
    assert out["tableau_version"] == "2024.1"


def test_stage2_empty_workbook_has_empty_data_model(tmp_path: Path):
    result = s02_canonicalize.run(_MIN_EXTRACT, _ctx(tmp_path))
    dm = result.output["data_model"]
    for key in ("datasources", "tables", "relationships",
                "calculations", "parameters", "hierarchies", "sets"):
        assert dm[key] == []
    assert result.output["sheets"] == []
    assert result.output["dashboards"] == []
    assert result.output["unsupported"] == []
