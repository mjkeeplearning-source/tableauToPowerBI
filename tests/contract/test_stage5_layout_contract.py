"""Contract: after stage 5, every Leaf.position is populated and the full
IR still round-trips through Workbook.model_validate."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tableau2pbir.ir.workbook import Workbook


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


def _all_leaves(node: dict) -> list[dict]:
    """Recursively collect all leaf dicts from a layout tree node."""
    if "children" not in node:
        return [node]
    leaves = []
    for child in node["children"]:
        leaves.extend(_all_leaves(child))
    return leaves


# trivial.twb has no sheets needing AI; visual_marks_v1.twb has snapshots.
@pytest.mark.parametrize("fixture", ["trivial", "visual_marks_v1"])
def test_stage5_output_validates_as_workbook(
    tmp_path: Path, synthetic_fixtures_dir: Path, fixture: str
):
    out = tmp_path / "out"
    result = _convert(
        synthetic_fixtures_dir / f"{fixture}.twb", out,
        env={"PYTEST_SNAPSHOT": "replay"},
    )
    assert result.returncode == 0, result.stderr
    ir5 = _stage_json(out, fixture, 5, "compute_layout")
    # Must round-trip cleanly — raises ValidationError if schema is violated.
    Workbook.model_validate(ir5)


def test_stage5_all_leaves_have_position(
    tmp_path: Path, synthetic_fixtures_dir: Path
):
    """visual_marks_v1 has a dashboard with 7 leaves — verify all get positions."""
    out = tmp_path / "out"
    result = _convert(
        synthetic_fixtures_dir / "visual_marks_v1.twb", out,
        env={"PYTEST_SNAPSHOT": "replay"},
    )
    assert result.returncode == 0, result.stderr
    ir5 = _stage_json(out, "visual_marks_v1", 5, "compute_layout")
    for dash in ir5["dashboards"]:
        for leaf in _all_leaves(dash["layout_tree"]):
            assert leaf["position"] is not None, (
                f"Leaf in dashboard '{dash['name']}' has no position after stage 5"
            )
