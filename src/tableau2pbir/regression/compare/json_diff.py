"""PBIR JSON semantic normalise + deep diff."""
from __future__ import annotations
import json
from typing import Any


def _norm_str(s: str) -> str:
    return s.strip()


def _normalise(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _normalise(v) for k, v in sorted(obj.items())}
    if isinstance(obj, list):
        normalised = [_normalise(i) for i in obj]
        if normalised and isinstance(normalised[0], dict):
            def _sort_key(item: Any) -> tuple[str, str]:
                if isinstance(item, dict):
                    return (str(item.get("name", "")), str(item.get("id", "")))
                return ("", "")
            try:
                normalised = sorted(normalised, key=_sort_key)
            except TypeError:
                pass
        return normalised
    if isinstance(obj, str):
        return _norm_str(obj)
    return obj


def _collect(path: str, old: Any, new: Any, out: list[tuple[str, str, str]]) -> None:
    if old == new:
        return
    if isinstance(old, dict) and isinstance(new, dict):
        for k in sorted(set(old) | set(new)):
            _collect(f"{path}.{k}", old.get(k), new.get(k), out)
    elif isinstance(old, list) and isinstance(new, list):
        for i in range(max(len(old), len(new))):
            o = old[i] if i < len(old) else None
            n = new[i] if i < len(new) else None
            _collect(f"{path}[{i}]", o, n, out)
    else:
        out.append((path, str(old), str(new)))


def diff_json(snapshot_text: str, new_text: str) -> list[tuple[str, str, str]]:
    """Return list of (json_path, old_value, new_value) for semantic differences."""
    old = _normalise(json.loads(snapshot_text))
    new = _normalise(json.loads(new_text))
    diffs: list[tuple[str, str, str]] = []
    _collect("$", old, new, diffs)
    return diffs
