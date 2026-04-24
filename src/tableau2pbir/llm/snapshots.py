"""LLM snapshot replay — §9 layer vi + §7 step 4."""
from __future__ import annotations

import json
import os
from pathlib import Path


def is_replay_mode() -> bool:
    """True iff PYTEST_SNAPSHOT=replay is set. Drives zero-network test runs."""
    return os.environ.get("PYTEST_SNAPSHOT") == "replay"


class SnapshotStore:
    """Reads tests/llm_snapshots/<method>/<fixture>.json files."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def load(self, method: str, fixture: str) -> dict:
        path = self.root / method / f"{fixture}.json"
        if not path.exists():
            raise FileNotFoundError(f"no snapshot: {path}")
        return json.loads(path.read_text(encoding="utf-8"))
