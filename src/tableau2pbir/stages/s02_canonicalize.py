"""Stage 2 — canonicalize → IR (pure python). See spec §6 Stage 2. Plan-1 stub."""
from __future__ import annotations

from tableau2pbir.pipeline import StageContext, StageResult


def run(input_json: dict[str, object], ctx: StageContext) -> StageResult:
    return StageResult(
        output={"stub_stage": "canonicalize", "input_keys": list(input_json.keys())},
        summary_md="# Stage 2 — canonicalize (stub)\n\nNo-op in Plan 1.\n",
        errors=(),
    )
