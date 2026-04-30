"""Stage 6 — build TMDL (pure python). §6 Stage 6."""
from __future__ import annotations

from typing import Any

from tableau2pbir.emit.tmdl.render import render_semantic_model
from tableau2pbir.emit.tmdl.summary import render_summary
from tableau2pbir.ir.workbook import Workbook
from tableau2pbir.pipeline import StageContext, StageResult


def run(input_json: dict[str, Any], ctx: StageContext) -> StageResult:
    wb = Workbook.model_validate(input_json)
    manifest = render_semantic_model(wb, ctx.output_dir)
    return StageResult(
        output=manifest,
        summary_md=render_summary(manifest),
        errors=(),
    )
