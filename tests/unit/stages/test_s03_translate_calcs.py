"""Stage 3 orchestrator. Reads stage-2 IR JSON, populates dax_expr on every
v1 calc, leaves deferred calcs untouched (their ids are already in
unsupported[]), routes syntax-gate failures to unsupported[]."""
from __future__ import annotations

from pathlib import Path

from tableau2pbir.pipeline import StageContext
from tableau2pbir.stages.s03_translate_calcs import run


def _ctx(tmp_path: Path) -> StageContext:
    return StageContext(
        workbook_id="wb", output_dir=tmp_path, config={}, stage_number=3,
    )


def _ir_with_one_row_calc() -> dict:
    return {
        "ir_schema_version": "1.1.0",
        "source_path": "x.twb", "source_hash": "0" * 64,
        "tableau_version": "18.1", "config": {},
        "data_model": {
            "datasources": [], "tables": [], "relationships": [],
            "calculations": [{
                "id": "c_zn_sales", "name": "ZNSales", "scope": "measure",
                "tableau_expr": "ZN([Sales])", "dax_expr": None,
                "depends_on": [], "kind": "row", "phase": "row",
                "table_calc": None, "lod_fixed": None, "lod_relative": None,
                "owner_sheet_id": None,
            }],
            "parameters": [], "hierarchies": [], "sets": [],
        },
        "sheets": [], "dashboards": [], "unsupported": [],
    }


def test_stage3_populates_dax_via_rule(tmp_path: Path):
    result = run(_ir_with_one_row_calc(), _ctx(tmp_path))
    out = result.output
    [calc] = out["data_model"]["calculations"]
    assert calc["dax_expr"] == "COALESCE([Sales], 0)"
    # Stage 3 preserves every other field.
    assert calc["id"] == "c_zn_sales"


def test_stage3_skips_deferred_calcs(tmp_path: Path):
    ir = _ir_with_one_row_calc()
    # Mark the calc as already deferred (e.g. quick-table-calc).
    ir["data_model"]["calculations"][0]["kind"] = "table_calc"
    ir["unsupported"].append({
        "object_kind": "calc", "object_id": "c_zn_sales",
        "source_excerpt": "ZN([Sales])",
        "reason": "table calcs deferred", "code": "deferred_feature_table_calcs",
    })
    result = run(ir, _ctx(tmp_path))
    [calc] = result.output["data_model"]["calculations"]
    assert calc["dax_expr"] is None
