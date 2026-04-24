"""Stage 7 — build report PBIR (pure python). See spec §6 Stage 7. Plan-1 stub."""
from __future__ import annotations

from tableau2pbir.pipeline import StageContext, StageResult


def run(input_json: dict[str, object], ctx: StageContext) -> StageResult:
    return StageResult(
        output={"stub_stage": "build_pbir", "input_keys": list(input_json.keys())},
        summary_md="# Stage 7 — build PBIR (stub)\n\nNo-op in Plan 1.\n",
        errors=(),
    )
