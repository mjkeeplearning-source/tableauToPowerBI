import json
from pathlib import Path
from tableau2pbir.validate.trace_events import (
    CANONICAL_EVENTS, load_version_map, parse_trace_file,
)


def test_canonical_set_matches_spec():
    assert CANONICAL_EVENTS == frozenset({
        "ReportLoaded", "ModelLoaded", "RepairPrompt", "ModelError",
        "VisualError", "AuthenticationNeeded", "AuthUIDisplayed",
    })


def test_parses_jsonl_trace_with_canonical_names(tmp_path: Path):
    trace = tmp_path / "trace.json"
    trace.write_text("\n".join([
        json.dumps({"ts": 1000, "event": "Microsoft.PowerBI.Client.Core.ReportLoaded"}),
        json.dumps({"ts": 2000, "event": "ModelLoaded"}),
        json.dumps({"ts": 3000, "event": "Microsoft.AnalysisServices.AuthenticationNeeded"}),
        json.dumps({"ts": 4000, "event": "VisualError", "error": "boom"}),
        json.dumps({"ts": 5000, "event": "UnknownGarbage"}),
    ]), encoding="utf-8")
    events = parse_trace_file(trace, version_map=load_version_map(version="2.130"))
    names = [e.name for e in events]
    assert names == ["ReportLoaded", "ModelLoaded", "AuthenticationNeeded", "VisualError"]
    assert events[0].timestamp_ms == 1000


def test_load_version_map_unknown_version_returns_default(tmp_path):
    m = load_version_map(version="9.9.9")
    # Unknown still returns a usable map (canonical → canonical identity)
    assert "ReportLoaded" in m.values()
