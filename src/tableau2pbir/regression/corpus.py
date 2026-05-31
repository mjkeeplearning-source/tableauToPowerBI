"""Corpus manifest load/save."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class CorpusEntry:
    name: str
    path: str
    added_by: str
    added_on: str
    notes: str = ""


def load_corpus(corpus_path: Path) -> list[CorpusEntry]:
    if not corpus_path.exists():
        return []
    data = yaml.safe_load(corpus_path.read_text(encoding="utf-8")) or {}
    entries = []
    for item in data.get("workbooks", []):
        entries.append(CorpusEntry(
            name=item["name"],
            path=item["path"],
            added_by=item["added_by"],
            added_on=str(item["added_on"]),
            notes=item.get("notes", ""),
        ))
    return entries


def save_corpus(entries: list[CorpusEntry], corpus_path: Path) -> None:
    corpus_path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "workbooks": [
            {
                "name": e.name,
                "path": e.path,
                "added_by": e.added_by,
                "added_on": e.added_on,
                "notes": e.notes,
            }
            for e in entries
        ]
    }
    corpus_path.write_text(
        yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
