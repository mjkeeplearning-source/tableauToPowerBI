"""Real-workbook smoke tests for Stage 1 (s01_extract.run).

Covers the 5 new .twb workbooks added in tests/golden/real/ that are not
yet covered by the extract-helper-level tests. All are Tableau 2026.1
workbooks with a single federated datasource (RDS/Databricks/Snowflake).
"""
from __future__ import annotations

import pathlib
import tempfile

import pytest

from tableau2pbir.pipeline import StageContext
from tableau2pbir.stages import s01_extract

_REAL_DIR = pathlib.Path(__file__).parent / "real"

_REQUIRED_OUTPUT_KEYS = {
    "source_path", "source_hash", "tableau_version",
    "datasources", "parameters", "worksheets", "dashboards",
    "actions", "unsupported",
}


def _run(name: str) -> dict:
    path = _REAL_DIR / name
    if not path.exists():
        pytest.skip(f"{name} not present")
    with tempfile.TemporaryDirectory() as tmp:
        ctx = StageContext(workbook_id=name, output_dir=pathlib.Path(tmp),
                          config={}, stage_number=1)
        return s01_extract.run({"source_path": str(path)}, ctx).output


# ── parametrized smoke: all 5 workbooks must produce well-shaped output ──────

@pytest.mark.parametrize("name", [
    "daatabricks.twb",
    "join_custom_rds.twb",
    "rds_compllex_cal.twb",
    "snowflkake.twb",
    "sql_custom_rds.twb",
])
def test_stage1_smoke(name):
    out = _run(name)
    assert _REQUIRED_OUTPUT_KEYS <= out.keys()
    assert len(out["source_hash"]) == 64
    assert out["tableau_version"].startswith("2026")
    # all are single-datasource federated workbooks
    assert len(out["datasources"]) == 1
    assert out["datasources"][0]["connection"]["class"] == "federated"
    # no tier-C objects in any of these workbooks
    assert out["unsupported"] == []


# ── workbook-specific counts ─────────────────────────────────────────────────

def test_daatabricks_sheets_and_dashboard():
    out = _run("daatabricks.twb")
    assert len(out["worksheets"]) == 2
    assert len(out["dashboards"]) == 1


def test_join_custom_rds_sheets_and_dashboards():
    out = _run("join_custom_rds.twb")
    assert len(out["worksheets"]) == 4
    assert len(out["dashboards"]) == 2


def test_rds_complex_cal_sheets():
    out = _run("rds_compllex_cal.twb")
    assert len(out["worksheets"]) == 5
    assert len(out["dashboards"]) == 0


def test_snowflake_sheets():
    out = _run("snowflkake.twb")
    assert len(out["worksheets"]) == 3
    assert len(out["dashboards"]) == 0


def test_sql_custom_rds_sheets():
    out = _run("sql_custom_rds.twb")
    assert len(out["worksheets"]) == 2
    assert len(out["dashboards"]) == 0
