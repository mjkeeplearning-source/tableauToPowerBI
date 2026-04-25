"""Private builders for Stage 2. One function per IR sub-tree. These are
pure: no I/O, no module-level state, fully unit-testable."""
from __future__ import annotations

from typing import Any

from tableau2pbir.classify.connector_tier import classify_connector
from tableau2pbir.ir.common import UnsupportedItem
from tableau2pbir.ir.datasource import ConnectorTier, Datasource
from tableau2pbir.util.ids import stable_id


def _connection_params(raw_ds: dict[str, Any]) -> dict[str, str]:
    conn = raw_ds.get("connection") or {}
    params: dict[str, str] = {}
    for key in ("server", "dbname", "database", "warehouse", "filename",
                "directory", "host", "port", "schema", "http_path",
                "billing_project", "catalog"):
        if key in conn and conn[key]:
            params[key] = conn[key]
    return params


def _source_excerpt(raw_ds: dict[str, Any]) -> str:
    conn = raw_ds.get("connection") or {}
    return f"<datasource name={raw_ds.get('name')!r} connection.class={conn.get('class')!r}/>"


def build_datasources(
    raw_datasources: list[dict[str, Any]],
) -> tuple[tuple[Datasource, ...], tuple[UnsupportedItem, ...]]:
    """Map raw extract datasources to IR Datasources with §5.8 classification.
    Returns (datasources, unsupported_items). Tier 3/4 datasources get both
    an IR record AND an UnsupportedItem appended."""
    datasources: list[Datasource] = []
    unsupported: list[UnsupportedItem] = []

    for raw in raw_datasources:
        classification = classify_connector(raw)
        ds_id = stable_id("ds", raw["name"])
        extract_ignored = raw.get("extract") is not None and classification.tier in (1, 2)

        ds = Datasource(
            id=ds_id,
            name=raw["name"],
            tableau_kind=(raw.get("connection") or {}).get("class", "unknown"),
            connector_tier=ConnectorTier(classification.tier),
            pbi_m_connector=classification.pbi_m_connector,
            connection_params=_connection_params(raw),
            user_action_required=classification.user_action_required,
            table_ids=(),                # populated in task 16 (build_tables)
            extract_ignored=extract_ignored,
        )
        datasources.append(ds)

        if classification.tier == 4:
            unsupported.append(UnsupportedItem(
                object_kind="datasource",
                object_id=ds_id,
                source_excerpt=_source_excerpt(raw),
                reason=classification.reason or "Tier 4 datasource — no PBI mapping.",
                code="unsupported_datasource_tier_4",
            ))
        elif classification.tier == 3:
            unsupported.append(UnsupportedItem(
                object_kind="datasource",
                object_id=ds_id,
                source_excerpt=_source_excerpt(raw),
                reason=classification.reason or "Tier 3 datasource — deferred to v1.2.",
                code="deferred_feature_tier3",
            ))

    return tuple(datasources), tuple(unsupported)
