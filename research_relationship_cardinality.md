# Research: Tableau Logical Relationship → PBI Relationship Cardinality

**Date:** 2026-06-04  
**Workbook investigated:** `simple_join_calculated_line.twb`  
**Symptom:** PBI shows grand total repeated for every dimension value instead of per-dimension aggregates.  
**Updated:** 2026-06-04 — added MVP project findings (Strategy E) and physical join inference algorithm.

---

## The Bug

Tableau Sheet 1 has `Region` on Columns and `SUM(Profit)` / `SUM(Sales)` on Rows. The data is sourced from three tables: `people`, `orders`, `returns`.

| Tableau (correct) | PBI (broken) |
|---|---|
| West: 110,798 profit | Every region: **292,295** profit |
| East: 94,882 profit | Every region: **292,295** profit |
| Central: 39,865 profit | Every region: **292,295** profit |

292,295 is the grand total (sum of all regions). PBI returns the grand total for every row because the cross-filter that should propagate `Region` from the `people` table into the `orders` table is flowing in the wrong direction.

---

## Official PBI Cross-Filter Rule (Verified)

Source: [Relationships object (TMSL) — Microsoft Learn](https://learn.microsoft.com/en-us/analysis-services/tmsl/relationships-object-tmsl?view=sql-analysis-services-2025)

> **OneDirection (default):** *"The rows selected in the 'To' end of the relationship will automatically filter scans of the table in the 'From' end of the relationship."*

Filter travels: **TO end → FROM end**

Source: [Model relationships in Power BI Desktop — Microsoft Learn](https://learn.microsoft.com/en-us/power-bi/transform-model/desktop-relationships-understand)

> *"For one-to-many relationships, the cross filter direction is always from the 'one' side."*  
> *"The 'one' side means the column contains unique values."*

The TMDL convention therefore is:
- `fromColumn` = the **MANY side** (fact table — gets filtered)
- `toColumn` = the **ONE side** (dimension table — filter originates here)
- With `oneDirection`: filters flow `toColumn` (ONE/dimension) → `fromColumn` (MANY/fact)

---

## Tableau's Logical Relationship XML — What Is and Is Not Stored

The workbook uses Tableau's **logical layer** (`<object-graph>`), not the older physical join layer (`<relation type='join'>`).

```xml
<!-- tests/golden/real/simple_join_calculated_line.twb, lines 517–534 -->
<object-graph>
  <relationships>
    <relationship>
      <expression op="=">
        <expression op="[region]" />           <!-- people table column -->
        <expression op="[region (orders)]" />  <!-- orders table column -->
      </expression>
      <first-end-point  object-id="people (superstore.people)_..." />
      <second-end-point object-id="orders (superstore.orders)_..." />
    </relationship>
    <relationship>
      <expression op="=">
        <expression op="[order_id]" />
        <expression op="[order_id (returns)]" />
      </expression>
      <first-end-point  object-id="orders ..." />
      <second-end-point object-id="returns ..." />
    </relationship>
  </relationships>
</object-graph>
```

**Validated against the official Tableau document schema (`tableau-document-schemas` — `twb_2026.1.0.xsd`):**

The XSD defines `EndPointAttributes-G` — the attributes available on each endpoint element:

| Attribute | Required | Meaning |
|---|---|---|
| `object-id` | Required | Identifies the participating table object |
| `unique-key` | Optional | `"true"` = this side has unique values = the ONE side |
| `guaranteed-value` | Optional | Referential integrity hint |
| `is-db-set-unique-key` | Optional | DB-enforced uniqueness |
| `is-db-set-guaranteed-value` | Optional | DB-enforced referential integrity |

**`unique-key` is the only cardinality signal in the Tableau XSD.** There is no explicit `cardinality` attribute. When `unique-key` is absent on both endpoints (as in our workbook), Tableau applies its documented default.

**Tableau default cardinality when `unique-key` is absent:**

Source: [Optimize Relationship Queries — Tableau Help](https://help.tableau.com/current/server/en-us/datasource_relationships_perfoptions.htm)

> *"The default settings are: Cardinality: Many-to-Many, Referential integrity: Some Records Match."*

Our workbook has no `unique-key` on either endpoint — confirmed by grepping the TWB (zero matches). This means Tableau treats `people ↔ orders` as **M:M by default**.

**`first-end-point` and `second-end-point` ordering does NOT encode cardinality.**  
It reflects the order tables were dragged onto the logical canvas in Tableau Desktop. A workbook author anchoring on the fact table (e.g. `orders`) will have `orders` as `first-end-point`. Never use ordering as a cardinality signal.

---

## What the Pipeline Currently Emits (Broken)

### Extract layer — `extract/datasources.py`, lines 140–151

```python
children = expr.findall("expression")
left_col  = children[0].get("op", "").strip("[]")
right_col = children[1].get("op", "").strip("[]")
out.append({"left_col": left_col, "right_col": right_col})
# first-end-point / second-end-point elements are never read
```

The `<first-end-point>` and `<second-end-point>` elements — including the `unique-key` attribute — are completely discarded. Only bare join key names are forwarded.

### Canonicalize layer — `stages/_build_data_model.py`, lines 225–232

```python
out.append(Relationship(
    from_ref=FieldRef(table_id=left_table.id, column_id=left_phys_col),  # always left expr
    to_ref=FieldRef(table_id=right_table.id, column_id=right_phys_col),  # always right expr
    cardinality="many_to_one",   # hardcoded — no semantic basis
    cross_filter="single",       # hardcoded — produces oneDirection
    ...
))
```

`left_col = "region"` resolves to `people.region`, so `from_ref = people`. With `many_to_one`, `from` is declared the many-side. This is backwards for this workbook: `people` has 4 rows (one per region) and is the one-side; `orders` has 9,994 rows and is the many-side. And even if cardinality were correct, `cross_filter="single"` with the wrong from/to causes filters to flow in the wrong direction.

### Emitted TMDL — `relationships.tmdl`

```
relationship rel__people_orders
    fromColumn: people.region       ← people declared "many" side  (WRONG)
    toColumn: orders.region         ← orders declared "one" side   (WRONG)
    fromCardinality: many
    toCardinality: one
    crossFilteringBehavior: oneDirection
```

Applying the official PBI rule: `oneDirection` flows `TO → FROM` = `orders → people`. But the visual needs filters to flow from `people.region` (Category axis) into `orders` (where the measures live). The filter never arrives. Grand total is returned for every bar.

### Additional insight: why single-sheet pages hid this bug

Source: MVP research (`C:\vibe_coding\tabToPbi\docs\relationship_dashboard.md`)

On regular worksheet pages, static visual-level filters are emitted as a `filterConfig` block in `visual.json` — a hardcoded WHERE clause applied directly to the queried table:

```json
"filterConfig": {
  "filters": [{
    "field": { "Column": { "Entity": "orders", "Property": "region" } },
    "filter": { "Where": [{ "Condition": { "In": { "Values": [...] } } }] }
  }]
}
```

This WHERE clause is applied to `orders` directly. **No relationship traversal occurs.** The broken relationship direction is completely bypassed for static filters, which is why the existing regression snapshots do not surface the bug.

The bug becomes visible when:
1. A visual groups by a dimension from one table (`people.region`) and measures from another (`orders.profit`) — PBI must propagate filter context through the relationship at query time.
2. A dashboard slicer on `people.region` tries to cross-filter a visual that queries `orders` — live cross-filtering requires correct relationship direction.

---

## Why the Bug Was Not Caught

1. **Snapshot regression tests verify structure, not data correctness.** The golden snapshots in `tests/golden/real/` compare TMDL text byte-for-byte. The relationship block is syntactically valid — so snapshots pass. No test asserts `West = 110,798`, not `292,295`.

2. **No cross-filter path validation.** No test checks: "given a visual with `Category=people.region` and `Y=orders.measure`, does a valid filter-propagation path exist from `people` to `orders`?"

3. **The logical-layer path was added without implementing endpoint mapping.** When support for `<object-graph>` was added to the extractor, only the join key names were forwarded, leaving direction and cardinality as hardcoded defaults with no semantic basis.

---

## The Core Architectural Problem

Any mapping of Tableau's logical relationships to PBI's directed relationship model requires information that **does not exist in the TWB XML** — unless the workbook author explicitly set `unique-key`. The pipeline must make a conscious architectural choice. The strategies below are ordered from least to most complete.

---

## Strategy Comparison

### Strategy A — `bothDirections` for all logical-layer joins (partial fix)

Change `cross_filter="single"` → `cross_filter="both"` for all `TABLEAU_JOIN`-sourced relationships.

**Basis:** Tableau's logical layer is documented as context-sensitive and bidirectional. `bothDirections` in PBI is the structural equivalent. This is schema-grounded, not a workbook-specific guess.

| Property | Assessment |
|---|---|
| Schema-grounded | **Yes** — matches Tableau's bidirectional relationship semantics |
| Works for star schema and chains | Yes |
| Works for diamond topology (two paths between same pair of tables) | **No** — PBI raises "ambiguous filter path" error |
| Handles `unique-key`-carrying workbooks correctly | **No** — ignores the one signal Tableau provides for 1:M |
| Requires data access | No |
| Implementation scope | One-line change |

Strategy A is correct for this workbook (M:M default → `bothDirections`). It is NOT the complete solution — it ignores the `unique-key` signal that Tableau explicitly provides for 1:M workbooks.

---

### Strategy B — Use `first-end-point` as one-side

**Rejected.** Not documented in the Tableau schema. Reflects drag-order only. Will silently produce wrong TMDL when a workbook anchors on the fact table.

---

### Strategy C — Flatten to a single M table

Emit one merged Power Query table replicating Tableau's flat join in M. No relationship model, no cardinality decision needed. Correct for all topologies but loses star-schema benefits and risks row multiplication for M:M joins.

---

### Strategy D — Data profiling (requires live DB connection)

Run `COUNT(DISTINCT join_key)` vs `COUNT(*)` at conversion time. Mathematically correct but requires DB access, adds latency, and may not reflect production cardinality if run against dev/staging data.

---

### Strategy E — `unique-key`-driven cardinality with M:M fallback (RECOMMENDED)

**Source:** MVP project at `C:\vibe_coding\tabToPbi`, researched and implemented 2026-05-09. Validated against official Tableau XSD and official PBI TMSL documentation. All cases TDD-tested.

This is the only strategy that is:
- Fully grounded in the official Tableau XSD (uses the one signal Tableau provides)
- Fully grounded in official PBI TMSL documentation (correct `fromColumn`/`toColumn` convention)
- Deterministic for all four possible states of `unique-key`
- Falls back to the correct M:M default when no signal is present (which is also grounded in Tableau's documented default)

#### The four exhaustive cases (from Tableau XSD `EndPointAttributes-G`)

| `first-end-point unique-key` | `second-end-point unique-key` | Cardinality | TMDL `fromColumn` | TMDL `toColumn` | `crossFilteringBehavior` |
|---|---|---|---|---|---|
| absent | `"true"` | 1:M | first endpoint (MANY) | second endpoint (ONE) | `oneDirection` |
| `"true"` | absent | 1:M — swap needed | second endpoint (MANY) | first endpoint (ONE) | `oneDirection` |
| `"true"` | `"true"` | 1:1 | first endpoint | second endpoint | `bothDirections` (PBI mandates this for 1:1) |
| absent | absent | M:M (Tableau default) | first endpoint | second endpoint | `bothDirections` (matches Tableau M:M semantics) |

**Critical TMDL convention:** PBI TMDL requires `fromColumn` = MANY side and `toColumn` = ONE side. If inference produces `one:many` (ONE side in `from` position), the `from`/`to` pair must be physically swapped before writing. The generator must enforce this invariant.

#### Applying to our workbook

`simple_join_calculated_line.twb` has **no `unique-key`** on either endpoint (grep confirmed, zero matches). Falls into case 4 — M:M default:
- `fromCardinality: many`, `toCardinality: many`
- `crossFilteringBehavior: bothDirections`

This fixes the grand-total bug. It is also exactly what Strategy A would produce for this specific workbook — but Strategy E gets there via the correct algorithm rather than a blanket override.

#### The 1:1 case — additional note

Per [Microsoft's one-to-one relationship guidance](https://learn.microsoft.com/en-us/power-bi/guidance/relationships-one-to-one), 1:1 relationships are a model design smell. When both endpoints carry `unique-key="true"`, the migration report should flag: *"One-to-one relationship detected between {table_a} and {table_b}. Microsoft recommends merging these tables in Power Query instead."* Do not attempt an automatic merge — the tool lacks the context to determine which columns to keep.

---

## Physical Join Layer — Separate Inference Algorithm

The Tableau physical join path (`<relation type='join'>`) encodes `join_type` (INNER/LEFT/FULL OUTER/RIGHT) but still does not encode cardinality. The MVP project developed a three-signal inference for this path:

```xml
<relation join='inner' type='join'>
  <clause type='join'>
    <expression op='='>
      <expression op='[orders].[region]' />
      <expression op='[people].[region]' />
    </expression>
  </clause>
</relation>
```

**Signal 2 — Join type (structural, highest reliability for LEFT/INNER):**
- `LEFT JOIN`: the preserved/left table is always the ONE side. Definitive — no override.
- `INNER JOIN`: the accumulated left-expression table is treated as the ONE side (primary). Signal 1 can override.

**Signal 1 — Column naming convention (useful for FULL OUTER; confirmation for INNER):**
- Strip PK suffix (e.g. `_id`), singularize, exact-match column base name against table name.
- If `order_id` base `order` matches table `orders` → `orders.order_id` is the PK column → `orders` is the ONE side.
- Applied as: override Signal 2 for INNER when naming contradicts; primary for FULL OUTER.

**Fallback:** `to_table` (the right-child / newly-added table) = ONE side (dimension convention).

| Join type | Signal 2 | Signal 1 | Result |
|---|---|---|---|
| LEFT | `from_table` = ONE | — (Signal 2 definitive) | `from: one, to: many` |
| INNER | `from_table` = ONE | Overrides if `to_col` matches `to_table` name | Usually `from: one, to: many` |
| FULL OUTER | Unreliable | Primary | Whichever col matches table name = ONE; fallback to `to: one` |

The current project (`tableau2pbir`) handles physical joins via a separate code path in `extract/datasources.py`. Verify that path also uses `cross_filter="single"` and apply the same fix if so.

---

## Implementation Plan for This Project (Strategy E)

### Stage 1 — Extract (`extract/datasources.py`)

Extend `extract_object_graph_relationships()` to read and forward `unique-key` from each endpoint:

```python
first_ep  = rel.find("first-end-point")
second_ep = rel.find("second-end-point")
out.append({
    "left_col":            children[0].get("op", "").strip("[]"),
    "right_col":           children[1].get("op", "").strip("[]"),
    "first_unique_key":    first_ep  is not None and first_ep.get("unique-key")  == "true",
    "second_unique_key":   second_ep is not None and second_ep.get("unique-key") == "true",
})
```

The `left_col` / `right_col` names resolve to `first_endpoint_table` and `second_endpoint_table` respectively via the datasource `col_map` in Stage 2.

### Stage 2 — Canonicalize (`stages/_build_data_model.py`)

Replace the hardcoded `cardinality` and `cross_filter` in `build_relationships()` with logic covering all four cases. The input now includes `first_unique_key` and `second_unique_key`. After resolving to physical table/column, the `left_table`/`right_table` correspond to the `first-end-point`/`second-end-point` tables respectively:

```python
first_unique  = raw.get("first_unique_key", False)
second_unique = raw.get("second_unique_key", False)

if first_unique and second_unique:
    # 1:1 — both sides unique
    cardinality  = "one_to_one"
    cross_filter = "both"
elif first_unique:
    # first endpoint is ONE side → swap so from=MANY (right/orders), to=ONE (left/people)
    left_table, left_phys_col, right_table, right_phys_col = (
        right_table, right_phys_col, left_table, left_phys_col
    )
    cardinality  = "many_to_one"
    cross_filter = "single"
elif second_unique:
    # second endpoint is ONE side → current order is already from=MANY, to=ONE
    cardinality  = "many_to_one"
    cross_filter = "single"
else:
    # No unique-key — Tableau M:M default
    cardinality  = "many_to_many"
    cross_filter = "both"
```

### Stage 6 — Emit TMDL (`emit/tmdl/relationship.py`)

Add support for `many_to_many` cardinality in `_CARD_MAP`:

```python
_CARD_MAP = {
    "one_to_one":   ("one",  "one"),
    "one_to_many":  ("one",  "many"),
    "many_to_one":  ("many", "one"),
    "many_to_many": ("many", "many"),
}
```

The `render_relationship()` function already handles `cross_filter == "both"` → `bothDirections` correctly. No change needed there.

### IR model (`ir/model.py`)

Add `"many_to_many"` as a valid `cardinality` value and `"one_to_one"` if not already present.

### Migration report

Flag all relationships that fell into the M:M fallback case (no `unique-key` present):

> "Relationship `{from_table}.{from_col}` ↔ `{to_table}.{to_col}`: cardinality not set in Tableau source — defaulted to M:M bidirectional cross-filter. Verify intended cardinality in PBI Desktop Model View."

Flag all 1:1 relationships:

> "One-to-one relationship detected between `{table_a}` and `{table_b}`. Microsoft recommends merging these tables in Power Query instead."

### Tests to add

Following the MVP test pattern (`C:\vibe_coding\tabToPbi\tests\test_t12.py`, lines 368–526):

| Test | Assertion |
|---|---|
| `test_extract_logical_rel_no_unique_key` | Both flags are `False` when no `unique-key` present |
| `test_extract_logical_rel_second_unique_key` | `second_unique_key=True`, `first_unique_key=False` |
| `test_extract_logical_rel_first_unique_key` | `first_unique_key=True`, `second_unique_key=False` |
| `test_extract_logical_rel_both_unique_key` | Both flags `True` |
| `test_build_rel_second_unique_keeps_order` | `from_ref=first(MANY), to_ref=second(ONE)`, `cardinality=many_to_one`, `cross_filter=single` |
| `test_build_rel_first_unique_swaps` | `from_ref=second(MANY), to_ref=first(ONE)` after swap |
| `test_build_rel_no_unique_mm` | `cardinality=many_to_many`, `cross_filter=both` |
| `test_build_rel_both_unique_one_to_one` | `cardinality=one_to_one`, `cross_filter=both` |
| `test_render_mm_relationship_writes_both_directions` | TMDL output contains `crossFilteringBehavior: bothDirections` for M:M |
| `test_cross_filter_path_validation` | For a visual with cross-table Category+Measure binding, assert a `bothDirections` or correctly-directed `oneDirection` path exists |

---

## Decision Summary

| Workbook state | Correct TMDL output | Basis |
|---|---|---|
| No `unique-key` on either endpoint (our workbook, Tableau M:M default) | `many:many`, `bothDirections` | Tableau default cardinality documentation |
| `unique-key="true"` on `second-end-point` only | `many:one`, `fromCol=first`, `toCol=second`, `oneDirection` | Tableau XSD `unique-key` attribute |
| `unique-key="true"` on `first-end-point` only | `many:one` with swap, `fromCol=second`, `toCol=first`, `oneDirection` | Tableau XSD + PBI TMDL `from=MANY` convention |
| `unique-key="true"` on both endpoints | `one:one`, `bothDirections` | PBI mandates `bothDirections` for 1:1 |

Strategy A (`bothDirections` universal) is a valid quick fix for the immediate bug in this workbook. Strategy E is the correct general solution and should be implemented when the plan for this fix is scheduled — it handles all four cases deterministically using the one cardinality signal that Tableau's XSD actually provides, with a safe M:M fallback that matches Tableau's documented default.

---

## Sources

- [Relationships object (TMSL) — Microsoft Learn](https://learn.microsoft.com/en-us/analysis-services/tmsl/relationships-object-tmsl?view=sql-analysis-services-2025)
- [Model relationships in Power BI Desktop — Microsoft Learn](https://learn.microsoft.com/en-us/power-bi/transform-model/desktop-relationships-understand)
- [One-to-one relationship guidance — Microsoft Learn](https://learn.microsoft.com/en-us/power-bi/guidance/relationships-one-to-one)
- [Object definitions in TMDL — Microsoft Learn](https://learn.microsoft.com/en-us/analysis-services/tmdl/tmdl-reference-tabular-object?view=sql-analysis-services-2025)
- [Tableau Document Schemas — GitHub (official XSD)](https://github.com/tableau/tableau-document-schemas)
- [Cardinality and Referential Integrity — Tableau Help](https://help.tableau.com/current/pro/desktop/en-us/cardinality_and_ri.htm)
- [Optimize Relationship Queries (M:M default) — Tableau Help](https://help.tableau.com/current/server/en-us/datasource_relationships_perfoptions.htm)

---

## Files Referenced

| File | Role |
|---|---|
| `src/tableau2pbir/extract/datasources.py` lines 132–152 | Extracts join predicates; currently discards `unique-key` from endpoints |
| `src/tableau2pbir/stages/_build_data_model.py` lines 187–234 | `build_relationships()` — hardcodes direction and cardinality |
| `src/tableau2pbir/emit/tmdl/relationship.py` lines 16–26 | `render_relationship()` — faithfully emits IR; bug is upstream |
| `src/tableau2pbir/ir/model.py` | `Relationship` IR — needs `many_to_many` and `one_to_one` cardinality values |
| `out/simple_join_calculated_line/SemanticModel/definition/relationships.tmdl` | Generated broken output |
| `out/simple_join_calculated_line/Report/definition/pages/ReportSection1/visuals/visual_1/visual.json` | Cross-table visual binding requiring correct filter propagation |
| `tests/golden/real/simple_join_calculated_line.twb` lines 517–535 | Source TWB — `<object-graph>` with no `unique-key` attributes (M:M default) |
| `C:\vibe_coding\tabToPbi\docs\relationship_dashboard.md` | MVP research — root-cause analysis and full implementation of Strategy E |
| `C:\vibe_coding\tabToPbi\tab_to_pbi\parser.py` lines 425–477 | MVP implementation — `_parse_relationships()` reading `unique-key` |
| `C:\vibe_coding\tabToPbi\tab_to_pbi\transformer.py` lines 261–306 | MVP implementation — `_map_relationship()` four-case decision logic |
| `C:\vibe_coding\tabToPbi\tab_to_pbi\generator.py` lines 394–420 | MVP implementation — TMDL writer with from/to swap and `bothDirections` condition |
| `C:\vibe_coding\tabToPbi\tests\test_t12.py` lines 368–526 | MVP TDD tests — all four `unique-key` cases with assertions |
