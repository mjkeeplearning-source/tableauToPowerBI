"""Structural cross-reference checker. See spec §6 Stage 8 step 4."""
from __future__ import annotations

import json
import re
from pathlib import Path

from tableau2pbir.validate.results import (
    StructuralFinding, StructuralResult, ValidatorOutcome,
)

_MEASURE_RE = re.compile(r"^\s*(?:measure|column|calculatedColumn)\s+([A-Za-z_][\w ]*)", re.M)
_TABLE_RE   = re.compile(r"^table\s+([A-Za-z_][\w ]*)", re.M)
_FROM_RE    = re.compile(r"fromTable\s*:\s*([A-Za-z_][\w ]*)")
_TO_RE      = re.compile(r"toTable\s*:\s*([A-Za-z_][\w ]*)")


def run_structural(out_dir: Path) -> StructuralResult:
    findings: list[StructuralFinding] = []

    # Collect known table → fields from TMDL (files live in SemanticModel/definition/).
    sm = out_dir / "SemanticModel" / "definition"
    table_fields: dict[str, set[str]] = {}
    for tmdl_path in (sm / "tables").glob("*.tmdl"):
        text = tmdl_path.read_text(encoding="utf-8")
        m = _TABLE_RE.search(text)
        if not m:
            continue
        tname = m.group(1).strip()
        fields = {fm.group(1).strip() for fm in _MEASURE_RE.finditer(text)}
        table_fields[tname] = fields

    # Walk PBIR visuals and check field refs resolve.
    rd = out_dir / "Report" / "definition"
    pages_dir = rd / "pages"
    if pages_dir.is_dir():
        for page_dir in sorted(p for p in pages_dir.iterdir() if p.is_dir()):
            visuals_dir = page_dir / "visuals"
            seen_vids: set[str] = set()
            if visuals_dir.is_dir():
                for vdir in sorted(p for p in visuals_dir.iterdir() if p.is_dir()):
                    if vdir.name in seen_vids:
                        findings.append(StructuralFinding(
                            code="visual.duplicate_id", severity="error",
                            message=f"duplicate visual id {vdir.name!r} in page {page_dir.name!r}",
                            location=str(vdir.relative_to(out_dir)),
                        ))
                    seen_vids.add(vdir.name)
                    vjson = vdir / "visual.json"
                    if not vjson.is_file():
                        continue
                    payload = json.loads(vjson.read_text(encoding="utf-8"))
                    for ref in payload.get("fieldRefs", []):
                        if "." not in ref:
                            continue
                        tname, fname = ref.split(".", 1)
                        if tname not in table_fields or fname not in table_fields[tname]:
                            findings.append(StructuralFinding(
                                code="visual.missing_field", severity="error",
                                message=f"visual {vdir.name!r} references unknown field {ref!r}",
                                location=str(vjson.relative_to(out_dir)),
                            ))

    # Page-order check — reads pages/pages.json (schema 3.2.0 format).
    pages_manifest = rd / "pages" / "pages.json"
    if pages_manifest.is_file():
        order = json.loads(pages_manifest.read_text(encoding="utf-8")).get("pageOrder", [])
        disk_pages = {p.name for p in pages_dir.iterdir() if p.is_dir()} if pages_dir.is_dir() else set()
        if set(order) != disk_pages:
            findings.append(StructuralFinding(
                code="report.page_order_mismatch", severity="error",
                message=f"pageOrder {order!r} != on-disk pages {sorted(disk_pages)!r}",
                location="Report/definition/pages/pages.json",
            ))

    # Relationship endpoint check.
    rel_dir = sm / "relationships"
    if rel_dir.is_dir():
        for rel_path in sorted(rel_dir.glob("*.tmdl")):
            text = rel_path.read_text(encoding="utf-8")
            for m, side in ((_FROM_RE.search(text), "from"), (_TO_RE.search(text), "to")):
                if m and m.group(1).strip() not in table_fields:
                    findings.append(StructuralFinding(
                        code="relationship.missing_table", severity="error",
                        message=f"{side}Table {m.group(1).strip()!r} not in SemanticModel/definition/tables/",
                        location=str(rel_path.relative_to(out_dir)),
                    ))

    outcome = ValidatorOutcome.FAILED if findings else ValidatorOutcome.PASSED
    return StructuralResult(outcome=outcome, findings=tuple(findings))
