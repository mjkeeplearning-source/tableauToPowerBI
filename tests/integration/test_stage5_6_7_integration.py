"""End-to-end integration: stages 5, 6, and 7 produce all expected artifacts."""
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


# dashboard_tiled_floating has a 'bar' sheet that hits the Stage 4 AI fallback
# (map_visual) with no LLM snapshot — requires a live cache hit. Excluded from
# snapshot-replay parametrize; covered separately by the real-workbook E2E gate.
_REPLAY_FIXTURES = [
    "trivial",
    "visual_marks_v1",
    "params_all_intents",
    "datasources_mixed",
]


@pytest.mark.integration
@pytest.mark.parametrize("fixture", _REPLAY_FIXTURES)
def test_full_v1_pipeline_semantic_model_artifacts(
    synthetic_fixtures_dir: Path, tmp_path: Path, fixture: str
):
    out = tmp_path / "out"
    result = _convert(
        synthetic_fixtures_dir / f"{fixture}.twb", out,
        env={"PYTEST_SNAPSHOT": "replay"},
    )
    assert result.returncode == 0, result.stderr

    sm = out / fixture / "SemanticModel"
    assert (sm / "definition.pbism").is_file(), "definition.pbism missing"
    assert (sm / "definition" / "database.tmdl").is_file(), "database.tmdl missing"
    assert (sm / "definition" / "model.tmdl").is_file(), "model.tmdl missing"


@pytest.mark.integration
@pytest.mark.parametrize("fixture", _REPLAY_FIXTURES)
def test_full_v1_pipeline_report_artifacts(
    synthetic_fixtures_dir: Path, tmp_path: Path, fixture: str
):
    out = tmp_path / "out"
    result = _convert(
        synthetic_fixtures_dir / f"{fixture}.twb", out,
        env={"PYTEST_SNAPSHOT": "replay"},
    )
    assert result.returncode == 0, result.stderr

    rd = out / fixture / "Report" / "definition"
    assert (rd / "report.json").is_file(), "report.json missing"
    assert (rd / "pages" / "pages.json").is_file(), "pages/pages.json missing"
    pages_manifest = json.loads((rd / "pages" / "pages.json").read_text(encoding="utf-8"))
    assert "pageOrder" in pages_manifest, "pageOrder missing from pages.json"
    page_dirs = [p for p in (rd / "pages").iterdir() if p.is_dir()]
    for pd in page_dirs:
        assert pd.name.startswith("ReportSection"), f"page folder must be ReportSectionN, got {pd.name}"


@pytest.mark.integration
@pytest.mark.parametrize("fixture", _REPLAY_FIXTURES)
def test_full_v1_pipeline_stage_manifests_present(
    synthetic_fixtures_dir: Path, tmp_path: Path, fixture: str
):
    out = tmp_path / "out"
    result = _convert(
        synthetic_fixtures_dir / f"{fixture}.twb", out,
        env={"PYTEST_SNAPSHOT": "replay"},
    )
    assert result.returncode == 0, result.stderr

    stages_dir = out / fixture / "stages"
    assert (stages_dir / "05_compute_layout.json").is_file()
    assert (stages_dir / "06_build_tmdl.json").is_file()
    assert (stages_dir / "07_build_pbir.json").is_file()

    manifest7 = json.loads((stages_dir / "07_build_pbir.json").read_text(encoding="utf-8"))
    assert isinstance(manifest7.get("blocked_visuals"), list), (
        "07_build_pbir.json must contain blocked_visuals list"
    )
