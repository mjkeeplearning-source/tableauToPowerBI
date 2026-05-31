from __future__ import annotations
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from tableau2pbir.regression.corpus import CorpusEntry, load_corpus
from tableau2pbir.regression.snapshot import register_workbook, RegistrationError


def _make_fake_pipeline_output(out_dir: Path, wb_name: str) -> None:
    """Create a minimal fake pipeline output tree."""
    sm = out_dir / wb_name / "SemanticModel" / "definition" / "tables"
    sm.mkdir(parents=True)
    (sm / "orders.tmdl").write_text("table orders\n\tcolumn id\n\t\tdataType: int64\n", encoding="utf-8")
    rd = out_dir / wb_name / "Report" / "definition"
    rd.mkdir(parents=True)
    (rd / "report.json").write_text('{"$schema":"x","id":"r1"}', encoding="utf-8")
    stages = out_dir / wb_name / "stages"
    stages.mkdir()
    (stages / "01_extract.json").write_text("{}", encoding="utf-8")


def test_register_copies_tmdl_and_json(tmp_path: Path):
    workbook = tmp_path / "simple.twb"
    workbook.write_text("<workbook/>", encoding="utf-8")
    corpus_path = tmp_path / "corpus.yaml"
    corpus_path.write_text("workbooks: []\n", encoding="utf-8")
    snap_root = tmp_path / "snapshots"

    def fake_run(cmd, **kwargs):
        wb_name = Path(cmd[cmd.index("convert") + 1]).stem
        out_dir = Path(cmd[cmd.index("--out") + 1])
        _make_fake_pipeline_output(out_dir, wb_name)
        return MagicMock(returncode=0, stderr="", stdout="")

    with patch("subprocess.run", side_effect=fake_run):
        register_workbook(
            workbook_path=workbook,
            corpus_path=corpus_path,
            snapshots_root=snap_root,
            notes="test wb",
            added_by="tester",
            added_on="2026-05-31",
        )

    snap_dir = snap_root / "simple"
    assert (snap_dir / "SemanticModel" / "definition" / "tables" / "orders.tmdl").exists()
    assert (snap_dir / "Report" / "definition" / "report.json").exists()
    assert not (snap_dir / "stages" / "01_extract.json").exists(), "stage JSON must not be snapshotted"


def test_register_appends_to_corpus(tmp_path: Path):
    workbook = tmp_path / "simple.twb"
    workbook.write_text("<workbook/>", encoding="utf-8")
    corpus_path = tmp_path / "corpus.yaml"
    corpus_path.write_text("workbooks: []\n", encoding="utf-8")
    snap_root = tmp_path / "snapshots"

    def fake_run(cmd, **kwargs):
        wb_name = Path(cmd[cmd.index("convert") + 1]).stem
        out_dir = Path(cmd[cmd.index("--out") + 1])
        _make_fake_pipeline_output(out_dir, wb_name)
        return MagicMock(returncode=0, stderr="", stdout="")

    with patch("subprocess.run", side_effect=fake_run):
        register_workbook(
            workbook_path=workbook,
            corpus_path=corpus_path,
            snapshots_root=snap_root,
            notes="test wb",
            added_by="tester",
            added_on="2026-05-31",
        )

    entries = load_corpus(corpus_path)
    assert len(entries) == 1
    assert entries[0].name == "simple"
    assert entries[0].notes == "test wb"
    assert entries[0].added_by == "tester"


def test_register_duplicate_raises(tmp_path: Path):
    workbook = tmp_path / "simple.twb"
    workbook.write_text("<workbook/>", encoding="utf-8")
    corpus_path = tmp_path / "corpus.yaml"
    import yaml
    corpus_path.write_text(
        yaml.dump({"workbooks": [{"name": "simple", "path": "x", "added_by": "me", "added_on": "2026-01-01", "notes": ""}]}),
        encoding="utf-8",
    )
    snap_root = tmp_path / "snapshots"

    with pytest.raises(RegistrationError, match="already registered"):
        register_workbook(
            workbook_path=workbook,
            corpus_path=corpus_path,
            snapshots_root=snap_root,
        )


def test_register_aborts_on_pipeline_failure(tmp_path: Path):
    workbook = tmp_path / "simple.twb"
    workbook.write_text("<workbook/>", encoding="utf-8")
    corpus_path = tmp_path / "corpus.yaml"
    corpus_path.write_text("workbooks: []\n", encoding="utf-8")
    snap_root = tmp_path / "snapshots"

    with patch("subprocess.run", return_value=MagicMock(returncode=1, stderr="stage failed", stdout="")):
        with pytest.raises(RegistrationError, match="pipeline failed"):
            register_workbook(
                workbook_path=workbook,
                corpus_path=corpus_path,
                snapshots_root=snap_root,
            )

    assert not (snap_root / "simple").exists(), "snapshot dir must not be created on failure"
    assert load_corpus(corpus_path) == [], "corpus must not be modified on failure"
