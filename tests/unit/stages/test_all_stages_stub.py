"""Every stage module exports a `run(input_json, ctx) -> StageResult` function.
Verified here to pin the contract."""
from __future__ import annotations

from pathlib import Path

import pytest

from tableau2pbir.pipeline import StageContext, StageResult

STAGE_MODULES = [
    # s01–s07 require real IR; tested separately
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
