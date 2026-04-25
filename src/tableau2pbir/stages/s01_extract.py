"""Stage 1 — extract (pure python). See spec §6 Stage 1.

Loads the workbook XML (zip-aware for .twbx), walks the tree using the
`extract/` helpers, and returns a single JSON-serializable dict suitable
for persistence as `01_extract.json`."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from tableau2pbir.extract.actions import extract_actions
from tableau2pbir.extract.dashboards import extract_dashboards
from tableau2pbir.extract.datasources import extract_datasources
from tableau2pbir.extract.parameters import extract_parameters
from tableau2pbir.extract.tier_c_detect import detect_tier_c
from tableau2pbir.extract.worksheets import extract_worksheets
from tableau2pbir.pipeline import StageContext, StageResult
from tableau2pbir.util.xml import attr, parse_workbook_xml
from tableau2pbir.util.zip import read_workbook


def _tableau_version(root: Any) -> str:
    # Tableau writes source-build='2024.1' (major.minor) and version='18.1' (internal).
    # We prefer source-build when present since that tracks user-visible versions.
    build = attr(root, "source-build")
    if build:
        return build
    return attr(root, "version", default="unknown")


def _summary(counts: dict[str, int]) -> str:
    lines = ["# Stage 1 — extract", ""]
    for key in ("datasources", "parameters", "worksheets", "dashboards",
                "actions", "tier_c_objects"):
        lines.append(f"- {key}: {counts.get(key, 0)}")
    return "\n".join(lines) + "\n"


def run(input_json: dict[str, Any], ctx: StageContext) -> StageResult:
    source_path = Path(input_json["source_path"])
    wb = read_workbook(source_path)
    root = parse_workbook_xml(wb.xml_bytes)

    datasources = extract_datasources(root)
    parameters = extract_parameters(root)
    worksheets = extract_worksheets(root)
    dashboards = extract_dashboards(root)
    actions = extract_actions(root)
    unsupported = detect_tier_c(root)

    output: dict[str, Any] = {
        "source_path": wb.source_path,
        "source_hash": wb.source_hash,
        "tableau_version": _tableau_version(root),
        "datasources": datasources,
        "parameters": parameters,
        "worksheets": worksheets,
        "dashboards": dashboards,
        "actions": actions,
        "unsupported": unsupported,
    }
    counts = {
        "datasources": len(datasources),
        "parameters": len(parameters),
        "worksheets": len(worksheets),
        "dashboards": len(dashboards),
        "actions": len(actions),
        "tier_c_objects": len(unsupported),
    }
    return StageResult(output=output, summary_md=_summary(counts), errors=())
