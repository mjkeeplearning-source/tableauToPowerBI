"""Real-workbook smoke tests for classify/connector_tier.

Locks in the expected tier and PBI M connector for every datasource
in the real workbook set as a regression baseline."""
from __future__ import annotations

import pathlib

import pytest

from tableau2pbir.classify.connector_tier import classify_connector
from tableau2pbir.extract.datasources import extract_datasources
from tableau2pbir.util.xml import parse_workbook_xml
from tableau2pbir.util.zip import read_workbook

_REAL_DIR = pathlib.Path(__file__).parent / "real"


def _classify_all(name: str) -> list[dict]:
    path = _REAL_DIR / name
    if not path.exists():
        pytest.skip(f"{name} not present")
    wb = read_workbook(path)
    root = parse_workbook_xml(wb.xml_bytes)
    return [
        {"tier": classify_connector(ds).tier,
         "m": classify_connector(ds).pbi_m_connector}
        for ds in extract_datasources(root)
    ]


# ── Tier-1 workbooks ────────────────────────────────────────────────────────

def test_join_custom_rds_is_tier1_sqlserver():
    results = _classify_all("join_custom_rds.twb")
    assert len(results) == 1
    assert results[0] == {"tier": 1, "m": "Sql.Database"}


def test_rds_complex_cal_is_tier1_sqlserver():
    results = _classify_all("rds_compllex_cal.twb")
    assert len(results) == 1
    assert results[0] == {"tier": 1, "m": "Sql.Database"}


def test_sql_custom_rds_is_tier1_sqlserver():
    results = _classify_all("sql_custom_rds.twb")
    assert len(results) == 1
    assert results[0] == {"tier": 1, "m": "Sql.Database"}


def test_sales_insights_is_tier1_excel():
    results = _classify_all("Sales Insights - Data Analysis Project using Tableau.twbx")
    assert len(results) == 1
    assert results[0] == {"tier": 1, "m": "Excel.Workbook"}


def test_superstore_all_tier1():
    results = _classify_all("Superstore.twbx")
    assert len(results) == 3
    tiers = {r["tier"] for r in results}
    assert tiers == {1}
    connectors = {r["m"] for r in results}
    assert connectors == {"Excel.Workbook", "Csv.Document"}


# ── Tier-2 workbooks ────────────────────────────────────────────────────────

def test_databricks_is_tier2():
    results = _classify_all("daatabricks.twb")
    assert len(results) == 1
    assert results[0] == {"tier": 2, "m": "DatabricksMultiCloud.Catalogs"}


def test_snowflake_is_tier2():
    results = _classify_all("snowflkake.twb")
    assert len(results) == 1
    assert results[0] == {"tier": 2, "m": "Snowflake.Databases"}


def test_simple_join_postgres_is_tier2():
    results = _classify_all("simple_join.twb")
    assert len(results) == 1
    assert results[0] == {"tier": 2, "m": "PostgreSQL.Database"}


def test_simple_join_calculated_line_postgres_is_tier2():
    results = _classify_all("simple_join_calculated_line.twb")
    assert len(results) == 1
    assert results[0] == {"tier": 2, "m": "PostgreSQL.Database"}
