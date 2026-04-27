"""Contract: after stage 3, every non-deferred Calculation has
either a non-null dax_expr OR an UnsupportedItem with a stage-3 code."""
from __future__ import annotations

from pathlib import Path

from tableau2pbir.pipeline import StageContext
from tableau2pbir.stages.s03_translate_calcs import run

_STAGE3_CODES = frozenset({
    "calc_dax_syntax_failed", "calc_no_rule_or_ai",
})
_DEFERRED_PREFIX = "deferred_feature_"


def test_every_v1_calc_has_dax_or_is_unsupported(tmp_path: Path):
    ir = {
        "ir_schema_version": "1.1.0",
        "source_path": "x.twb", "source_hash": "0" * 64,
        "tableau_version": "18.1", "config": {},
        "data_model": {
            "datasources": [], "tables": [], "relationships": [],
            "calculations": [
                {
                    "id": "c1", "name": "C1", "scope": "measure",
                    "tableau_expr": "AVG([Sales])", "dax_expr": None,
                    "depends_on": [], "kind": "aggregate", "phase": "aggregate",
                    "table_calc": None, "lod_fixed": None, "lod_relative": None,
                    "owner_sheet_id": None,
                },
            ],
            "parameters": [], "hierarchies": [], "sets": [],
        },
        "sheets": [], "dashboards": [], "unsupported": [],
    }
    out = run(ir, StageContext(workbook_id="w", output_dir=tmp_path,
                                config={}, stage_number=3)).output
    deferred_ids = {
        u["object_id"] for u in out["unsupported"]
        if u["code"].startswith(_DEFERRED_PREFIX)
        or u["code"] in _STAGE3_CODES
    }
    for c in out["data_model"]["calculations"]:
        if c["id"] in deferred_ids:
            continue
        assert c["dax_expr"] is not None, \
            f"calc {c['id']} has no dax_expr and is not unsupported"
