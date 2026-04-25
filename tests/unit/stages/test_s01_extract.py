"""Stage 1 wiring test — exercises the real extract path against the
trivial Plan-1 fixture and asserts the shape of `01_extract.json`."""
from __future__ import annotations

from pathlib import Path

from tableau2pbir.pipeline import StageContext
from tableau2pbir.stages import s01_extract


def _ctx(tmp_path: Path) -> StageContext:
    return StageContext(workbook_id="trivial", output_dir=tmp_path,
                        config={}, stage_number=1)


def test_stage1_on_trivial_fixture(tmp_path: Path, synthetic_fixtures_dir: Path):
    fixture = synthetic_fixtures_dir / "trivial.twb"
    result = s01_extract.run({"source_path": str(fixture)}, _ctx(tmp_path))
    out = result.output

    assert out["source_path"].endswith("trivial.twb")
    assert len(out["source_hash"]) == 64
    assert out["tableau_version"] == "2024.1"       # parsed from source-build
    assert len(out["datasources"]) == 1
    assert out["datasources"][0]["name"] == "sample.csv"
    assert len(out["worksheets"]) == 1
    assert out["worksheets"][0]["name"] == "Revenue"
    assert len(out["dashboards"]) == 1
    assert out["parameters"] == []
    assert out["actions"] == []
    assert out["unsupported"] == []


def test_stage1_summary_contains_counts(tmp_path: Path, synthetic_fixtures_dir: Path):
    fixture = synthetic_fixtures_dir / "trivial.twb"
    result = s01_extract.run({"source_path": str(fixture)}, _ctx(tmp_path))
    assert "Stage 1 — extract" in result.summary_md
    assert "datasources: 1" in result.summary_md
    assert "worksheets: 1" in result.summary_md
    assert "dashboards: 1" in result.summary_md


def test_stage1_missing_source_path_raises(tmp_path: Path):
    import pytest
    with pytest.raises(KeyError):
        s01_extract.run({}, _ctx(tmp_path))
