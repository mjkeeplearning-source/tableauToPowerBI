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
    rels, _ = build_relationships(_RAW_RELS, [_RAW_FEDERATED_DS], tables)
    assert len(rels) == 1
    r = rels[0]
    assert r.source == RelationshipSource.TABLEAU_JOIN


def test_build_relationships_from_ref_resolves_to_orders_table():
    tables, _ = build_tables([_RAW_FEDERATED_DS])
    rels, _ = build_relationships(_RAW_RELS, [_RAW_FEDERATED_DS], tables)
    r = rels[0]
    orders_table = next(t for t in tables if t.name == "orders")
    assert r.from_ref.table_id == orders_table.id
    assert r.from_ref.column_id == "order_id"


def test_build_relationships_to_ref_resolves_to_returns_table():
    tables, _ = build_tables([_RAW_FEDERATED_DS])
    rels, _ = build_relationships(_RAW_RELS, [_RAW_FEDERATED_DS], tables)
    r = rels[0]
    returns_table = next(t for t in tables if t.name == "returns")
    assert r.to_ref.table_id == returns_table.id
    assert r.to_ref.column_id == "order_id"


def test_build_relationships_empty_when_no_raw_rels():
    tables, _ = build_tables([_RAW_FEDERATED_DS])
    assert build_relationships([], [_RAW_FEDERATED_DS], tables) == ((), ())


def test_build_relationships_skips_unresolvable_col():
    raw_rels = [{"left_col": "nonexistent", "right_col": "order_id (returns)"}]
    tables, _ = build_tables([_RAW_FEDERATED_DS])
    rels, _ = build_relationships(raw_rels, [_RAW_FEDERATED_DS], tables)
    assert rels == ()


# ---------------------------------------------------------------------------
# Fixtures for unique-key cases
# ---------------------------------------------------------------------------

_RAW_DS_PEOPLE_ORDERS = {
    "name": "federated.xyz",
    "connection": {"class": "federated"},
    "named_connections": [
        {"name": "pg.abc", "caption": "srv",
         "connection": {"class": "postgres", "server": "srv", "dbname": "db"}}
    ],
    "relations": [
        {"name": "people", "table": "[public].[people]", "connection": "pg.abc"},
        {"name": "orders", "table": "[public].[orders]", "connection": "pg.abc"},
    ],
    "col_map": {
        "region":           ("people", "region"),
        "region (orders)":  ("orders", "region"),
    },
    "columns": [
        {"name": "region",          "datatype": "string", "role": "dimension", "type": None},
        {"name": "region (orders)", "datatype": "string", "role": "dimension", "type": None},
    ],
    "calculations": [],
    "extract": None,
}


def _po_rel(first_unique: bool = False, second_unique: bool = False) -> dict:
    return {
        "left_col":          "region",
        "right_col":         "region (orders)",
        "first_unique_key":  first_unique,
        "second_unique_key": second_unique,
    }


# --- Case 1: No unique-key (M:M Tableau default) ---

def test_no_unique_key_produces_many_to_many():
    tables, _ = build_tables([_RAW_DS_PEOPLE_ORDERS])
    rels, _ = build_relationships([_po_rel()], [_RAW_DS_PEOPLE_ORDERS], tables)
    assert rels[0].cardinality == "many_to_many"


def test_no_unique_key_produces_cross_filter_both():
    tables, _ = build_tables([_RAW_DS_PEOPLE_ORDERS])
    rels, _ = build_relationships([_po_rel()], [_RAW_DS_PEOPLE_ORDERS], tables)
    assert rels[0].cross_filter == "both"


# --- Case 2: second-end-point is ONE side ---

def test_second_unique_produces_many_to_one():
    tables, _ = build_tables([_RAW_DS_PEOPLE_ORDERS])
    rels, _ = build_relationships([_po_rel(second_unique=True)], [_RAW_DS_PEOPLE_ORDERS], tables)
    assert rels[0].cardinality == "many_to_one"


def test_second_unique_from_ref_is_people_many_side():
    tables, _ = build_tables([_RAW_DS_PEOPLE_ORDERS])
    rels, _ = build_relationships([_po_rel(second_unique=True)], [_RAW_DS_PEOPLE_ORDERS], tables)
    people_table = next(t for t in tables if t.name == "people")
    assert rels[0].from_ref.table_id == people_table.id  # people = MANY, stays as from


# --- Case 3: first-end-point is ONE side (requires swap) ---

def test_first_unique_produces_many_to_one():
    tables, _ = build_tables([_RAW_DS_PEOPLE_ORDERS])
    rels, _ = build_relationships([_po_rel(first_unique=True)], [_RAW_DS_PEOPLE_ORDERS], tables)
    assert rels[0].cardinality == "many_to_one"


def test_first_unique_swaps_from_ref_to_orders_many_side():
    """first=ONE (people) must become to_ref; orders=MANY becomes from_ref."""
    tables, _ = build_tables([_RAW_DS_PEOPLE_ORDERS])
    rels, _ = build_relationships([_po_rel(first_unique=True)], [_RAW_DS_PEOPLE_ORDERS], tables)
    orders_table = next(t for t in tables if t.name == "orders")
    people_table = next(t for t in tables if t.name == "people")
    assert rels[0].from_ref.table_id == orders_table.id   # orders = MANY → from
    assert rels[0].to_ref.table_id   == people_table.id   # people = ONE  → to


# --- Case 4: both unique (1:1) ---

def test_both_unique_produces_one_to_one():
    tables, _ = build_tables([_RAW_DS_PEOPLE_ORDERS])
    rels, _ = build_relationships(
        [_po_rel(first_unique=True, second_unique=True)],
        [_RAW_DS_PEOPLE_ORDERS], tables,
    )
    assert rels[0].cardinality == "one_to_one"


def test_both_unique_produces_cross_filter_both():
    tables, _ = build_tables([_RAW_DS_PEOPLE_ORDERS])
    rels, _ = build_relationships(
        [_po_rel(first_unique=True, second_unique=True)],
        [_RAW_DS_PEOPLE_ORDERS], tables,
    )
    assert rels[0].cross_filter == "both"


# ---------------------------------------------------------------------------
# Migration warning tests
# ---------------------------------------------------------------------------

def test_no_unique_key_emits_mm_warning():
    tables, _ = build_tables([_RAW_DS_PEOPLE_ORDERS])
    _, warnings = build_relationships([_po_rel()], [_RAW_DS_PEOPLE_ORDERS], tables)
    assert len(warnings) == 1
    w = warnings[0]
    assert w.code == "relationship_cardinality_mm_default"
    assert w.object_kind == "relationship"


def test_one_to_one_emits_design_smell_warning():
    tables, _ = build_tables([_RAW_DS_PEOPLE_ORDERS])
    _, warnings = build_relationships(
        [_po_rel(first_unique=True, second_unique=True)],
        [_RAW_DS_PEOPLE_ORDERS], tables,
    )
    assert len(warnings) == 1
    assert warnings[0].code == "relationship_cardinality_one_to_one"
    assert warnings[0].object_kind == "relationship"


def test_directed_relationships_emit_no_warnings():
    """Case 2 and Case 3 (clean 1:M) should not produce any warnings."""
    tables, _ = build_tables([_RAW_DS_PEOPLE_ORDERS])
    _, w2 = build_relationships([_po_rel(second_unique=True)], [_RAW_DS_PEOPLE_ORDERS], tables)
    _, w3 = build_relationships([_po_rel(first_unique=True)],  [_RAW_DS_PEOPLE_ORDERS], tables)
    assert w2 == ()
    assert w3 == ()
