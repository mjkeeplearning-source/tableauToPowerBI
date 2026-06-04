"""Atomic UTF-8 / LF file writes."""
from __future__ import annotations

import sys
from pathlib import Path


def _long_path(p: Path) -> Path:
    """On Windows, prefix absolute paths with '\\\\?\\' to bypass the 260-char MAX_PATH limit."""
    if sys.platform != "win32":
        return p
    resolved = p.resolve()
    s = str(resolved)
    if s.startswith("\\\\?\\"):
        return Path(s)
    return Path("\\\\?\\" + s)


def write_text(path: Path, content: str) -> None:
    path = _long_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8", newline="\n")
    tmp.replace(path)
