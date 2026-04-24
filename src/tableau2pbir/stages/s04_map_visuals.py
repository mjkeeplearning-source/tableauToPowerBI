"""Stage 4 — map visuals (python + AI fallback). See spec §6 Stage 4. Plan-1 stub."""
from __future__ import annotations

from tableau2pbir.pipeline import StageContext, StageResult


def run(input_json: dict, ctx: StageContext) -> StageResult:
    return StageResult(
        output={"stub_stage": "map_visuals", "input_keys": list(input_json.keys())},
        summary_md="# Stage 4 — map visuals (stub)\n\nNo-op in Plan 1.\n",
        errors=(),
    )
