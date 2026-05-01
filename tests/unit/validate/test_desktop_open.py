from pathlib import Path
from unittest.mock import patch, MagicMock
import json

from tableau2pbir.validate.desktop_open import run_desktop_open
from tableau2pbir.validate.results import ValidatorOutcome


def _write_trace(traces_dir: Path, events: list[dict]) -> Path:
    traces_dir.mkdir(parents=True)
    p = traces_dir / "session.json"
    p.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")
    return p


def test_skipped_when_pbi_desktop_unavailable(tmp_path, monkeypatch):
    monkeypatch.delenv("PBI_DESKTOP_PATH", raising=False)
    with patch("tableau2pbir.validate.desktop_open.shutil.which", return_value=None):
        r = run_desktop_open(tmp_path / "wb.pbip", datasource_tiers=(1,),
                             traces_dir=tmp_path / "traces")
    assert r.outcome == ValidatorOutcome.SKIPPED
    assert r.reason == "desktop_unavailable"


def test_tier1_passes_with_report_and_model_loaded(tmp_path, monkeypatch):
    monkeypatch.setenv("PBI_DESKTOP_PATH", "C:/fake/PBIDesktop.exe")
    pbip = tmp_path / "wb.pbip"
    pbip.write_text("{}", encoding="utf-8")
    traces = tmp_path / "traces"
    _write_trace(traces, [
        {"ts": 1000, "event": "ReportLoaded"},
        {"ts": 2000, "event": "ModelLoaded"},
    ])
    fake_proc = MagicMock()
    fake_proc.poll.return_value = None
    fake_proc.terminate = MagicMock()
    fake_proc.wait = MagicMock(return_value=0)
    with patch("tableau2pbir.validate.desktop_open.subprocess.Popen", return_value=fake_proc), \
         patch("tableau2pbir.validate.desktop_open._wait_for_load",
               return_value=("done", None)):
        r = run_desktop_open(pbip, datasource_tiers=(1,), traces_dir=traces,
                             desktop_version="2.130")
    assert r.outcome == ValidatorOutcome.PASSED


def test_tier1_fails_when_only_report_loaded(tmp_path, monkeypatch):
    monkeypatch.setenv("PBI_DESKTOP_PATH", "C:/fake/PBIDesktop.exe")
    pbip = tmp_path / "wb.pbip"
    pbip.write_text("{}", encoding="utf-8")
    traces = tmp_path / "traces"
    _write_trace(traces, [{"ts": 1000, "event": "ReportLoaded"}])
    fake_proc = MagicMock()
    fake_proc.poll.return_value = None
    with patch("tableau2pbir.validate.desktop_open.subprocess.Popen", return_value=fake_proc), \
         patch("tableau2pbir.validate.desktop_open._wait_for_load",
               return_value=("done", None)):
        r = run_desktop_open(pbip, datasource_tiers=(1,), traces_dir=traces,
                             desktop_version="2.130")
    assert r.outcome == ValidatorOutcome.FAILED


def test_tier2_passes_with_only_report_loaded_and_auth_event(tmp_path, monkeypatch):
    monkeypatch.setenv("PBI_DESKTOP_PATH", "C:/fake/PBIDesktop.exe")
    pbip = tmp_path / "wb.pbip"
    pbip.write_text("{}", encoding="utf-8")
    traces = tmp_path / "traces"
    _write_trace(traces, [
        {"ts": 1000, "event": "ReportLoaded"},
        {"ts": 1500, "event": "AuthenticationNeeded"},
    ])
    fake_proc = MagicMock()
    fake_proc.poll.return_value = None
    with patch("tableau2pbir.validate.desktop_open.subprocess.Popen", return_value=fake_proc), \
         patch("tableau2pbir.validate.desktop_open._wait_for_load",
               return_value=("done", None)):
        r = run_desktop_open(pbip, datasource_tiers=(1, 2), traces_dir=traces,
                             desktop_version="2.130")
    assert r.outcome == ValidatorOutcome.PASSED
    assert any(e.name == "AuthenticationNeeded" for e in r.expected_credential_prompts)


def test_tier1_fails_when_visual_error_present(tmp_path, monkeypatch):
    monkeypatch.setenv("PBI_DESKTOP_PATH", "C:/fake/PBIDesktop.exe")
    pbip = tmp_path / "wb.pbip"
    pbip.write_text("{}", encoding="utf-8")
    traces = tmp_path / "traces"
    _write_trace(traces, [
        {"ts": 1000, "event": "ReportLoaded"},
        {"ts": 1500, "event": "ModelLoaded"},
        {"ts": 2000, "event": "VisualError"},
    ])
    fake_proc = MagicMock()
    fake_proc.poll.return_value = None
    with patch("tableau2pbir.validate.desktop_open.subprocess.Popen", return_value=fake_proc), \
         patch("tableau2pbir.validate.desktop_open._wait_for_load",
               return_value=("done", None)):
        r = run_desktop_open(pbip, datasource_tiers=(1,), traces_dir=traces,
                             desktop_version="2.130")
    assert r.outcome == ValidatorOutcome.FAILED
