"""End-to-end stage 1 → 4 against synthetic fixtures. Stages 5–8 still
run as no-op stubs."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


def _convert(fixture: Path, out: Path, *, env: dict[str, str] | None = None):
    return subprocess.run(
        [sys.executable, "-m", "tableau2pbir.cli", "convert",
         str(fixture), "--out", str(out)],
        capture_output=True, text=True,
        env={**os.environ, **(env or {})},
    )


def _stage_json(out: Path, wb_name: str, n: int, name: str) -> dict:
    return json.loads(
        (out / wb_name / "stages" / f"{n:02d}_{name}.json")
        .read_text(encoding="utf-8"),
    )


@pytest.mark.integration
def test_stage3_translates_row_calc(tmp_path: Path, synthetic_fixtures_dir: Path):
    out = tmp_path / "out"
    result = _convert(synthetic_fixtures_dir / "calc_row.twb", out,
                      env={"PYTEST_SNAPSHOT": "replay"})
    assert result.returncode == 0, result.stderr
    ir3 = _stage_json(out, "calc_row", 3, "translate_calcs")
    [calc] = [c for c in ir3["data_model"]["calculations"]
              if c["kind"] == "row"]
    assert calc["dax_expr"] is not None


@pytest.mark.integration
def test_stage3_skips_deferred_table_calc(tmp_path: Path, synthetic_fixtures_dir: Path):
    out = tmp_path / "out"
    result = _convert(synthetic_fixtures_dir / "calc_quick_table.twb", out,
                      env={"PYTEST_SNAPSHOT": "replay"})
    assert result.returncode == 0, result.stderr
    ir3 = _stage_json(out, "calc_quick_table", 3, "translate_calcs")
    deferred_codes = [u["code"] for u in ir3["unsupported"]
                      if u["code"].startswith("deferred_feature_")]
    assert "deferred_feature_table_calcs" in deferred_codes
    # The deferred calc has no dax_expr.
    for c in ir3["data_model"]["calculations"]:
        if c["kind"] == "table_calc":
            assert c["dax_expr"] is None


@pytest.mark.integration
def test_stage4_attaches_visual_for_bar_fixture(
    tmp_path: Path, synthetic_fixtures_dir: Path,
):
    out = tmp_path / "out"
    result = _convert(synthetic_fixtures_dir / "visual_marks_v1.twb", out,
                      env={"PYTEST_SNAPSHOT": "replay"})
    assert result.returncode == 0, result.stderr
    ir4 = _stage_json(out, "visual_marks_v1", 4, "map_visuals")
    visual_types = {sh["pbir_visual"]["visual_type"]
                    for sh in ir4["sheets"]
                    if sh["pbir_visual"] is not None}
    # At least the bar and line marks should map to v1 visuals.
    assert "clusteredBarChart" in visual_types
    assert "lineChart" in visual_types
