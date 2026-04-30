"""TMDL identifier and string-literal escaping."""
from __future__ import annotations

import re

_SAFE_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def tmdl_ident(name: str) -> str:
    if name and _SAFE_IDENT.match(name):
        return name
    return "'" + name.replace("'", "''") + "'"


def tmdl_string(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'
