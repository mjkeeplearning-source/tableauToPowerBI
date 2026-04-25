"""Stage 2 — canonicalize → IR (pure python). See spec §6 Stage 2.

This module is built in layers (one task per IR sub-tree). The top-level
orchestrator `run(input_json, ctx)` delegates to small pure builders
that take raw extract dicts and return pydantic IR fragments."""
from __future__ import annotations

from typing import Any

from tableau2pbir.ir.version import IR_SCHEMA_VERSION
from tableau2pbir.ir.workbook import DataModel, Workbook
from tableau2pbir.pipeline import StageContext, StageResult
from tableau2pbir.stages._build_data_model import (
    build_calculations, build_datasources, build_parameters, build_tables,
)


def _parameter_usage(input_json: dict[str, Any]) -> dict[str, str]:
    """Derive card vs shelf vs calc_only exposure for each parameter."""
    usage: dict[str, str] = {}
    for db in input_json.get("dashboards", []):
        for leaf in db.get("leaves", []):
            if leaf["leaf_kind"] == "parameter_card":
                name = leaf["payload"].get("parameter_name")
                if name:
                    usage[name] = "card"
    for ws in input_json.get("worksheets", []):
        for channel in ("rows", "columns"):
            for ref in ws["encodings"].get(channel, ()):
                usage.setdefault(ref, "shelf")
    return usage


def run(input_json: dict[str, Any], ctx: StageContext) -> StageResult:
    """Orchestrator. Each sub-builder is pure and side-effect-free."""
    datasources, ds_unsupported = build_datasources(input_json.get("datasources", []))
    tables, _columns = build_tables(input_json.get("datasources", []))
    calculations = build_calculations(input_json.get("datasources", []))
    usage = _parameter_usage(input_json)
    parameters = build_parameters(input_json.get("parameters", []), usage)
    # Columns live inside tables via column_ids; IR DataModel tracks tables only.
    data_model = DataModel(
        datasources=datasources, tables=tables,
        calculations=calculations, parameters=parameters,
    )

    wb = Workbook(
        ir_schema_version=IR_SCHEMA_VERSION,
        source_path=input_json["source_path"],
        source_hash=input_json["source_hash"],
        tableau_version=input_json["tableau_version"],
        config={},
        data_model=data_model,
        sheets=(),
        dashboards=(),
        unsupported=ds_unsupported,
    )
    return StageResult(
        output=wb.model_dump(mode="json"),
        summary_md="# Stage 2 — canonicalize\n\n(datasources wired)\n",
        errors=(),
    )
