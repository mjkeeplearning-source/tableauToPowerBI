"""Format and print the regression result report."""
from __future__ import annotations

from tableau2pbir.regression.compare.result import RegressionResult, WorkbookResult


def format_report(result: RegressionResult) -> str:
    lines: list[str] = []
    for wb in result.workbook_results:
        lines.append(_format_workbook(wb))
    return "\n".join(lines)


def _format_workbook(wb: WorkbookResult) -> str:
    lines: list[str] = []
    if wb.status == "SKIP":
        lines.append(f"SKIP  {wb.name}  ({wb.skip_reason})")
        return "\n".join(lines)
    if wb.status == "PASS":
        lines.append(f"PASS  {wb.name}")
        return "\n".join(lines)
    lines.append(f"FAIL  {wb.name}")
    for fd in wb.file_diffs:
        if not fd.has_changes:
            continue
        lines.append(f"  {fd.relative_path}")
        if fd.missing:
            lines.append("    <file deleted from output>")
            continue
        for d in fd.diffs:
            if d.entity_type in ("measure", "column"):
                lines.append(f"    {d.entity_type} [{d.entity_name}]  {d.attribute} changed")
                lines.append(f"      - {d.old_value}")
                lines.append(f"      + {d.new_value}")
            elif d.entity_type == "json":
                lines.append(f"    {d.entity_name}  value changed")
                lines.append(f"      - {d.old_value}")
                lines.append(f"      + {d.new_value}")
            else:
                lines.append(f"    {d.entity_type} [{d.entity_name}]  {d.attribute}: {d.old_value} → {d.new_value}")
    return "\n".join(lines)
