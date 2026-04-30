"""Render database.tmdl. See PBIR TMDL spec."""
from __future__ import annotations

from tableau2pbir.emit.tmdl.escape import tmdl_ident


def render_database(name: str, compatibility_level: int = 1567) -> str:
    # TMDL database declarations always use single-quoted names.
    quoted = "'" + name.replace("'", "''") + "'"
    return (
        f"database {quoted}\n"
        f"\tcompatibilityLevel: {compatibility_level}\n"
    )
