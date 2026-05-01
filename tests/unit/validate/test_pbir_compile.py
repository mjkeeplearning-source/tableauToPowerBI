from pathlib import Path
from unittest.mock import patch, MagicMock
from tableau2pbir.validate.pbir_compile import run_pbir_compile
from tableau2pbir.validate.results import ValidatorOutcome


def test_skipped_when_pbi_tools_unavailable(tmp_path, monkeypatch):
    monkeypatch.delenv("PBI_TOOLS_PATH", raising=False)
    with patch("tableau2pbir.validate.pbir_compile.shutil.which", return_value=None):
        r = run_pbir_compile(tmp_path)
    assert r.outcome == ValidatorOutcome.SKIPPED
    assert r.reason == "pbi_tools_unavailable"


def test_passed_on_zero_exit(tmp_path, monkeypatch):
    monkeypatch.setenv("PBI_TOOLS_PATH", "C:/fake/pbi-tools.exe")
    fake = MagicMock(returncode=0, stdout="compile ok", stderr="")
    with patch("tableau2pbir.validate.pbir_compile.subprocess.run", return_value=fake) as srun:
        r = run_pbir_compile(tmp_path)
    assert r.outcome == ValidatorOutcome.PASSED
    assert "compile ok" in (tmp_path / "validation" / "pbir_compile.log").read_text(encoding="utf-8")
    assert srun.call_args[0][0][0:2] == ["C:/fake/pbi-tools.exe", "compile"]


def test_failed_on_nonzero_exit(tmp_path, monkeypatch):
    monkeypatch.setenv("PBI_TOOLS_PATH", "C:/fake/pbi-tools.exe")
    fake = MagicMock(returncode=2, stdout="", stderr="missing report.json")
    with patch("tableau2pbir.validate.pbir_compile.subprocess.run", return_value=fake):
        r = run_pbir_compile(tmp_path)
    assert r.outcome == ValidatorOutcome.FAILED
