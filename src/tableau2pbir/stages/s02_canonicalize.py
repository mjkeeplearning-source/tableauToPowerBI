"""Stage 2 — canonicalize → IR (pure python). See spec §6 Stage 2.

This module is built in layers (one task per IR sub-tree). The top-level
orchestrator `run(input_json, ctx)` delegates to small pure builders
that take raw extract dicts and return pydantic IR fragments."""
from __future__ import annotations

from typing import Any

from tableau2pbir.ir.version import IR_SCHEMA_VERSION
from tableau2pbir.ir.workbook import DataModel, Workbook
from tableau2pbir.pipeline import StageContext, StageResult
from tableau2pbir.stages._build_data_model import build_datasources


def run(input_json: dict[str, Any], ctx: StageContext) -> StageResult:
    """Orchestrator. Each sub-builder is pure and side-effect-free."""
    datasources, ds_unsupported = build_datasources(input_json.get("datasources", []))

    wb = Workbook(
        ir_schema_version=IR_SCHEMA_VERSION,
        source_path=input_json["source_path"],
        source_hash=input_json["source_hash"],
        tableau_version=input_json["tableau_version"],
        config={},
        data_model=DataModel(datasources=datasources),
        sheets=(),
        dashboards=(),
        unsupported=ds_unsupported,
    )
    return StageResult(
        output=wb.model_dump(mode="json"),
        summary_md="# Stage 2 — canonicalize\n\n(datasources wired)\n",
        errors=(),
    )
