"""On-disk LLM response cache — §7. Content-hash keyed; JSON-on-disk."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, cast


def _long_path(p: Path) -> Path:
    """On Windows, prefix absolute paths with '\\\\?\\' to bypass the 260-char MAX_PATH limit."""
    if sys.platform != "win32":
        return p
    resolved = p.resolve()
    s = str(resolved)
    if s.startswith("\\\\?\\"):
        return Path(s)
    return Path("\\\\?\\" + s)


def make_cache_key(*, model: str, prompt_hash: str, schema_hash: str, payload: dict[str, Any]) -> str:
    """Return a stable 64-char sha256 hex over (model, prompt, schema, payload)."""
    h = hashlib.sha256()
    h.update(model.encode("utf-8"))
    h.update(b"\x00")
    h.update(prompt_hash.encode("utf-8"))
    h.update(b"\x00")
    h.update(schema_hash.encode("utf-8"))
    h.update(b"\x00")
    h.update(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    return h.hexdigest()


class OnDiskCache:
    """Simple read-through cache rooted at a directory. One file per key."""

    def __init__(self, root: Path) -> None:
        self.root = _long_path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.root / f"{key}.json"

    def get(self, key: str) -> dict[str, Any] | None:
        p = self._path(key)
        if not p.exists():
            return None
        return cast(dict[str, Any], json.loads(p.read_text(encoding="utf-8")))

    def put(self, key: str, value: dict[str, Any]) -> None:
        self._path(key).write_text(
            json.dumps(value, indent=2, sort_keys=True), encoding="utf-8",
        )
