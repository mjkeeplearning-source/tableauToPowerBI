from tableau2pbir.emit.tmdl.m_expression import render_m_expression
from tableau2pbir.ir.datasource import ConnectorTier, Datasource


def _ds(**kw):
    defaults = dict(
        id="d", name="DS", tableau_kind="csv", connector_tier=ConnectorTier.TIER_1,
        pbi_m_connector="Csv.Document", connection_params={"filename": "C:/data/sales.csv"},
        user_action_required=(), table_ids=(), extract_ignored=False,
    )
    defaults.update(kw)
    return Datasource(**defaults)


def test_csv_tier1():
    ds = _ds()
    m = render_m_expression(ds, table_name="Sales")
    assert "Csv.Document(File.Contents(\"C:/data/sales.csv\"))" in m
    assert "Source" in m


def test_sql_server_tier1():
    ds = _ds(
        tableau_kind="sqlserver", connector_tier=ConnectorTier.TIER_1,
        pbi_m_connector="Sql.Database",
        connection_params={"server": "srv01", "dbname": "Adventure"},
    )
    m = render_m_expression(ds, table_name="DimCustomer")
    assert "Sql.Database(\"srv01\", \"Adventure\")" in m


def test_snowflake_tier2_omits_credentials():
    ds = _ds(
        tableau_kind="snowflake", connector_tier=ConnectorTier.TIER_2,
        pbi_m_connector="Snowflake.Databases",
        connection_params={"server": "acct.snowflakecomputing.com", "warehouse": "WH"},
        user_action_required=("enter credentials",),
    )
    m = render_m_expression(ds, table_name="ORDERS")
    assert "Snowflake.Databases(\"acct.snowflakecomputing.com\", \"WH\")" in m
    assert "password" not in m.lower()


def test_tier4_emits_error_placeholder():
    ds = _ds(
        tableau_kind="webdata", connector_tier=ConnectorTier.TIER_4,
        pbi_m_connector=None, connection_params={},
        user_action_required=("Web Data Connector unsupported",),
    )
    m = render_m_expression(ds, table_name="X")
    assert "error" in m
    assert "Web Data Connector unsupported" in m
