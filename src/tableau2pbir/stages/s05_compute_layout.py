"""Stage 5 — compute layout (pure python). See spec §6 Stage 5. Plan-1 stub."""
from __future__ import annotations

from tableau2pbir.pipeline import StageContext, StageResult


def run(input_json: dict, ctx: StageContext) -> StageResult:
    return StageResult(
        output={"stub_stage": "compute_layout", "input_keys": list(input_json.keys())},
        summary_md="# Stage 5 — compute layout (stub)\n\nNo-op in Plan 1.\n",
        errors=(),
    )
