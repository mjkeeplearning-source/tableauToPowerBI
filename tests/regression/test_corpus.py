from __future__ import annotations
import pytest
from pathlib import Path
from tableau2pbir.regression.corpus import CorpusEntry, load_corpus, save_corpus


def test_load_empty_corpus(tmp_path: Path):
    corpus_path = tmp_path / "corpus.yaml"
    corpus_path.write_text("workbooks: []\n", encoding="utf-8")
    assert load_corpus(corpus_path) == []


def test_save_and_load_roundtrip(tmp_path: Path):
    corpus_path = tmp_path / "corpus.yaml"
    entries = [
        CorpusEntry(
            name="simple_join",
            path="tests/golden/real/simple_join.twb",
            added_by="Test User",
            added_on="2026-05-31",
            notes="baseline",
        )
    ]
    save_corpus(entries, corpus_path)
    loaded = load_corpus(corpus_path)
    assert len(loaded) == 1
    assert loaded[0].name == "simple_join"
    assert loaded[0].path == "tests/golden/real/simple_join.twb"
    assert loaded[0].added_by == "Test User"
    assert loaded[0].added_on == "2026-05-31"
    assert loaded[0].notes == "baseline"


def test_load_missing_corpus_returns_empty(tmp_path: Path):
    corpus_path = tmp_path / "nonexistent.yaml"
    assert load_corpus(corpus_path) == []


def test_notes_defaults_to_empty_string(tmp_path: Path):
    corpus_path = tmp_path / "corpus.yaml"
    corpus_path.write_text(
        "workbooks:\n  - name: wb\n    path: p.twb\n    added_by: me\n    added_on: '2026-01-01'\n",
        encoding="utf-8",
    )
    entries = load_corpus(corpus_path)
    assert entries[0].notes == ""


def test_duplicate_name_detection(tmp_path: Path):
    corpus_path = tmp_path / "corpus.yaml"
    e = CorpusEntry(name="wb", path="wb.twb", added_by="me", added_on="2026-01-01", notes="")
    save_corpus([e], corpus_path)
    entries = load_corpus(corpus_path)
    names = {entry.name for entry in entries}
    assert "wb" in names
    # caller is responsible for the duplicate check; load_corpus just reads
    # test that two entries with same name can be detected:
    save_corpus([e, e], corpus_path)
    loaded = load_corpus(corpus_path)
    assert sum(1 for x in loaded if x.name == "wb") == 2
