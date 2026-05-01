"""Canonical PBI Desktop trace event mapping. See spec §9 layer vii."""
from __future__ import annotations

import json
from pathlib import Path

from tableau2pbir.validate.results import TraceEvent

CANONICAL_EVENTS = frozenset({
    "ReportLoaded", "ModelLoaded", "RepairPrompt", "ModelError",
    "VisualError", "AuthenticationNeeded", "AuthUIDisplayed",
})

_PROBE_DIR = Path(__file__).resolve().parents[3] / "tests" / "desktop_open" / "version_probes"
_DEFAULT_MAP = {name: name for name in CANONICAL_EVENTS}


def load_version_map(*, version: str) -> dict[str, str]:
    """Load `<major>_<minor>.json` from the version_probes/ directory.

    Returns an identity-only canonical map when no probe matches the version.
    """
    safe = version.replace(".", "_")
    candidate = _PROBE_DIR / f"{safe}.json"
    if not candidate.is_file():
        parts = version.split(".")
        if len(parts) >= 2:
            candidate = _PROBE_DIR / f"{parts[0]}_{parts[1]}.json"
    if candidate.is_file():
        data = json.loads(candidate.read_text(encoding="utf-8"))
        m = dict(_DEFAULT_MAP)
        m.update(data.get("map", {}))
        return m
    return dict(_DEFAULT_MAP)


def parse_trace_file(path: Path, *, version_map: dict[str, str]) -> tuple[TraceEvent, ...]:
    """Parse a JSONL trace file. Lines whose `event` field maps to a canonical
    name are kept; unknown events are dropped. Order is preserved."""
    events: list[TraceEvent] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        try:
            obj = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        raw_name = obj.get("event")
        if not raw_name:
            continue
        canonical = version_map.get(raw_name)
        if canonical not in CANONICAL_EVENTS:
            continue
        ts = int(obj.get("ts", 0))
        events.append(TraceEvent(name=canonical, timestamp_ms=ts, raw=raw_line))
    return tuple(events)
