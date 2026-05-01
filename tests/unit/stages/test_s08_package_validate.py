from pathlib import Path
import json
from unittest.mock import patch
from tableau2pbir.stages import s08_package_validate
from tableau2pbir.pipeline import StageContext
from tableau2pbir.validate.results import ValidatorOutcome


def _scaffold_prior_outputs(out: Path, *, workbook_id: str = "wb"):
    (out / "Report" / "definition" / "pages" / "p1" / "visuals" / "v1").mkdir(parents=True)
    (out / "Report" / "definition" / "report.json").write_text(
        json.dumps({"name": workbook_id, "pageOrder": ["p1"]}), encoding="utf-8")
    (out / "Report" / "definition" / "pages" / "p1" / "page.json").write_text(
        json.dumps({"name": "p1"}), encoding="utf-8")
    (out / "Report" / "definition" / "pages" / "p1" / "visuals" / "v1" / "visual.json").write_text(
        json.dumps({"name": "v1", "fieldRefs": []}), encoding="utf-8")
    (out / "SemanticModel" / "definition" / "tables").mkdir(parents=True)

    stages = out / "stages"
    stages.mkdir()
    (stages / "02_canonicalize.json").write_text(json.dumps({
        "ir_schema_version": "1.1.0",
        "source_path": "x.twb",
        "source_hash": "0",
        "tableau_version": None,
        "config": {},
        "data_model": {
            "datasources": [{"id": "d1", "name": "Sales", "connector_tier": 1,
                             "tableau_kind": "csv", "pbi_m_connector": "Csv.Document",
                             "connection_params": {}, "user_action_required": [],
                             "tables": [], "extract_ignored": False}],
            "tables": [], "relationships": [], "calculations": [],
            "parameters": [], "hierarchies": [], "sets": [],
        },
        "sheets": [], "dashboards": [{"id": "d1", "name": "p1",
                                       "size": {"w": 1280, "h": 720, "kind": "auto"},
                                       "layout_tree": {"kind": "h", "children": [],
                                                        "padding": {"top":0,"right":0,"bottom":0,"left":0}},
                                       "actions": []}],
        "unsupported": [],
    }), encoding="utf-8")
    (stages / "07_build_pbir.json").write_text(json.dumps({
        "counts": {"pages": 1, "visuals": 1, "slicers": 0},
        "blocked_visuals": [],
        "visual_interactions": [],
    }), encoding="utf-8")
    (out / "unsupported.json").write_text("[]", encoding="utf-8")


def test_orchestrator_writes_pbip_and_returns_status_ok(tmp_path):
    out = tmp_path / "out"
    _scaffold_prior_outputs(out)
    ctx = StageContext(workbook_id="wb", output_dir=out, config={}, stage_number=8)
    # external validators unavailable → all skipped → ok
    with patch("tableau2pbir.validate.tmdl_schema._resolve_te2", return_value=None), \
         patch("tableau2pbir.validate.pbir_compile._resolve_pbi_tools", return_value=None), \
         patch("tableau2pbir.validate.desktop_open._resolve_pbi_desktop", return_value=None):
        result = s08_package_validate.run({}, ctx)
    assert result.output["status"] == "ok"
    assert (out / "wb.pbip").is_file()
    assert (out / "validation" / "structural.json").is_file()
    assert "wb.pbip" in result.output["pbip_path"]
    assert "Stage 8" in result.summary_md


def test_orchestrator_records_failed_when_structural_check_fails(tmp_path):
    out = tmp_path / "out"
    _scaffold_prior_outputs(out)
    # break a reference: visual references unknown field
    bad = out / "Report" / "definition" / "pages" / "p1" / "visuals" / "v1" / "visual.json"
    bad.write_text(json.dumps({"name": "v1", "fieldRefs": ["Ghost.Col"]}), encoding="utf-8")
    ctx = StageContext(workbook_id="wb", output_dir=out, config={}, stage_number=8)
    with patch("tableau2pbir.validate.tmdl_schema._resolve_te2", return_value=None), \
         patch("tableau2pbir.validate.pbir_compile._resolve_pbi_tools", return_value=None), \
         patch("tableau2pbir.validate.desktop_open._resolve_pbi_desktop", return_value=None):
        result = s08_package_validate.run({}, ctx)
    # Structural failure is recorded but does not by itself flip §8.1 status to failed
    assert result.output["validators"]["structural"]["result"] == "failed"


def test_orchestrator_skips_rubric_for_synthetic_workbook(tmp_path):
    out = tmp_path / "out"
    _scaffold_prior_outputs(out)
    ctx = StageContext(workbook_id="synthetic_wb", output_dir=out,
                       config={"is_real_workbook": False}, stage_number=8)
    with patch("tableau2pbir.validate.tmdl_schema._resolve_te2", return_value=None), \
         patch("tableau2pbir.validate.pbir_compile._resolve_pbi_tools", return_value=None), \
         patch("tableau2pbir.validate.desktop_open._resolve_pbi_desktop", return_value=None):
        result = s08_package_validate.run({}, ctx)
    assert result.output["validators"]["rubric"]["result"] == "skipped"
    assert result.output["validators"]["rubric"]["reason"] == "synthetic"
    assert result.output["validators"]["desktop_open"]["result"] == "skipped"
