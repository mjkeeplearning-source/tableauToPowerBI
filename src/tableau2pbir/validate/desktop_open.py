"""Desktop-open gate launcher. See spec §6 Stage 8 step 5 + §9 layer vii."""
from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

from tableau2pbir.validate.results import (
    DesktopOpenResult, TraceEvent, ValidatorOutcome,
)
from tableau2pbir.validate.trace_events import load_version_map, parse_trace_file

_TIMEOUT_S = 300
_FLAKE_RETRY_AFTER_S = 60


def _resolve_pbi_desktop() -> str | None:
    return os.environ.get("PBI_DESKTOP_PATH") or shutil.which("PBIDesktop.exe") \
           or shutil.which("PBIDesktop")


def _wait_for_load(traces_dir: Path, *, timeout_s: int) -> tuple[str, str | None]:
    """Poll the traces directory until any trace JSON appears or timeout.
    Returns ('done', None) on success, ('timeout', reason) otherwise.
    One retry on suspected flake: if no events appear within 60 s, report it.
    """
    deadline = time.monotonic() + timeout_s
    saw_any_event_by_60s = False
    start = time.monotonic()
    while time.monotonic() < deadline:
        if traces_dir.is_dir() and any(traces_dir.glob("*.json")):
            saw_any_event_by_60s = True
            return ("done", None)
        if (time.monotonic() - start) > _FLAKE_RETRY_AFTER_S and not saw_any_event_by_60s:
            return ("timeout", "no_events_60s")
        time.sleep(2)
    return ("timeout", "overall")


def _evaluate(events: tuple[TraceEvent, ...], tiers: tuple[int, ...]
              ) -> tuple[ValidatorOutcome, tuple[TraceEvent, ...]]:
    names = {e.name for e in events}
    auth_events = tuple(e for e in events if e.name in {"AuthenticationNeeded", "AuthUIDisplayed"})
    error_names = {"VisualError", "ModelError", "RepairPrompt"}
    has_non_auth_error = bool(names & error_names)

    if 2 in tiers:
        ok = "ReportLoaded" in names and not has_non_auth_error
        return (ValidatorOutcome.PASSED if ok else ValidatorOutcome.FAILED, auth_events)
    # Tier 1 / Tier 3-as-Tier-1
    ok = "ReportLoaded" in names and "ModelLoaded" in names and not has_non_auth_error
    return (ValidatorOutcome.PASSED if ok else ValidatorOutcome.FAILED, ())


def run_desktop_open(pbip_path: Path, *, datasource_tiers: tuple[int, ...],
                     traces_dir: Path, desktop_version: str = "2.130",
                     log_path: Path | None = None) -> DesktopOpenResult:
    desktop = _resolve_pbi_desktop()
    if desktop is None:
        return DesktopOpenResult(outcome=ValidatorOutcome.SKIPPED, reason="desktop_unavailable")

    proc = subprocess.Popen([desktop, "/Open", str(pbip_path)])
    try:
        status, why = _wait_for_load(traces_dir, timeout_s=_TIMEOUT_S)
        if status == "timeout":
            return DesktopOpenResult(outcome=ValidatorOutcome.FAILED, reason=why or "timeout")

        version_map = load_version_map(version=desktop_version)
        events: list[TraceEvent] = []
        for trace_file in sorted(traces_dir.glob("*.json")):
            events.extend(parse_trace_file(trace_file, version_map=version_map))
        outcome, auth_events = _evaluate(tuple(events), datasource_tiers)
        return DesktopOpenResult(outcome=outcome, reason=None,
                                 events=tuple(events),
                                 expected_credential_prompts=auth_events,
                                 log_path=str(log_path) if log_path else None)
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=10)
        except Exception:
            pass
