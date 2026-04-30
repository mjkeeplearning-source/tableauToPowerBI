"""Stable PBIR id generator (deterministic for diffable output)."""
from __future__ import annotations

import hashlib


def stable_id(*parts: str) -> str:
    h = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()
    return h[:16]
