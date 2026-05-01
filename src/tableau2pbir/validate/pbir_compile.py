"""PBIR compile validity via pbi-tools. See spec §6 Stage 8 step 3 + §9 layer iv-b."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from tableau2pbir.validate.results import ValidatorOutcome, ValidatorResult

_TIMEOUT_S = 120


def _resolve_pbi_tools() -> str | None:
    return os.environ.get("PBI_TOOLS_PATH") or shutil.which("pbi-tools") \
           or shutil.which("pbi-tools.exe")


def run_pbir_compile(out_dir: Path) -> ValidatorResult:
    log_rel = "validation/pbir_compile.log"
    log_path = out_dir / log_rel
    log_path.parent.mkdir(parents=True, exist_ok=True)

    pbi = _resolve_pbi_tools()
    if pbi is None:
        log_path.write_text(
            "pbi-tools not found on PATH and PBI_TOOLS_PATH is unset; skipped.\n",
            encoding="utf-8")
        return ValidatorResult(outcome=ValidatorOutcome.SKIPPED, reason="pbi_tools_unavailable",
                               log_path=log_rel)

    try:
        proc = subprocess.run(
            [pbi, "compile", str(out_dir)],
            capture_output=True, text=True, timeout=_TIMEOUT_S,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        log_path.write_text(f"pbi-tools compile failed: {e!r}\n", encoding="utf-8")
        return ValidatorResult(outcome=ValidatorOutcome.FAILED, reason="pbi_tools_invocation_error",
                               log_path=log_rel)

    log_path.write_text(
        (proc.stdout or "") + ("\n--- STDERR ---\n" + proc.stderr if proc.stderr else ""),
        encoding="utf-8",
    )
    outcome = ValidatorOutcome.PASSED if proc.returncode == 0 else ValidatorOutcome.FAILED
    return ValidatorResult(outcome=outcome, reason=None, log_path=log_rel)
