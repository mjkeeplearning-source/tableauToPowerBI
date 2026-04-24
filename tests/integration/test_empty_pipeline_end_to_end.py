"""Layer iii (§9) smoke: `tableau2pbir convert` on the trivial fixture produces
the full expected artifact tree. Real IR/DAX/PBIR content comes in Plans 2–5."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.integration
def test_end_to_end_empty_pipeline(tmp_path: Path, synthetic_fixtures_dir: Path):
    out = tmp_path / "out"
    fixture = synthetic_fixtures_dir / "trivial.twb"

    result = subprocess.run(
        [sys.executable, "-m", "tableau2pbir.cli", "convert",
         str(fixture), "--out", str(out)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"stderr:\n{result.stderr}\nstdout:\n{result.stdout}"

    wb_dir = out / "trivial"
    stages = wb_dir / "stages"

    expected_stages = [
        (1, "extract"), (2, "canonicalize"), (3, "translate_calcs"),
        (4, "map_visuals"), (5, "compute_layout"), (6, "build_tmdl"),
        (7, "build_pbir"), (8, "package_validate"),
    ]
    for idx, name in expected_stages:
        assert (stages / f"{idx:02d}_{name}.json").exists(), f"missing {idx:02d}_{name}.json"
        assert (stages / f"{idx:02d}_{name}.summary.md").exists(), f"missing {idx:02d}_{name}.summary.md"

    assert (wb_dir / "trivial.pbip").exists()
    assert (wb_dir / "unsupported.json").exists()
