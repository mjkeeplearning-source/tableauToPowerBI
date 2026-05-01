"""Every stage module exports a `run(input_json, ctx) -> StageResult` function.
Verified here to pin the contract."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from tableau2pbir.pipeline import StageContext, StageResult

STAGE_MODULES = [
    # s01–s07 require real IR; tested separately
    "tableau2pbir.stages.s08_package_validate",
]


def _scaffold_s08(out: Path) -> None:
    """Minimal prior-stage artifacts for s08 smoke test."""
    (out / "Report" / "definition" / "pages").mkdir(parents=True)
    (out / "Report" / "definition" / "report.json").write_text(
        json.dumps({"name": "wb", "pageOrder": []}), encoding="utf-8")
    (out / "SemanticModel" / "tables").mkdir(parents=True)
    stages = out / "stages"
    stages.mkdir()
    (stages / "02_canonicalize.json").write_text(json.dumps({
        "data_model": {"datasources": [], "calculations": [], "parameters": []},
        "dashboards": [], "unsupported": [],
    }), encoding="utf-8")
    (stages / "07_build_pbir.json").write_text(
        json.dumps({"blocked_visuals": [], "counts": {}}), encoding="utf-8")
    (out / "unsupported.json").write_text("[]", encoding="utf-8")


@pytest.mark.parametrize("module_path", STAGE_MODULES)
def test_each_stage_has_run_returning_stage_result(module_path: str, tmp_path: Path):
    import importlib
    mod = importlib.import_module(module_path)
    assert hasattr(mod, "run"), f"{module_path} missing run()"
    if module_path.endswith("s08_package_validate"):
        _scaffold_s08(tmp_path)
    ctx = StageContext(workbook_id="wb", output_dir=tmp_path, config={}, stage_number=8)
    with patch("tableau2pbir.validate.tmdl_schema._resolve_te2", return_value=None), \
         patch("tableau2pbir.validate.pbir_compile._resolve_pbi_tools", return_value=None), \
         patch("tableau2pbir.validate.desktop_open._resolve_pbi_desktop", return_value=None):
        result = mod.run({}, ctx)
    assert isinstance(result, StageResult)
