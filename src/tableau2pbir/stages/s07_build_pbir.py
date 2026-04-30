"""Stage 7 — build report PBIR (pure python). §6 Stage 7."""
from __future__ import annotations

from typing import Any

from tableau2pbir.emit.pbir.render import render_report
from tableau2pbir.emit.pbir.summary import render_summary
from tableau2pbir.ir.workbook import Workbook
from tableau2pbir.pipeline import StageContext, StageResult


def run(input_json: dict[str, Any], ctx: StageContext) -> StageResult:
    wb = Workbook.model_validate(input_json)
    manifest = render_report(wb, ctx.output_dir)
    return StageResult(
        output=manifest,
        summary_md=render_summary(manifest),
        errors=(),
    )
