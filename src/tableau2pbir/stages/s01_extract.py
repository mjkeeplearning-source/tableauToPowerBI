"""Stage 1 — extract (pure python). See spec §6 Stage 1. This is a
Plan-1 stub; real implementation in Plan 2."""
from __future__ import annotations

from tableau2pbir.pipeline import StageContext, StageResult


def run(input_json: dict, ctx: StageContext) -> StageResult:
    return StageResult(
        output={"stub_stage": "extract", "input_keys": list(input_json.keys())},
        summary_md="# Stage 1 — extract (stub)\n\nNo-op in Plan 1.\n",
        errors=(),
    )
