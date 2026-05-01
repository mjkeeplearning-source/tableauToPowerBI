from pathlib import Path
from unittest.mock import patch, MagicMock
from tableau2pbir.validate.tmdl_schema import run_tmdl_validity
from tableau2pbir.validate.results import ValidatorOutcome


def test_skipped_when_te2_unavailable(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("TE2_CLI_PATH", raising=False)
    with patch("tableau2pbir.validate.tmdl_schema.shutil.which", return_value=None):
        r = run_tmdl_validity(tmp_path)
    assert r.outcome == ValidatorOutcome.SKIPPED
    assert r.reason == "te2_unavailable"


def test_passed_when_te2_returns_zero(tmp_path: Path, monkeypatch):
    (tmp_path / "SemanticModel" / "definition").mkdir(parents=True)
    monkeypatch.setenv("TE2_CLI_PATH", "C:/fake/TabularEditor.exe")
    fake_proc = MagicMock(returncode=0, stdout="OK", stderr="")
    with patch("tableau2pbir.validate.tmdl_schema.subprocess.run", return_value=fake_proc) as srun:
        r = run_tmdl_validity(tmp_path)
    assert r.outcome == ValidatorOutcome.PASSED
    assert r.log_path == "validation/tmdl.log"
    log = (tmp_path / "validation" / "tmdl.log").read_text(encoding="utf-8")
    assert "OK" in log
    cmd = srun.call_args[0][0]
    assert cmd[0] == "C:/fake/TabularEditor.exe"
    assert "-B" in cmd and "/c" in cmd
    # TE2 must be pointed at the definition/ subfolder, not the root
    assert str(tmp_path / "SemanticModel" / "definition") in cmd


def test_failed_when_te2_returns_nonzero(tmp_path: Path, monkeypatch):
    (tmp_path / "SemanticModel" / "definition").mkdir(parents=True)
    monkeypatch.setenv("TE2_CLI_PATH", "C:/fake/TabularEditor.exe")
    fake_proc = MagicMock(returncode=1, stdout="", stderr="schema error: bad measure")
    with patch("tableau2pbir.validate.tmdl_schema.subprocess.run", return_value=fake_proc):
        r = run_tmdl_validity(tmp_path)
    assert r.outcome == ValidatorOutcome.FAILED
    assert "schema error" in (tmp_path / "validation" / "tmdl.log").read_text(encoding="utf-8")


def test_skipped_when_semanticmodel_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("TE2_CLI_PATH", "C:/fake/TabularEditor.exe")
    r = run_tmdl_validity(tmp_path)
    assert r.outcome == ValidatorOutcome.SKIPPED
    assert r.reason == "semanticmodel_missing"
