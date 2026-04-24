"""Stage 6 — build TMDL (pure python). See spec §6 Stage 6. Plan-1 stub."""
from __future__ import annotations

from tableau2pbir.pipeline import StageContext, StageResult


def run(input_json: dict, ctx: StageContext) -> StageResult:
    return StageResult(
        output={"stub_stage": "build_tmdl", "input_keys": list(input_json.keys())},
        summary_md="# Stage 6 — build TMDL (stub)\n\nNo-op in Plan 1.\n",
        errors=(),
    )
