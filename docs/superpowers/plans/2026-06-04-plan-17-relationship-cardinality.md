# Plan 17 — Relationship Cardinality: `unique-key`-Driven Four-Case Logic

> **Execution approach: Subagent-Driven (chosen).** Use `superpowers:subagent-driven-development` to implement this plan — dispatch a fresh subagent per task, review output between tasks. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Replace the two hardcoded lines `cardinality="many_to_one"` and `cross_filter="single"` in `build_relationships()` with a deterministic four-case algorithm driven by the `unique-key` attribute from Tableau's official XSD, fixing the grand-total data mismatch bug and making all future multi-table workbooks produce correct PBI cross-filter topology.

**Architecture:** Three-layer fix — (1) the extract layer reads `unique-key` from `<first-end-point>`/`<second-end-point>` and forwards two boolean flags; (2) the canonicalize layer applies the four-case decision and optionally swaps `from_ref`/`to_ref` to enforce PBI's TMDL invariant (`fromColumn` = MANY side); (3) the emit layer gets one new `_CARD_MAP` entry for `many_to_many`. A new return value from `build_relationships()` also pipes M:M fallback and 1:1 migration warnings into the workbook's `unsupported` list.

**Tech Stack:** Python 3.11+, lxml, pydantic v2, pytest — no new dependencies.

**Research:** See `research_relationship_cardinality.md` at project root and `C:\vibe_coding\tabToPbi\docs\relationship_dashboard.md` (MVP project reference implementation).

---

## Background: The Four Cases

| `first-end-point unique-key` | `second-end-point unique-key` | Cardinality IR | `cross_filter` IR | TMDL `crossFilteringBehavior` | Swap `from`/`to`? |
|---|---|---|---|---|---|
| absent | absent | `many_to_many` | `"both"` | `bothDirections` | No |
| absent | `"true"` | `many_to_one` | `"single"` | `oneDirection` | No |
| `"true"` | absent | `many_to_one` | `"single"` | `oneDirection` | **Yes** — first→`to_ref`, second→`from_ref` |
| `"true"` | `"true"` | `one_to_one` | `"both"` | `bothDirections` | No |

**Why the swap?** PBI TMDL mandates `fromColumn` = MANY side. When `first-end-point` is the ONE side, `left_col`'s table maps to `from_ref` by default — violating the convention. Swapping before constructing `FieldRef` fixes this without any special-casing in the emitter.

**Our workbook (`simple_join_calculated_line.twb`)** has no `unique-key` on either endpoint (grep confirmed zero matches) → Case 1 → `many_to_many` + `bothDirections`. This fixes the grand-total bug.

---

## File Map

| File | Change |
|---|---|
| `src/tableau2pbir/extract/datasources.py` | Modify `extract_object_graph_relationships()` — read `unique-key` attribute from endpoints |
| `src/tableau2pbir/stages/_build_data_model.py` | Modify `build_relationships()` — four-case logic + new `UnsupportedItem` return |
| `src/tableau2pbir/stages/s02_canonicalize.py` | Modify `run()` — unpack new `build_relationships()` return, add `rel_warnings` to `unsupported` |
| `src/tableau2pbir/emit/tmdl/relationship.py` | Modify `_CARD_MAP` — add `"many_to_many"` entry |
| `tests/unit/extract/test_datasources.py` | Add 4 tests for `unique-key` flag extraction |
| `tests/unit/stages/test_s02_relationships.py` | Add 8 tests for four-case cardinality + swap + warnings |
| `tests/unit/emit/tmdl/test_relationship.py` | **Create** — unit tests for `render_relationship()` across all four cardinality values |
| `tests/golden/test_real_stage2.py` | Add relationship cardinality assertions for `simple_join_calculated_line` |

---

## Task 1: Extract layer — forward `unique-key` flags from object-graph endpoints

**Files:**
- Modify: `src/tableau2pbir/extract/datasources.py:132-152`
- Modify: `tests/unit/extract/test_datasources.py`

### Step 1.1 — Write the failing tests

Add these four tests to `tests/unit/extract/test_datasources.py`. The existing `_XML_WITH_OBJECT_GRAPH` fixture at line 141 has no `unique-key` attributes. Define three new XML constants below it:

```python
_XML_FIRST_UNIQUE = b"""<?xml version='1.0'?>
<workbook>
  <object-graph>
    <relationships>
      <relationship>
        <expression op="=">
          <expression op="[region]"/>
          <expression op="[region (orders)]"/>
        </expression>
        <first-end-point  object-id="people_OBJ" unique-key="true"/>
        <second-end-point object-id="orders_OBJ"/>
      </relationship>
    </relationships>
  </object-graph>
</workbook>
"""

_XML_SECOND_UNIQUE = b"""<?xml version='1.0'?>
<workbook>
  <object-graph>
    <relationships>
      <relationship>
        <expression op="=">
          <expression op="[region]"/>
          <expression op="[region (orders)]"/>
        </expression>
        <first-end-point  object-id="people_OBJ"/>
        <second-end-point object-id="orders_OBJ" unique-key="true"/>
      </relationship>
    </relationships>
  </object-graph>
</workbook>
"""

_XML_BOTH_UNIQUE = b"""<?xml version='1.0'?>
<workbook>
  <object-graph>
    <relationships>
      <relationship>
        <expression op="=">
          <expression op="[id]"/>
          <expression op="[id (shadow)]"/>
        </expression>
        <first-end-point  object-id="a_OBJ" unique-key="true"/>
        <second-end-point object-id="b_OBJ" unique-key="true"/>
      </relationship>
    </relationships>
  </object-graph>
</workbook>
"""


def test_object_graph_no_unique_key_both_flags_false():
    root = parse_workbook_xml(_XML_WITH_OBJECT_GRAPH)
    rels = extract_object_graph_relationships(root)
    assert rels[0]["first_unique_key"] is False
    assert rels[0]["second_unique_key"] is False


def test_object_graph_first_unique_key_true():
    root = parse_workbook_xml(_XML_FIRST_UNIQUE)
    rels = extract_object_graph_relationships(root)
    assert rels[0]["first_unique_key"] is True
    assert rels[0]["second_unique_key"] is False


def test_object_graph_second_unique_key_true():
    root = parse_workbook_xml(_XML_SECOND_UNIQUE)
    rels = extract_object_graph_relationships(root)
    assert rels[0]["first_unique_key"] is False
    assert rels[0]["second_unique_key"] is True


def test_object_graph_both_unique_key_true():
    root = parse_workbook_xml(_XML_BOTH_UNIQUE)
    rels = extract_object_graph_relationships(root)
    assert rels[0]["first_unique_key"] is True
    assert rels[0]["second_unique_key"] is True
```

- [x] Add the four XML constants and four test functions above to `tests/unit/extract/test_datasources.py`

### Step 1.2 — Run tests to confirm they fail

```
pytest tests/unit/extract/test_datasources.py::test_object_graph_no_unique_key_both_flags_false tests/unit/extract/test_datasources.py::test_object_graph_first_unique_key_true tests/unit/extract/test_datasources.py::test_object_graph_second_unique_key_true tests/unit/extract/test_datasources.py::test_object_graph_both_unique_key_true -v
```

Expected: 4 × `KeyError` or `AssertionError` — `"first_unique_key"` key not present in dict.

- [x] Run and confirm failure

### Step 1.3 — Implement the fix

In `src/tableau2pbir/extract/datasources.py`, replace lines 140–151 of `extract_object_graph_relationships()`:

```python
    out: list[dict[str, Any]] = []
    for og in root.iter("object-graph"):
        for rel in og.findall("relationships/relationship"):
            expr = rel.find("expression[@op='=']")
            if expr is None:
                continue
            children = expr.findall("expression")
            if len(children) != 2:
                continue
            left_col = children[0].get("op", "").strip("[]")
            right_col = children[1].get("op", "").strip("[]")
            if not left_col or not right_col:
                continue
            first_ep  = rel.find("first-end-point")
            second_ep = rel.find("second-end-point")
            out.append({
                "left_col":          left_col,
                "right_col":         right_col,
                "first_unique_key":  first_ep  is not None and first_ep.get("unique-key")  == "true",
                "second_unique_key": second_ep is not None and second_ep.get("unique-key") == "true",
            })
    return out
```

- [x] Apply the implementation above

### Step 1.4 — Run tests to confirm they pass

```
pytest tests/unit/extract/test_datasources.py -v
```

Expected: all tests pass (the four new ones + the two existing object-graph tests).

- [x] Confirm pass

### Step 1.5 — Commit

```
git add src/tableau2pbir/extract/datasources.py tests/unit/extract/test_datasources.py
git commit -m "feat: extract unique-key flags from object-graph relationship endpoints"
```

- [x] Commit

---

## Task 2: Emit layer — add `many_to_many` to `_CARD_MAP`

**Files:**
- Modify: `src/tableau2pbir/emit/tmdl/relationship.py`
- Create: `tests/unit/emit/tmdl/test_relationship.py`

### Step 2.1 — Create the test file

Create `tests/unit/emit/tmdl/test_relationship.py` with:

```python
"""Unit tests for render_relationship()."""
from __future__ import annotations

from tableau2pbir.emit.tmdl.relationship import render_relationship
from tableau2pbir.ir.common import FieldRef
from tableau2pbir.ir.model import Relationship, RelationshipSource


def _rel(cardinality: str, cross_filter: str) -> Relationship:
    return Relationship(
        id="rel__a__b",
        from_ref=FieldRef(table_id="tbl__a", column_id="fk_col"),
        to_ref=FieldRef(table_id="tbl__b", column_id="pk_col"),
        cardinality=cardinality,
        cross_filter=cross_filter,
        source=RelationshipSource.TABLEAU_JOIN,
    )


def test_many_to_one_renders_one_direction():
    out = render_relationship(_rel("many_to_one", "single"), "factA", "dimB")
    assert "fromCardinality: many" in out
    assert "toCardinality: one" in out
    assert "crossFilteringBehavior: oneDirection" in out


def test_many_to_many_renders_both_directions():
    out = render_relationship(_rel("many_to_many", "both"), "tableA", "tableB")
    assert "fromCardinality: many" in out
    assert "toCardinality: many" in out
    assert "crossFilteringBehavior: bothDirections" in out


def test_one_to_one_renders_both_directions():
    out = render_relationship(_rel("one_to_one", "both"), "tableA", "tableB")
    assert "fromCardinality: one" in out
    assert "toCardinality: one" in out
    assert "crossFilteringBehavior: bothDirections" in out


def test_from_and_to_column_names_appear_in_output():
    out = render_relationship(_rel("many_to_one", "single"), "orders", "people")
    assert "fromColumn: orders.fk_col" in out
    assert "toColumn: people.pk_col" in out
```

- [x] Create `tests/unit/emit/tmdl/test_relationship.py` with the content above

### Step 2.2 — Run tests to confirm they fail

```
pytest tests/unit/emit/tmdl/test_relationship.py -v
```

Expected: `test_many_to_many_renders_both_directions` and `test_one_to_one_renders_both_directions` fail — `_CARD_MAP` has no `many_to_many` key and falls through to the `("many", "one")` fallback.

- [x] Confirm failure

### Step 2.3 — Add `many_to_many` to `_CARD_MAP`

In `src/tableau2pbir/emit/tmdl/relationship.py`, replace `_CARD_MAP`:

```python
_CARD_MAP = {
    "one_to_one":   ("one",  "one"),
    "one_to_many":  ("one",  "many"),
    "many_to_one":  ("many", "one"),
    "many_to_many": ("many", "many"),
}
```

- [x] Apply the change

### Step 2.4 — Run tests to confirm they pass

```
pytest tests/unit/emit/tmdl/test_relationship.py -v
```

Expected: all 4 tests pass.

- [x] Confirm pass

### Step 2.5 — Commit

```
git add src/tableau2pbir/emit/tmdl/relationship.py tests/unit/emit/tmdl/test_relationship.py
git commit -m "feat: add many_to_many cardinality to relationship TMDL renderer"
```

- [x] Commit

---

## Task 3: Canonicalize layer — four-case cardinality logic in `build_relationships()`

This is the main fix. It also changes the return type to `tuple[tuple[Relationship, ...], tuple[UnsupportedItem, ...]]` so migration warnings can flow into the workbook report.

**Files:**
- Modify: `src/tableau2pbir/stages/_build_data_model.py:187-234`
- Modify: `src/tableau2pbir/stages/s02_canonicalize.py:99-103` and `143-150`
- Modify: `tests/unit/stages/test_s02_relationships.py`

### Step 3.1 — Write the failing tests

Add these tests to `tests/unit/stages/test_s02_relationships.py`. They extend the existing fixture style. Add a new helper and eight new test functions after the last existing test:

```python
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
```

Also update the **existing** tests to unpack the new two-tuple return:

```python
# Change every existing call:
#   rels = build_relationships(...)
# to:
#   rels, _ = build_relationships(...)
```

The five existing tests use:
```python
rels = build_relationships(_RAW_RELS, [_RAW_FEDERATED_DS], tables)
```
Replace all five with:
```python
rels, _ = build_relationships(_RAW_RELS, [_RAW_FEDERATED_DS], tables)
```

- [x] Add the new fixtures (`_RAW_DS_PEOPLE_ORDERS`, `_po_rel()`) and eight test functions to `tests/unit/stages/test_s02_relationships.py`
- [x] Update the five existing `rels = build_relationships(...)` calls to `rels, _ = build_relationships(...)`

### Step 3.2 — Run tests to confirm they fail

```
pytest tests/unit/stages/test_s02_relationships.py -v
```

Expected: all five existing tests fail (return type mismatch — can't unpack one value), plus the eight new tests fail.

- [x] Confirm failure

### Step 3.3 — Implement the four-case logic in `build_relationships()`

Replace `build_relationships()` in `src/tableau2pbir/stages/_build_data_model.py` entirely (lines 187–234):

```python
def build_relationships(
    raw_rels: list[dict[str, Any]],
    raw_datasources: list[dict[str, Any]],
    tables: tuple[Table, ...],
) -> tuple[tuple[Relationship, ...], tuple[UnsupportedItem, ...]]:
    """Build Relationship IR from raw Stage-1 join predicates.

    Applies the four-case algorithm driven by Tableau's official unique-key
    XSD attribute. See research_relationship_cardinality.md for full rationale.

    Returns (relationships, unsupported_warnings).
    """
    if not raw_rels:
        return (), ()

    merged_col_map: dict[str, tuple[str, str]] = {}
    for raw_ds in raw_datasources:
        merged_col_map.update(raw_ds.get("col_map") or {})

    table_by_name: dict[str, Table] = {t.name: t for t in tables}

    out: list[Relationship] = []
    warnings: list[UnsupportedItem] = []

    for raw in raw_rels:
        left_col  = raw.get("left_col", "")
        right_col = raw.get("right_col", "")

        left_resolved  = merged_col_map.get(left_col)
        right_resolved = merged_col_map.get(right_col)
        if not left_resolved or not right_resolved:
            continue

        left_table_name,  left_phys_col  = left_resolved
        right_table_name, right_phys_col = right_resolved

        left_table  = table_by_name.get(left_table_name)
        right_table = table_by_name.get(right_table_name)
        if not left_table or not right_table:
            continue

        first_unique  = raw.get("first_unique_key",  False)
        second_unique = raw.get("second_unique_key", False)

        if first_unique and second_unique:
            # Case 4 — 1:1: both sides unique; PBI mandates bothDirections for 1:1.
            cardinality  = "one_to_one"
            cross_filter = "both"
            from_table, from_col = left_table,  left_phys_col
            to_table,   to_col   = right_table, right_phys_col
            warnings.append(UnsupportedItem(
                object_kind="relationship",
                object_id=stable_id("rel", f"{left_table_name}__{right_table_name}"),
                source_excerpt=f"{left_table_name}.{left_phys_col} = {right_table_name}.{right_phys_col}",
                reason=(
                    f"One-to-one relationship detected between {left_table_name!r} and "
                    f"{right_table_name!r}. Microsoft recommends merging these tables in "
                    "Power Query instead."
                ),
                code="relationship_cardinality_one_to_one",
            ))
        elif first_unique:
            # Case 3 — first endpoint is ONE side.
            # Swap so PBI TMDL invariant holds: fromColumn = MANY side.
            cardinality  = "many_to_one"
            cross_filter = "single"
            from_table, from_col = right_table, right_phys_col   # MANY side
            to_table,   to_col   = left_table,  left_phys_col    # ONE side
        elif second_unique:
            # Case 2 — second endpoint is ONE side; current order is already correct.
            cardinality  = "many_to_one"
            cross_filter = "single"
            from_table, from_col = left_table,  left_phys_col    # MANY side
            to_table,   to_col   = right_table, right_phys_col   # ONE side
        else:
            # Case 1 — No unique-key: Tableau M:M default → bothDirections.
            cardinality  = "many_to_many"
            cross_filter = "both"
            from_table, from_col = left_table,  left_phys_col
            to_table,   to_col   = right_table, right_phys_col
            warnings.append(UnsupportedItem(
                object_kind="relationship",
                object_id=stable_id("rel", f"{left_table_name}__{right_table_name}"),
                source_excerpt=f"{left_table_name}.{left_phys_col} = {right_table_name}.{right_phys_col}",
                reason=(
                    f"Relationship {left_table_name!r}.{left_phys_col} ↔ "
                    f"{right_table_name!r}.{right_phys_col}: no unique-key set in Tableau "
                    "source — defaulted to M:M bidirectional cross-filter. Verify "
                    "intended cardinality in PBI Desktop Model View."
                ),
                code="relationship_cardinality_mm_default",
            ))

        rel_id = stable_id("rel", f"{from_table.name}__{to_table.name}")
        out.append(Relationship(
            id=rel_id,
            from_ref=FieldRef(table_id=from_table.id, column_id=from_col),
            to_ref=FieldRef(table_id=to_table.id,   column_id=to_col),
            cardinality=cardinality,
            cross_filter=cross_filter,
            source=RelationshipSource.TABLEAU_JOIN,
        ))

    return tuple(out), tuple(warnings)
```

- [x] Replace `build_relationships()` with the implementation above

### Step 3.4 — Update the caller in `s02_canonicalize.py`

In `src/tableau2pbir/stages/s02_canonicalize.py`, change lines 99–103:

```python
    relationships, rel_warnings = build_relationships(
        input_json.get("relationships", []),
        input_json.get("datasources", []),
        tables,
    )
```

And change the `unsupported` assembly at lines 143–150 to include `rel_warnings`:

```python
    unsupported = (
        ds_unsupported
        + qtc_unsupported
        + cycle_items
        + tier_c_items
        + deferred_calc_items
        + deferred_param_items
        + rel_warnings
    )
```

- [x] Apply both changes to `s02_canonicalize.py`

### Step 3.5 — Run relationship tests to confirm they pass

```
pytest tests/unit/stages/test_s02_relationships.py -v
```

Expected: all 13 tests pass (5 existing + 8 new).

- [x] Confirm pass

### Step 3.6 — Run broader stage tests to catch any regressions

```
pytest tests/unit/stages/ tests/unit/extract/ tests/unit/emit/ -v
```

Expected: all tests pass.

- [x] Confirm pass

### Step 3.7 — Commit

```
git add src/tableau2pbir/stages/_build_data_model.py src/tableau2pbir/stages/s02_canonicalize.py tests/unit/stages/test_s02_relationships.py
git commit -m "fix: replace hardcoded relationship cardinality with four-case unique-key algorithm"
```

- [x] Commit

---

## Task 4: Add migration warning tests

The `build_relationships()` implementation already emits `UnsupportedItem` warnings. This task verifies them with explicit tests.

**Files:**
- Modify: `tests/unit/stages/test_s02_relationships.py`

### Step 4.1 — Write the warning tests

Add these three tests to `tests/unit/stages/test_s02_relationships.py`:

```python
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


def test_directed_relationships_emit_no_warnings():
    """Case 2 and Case 3 (clean 1:M) should not produce any warnings."""
    tables, _ = build_tables([_RAW_DS_PEOPLE_ORDERS])
    _, w2 = build_relationships([_po_rel(second_unique=True)], [_RAW_DS_PEOPLE_ORDERS], tables)
    _, w3 = build_relationships([_po_rel(first_unique=True)],  [_RAW_DS_PEOPLE_ORDERS], tables)
    assert w2 == ()
    assert w3 == ()
```

- [x] Add the three warning tests to `tests/unit/stages/test_s02_relationships.py`

### Step 4.2 — Run tests

```
pytest tests/unit/stages/test_s02_relationships.py -v
```

Expected: all 16 tests pass.

- [x] Confirm pass

### Step 4.3 — Commit

```
git add tests/unit/stages/test_s02_relationships.py
git commit -m "test: verify migration warnings for M:M and 1:1 relationships"
```

- [x] Commit

---

## Task 5: Golden test — assert corrected cardinality for `simple_join_calculated_line`

**Files:**
- Modify: `tests/golden/test_real_stage2.py`

### Step 5.1 — Write the failing assertions

Find `test_simple_join_calculated_line_counts` in `tests/golden/test_real_stage2.py` (currently at lines 111–117) and extend it:

```python
def test_simple_join_calculated_line_counts():
    out = _run_pipeline("simple_join_calculated_line.twb")
    dm = out["data_model"]
    assert len(dm["datasources"]) == 1
    assert len(dm["tables"]) == 3  # people, orders, returns
    assert len(dm["calculations"]) == 0
    assert len(out["sheets"]) == 2
    # Relationship cardinality assertions — Plan 17 fix
    assert len(dm["relationships"]) == 2
    rels_by_id = {r["id"]: r for r in dm["relationships"]}
    # people ↔ orders: no unique-key in TWB → M:M default
    people_orders = next(
        r for r in dm["relationships"]
        if "people" in r["from_ref"]["table_id"] or "people" in r["to_ref"]["table_id"]
    )
    assert people_orders["cardinality"] == "many_to_many"
    assert people_orders["cross_filter"] == "both"
    # orders ↔ returns: no unique-key in TWB → M:M default
    orders_returns = next(
        r for r in dm["relationships"]
        if "returns" in r["from_ref"]["table_id"] or "returns" in r["to_ref"]["table_id"]
    )
    assert orders_returns["cardinality"] == "many_to_many"
    assert orders_returns["cross_filter"] == "both"
```

- [x] Replace `test_simple_join_calculated_line_counts` in `tests/golden/test_real_stage2.py` with the extended version above

### Step 5.2 — Run to confirm the test fails (before fix would have failed with `many_to_one`)

```
pytest tests/golden/test_real_stage2.py::test_simple_join_calculated_line_counts -v
```

At this stage, after Tasks 1–4 are already committed, this test should **pass** since the pipeline now emits `many_to_many`. If it passes, skip to Step 5.4.

If it fails (e.g. the key names are slightly different), inspect the actual `dm["relationships"]` dict structure by temporarily adding `print(dm["relationships"])` and running with `-s`, then adjust the assertions to match the actual field names.

- [x] Run and confirm result

### Step 5.3 — Run the full golden suite

```
pytest tests/golden/ -v
```

Expected: all tests pass.

- [x] Confirm pass

### Step 5.4 — Run the E2E integration test for `simple_join_calculated_line`

```
pytest tests/integration/test_real_workbooks_e2e.py -k "simple_join_calculated_line" -v -m integration
```

Expected: passes (the E2E test checks pipeline completion, not TMDL byte content).

- [x] Confirm pass

### Step 5.5 — Commit

```
git add tests/golden/test_real_stage2.py
git commit -m "test: assert M:M cardinality for simple_join_calculated_line Stage 2 output"
```

- [x] Commit

---

## Task 6: Full regression and E2E gate

### Step 6.1 — Run all unit tests

```
pytest tests/unit/ tests/contract/ tests/golden/ -v
```

Expected: all pass.

- [x] Confirm pass

### Step 6.2 — Run the full real-workbook E2E suite

```
pytest tests/integration/test_real_workbooks_e2e.py -v -m integration
```

Expected: all pass (or skip with `requires a valid ANTHROPIC_API_KEY` for workbooks with untranslated calculations — that is a pre-existing condition unrelated to this plan).

- [x] Confirm pass

### Step 6.3 — Run the regression gate

```
python -m tableau2pbir regression-check
```

Expected: no regressions. Note: `simple_join_calculated_line` is NOT in the regression corpus (`tests/regression/corpus.yaml`) so its TMDL change does not trigger a snapshot failure.

- [x] Confirm clean

### Step 6.4 — Final commit tag

```
git commit --allow-empty -m "chore: Plan 17 relationship cardinality fix complete — all tests green"
```

- [x] Commit

---

## Self-Review Checklist

**Spec coverage:**
- [x] Extract layer reads `unique-key` — Task 1
- [x] Four-case logic in `build_relationships()` — Task 3
- [x] Case 3 swap enforces `fromColumn=MANY` TMDL invariant — Task 3 Step 3.3
- [x] `many_to_many` cardinality emits `bothDirections` — Task 2
- [x] M:M fallback warning in migration report — Task 3 Step 3.3 + Task 4
- [x] 1:1 design-smell warning in migration report — Task 3 Step 3.3 + Task 4
- [x] `simple_join_calculated_line` golden test updated — Task 5
- [x] Full regression gate passes — Task 6
- [x] `s02_canonicalize.py` caller updated — Task 3 Step 3.4

**No placeholders:** All code steps show complete, runnable code. All `pytest` commands include full paths. All commit messages are specific.

**Type consistency:**
- `build_relationships()` return type is `tuple[tuple[Relationship, ...], tuple[UnsupportedItem, ...]]` — consistent across Task 3 tests (unpacked as `rels, warnings = ...`) and the `s02_canonicalize.py` caller change.
- `_po_rel()` helper produces the same dict shape expected by `build_relationships()` — `left_col`, `right_col`, `first_unique_key`, `second_unique_key`.
- `stable_id("rel", f"{from_table.name}__{to_table.name}")` uses `.name` (the string table name, not `.id`) — matches the existing pattern at the original line 224.

---

## Notes for Future Work

- **Physical join path** (`<relation type='join'>`): The current project has no active physical-join extractor. When added, apply the three-signal cardinality inference from the MVP project (`C:\vibe_coding\tabToPbi\tab_to_pbi\transformer.py:_infer_cardinality`) — join type (LEFT → from=ONE), column naming (col base matches table name → PK side = ONE), fallback (right/to_table = ONE).
- **Diamond topology detector**: If future workbooks add two separate relationship paths between the same table pair, `bothDirections` will cause PBI to raise an "ambiguous filter path" error. Add a detector in `build_relationships()` that emits an `UnsupportedItem` with code `relationship_diamond_topology` when `{from_table, to_table}` is seen more than once.
- **Regression corpus**: After verifying in PBI Desktop that `simple_join_calculated_line` renders correctly with the M:M fix, add it to the regression corpus (user must explicitly request this per CLAUDE.md).
