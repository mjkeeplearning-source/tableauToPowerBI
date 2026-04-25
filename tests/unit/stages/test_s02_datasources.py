from __future__ import annotations

from tableau2pbir.ir.datasource import ConnectorTier
from tableau2pbir.stages._build_data_model import build_datasources


def test_tier_1_csv():
    raw = [{
        "name": "sample.csv", "caption": "Sample",
        "connection": {"class": "textscan", "filename": "sample.csv", "directory": "."},
        "named_connections": [], "extract": None,
        "columns": [], "calculations": [],
    }]
    datasources, unsupported = build_datasources(raw)
    assert len(datasources) == 1
    ds = datasources[0]
    assert ds.name == "sample.csv"
    assert ds.connector_tier == ConnectorTier.TIER_1
    assert ds.pbi_m_connector == "Csv.Document"
    assert ds.connection_params["filename"] == "sample.csv"
    assert unsupported == ()


def test_tier_2_snowflake_user_action():
    raw = [{
        "name": "sales", "caption": None,
        "connection": {"class": "snowflake", "server": "acct.snowflakecomputing.com",
                       "warehouse": "WH1"},
        "named_connections": [], "extract": None,
        "columns": [], "calculations": [],
    }]
    datasources, unsupported = build_datasources(raw)
    assert datasources[0].connector_tier == ConnectorTier.TIER_2
    assert "enter credentials" in datasources[0].user_action_required
    assert unsupported == ()


def test_tier_3_cross_db_emits_deferred_feature():
    raw = [{
        "name": "joined",
        "connection": {"class": "federated"},
        "named_connections": [
            {"name": "a", "caption": None, "connection": {"class": "sqlserver"}},
            {"name": "b", "caption": None, "connection": {"class": "snowflake"}},
        ],
        "extract": None, "columns": [], "calculations": [],
    }]
    datasources, unsupported = build_datasources(raw)
    assert datasources[0].connector_tier == ConnectorTier.TIER_3
    assert datasources[0].pbi_m_connector is None
    assert len(unsupported) == 1
    assert unsupported[0].code == "deferred_feature_tier3"
    assert unsupported[0].object_kind == "datasource"


def test_tier_4_published_emits_unsupported():
    raw = [{
        "name": "pub",
        "connection": {"class": "sqlproxy"},
        "named_connections": [], "extract": None,
        "columns": [], "calculations": [],
    }]
    datasources, unsupported = build_datasources(raw)
    assert datasources[0].connector_tier == ConnectorTier.TIER_4
    assert len(unsupported) == 1
    assert unsupported[0].code == "unsupported_datasource_tier_4"


def test_extract_ignored_flag_when_hyper_with_upstream():
    raw = [{
        "name": "extract_ds",
        "connection": {"class": "federated"},
        "named_connections": [
            {"name": "u", "caption": None, "connection": {"class": "sqlserver"}},
        ],
        "extract": {"connection": {"class": "hyper"}},
        "columns": [], "calculations": [],
    }]
    datasources, _ = build_datasources(raw)
    assert datasources[0].extract_ignored is True
