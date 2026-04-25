"""§5.8 connector matrix classifier.

Takes a raw datasource dict (from extract/datasources.py) and returns a
`ConnectorClassification` with tier, PBI M connector name, and per-source
user actions. Stage 2 converts this into `Datasource.connector_tier` and
`Datasource.pbi_m_connector`."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


_TIER_1 = {
    "textscan":       ("Csv.Document", ()),
    "csv":            ("Csv.Document", ()),
    "excel-direct":   ("Excel.Workbook", ()),
    "sqlserver":      ("Sql.Database", ()),
}

_TIER_2 = {
    "snowflake":      ("Snowflake.Databases", ("enter credentials",)),
    "databricks":     ("DatabricksMultiCloud.Catalogs", ("enter credentials",)),
    "bigquery":       ("GoogleBigQuery.Database", ("OAuth in Desktop",)),
    "google-bigquery":("GoogleBigQuery.Database", ("OAuth in Desktop",)),
    "postgres":       ("PostgreSQL.Database", ("enter credentials",)),
    "oracle":         ("Oracle.Database", ("enter credentials", "install oracle client")),
    "redshift":       ("AmazonRedshift.Database", ("enter credentials",)),
    "teradata":       ("Teradata.Database", ("enter credentials", "install teradata client")),
    "mysql":          ("MySql.Database", ("enter credentials",)),
}

_TIER_4_EXPLICIT = {
    "sqlproxy",       # Tableau Server / Online published datasource
    "wdc",            # Web Data Connector
    "tableau-r",
    "tableau-python",
    "odata",
    "sas",
    "spss",
}


@dataclass(frozen=True)
class ConnectorClassification:
    tier: int                                   # 1 | 2 | 3 | 4
    pbi_m_connector: str | None                 # None iff tier == 4
    user_action_required: tuple[str, ...] = ()
    reason: str = ""                            # filled in only when tier in {3, 4}


def _classify_class(cls: str) -> ConnectorClassification | None:
    if cls in _TIER_1:
        connector, actions = _TIER_1[cls]
        return ConnectorClassification(tier=1, pbi_m_connector=connector,
                                       user_action_required=actions)
    if cls in _TIER_2:
        connector, actions = _TIER_2[cls]
        return ConnectorClassification(tier=2, pbi_m_connector=connector,
                                       user_action_required=actions)
    if cls in _TIER_4_EXPLICIT:
        return ConnectorClassification(tier=4, pbi_m_connector=None,
                                       reason=f"connector class {cls!r} not in PBI matrix")
    return None


def classify_connector(raw_ds: dict[str, Any]) -> ConnectorClassification:
    outer_class = (raw_ds.get("connection") or {}).get("class", "unknown")

    # Tier 3 — cross-DB or blended federated datasource with 2+ distinct upstream classes.
    named = raw_ds.get("named_connections") or []
    upstream_classes = {
        (nc.get("connection") or {}).get("class")
        for nc in named
        if nc.get("connection") is not None
    }
    upstream_classes.discard(None)

    if outer_class == "federated" and len(upstream_classes) >= 2:
        return ConnectorClassification(
            tier=3, pbi_m_connector=None,
            reason="cross-database join / blend — deferred to v1.2",
        )

    # Hyper with upstream — use the single upstream class.
    if outer_class in {"federated", "hyper"} and len(upstream_classes) == 1:
        upstream = next(iter(upstream_classes))
        result = _classify_class(upstream)
        if result is not None:
            return result

    # Hyper with no upstream — Tier 4 per §5.8.
    if outer_class == "hyper" and not upstream_classes:
        return ConnectorClassification(
            tier=4, pbi_m_connector=None,
            reason="hyper extract with null/missing upstream <connection>",
        )

    result = _classify_class(outer_class)
    if result is not None:
        return result

    return ConnectorClassification(
        tier=4, pbi_m_connector=None,
        reason=f"connector class {outer_class!r} not in PBI matrix",
    )
