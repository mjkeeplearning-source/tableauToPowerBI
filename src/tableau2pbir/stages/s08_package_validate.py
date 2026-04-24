"""Stage 8 — package + validate (pure python). See spec §6 Stage 8. Plan-1 stub.

In Plan 1 this also writes an empty placeholder .pbip so the end-to-end smoke
test has something to assert on."""
from __future__ import annotations

from tableau2pbir.pipeline import StageContext, StageResult


def run(input_json: dict[str, object], ctx: StageContext) -> StageResult:
    pbip_path = ctx.output_dir / f"{ctx.workbook_id}.pbip"
    pbip_path.write_text("", encoding="utf-8")       # 0-byte placeholder for now
    return StageResult(
        output={"stub_stage": "package_validate", "pbip_path": str(pbip_path)},
        summary_md=(
            "# Stage 8 — package + validate (stub)\n\n"
            f"Wrote empty placeholder: `{pbip_path.name}`\n"
        ),
        errors=(),
    )
