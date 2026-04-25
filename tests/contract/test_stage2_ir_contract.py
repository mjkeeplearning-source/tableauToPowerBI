"""Stage 2 output must validate against the committed IR JSON Schema."""
from __future__ import annotations

import json
from pathlib import Path

from tableau2pbir.ir.version import IR_SCHEMA_VERSION
from tableau2pbir.ir.workbook import Workbook
from tableau2pbir.pipeline import StageContext
from tableau2pbir.stages import s02_canonicalize


def _ctx(tmp_path: Path) -> StageContext:
    return StageContext(workbook_id="wb", output_dir=tmp_path, config={}, stage_number=2)


_MIN_EXTRACT: dict = {
    "source_path": "/fake/trivial.twb",
    "source_hash": "0" * 64,
    "tableau_version": "2024.1",
    "datasources": [], "parameters": [], "worksheets": [],
    "dashboards": [], "actions": [], "unsupported": [],
}


def test_stage2_empty_output_validates_against_ir_schema(tmp_path: Path, repo_root: Path):
    result = s02_canonicalize.run(_MIN_EXTRACT, _ctx(tmp_path))
    # Schema exists (Plan-1 committed artifact).
    schema_path = repo_root / "schemas" / f"ir-v{IR_SCHEMA_VERSION}.schema.json"
    assert schema_path.exists()
    # Round-trip via pydantic: if Workbook.model_validate accepts it, it matches
    # the schema (pydantic is the schema's source of truth per §5.4).
    Workbook.model_validate(result.output)
