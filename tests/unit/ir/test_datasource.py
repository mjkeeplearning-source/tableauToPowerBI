from __future__ import annotations

import pytest

from tableau2pbir.ir.datasource import ConnectorTier, Datasource


def test_connector_tier_values():
    assert ConnectorTier.TIER_1.value == 1
    assert ConnectorTier.TIER_4.value == 4


def test_datasource_minimal():
    ds = Datasource(
        id="ds1",
        name="Sales",
        tableau_kind="sqlserver",
        connector_tier=ConnectorTier.TIER_1,
        pbi_m_connector="Sql.Database",
        connection_params={"server": "sql.example", "database": "Sales"},
        user_action_required=[],
        table_ids=[],
        extract_ignored=False,
    )
    assert ds.connector_tier == ConnectorTier.TIER_1
    assert ds.pbi_m_connector == "Sql.Database"


def test_datasource_tier_4_has_no_m_connector():
    ds = Datasource(
        id="ds2",
        name="Orphan",
        tableau_kind="published-datasource",
        connector_tier=ConnectorTier.TIER_4,
        pbi_m_connector=None,
        connection_params={},
        user_action_required=[],
        table_ids=[],
        extract_ignored=False,
    )
    assert ds.pbi_m_connector is None


def test_datasource_rejects_extra_fields():
    with pytest.raises(Exception):
        Datasource(
            id="ds3", name="X", tableau_kind="csv",
            connector_tier=ConnectorTier.TIER_1, pbi_m_connector="Csv.Document",
            connection_params={}, user_action_required=[], table_ids=[], extract_ignored=False,
            mystery_field="nope",                                      # type: ignore[call-arg]
        )
