"""Deterministic id generation. Stage 1 uses Tableau internal names where
available; Stage 2 backfills with `stable_id(kind, name)` so ids remain
stable across re-runs of the same workbook."""
from __future__ import annotations

import hashlib
import re

_UNSAFE = re.compile(r"[^a-z0-9]+")
_UNDERSCORE_RUN = re.compile(r"_+")


def slug_id(raw: str) -> str:
    """Lowercase, non-alnum → underscore, collapse runs, strip ends.
    Falls back to `id_<hash8>` if nothing usable remains."""
    lowered = raw.lower().replace("%", "_pct_")
    sub = _UNSAFE.sub("_", lowered)
    sub = _UNDERSCORE_RUN.sub("_", sub).strip("_")
    if not sub:
        h = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:8]
        return f"id_{h}"
    return sub


def stable_id(kind: str, name: str) -> str:
    """Stable id for IR objects, prefixed with the kind for readability.
    `stable_id('calc', 'Profit Margin') -> 'calc__profit_margin'`."""
    return f"{kind}__{slug_id(name)}"
