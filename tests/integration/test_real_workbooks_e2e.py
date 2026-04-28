"""End-to-end smoke tests against every .twb/.twbx in tests/golden/real.

Each workbook runs the full 8-stage pipeline. If stage 3 LLM fallback is
triggered and ANTHROPIC_API_KEY is not set, the test is skipped (not failed)
so CI remains green without credentials.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_REAL_DIR = Path(__file__).resolve().parents[1] / "golden" / "real"
_WORKBOOKS = sorted(
    p for p in _REAL_DIR.iterdir()
    if p.suffix in {".twb", ".twbx"}
)


def _convert(workbook: Path, out_dir: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "tableau2pbir.cli", "convert",
         str(workbook), "--out", str(out_dir)],
        capture_output=True, text=True, env=os.environ,
    )


def _stage_json(out: Path, wb_name: str, n: int, name: str) -> dict:
    return json.loads(
        (out / wb_name / "stages" / f"{n:02d}_{name}.json")
        .read_text(encoding="utf-8"),
    )


@pytest.mark.integration
@pytest.mark.parametrize("workbook", _WORKBOOKS, ids=[p.name for p in _WORKBOOKS])
def test_real_workbook_full_pipeline(workbook: Path, tmp_path: Path):
    out = tmp_path / "out"
    result = _convert(workbook, out)

    # Gracefully skip if the only failure is a missing or invalid API key.
    if result.returncode != 0 and (
        "ANTHROPIC_API_KEY not set" in result.stderr
        or "authentication_error" in result.stderr
        or "invalid x-api-key" in result.stderr
    ):
        pytest.skip(f"{workbook.name}: requires a valid ANTHROPIC_API_KEY for LLM calc translation")

    assert result.returncode == 0, (
        f"Pipeline failed for {workbook.name}:\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )

    wb_name = workbook.stem
    stages_dir = out / wb_name / "stages"

    expected = [
        (1, "extract"), (2, "canonicalize"), (3, "translate_calcs"),
        (4, "map_visuals"), (5, "compute_layout"), (6, "build_tmdl"),
        (7, "build_pbir"), (8, "package_validate"),
    ]
    for n, name in expected:
        stage_json = stages_dir / f"{n:02d}_{name}.json"
        stage_md = stages_dir / f"{n:02d}_{name}.summary.md"
        assert stage_json.exists(), f"Missing {stage_json.name} for {workbook.name}"
        assert stage_md.exists(), f"Missing {stage_md.name} for {workbook.name}"

    assert (out / wb_name / "unsupported.json").exists()

    # Structural IR checks on stages 1-2 output.
    ir2 = _stage_json(out, wb_name, 2, "canonicalize")
    assert "ir_schema_version" in ir2
    assert "data_model" in ir2
    assert "sheets" in ir2
    assert len(ir2["sheets"]) >= 1, f"{workbook.name} has no sheets in IR"


@pytest.mark.integration
@pytest.mark.parametrize("workbook", _WORKBOOKS, ids=[p.name for p in _WORKBOOKS])
def test_real_workbook_ir_structure(workbook: Path, tmp_path: Path):
    """Verify stage-2 IR is well-formed for every real workbook (no LLM needed)."""
    out = tmp_path / "out"
    result = subprocess.run(
        [sys.executable, "-m", "tableau2pbir.cli", "convert",
         str(workbook), "--out", str(out), "--gate", "canonicalize"],
        capture_output=True, text=True, env=os.environ,
    )
    assert result.returncode == 0, (
        f"Stages 1-2 failed for {workbook.name}:\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )

    wb_name = workbook.stem
    ir2 = _stage_json(out, wb_name, 2, "canonicalize")

    assert "ir_schema_version" in ir2
    assert "data_model" in ir2
    assert "sheets" in ir2
    assert "dashboards" in ir2
    assert isinstance(ir2["data_model"]["datasources"], list)
    assert len(ir2["sheets"]) >= 1, f"{workbook.name}: no sheets in stage-2 IR"
