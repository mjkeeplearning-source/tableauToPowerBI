from __future__ import annotations

import pytest

from tableau2pbir.classify.connector_tier import (
    ConnectorClassification,
    classify_connector,
)


def _raw(cls: str, **conn_extra: str) -> dict:
    return {
        "name": "ds",
        "connection": {"class": cls, **conn_extra},
        "named_connections": [],
        "extract": None,
    }


def test_tier_1_csv():
    r = classify_connector(_raw("textscan", filename="sample.csv"))
    assert isinstance(r, ConnectorClassification)
    assert r.tier == 1
    assert r.pbi_m_connector == "Csv.Document"
    assert r.user_action_required == ()


def test_tier_1_sqlserver():
    r = classify_connector(_raw("sqlserver", server="sql1", dbname="S"))
    assert r.tier == 1
    assert r.pbi_m_connector == "Sql.Database"


def test_tier_2_snowflake_needs_credentials():
    r = classify_connector(_raw("snowflake", server="acct.snowflakecomputing.com"))
    assert r.tier == 2
    assert r.pbi_m_connector == "Snowflake.Databases"
    assert "enter credentials" in r.user_action_required


def test_tier_2_oracle_needs_client_install():
    r = classify_connector(_raw("oracle", server="ora1"))
    assert r.tier == 2
    assert "install oracle client" in r.user_action_required


def test_tier_4_published_datasource():
    r = classify_connector(_raw("sqlproxy"))
    assert r.tier == 4
    assert r.pbi_m_connector is None


def test_hyper_with_upstream_reuses_upstream_class():
    raw = {
        "name": "e",
        "connection": {"class": "federated"},
        "named_connections": [
            {"name": "u", "caption": "x",
             "connection": {"class": "sqlserver", "server": "sql1"}},
        ],
        "extract": {"connection": {"class": "hyper"}},
    }
    r = classify_connector(raw)
    assert r.tier == 1
    assert r.pbi_m_connector == "Sql.Database"


def test_hyper_orphan_is_tier_4():
    raw = {
        "name": "e",
        "connection": {"class": "hyper"},
        "named_connections": [],
        "extract": None,
    }
    r = classify_connector(raw)
    assert r.tier == 4
    assert r.pbi_m_connector is None


def test_cross_db_joined_marked_tier_3():
    raw = {
        "name": "j",
        "connection": {"class": "federated"},
        "named_connections": [
            {"name": "a", "caption": None,
             "connection": {"class": "sqlserver", "server": "s"}},
            {"name": "b", "caption": None,
             "connection": {"class": "snowflake", "server": "acct"}},
        ],
        "extract": None,
    }
    r = classify_connector(raw)
    assert r.tier == 3
    assert r.pbi_m_connector is None


def test_unknown_class_falls_to_tier_4():
    r = classify_connector(_raw("mysteryproto"))
    assert r.tier == 4
