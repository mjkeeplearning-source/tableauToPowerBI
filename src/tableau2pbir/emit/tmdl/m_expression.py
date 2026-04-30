"""Datasource → M partition body. §5.8 connector matrix."""
from __future__ import annotations

from tableau2pbir.ir.datasource import ConnectorTier, Datasource


def render_m_expression(ds: Datasource, table_name: str) -> str:
    if ds.connector_tier == ConnectorTier.TIER_4 or not ds.pbi_m_connector:
        msg = "; ".join(ds.user_action_required) or f"connector {ds.tableau_kind} not supported"
        msg_escaped = msg.replace('"', '\\"')
        return (
            "let\n"
            f"    Source = error \"{msg_escaped}\"\n"
            "in\n"
            "    Source"
        )

    src_call = _source_call(ds)
    return (
        "let\n"
        f"    Source = {src_call},\n"
        f"    Navigation = Source{{[Item={_string(table_name)}]}}[Data]\n"
        "in\n"
        "    Navigation"
    )


def _source_call(ds: Datasource) -> str:
    p = ds.connection_params
    fn = ds.pbi_m_connector
    if fn == "Csv.Document":
        return f"Csv.Document(File.Contents({_string(p.get('filename', ''))}))"
    if fn == "Excel.Workbook":
        return f"Excel.Workbook(File.Contents({_string(p.get('filename', ''))}), null, true)"
    if fn == "Sql.Database":
        return f"Sql.Database({_string(p.get('server', ''))}, {_string(p.get('dbname') or p.get('database', ''))})"
    if fn == "Snowflake.Databases":
        return f"Snowflake.Databases({_string(p.get('server', ''))}, {_string(p.get('warehouse', ''))})"
    if fn == "DatabricksMultiCloud.Catalogs":
        return f"DatabricksMultiCloud.Catalogs({_string(p.get('host', ''))}, {_string(p.get('http_path', ''))})"
    if fn == "GoogleBigQuery.Database":
        return f"GoogleBigQuery.Database({_string(p.get('billing_project', ''))})"
    if fn == "PostgreSQL.Database":
        return f"PostgreSQL.Database({_string(p.get('server', ''))}, {_string(p.get('dbname') or p.get('database', ''))})"
    if fn == "Oracle.Database":
        return f"Oracle.Database({_string(p.get('server', ''))})"
    if fn == "AmazonRedshift.Database":
        return f"AmazonRedshift.Database({_string(p.get('server', ''))}, {_string(p.get('dbname') or p.get('database', ''))})"
    if fn == "Teradata.Database":
        return f"Teradata.Database({_string(p.get('server', ''))})"
    if fn == "MySql.Database":
        return f"MySql.Database({_string(p.get('server', ''))}, {_string(p.get('dbname') or p.get('database', ''))})"
    return f"{fn}()"


def _string(s: str) -> str:
    return '"' + (s or "").replace('"', '""') + '"'
