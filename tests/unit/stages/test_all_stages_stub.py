"""Every stage module exports a `run(input_json, ctx) -> StageResult` function.
Verified here to pin the contract."""
from __future__ import annotations

from pathlib import Path

import pytest

from tableau2pbir.pipeline import StageContext, StageResult

STAGE_MODULES = [
    "tableau2pbir.stages.s01_extract",
    "tableau2pbir.stages.s02_canonicalize",
    "tableau2pbir.stages.s03_translate_calcs",
    "tableau2pbir.stages.s04_map_visuals",
    "tableau2pbir.stages.s05_compute_layout",
    "tableau2pbir.stages.s06_build_tmdl",
    "tableau2pbir.stages.s07_build_pbir",
    "tableau2pbir.stages.s08_package_validate",
]


@pytest.mark.parametrize("module_path", STAGE_MODULES)
def test_each_stage_has_run_returning_stage_result(module_path: str, tmp_path: Path):
    import importlib
    mod = importlib.import_module(module_path)
    assert hasattr(mod, "run"), f"{module_path} missing run()"
    ctx = StageContext(workbook_id="wb", output_dir=tmp_path, config={}, stage_number=1)
    result = mod.run({}, ctx)
    assert isinstance(result, StageResult)
