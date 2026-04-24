"""Datasource IR — §5.1 and §5.8 connector matrix."""
from __future__ import annotations

from enum import IntEnum

from tableau2pbir.ir.common import IRBase


class ConnectorTier(IntEnum):
    """Connector classification per §5.8.

    Tier 1: full fidelity (file/DB connectors emitting real M).
    Tier 2: credential placeholders (user enters creds on first Desktop open).
    Tier 3: degraded fidelity (cross-DB joins, blends, custom SQL).
    Tier 4: unsupported (forces workbook status → failed)."""
    TIER_1 = 1
    TIER_2 = 2
    TIER_3 = 3
    TIER_4 = 4


class Datasource(IRBase):
    """One `<datasource>` from the Tableau workbook, canonicalized.

    `pbi_m_connector` is None iff `connector_tier == TIER_4`. Credentials
    are never persisted here (§5.8 credentials policy)."""
    id: str
    name: str
    tableau_kind: str                       # e.g. "sqlserver", "csv", "hyper"
    connector_tier: ConnectorTier
    pbi_m_connector: str | None             # e.g. "Sql.Database"; None for Tier 4
    connection_params: dict[str, str]       # server, database, path, ...
    user_action_required: tuple[str, ...]   # ("enter credentials", "install oracle client")
    table_ids: tuple[str, ...]              # Tables that read from this datasource
    extract_ignored: bool                   # True when .hyper skipped in favor of <connection>
