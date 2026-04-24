from __future__ import annotations

from pathlib import Path

import pytest

from tableau2pbir.llm.snapshots import SnapshotStore, is_replay_mode


def test_is_replay_mode_reads_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("PYTEST_SNAPSHOT", raising=False)
    assert is_replay_mode() is False
    monkeypatch.setenv("PYTEST_SNAPSHOT", "replay")
    assert is_replay_mode() is True
    monkeypatch.setenv("PYTEST_SNAPSHOT", "record")
    assert is_replay_mode() is False


def test_snapshot_store_load(tmp_path: Path):
    (tmp_path / "translate_calc").mkdir()
    (tmp_path / "translate_calc" / "fixture1.json").write_text(
        '{"dax_expr": "SUM([Sales])", "confidence": "high", "notes": ""}',
        encoding="utf-8",
    )
    store = SnapshotStore(tmp_path)
    data = store.load("translate_calc", "fixture1")
    assert data["dax_expr"] == "SUM([Sales])"


def test_snapshot_store_missing_raises(tmp_path: Path):
    store = SnapshotStore(tmp_path)
    with pytest.raises(FileNotFoundError):
        store.load("translate_calc", "missing")
