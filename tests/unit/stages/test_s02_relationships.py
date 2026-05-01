"""Tests for build_relationships — Stage 2 relationship IR construction."""
from __future__ import annotations

from tableau2pbir.ir.model import RelationshipSource
from tableau2pbir.stages._build_data_model import build_relationships, build_tables


_RAW_FEDERATED_DS = {
    "name": "federated.abc",
    "connection": {"class": "federated"},
    "named_connections": [
        {"name": "pg.xyz", "caption": "srv",
         "connection": {"class": "postgres", "server": "srv", "dbname": "db"}}
    ],
    "relations": [
        {"name": "orders", "table": "[public].[orders]", "connection": "pg.xyz"},
        {"name": "returns", "table": "[public].[returns]", "connection": "pg.xyz"},
    ],
    "col_map": {
        "order_id":           ("orders",  "order_id"),
        "order_id (returns)": ("returns", "order_id"),
        "sales":              ("orders",  "sales"),
    },
    "columns": [
        {"name": "order_id",           "datatype": "string", "role": "dimension", "type": None},
        {"name": "order_id (returns)", "datatype": "string", "role": "dimension", "type": None},
        {"name": "sales",              "datatype": "real",   "role": "measure",   "type": None},
    ],
    "calculations": [],
    "extract": None,
}

_RAW_RELS = [
    {"left_col": "order_id", "right_col": "order_id (returns)"},
]


def test_build_relationships_creates_one_relationship_for_join():
    tables, _ = build_tables([_RAW_FEDERATED_DS])
    rels = build_relationships(_RAW_RELS, [_RAW_FEDERATED_DS], tables)
    assert len(rels) == 1
    r = rels[0]
    assert r.source == RelationshipSource.TABLEAU_JOIN


def test_build_relationships_from_ref_resolves_to_orders_table():
    tables, _ = build_tables([_RAW_FEDERATED_DS])
    rels = build_relationships(_RAW_RELS, [_RAW_FEDERATED_DS], tables)
    r = rels[0]
    orders_table = next(t for t in tables if t.name == "orders")
    assert r.from_ref.table_id == orders_table.id
    assert r.from_ref.column_id == "order_id"


def test_build_relationships_to_ref_resolves_to_returns_table():
    tables, _ = build_tables([_RAW_FEDERATED_DS])
    rels = build_relationships(_RAW_RELS, [_RAW_FEDERATED_DS], tables)
    r = rels[0]
    returns_table = next(t for t in tables if t.name == "returns")
    assert r.to_ref.table_id == returns_table.id
    assert r.to_ref.column_id == "order_id"


def test_build_relationships_empty_when_no_raw_rels():
    tables, _ = build_tables([_RAW_FEDERATED_DS])
    assert build_relationships([], [_RAW_FEDERATED_DS], tables) == ()


def test_build_relationships_skips_unresolvable_col():
    raw_rels = [{"left_col": "nonexistent", "right_col": "order_id (returns)"}]
    tables, _ = build_tables([_RAW_FEDERATED_DS])
    assert build_relationships(raw_rels, [_RAW_FEDERATED_DS], tables) == ()
