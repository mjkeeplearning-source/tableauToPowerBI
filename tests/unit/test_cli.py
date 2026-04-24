from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_cli_convert_runs_empty_pipeline(tmp_path: Path, synthetic_fixtures_dir: Path):
    out = tmp_path / "out"
    result = subprocess.run(
        [sys.executable, "-m", "tableau2pbir.cli", "convert",
         str(synthetic_fixtures_dir / "trivial.twb"), "--out", str(out)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert (out / "trivial" / "trivial.pbip").exists()
    assert (out / "trivial" / "stages" / "08_package_validate.json").exists()
    assert (out / "trivial" / "unsupported.json").exists()


def test_cli_convert_with_gate_stops_early(tmp_path: Path, synthetic_fixtures_dir: Path):
    out = tmp_path / "out"
    result = subprocess.run(
        [sys.executable, "-m", "tableau2pbir.cli", "convert",
         str(synthetic_fixtures_dir / "trivial.twb"),
         "--out", str(out), "--gate", "canonicalize"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert (out / "trivial" / "stages" / "02_canonicalize.json").exists()
    assert not (out / "trivial" / "stages" / "03_translate_calcs.json").exists()


def test_cli_resume_continues_from(tmp_path: Path, synthetic_fixtures_dir: Path):
    out = tmp_path / "out"
    # First: gated run
    subprocess.run(
        [sys.executable, "-m", "tableau2pbir.cli", "convert",
         str(synthetic_fixtures_dir / "trivial.twb"),
         "--out", str(out), "--gate", "canonicalize"],
        capture_output=True, text=True, check=True,
    )
    # Resume
    result = subprocess.run(
        [sys.executable, "-m", "tableau2pbir.cli", "resume",
         str(out / "trivial"), "--from", "translate_calcs"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert (out / "trivial" / "trivial.pbip").exists()


def test_cli_help_lists_subcommands():
    result = subprocess.run(
        [sys.executable, "-m", "tableau2pbir.cli", "--help"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "convert" in result.stdout
    assert "resume" in result.stdout
