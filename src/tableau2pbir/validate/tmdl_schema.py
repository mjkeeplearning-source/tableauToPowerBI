"""TMDL validity via TabularEditor 2 CLI. See spec §6 Stage 8 step 2 + §9 layer iv."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from tableau2pbir.validate.results import ValidatorOutcome, ValidatorResult

_TIMEOUT_S = 120


def _resolve_te2() -> str | None:
    return os.environ.get("TE2_CLI_PATH") or shutil.which("TabularEditor.exe") \
           or shutil.which("TabularEditor")


def run_tmdl_validity(out_dir: Path) -> ValidatorResult:
    log_rel = "validation/tmdl.log"
    log_path = out_dir / log_rel
    log_path.parent.mkdir(parents=True, exist_ok=True)

    te2 = _resolve_te2()
    if te2 is None:
        log_path.write_text(
            "TabularEditor.exe not found on PATH and TE2_CLI_PATH is unset; skipped.\n",
            encoding="utf-8")
        return ValidatorResult(outcome=ValidatorOutcome.SKIPPED, reason="te2_unavailable",
                               log_path=log_rel)

    sm_root = out_dir / "SemanticModel"
    if not sm_root.is_dir():
        log_path.write_text("SemanticModel/ not found; nothing to validate.\n", encoding="utf-8")
        return ValidatorResult(outcome=ValidatorOutcome.SKIPPED, reason="semanticmodel_missing",
                               log_path=log_rel)

    sm = sm_root / "definition"   # TMDL files are in definition/ per PBIR spec
    try:
        proc = subprocess.run(
            [te2, "-B", "/c", str(sm)],
            capture_output=True, text=True, timeout=_TIMEOUT_S,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        log_path.write_text(f"TE2 invocation failed: {e!r}\n", encoding="utf-8")
        return ValidatorResult(outcome=ValidatorOutcome.FAILED, reason="te2_invocation_error",
                               log_path=log_rel)

    log_path.write_text(
        (proc.stdout or "") + ("\n--- STDERR ---\n" + proc.stderr if proc.stderr else ""),
        encoding="utf-8",
    )
    outcome = ValidatorOutcome.PASSED if proc.returncode == 0 else ValidatorOutcome.FAILED
    return ValidatorResult(outcome=outcome, reason=None, log_path=log_rel)
