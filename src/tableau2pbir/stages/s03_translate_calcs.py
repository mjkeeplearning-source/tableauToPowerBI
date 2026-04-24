"""Stage 3 — translate calcs (python + AI fallback). See spec §6 Stage 3. Plan-1 stub."""
from __future__ import annotations

from tableau2pbir.pipeline import StageContext, StageResult


def run(input_json: dict, ctx: StageContext) -> StageResult:
    return StageResult(
        output={"stub_stage": "translate_calcs", "input_keys": list(input_json.keys())},
        summary_md="# Stage 3 — translate calcs (stub)\n\nNo-op in Plan 1.\n",
        errors=(),
    )
