"""Real-workbook smoke tests for Stage 2 (s02_canonicalize.run).

Runs stage 1 → stage 2 for every workbook in tests/golden/real/ and confirms
the output round-trips through Workbook.model_validate — proving the skeleton
never produces a shape that violates the IR schema."""
from __future__ import annotations

import pathlib
import tempfile

import pytest

from tableau2pbir.ir.version import IR_SCHEMA_VERSION
from tableau2pbir.ir.workbook import Workbook
from tableau2pbir.pipeline import StageContext
from tableau2pbir.stages import s01_extract, s02_canonicalize

_REAL_DIR = pathlib.Path(__file__).parent / "real"

_ALL_WORKBOOKS = [
    "daatabricks.twb",
    "join_custom_rds.twb",
    "rds_compllex_cal.twb",
    "snowflkake.twb",
    "sql_custom_rds.twb",
    "simple_join.twb",
    "simple_join_calculated_line.twb",
    "Sales Insights - Data Analysis Project using Tableau.twbx",
    "Superstore.twbx",
]


def _run_pipeline(name: str) -> dict:
    path = _REAL_DIR / name
    if not path.exists():
        pytest.skip(f"{name} not present")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = pathlib.Path(tmp)
        ctx1 = StageContext(workbook_id=name, output_dir=tmp_path, config={}, stage_number=1)
        stage1_out = s01_extract.run({"source_path": str(path)}, ctx1).output
        ctx2 = StageContext(workbook_id=name, output_dir=tmp_path, config={}, stage_number=2)
        return s02_canonicalize.run(stage1_out, ctx2).output


@pytest.mark.parametrize("name", _ALL_WORKBOOKS)
def test_stage2_smoke(name):
    out = _run_pipeline(name)
    assert out["ir_schema_version"] == IR_SCHEMA_VERSION
    assert "source_path" in out
    assert len(out["source_hash"]) == 64
    # Must validate against the IR schema (pydantic is source of truth per §5.4).
    Workbook.model_validate(out)


# ── data_model count regression — locks in datasource/table/calc counts ───────

def test_daatabricks_counts():
    out = _run_pipeline("daatabricks.twb")
    dm = out["data_model"]
    assert len(dm["datasources"]) == 1
    assert len(dm["tables"]) == 1
    assert len(dm["calculations"]) == 0
    assert len(out["sheets"]) == 2


def test_join_custom_rds_counts():
    out = _run_pipeline("join_custom_rds.twb")
    dm = out["data_model"]
    assert len(dm["datasources"]) == 1
    assert len(dm["tables"]) == 1
    assert len(dm["calculations"]) == 1
    assert len(out["sheets"]) == 4


def test_rds_complex_cal_counts():
    out = _run_pipeline("rds_compllex_cal.twb")
    dm = out["data_model"]
    assert len(dm["datasources"]) == 1
    assert len(dm["tables"]) == 1
    assert len(dm["calculations"]) == 3
    assert len(out["sheets"]) == 5


def test_snowflake_counts():
    out = _run_pipeline("snowflkake.twb")
    dm = out["data_model"]
    assert len(dm["datasources"]) == 1
    assert len(dm["tables"]) == 1
    assert len(dm["calculations"]) == 0
    assert len(out["sheets"]) == 3


def test_sql_custom_rds_counts():
    out = _run_pipeline("sql_custom_rds.twb")
    dm = out["data_model"]
    assert len(dm["datasources"]) == 1
    assert len(dm["tables"]) == 1
    assert len(dm["calculations"]) == 0
    assert len(out["sheets"]) == 2


def test_simple_join_counts():
    out = _run_pipeline("simple_join.twb")
    dm = out["data_model"]
    assert len(dm["datasources"]) == 1
    assert len(dm["tables"]) == 1
    assert len(dm["calculations"]) == 2
    assert len(out["sheets"]) == 2


def test_simple_join_calculated_line_counts():
    out = _run_pipeline("simple_join_calculated_line.twb")
    dm = out["data_model"]
    assert len(dm["datasources"]) == 1
    assert len(dm["tables"]) == 1
    assert len(dm["calculations"]) == 0
    assert len(out["sheets"]) == 2


def test_sales_insights_counts():
    out = _run_pipeline("Sales Insights - Data Analysis Project using Tableau.twbx")
    dm = out["data_model"]
    assert len(dm["datasources"]) == 1
    assert len(dm["tables"]) == 1
    assert len(dm["calculations"]) == 3
    assert len(out["sheets"]) == 14


def test_superstore_counts():
    out = _run_pipeline("Superstore.twbx")
    dm = out["data_model"]
    assert len(dm["datasources"]) == 3
    assert len(dm["tables"]) == 3
    assert len(dm["calculations"]) == 21
    assert len(out["sheets"]) == 21
