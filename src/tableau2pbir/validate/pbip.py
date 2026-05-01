"""Write the .pbip root pointer file. See spec §4.4 + §6 Stage 8 step 1."""
from __future__ import annotations

import json
from pathlib import Path

_PBIP_PAYLOAD = {
    "version": "1.0",
    "artifacts": [{"report": {"path": "Report"}}],
    "settings": {"enableAutoRecovery": True},
}


def write_pbip_root(out_dir: Path, workbook_id: str) -> Path:
    """Write `<workbook_id>.pbip` at the root of `out_dir`. Returns the file path.

    Raises FileNotFoundError if Report/ is absent (the .pbip would be unusable).
    Overwrites any existing file (including the Plan-1 0-byte stub).
    """
    if not (out_dir / "Report").is_dir():
        raise FileNotFoundError(f"missing Report/ under {out_dir!s}; cannot write .pbip")
    target = out_dir / f"{workbook_id}.pbip"
    target.write_text(json.dumps(_PBIP_PAYLOAD, indent=2), encoding="utf-8")
    return target
