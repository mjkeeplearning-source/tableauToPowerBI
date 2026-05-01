"""Contract: Stage 7 emits valid PBIR JSON with required structural guarantees."""
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


# visual_marks_v1 has visuals + a dashboard; trivial is the baseline sanity check.
@pytest.mark.parametrize("fixture", ["trivial", "visual_marks_v1"])
def test_stage7_report_json_is_valid(
    synthetic_fixtures_dir: Path, tmp_path: Path, fixture: str
):
    out = tmp_path / "out"
    result = _convert(
        synthetic_fixtures_dir / f"{fixture}.twb", out,
        env={"PYTEST_SNAPSHOT": "replay"},
    )
    assert result.returncode == 0, result.stderr

    rd = out / fixture / "Report" / "definition"
    report_json = rd / "report.json"
    assert report_json.is_file(), "report.json missing"
    report = json.loads(report_json.read_text(encoding="utf-8"))
    assert "pages" in report


@pytest.mark.parametrize("fixture", ["trivial", "visual_marks_v1"])
def test_stage7_page_order_matches_disk(
    synthetic_fixtures_dir: Path, tmp_path: Path, fixture: str
):
    out = tmp_path / "out"
    result = _convert(
        synthetic_fixtures_dir / f"{fixture}.twb", out,
        env={"PYTEST_SNAPSHOT": "replay"},
    )
    assert result.returncode == 0, result.stderr

    rd = out / fixture / "Report" / "definition"
    report = json.loads((rd / "report.json").read_text(encoding="utf-8"))
    page_order = report["pages"]["pageOrder"]

    pages_dir = rd / "pages"
    pages_on_disk = (
        {p.name for p in pages_dir.iterdir() if p.is_dir()}
        if pages_dir.is_dir() else set()
    )
    assert set(page_order) == pages_on_disk


@pytest.mark.parametrize("fixture", ["trivial", "visual_marks_v1"])
def test_stage7_visuals_have_required_fields(
    synthetic_fixtures_dir: Path, tmp_path: Path, fixture: str
):
    out = tmp_path / "out"
    result = _convert(
        synthetic_fixtures_dir / f"{fixture}.twb", out,
        env={"PYTEST_SNAPSHOT": "replay"},
    )
    assert result.returncode == 0, result.stderr

    rd = out / fixture / "Report" / "definition"
    pages_dir = rd / "pages"
    if not pages_dir.is_dir():
        pytest.skip("no pages directory — fixture has no dashboards")

    for page_dir in pages_dir.iterdir():
        if not page_dir.is_dir():
            continue
        visuals_dir = page_dir / "visuals"
        if not visuals_dir.is_dir():
            continue
        for v_dir in visuals_dir.iterdir():
            if not v_dir.is_dir():
                continue
            obj = json.loads((v_dir / "visual.json").read_text(encoding="utf-8"))
            assert "name" in obj, f"{v_dir.name}/visual.json missing 'name'"
            assert "position" in obj, f"{v_dir.name}/visual.json missing 'position'"
            assert obj.get("visual", {}).get("visualType"), (
                f"{v_dir.name}/visual.json missing visual.visualType"
            )


@pytest.mark.parametrize("fixture", ["trivial", "visual_marks_v1"])
def test_stage7_manifest_has_blocked_visuals_list(
    synthetic_fixtures_dir: Path, tmp_path: Path, fixture: str
):
    out = tmp_path / "out"
    result = _convert(
        synthetic_fixtures_dir / f"{fixture}.twb", out,
        env={"PYTEST_SNAPSHOT": "replay"},
    )
    assert result.returncode == 0, result.stderr

    manifest_path = out / fixture / "stages" / "07_build_pbir.json"
    assert manifest_path.is_file(), "07_build_pbir.json stage manifest missing"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert isinstance(manifest.get("blocked_visuals"), list), (
        "manifest['blocked_visuals'] must be a list"
    )
