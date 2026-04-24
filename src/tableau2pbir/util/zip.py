"""Workbook reader — loads XML bytes from .twb or .twbx, computes sha256
of the *raw file bytes on disk* so the hash is stable and cheap.

A `.twbx` is a zip archive containing exactly one `.twb` entry plus data
files (csv, hyper, images). The `.twb` entry path varies by Tableau
version; we pick the first entry ending in `.twb`."""
from __future__ import annotations

import hashlib
import zipfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WorkbookBytes:
    xml_bytes: bytes
    source_path: str     # absolute path string
    source_hash: str     # sha256 hex of the on-disk file (not of xml_bytes)


def _sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_workbook(path: Path) -> WorkbookBytes:
    """Open a .twb or .twbx and return its XML bytes + a content hash."""
    resolved = path.resolve()
    suffix = resolved.suffix.lower()
    source_hash = _sha256_of_file(resolved)

    if suffix == ".twb":
        xml_bytes = resolved.read_bytes()
    elif suffix == ".twbx":
        with zipfile.ZipFile(resolved) as z:
            twb_names = [n for n in z.namelist() if n.lower().endswith(".twb")]
            if not twb_names:
                raise ValueError(f"no .twb entry in {resolved}")
            xml_bytes = z.read(twb_names[0])
    else:
        raise ValueError(f"unsupported workbook extension: {suffix!r}")

    return WorkbookBytes(
        xml_bytes=xml_bytes,
        source_path=str(resolved),
        source_hash=source_hash,
    )
