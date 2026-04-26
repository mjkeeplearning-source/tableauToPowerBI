"""Runs the Stage 1 + Stage 2 pipeline against each Plan-2 synthetic fixture
and asserts v1-scope IR shape. Stages 3–8 run as no-op stubs."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tableau2pbir.ir.version import IR_SCHEMA_VERSION


def _run_convert(fixture: Path, out: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "tableau2pbir.cli", "convert",
         str(fixture), "--out", str(out)],
        capture_output=True, text=True,
    )


def _load_ir(out: Path, wb_name: str) -> dict:
    path = out / wb_name / "stages" / "02_canonicalize.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.integration
def test_trivial_fixture_still_works(tmp_path: Path, synthetic_fixtures_dir: Path):
    out = tmp_path / "out"
    result = _run_convert(synthetic_fixtures_dir / "trivial.twb", out)
    assert result.returncode == 0, result.stderr
    ir = _load_ir(out, "trivial")
    assert ir["ir_schema_version"] == IR_SCHEMA_VERSION
    assert len(ir["data_model"]["datasources"]) == 1
    assert len(ir["sheets"]) == 1
    assert len(ir["dashboards"]) == 1


@pytest.mark.integration
def test_datasources_mixed_tiers(tmp_path: Path, synthetic_fixtures_dir: Path):
    out = tmp_path / "out"
    result = _run_convert(synthetic_fixtures_dir / "datasources_mixed.twb", out)
    assert result.returncode == 0, result.stderr
    ir = _load_ir(out, "datasources_mixed")
    tiers = sorted(ds["connector_tier"] for ds in ir["data_model"]["datasources"])
    # Tier 1 (csv + sqlserver) + Tier 2 (snowflake)
    assert tiers == [1, 1, 2]


@pytest.mark.integration
def test_hyper_orphan_forces_tier_4(tmp_path: Path, synthetic_fixtures_dir: Path):
    out = tmp_path / "out"
    result = _run_convert(synthetic_fixtures_dir / "datasource_hyper_orphan.twb", out)
    assert result.returncode == 0, result.stderr
    ir = _load_ir(out, "datasource_hyper_orphan")
    ds = ir["data_model"]["datasources"][0]
    assert ds["connector_tier"] == 4
    assert ds["pbi_m_connector"] is None
    codes = [u["code"] for u in ir["unsupported"]]
    assert "unsupported_datasource_tier_4" in codes


@pytest.mark.integration
@pytest.mark.parametrize("fixture,expected_kind", [
    ("calc_row.twb", "row"),
    ("calc_aggregate.twb", "aggregate"),
    ("calc_lod_fixed.twb", "lod_fixed"),
    ("calc_lod_include.twb", "lod_include"),
])
def test_calc_kind_classification(
    tmp_path: Path, synthetic_fixtures_dir: Path,
    fixture: str, expected_kind: str,
):
    out = tmp_path / "out"
    result = _run_convert(synthetic_fixtures_dir / fixture, out)
    assert result.returncode == 0, result.stderr
    wb_name = Path(fixture).stem
    ir = _load_ir(out, wb_name)
    calcs = ir["data_model"]["calculations"]
    assert len(calcs) >= 1
    kinds = {c["kind"] for c in calcs}
    assert expected_kind in kinds


@pytest.mark.integration
def test_lod_include_routed_to_deferred(tmp_path: Path, synthetic_fixtures_dir: Path):
    out = tmp_path / "out"
    _run_convert(synthetic_fixtures_dir / "calc_lod_include.twb", out)
    ir = _load_ir(out, "calc_lod_include")
    codes = [u["code"] for u in ir["unsupported"]]
    assert "deferred_feature_lod_relative" in codes


@pytest.mark.integration
def test_quick_table_calc_routed_to_deferred(tmp_path: Path, synthetic_fixtures_dir: Path):
    out = tmp_path / "out"
    _run_convert(synthetic_fixtures_dir / "calc_quick_table.twb", out)
    ir = _load_ir(out, "calc_quick_table")
    codes = [u["code"] for u in ir["unsupported"]]
    assert "deferred_feature_table_calcs" in codes


@pytest.mark.integration
def test_all_parameter_intents(tmp_path: Path, synthetic_fixtures_dir: Path):
    out = tmp_path / "out"
    _run_convert(synthetic_fixtures_dir / "params_all_intents.twb", out)
    ir = _load_ir(out, "params_all_intents")
    intents = {p["intent"] for p in ir["data_model"]["parameters"]}
    assert "numeric_what_if" in intents
    assert "categorical_selector" in intents
    assert "internal_constant" in intents


@pytest.mark.integration
def test_dashboard_leaves_include_floating(tmp_path: Path, synthetic_fixtures_dir: Path):
    out = tmp_path / "out"
    _run_convert(synthetic_fixtures_dir / "dashboard_tiled_floating.twb", out)
    ir = _load_ir(out, "dashboard_tiled_floating")
    d = ir["dashboards"][0]
    assert d["size"]["kind"] == "exact"
    # Root container's children — one tiled + one floating leaf; both carry positions.
    children = d["layout_tree"]["children"]
    assert len(children) == 2
    positions = [c["position"] for c in children]
    assert {"x": 100, "y": 200, "w": 500, "h": 200} in positions


@pytest.mark.integration
def test_actions_resolved_to_sheet_ids(tmp_path: Path, synthetic_fixtures_dir: Path):
    out = tmp_path / "out"
    _run_convert(synthetic_fixtures_dir / "action_filter.twb", out)
    ir = _load_ir(out, "action_filter")
    actions = ir["dashboards"][0]["actions"]
    assert len(actions) == 2
    kinds = {a["kind"] for a in actions}
    assert kinds == {"filter", "highlight"}
    filter_action = next(a for a in actions if a["kind"] == "filter")
    assert filter_action["source_sheet_ids"] == ["sheet__revenue"]
    assert filter_action["target_sheet_ids"] == ["sheet__detail"]
