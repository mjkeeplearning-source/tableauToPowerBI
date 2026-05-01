"""Stage 8 emits a JSON manifest with stable shape — see plan 5."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


_REPO = Path(__file__).resolve().parents[2]
_SYNTHETIC = _REPO / "tests" / "golden" / "synthetic"


@pytest.fixture(scope="module")
def synthetic_workbook() -> Path:
    candidates = sorted(p for p in _SYNTHETIC.glob("*.twb"))
    if not candidates:
        pytest.skip("no synthetic workbooks present")
    return candidates[0]


def test_stage8_manifest_has_expected_keys(tmp_path: Path, synthetic_workbook: Path):
    out = tmp_path / "out"
    proc = subprocess.run(
        [sys.executable, "-m", "tableau2pbir.cli", "convert",
         str(synthetic_workbook), "--out", str(out)],
        capture_output=True, text=True,
    )
    if proc.returncode != 0 and (
        "ANTHROPIC_API_KEY" in proc.stderr or "authentication_error" in proc.stderr
    ):
        pytest.skip("requires ANTHROPIC_API_KEY")
    assert proc.returncode == 0, proc.stderr

    wb_id = synthetic_workbook.stem
    manifest_path = out / wb_id / "stages" / "08_package_validate.json"
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert set(manifest.keys()) >= {"pbip_path", "validators", "status", "trigger_reasons"}
    assert manifest["status"] in {"ok", "partial", "failed"}
    for name in ("tmdl", "pbir_compile", "structural", "desktop_open", "rubric"):
        v = manifest["validators"][name]
        assert "result" in v
        assert v["result"] in {"passed", "failed", "skipped"}

    pbip = out / wb_id / manifest["pbip_path"]
    assert pbip.is_file()
    payload = json.loads(pbip.read_text(encoding="utf-8"))
    assert payload["version"] == "1.0"
    assert payload["artifacts"][0]["report"]["path"] == "Report"
