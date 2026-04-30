"""Contract: Stage 6 TMDL output is utf-8/LF-only and headers are well-formed."""
from __future__ import annotations

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


# trivial and datasources_mixed have no AI-dependent calcs
@pytest.mark.parametrize("fixture", ["trivial", "datasources_mixed"])
def test_stage6_emits_well_formed_tmdl(
    synthetic_fixtures_dir: Path, tmp_path: Path, fixture: str
):
    out = tmp_path / "out"
    result = _convert(
        synthetic_fixtures_dir / f"{fixture}.twb", out,
        env={"PYTEST_SNAPSHOT": "replay"},
    )
    assert result.returncode == 0, result.stderr

    wb_name = fixture
    sm = out / wb_name / "SemanticModel"
    assert (sm / "database.tmdl").is_file(), "database.tmdl missing"
    assert (sm / "model.tmdl").is_file(), "model.tmdl missing"

    for path in (sm / "tables").glob("*.tmdl"):
        raw = path.read_bytes()
        assert b"\r\n" not in raw, f"{path.name} has CRLF line endings"
        decoded = raw.decode("utf-8")
        assert decoded.startswith("table "), f"{path.name} missing 'table ' header"

    for path in (sm / "relationships").glob("*.tmdl"):
        decoded = path.read_text(encoding="utf-8")
        assert decoded.startswith("relationship "), f"{path.name} missing 'relationship ' header"
