# Plan 7 — TMDL Column Emission Fix

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix four root causes that prevent PBI Desktop from opening the generated PBIR output: (1) Column objects built in Stage 2 are discarded before Stage 6 can emit them; (2) RAW columns are missing the mandatory `sourceColumn` TMDL property; (3) Tableau datatypes are not mapped to TMDL types (`integer` → `int64`, etc.); (4) Tableau-internal tracking columns with `datatype="table"` pollute the TMDL output. Also bumps `compatibilityLevel` from 1567 to 1600 to match PBI Desktop's expected value.

**Architecture:** The fix flows through three layers — IR model (`Column.source_column` field), Stage 2 (preserve columns into `DataModel.columns`), and Stage 6 (pass per-table `Column` lists to `render_table`). `render_column` is extended with a datatype map, `sourceColumn` emission, and an internal-column guard. All changes are in `ir/`, `stages/`, and `emit/tmdl/`; Stage 7 and Stage 8 are untouched. Every task follows red → green → commit; E2E gate runs after Task 5.

**Tech Stack:** Python 3.11+, pydantic v2, pytest. No new dependencies.

**Spec reference:** `docs/superpowers/specs/2026-04-23-tableau-to-pbir-design.md` §5.1 (Column IR), §6 Stage 2 + Stage 6, §4.4 (PBIR layout). Working reference output: `C:\vibe_coding\tabToPbi\output\simple_join.SemanticModel\`.

---

## Root cause summary

| # | Symptom | Root cause | Files to change |
|---|---------|-----------|-----------------|
| 1 | PBI error: `FromColumn … cannot be found` | Stage 6 always calls `render_table(columns=[])` — Column objects built in Stage 2 are discarded (`_columns` variable) | `ir/workbook.py`, `stages/s02_canonicalize.py`, `emit/tmdl/render.py` |
| 2 | TMDL missing `sourceColumn` property | `render_column()` never emits `sourceColumn:` for RAW columns | `emit/tmdl/column.py` |
| 3 | TMDL shows `dataType: integer` not `int64` | Tableau-type strings passed through raw; no mapping applied | `emit/tmdl/column.py` |
| 4 | Tableau internal rows in TMDL | Columns with `datatype="table"` (Tableau join keys) not filtered | `emit/tmdl/column.py` |
| + | Compatibility level 1567 vs 1600 (MVP) | `render_database()` called with default 1567 | `emit/tmdl/render.py` |

---

## File map

**Modify (existing):**

```
src/tableau2pbir/ir/model.py                  — add source_column field to Column
src/tableau2pbir/ir/workbook.py               — add columns field to DataModel
src/tableau2pbir/stages/_build_data_model.py  — populate source_column; preserve _columns
src/tableau2pbir/stages/s02_canonicalize.py   — pass columns into DataModel constructor
src/tableau2pbir/emit/tmdl/column.py          — datatype map + sourceColumn + internal filter
src/tableau2pbir/emit/tmdl/render.py          — pass per-table Column lists; bump compat level

tests/unit/emit/tmdl/test_column.py           — new tests for render_column fixes
tests/unit/stages/test_s02_tables.py          — add source_column + DataModel.columns assertions
```

---

## Tasks

### Task 1: Add `source_column` field to Column IR and fix `render_column`

The two changes go together: `Column.source_column` must exist before `render_column` can read it, and the four `render_column` fixes all land in one commit.

**Files:**
- Modify: `src/tableau2pbir/ir/model.py`
- Modify: `src/tableau2pbir/emit/tmdl/column.py`
- Modify: `tests/unit/emit/tmdl/test_column.py`

- [x] **Step 1: Add the failing tests to `tests/unit/emit/tmdl/test_column.py`**

Append these six tests (leave the three existing tests untouched):

```python
# ── datatype mapping ───────────────────────────────────────────────────────
def test_datatype_integer_maps_to_int64():
    col = Column(id="c4", name="row_id", datatype="integer", role=ColumnRole.DIMENSION, kind=ColumnKind.RAW)
    assert "dataType: int64" in render_column(col)


def test_datatype_real_maps_to_double():
    col = Column(id="c5", name="sales", datatype="real", role=ColumnRole.MEASURE, kind=ColumnKind.RAW)
    assert "dataType: double" in render_column(col)


def test_datatype_datetime_maps_to_dateTime():
    col = Column(id="c6", name="order_date", datatype="datetime", role=ColumnRole.DIMENSION, kind=ColumnKind.RAW)
    assert "dataType: dateTime" in render_column(col)


# ── sourceColumn ────────────────────────────────────────────────────────────
def test_raw_column_emits_source_column():
    col = Column(id="c7", name="order_id", datatype="string", role=ColumnRole.DIMENSION,
                 kind=ColumnKind.RAW, source_column="order_id")
    out = render_column(col)
    assert "sourceColumn: order_id" in out


def test_raw_column_falls_back_to_name_when_source_column_none():
    col = Column(id="c8", name="region", datatype="string", role=ColumnRole.DIMENSION,
                 kind=ColumnKind.RAW, source_column=None)
    assert "sourceColumn: region" in render_column(col)


# ── internal column filter ──────────────────────────────────────────────────
def test_internal_table_datatype_column_returns_empty():
    col = Column(id="c9", name="__tableau_internal_object_id__", datatype="table",
                 role=ColumnRole.DIMENSION, kind=ColumnKind.RAW)
    assert render_column(col) == ""
```

- [x] **Step 2: Run tests to confirm they fail**

```
pytest tests/unit/emit/tmdl/test_column.py -v
```

Expected: all six new tests FAIL — `source_column` is not a valid Column field and the datatype/sourceColumn logic is missing.

- [x] **Step 3: Add `source_column` to `Column` in `src/tableau2pbir/ir/model.py`**

Add one line to the `Column` class (after `dax_expr`):

```python
class Column(IRBase):
    id: str
    name: str
    datatype: str
    role: ColumnRole
    kind: ColumnKind
    tableau_expr: str | None = None
    dax_expr: str | None = None
    source_column: str | None = None      # physical DB column name; used as TMDL sourceColumn
```

- [x] **Step 4: Rewrite `src/tableau2pbir/emit/tmdl/column.py`**

Replace the entire file content:

```python
"""Render a column or calculated-column block (nested under a table)."""
from __future__ import annotations

from textwrap import indent

from tableau2pbir.emit.tmdl.escape import tmdl_ident
from tableau2pbir.ir.model import Column, ColumnKind

_DATATYPE_MAP: dict[str, str] = {
    "integer":  "int64",
    "real":     "double",
    "datetime": "dateTime",
    "date":     "date",
    "boolean":  "boolean",
    "string":   "string",
}


def render_column(col: Column) -> str:
    if col.datatype == "table":
        return ""   # Tableau internal join-tracking column — not a real DB column
    if col.kind == ColumnKind.CALCULATED and col.dax_expr is None:
        return ""   # deferred / unsupported / not yet translated
    head = "column " + tmdl_ident(col.name)
    tmdl_type = _DATATYPE_MAP.get(col.datatype, col.datatype)
    body_lines = [f"dataType: {tmdl_type}"]
    if col.kind == ColumnKind.CALCULATED:
        body_lines.append(f"expression: {col.dax_expr}")
    else:
        src = col.source_column if col.source_column is not None else col.name
        body_lines.append(f"sourceColumn: {src}")
    body = indent("\n".join(body_lines), "\t")
    return f"\t{head}\n{body}\n"
```

- [x] **Step 5: Run all column tests**

```
pytest tests/unit/emit/tmdl/test_column.py -v
```

Expected: all 9 tests PASS (3 existing + 6 new).

- [x] **Step 6: Run full suite to check for regressions**

```
pytest -q
```

Expected: green.

- [x] **Step 7: Commit**

```
git add src/tableau2pbir/ir/model.py src/tableau2pbir/emit/tmdl/column.py tests/unit/emit/tmdl/test_column.py
git commit -m "fix(tmdl): add source_column to Column IR; datatype map, sourceColumn, internal-column filter in render_column"
```

---

### Task 2: Populate `source_column` in `build_tables` from `col_map`

For federated datasources the `col_map` tells us the physical column name, which may differ from the logical Tableau alias (e.g., Tableau's `order_id (returns)` maps to physical `order_id`). For plain datasources the physical name equals the column name.

**Files:**
- Modify: `src/tableau2pbir/stages/_build_data_model.py`
- Modify: `tests/unit/stages/test_s02_tables.py`

- [x] **Step 1: Add a failing test to `tests/unit/stages/test_s02_tables.py`**

Append after the last existing test:

```python
def test_source_column_populated_from_col_map():
    """Federated col_map physical name flows into Column.source_column."""
    raw = [{
        "name": "federated.abc",
        "connection": {"class": "federated"},
        "named_connections": [
            {"name": "pg", "caption": None,
             "connection": {"class": "postgres", "server": "srv", "dbname": "db"}},
        ],
        "extract": None,
        "relations": [
            {"name": "orders",  "table": "[public].[orders]",  "connection": "pg"},
            {"name": "returns", "table": "[public].[returns]", "connection": "pg"},
        ],
        "col_map": {
            "order_id":           ("orders",  "order_id"),
            "order_id (returns)": ("returns", "order_id"),   # Tableau alias → physical "order_id"
        },
        "columns": [
            {"name": "order_id",           "datatype": "string", "role": "dimension", "type": "nominal"},
            {"name": "order_id (returns)", "datatype": "string", "role": "dimension", "type": "nominal"},
        ],
        "calculations": [],
    }]
    _, columns = build_tables(raw)
    orders_col  = next(c for c in columns if c.name == "order_id")
    returns_col = next(c for c in columns if c.name == "order_id (returns)")
    assert orders_col.source_column == "order_id"
    assert returns_col.source_column == "order_id"   # physical name, not the alias


def test_plain_datasource_source_column_equals_name():
    """Plain datasource: source_column = column name (no col_map)."""
    raw = [{
        "name": "sales", "caption": None,
        "connection": {"class": "sqlserver"}, "named_connections": [], "extract": None,
        "columns": [
            {"name": "profit", "datatype": "real", "role": "measure", "type": "quantitative"},
        ],
        "calculations": [],
    }]
    _, columns = build_tables(raw)
    assert columns[0].source_column == "profit"
```

- [x] **Step 2: Run to confirm failure**

```
pytest tests/unit/stages/test_s02_tables.py::test_source_column_populated_from_col_map tests/unit/stages/test_s02_tables.py::test_plain_datasource_source_column_equals_name -v
```

Expected: FAIL — `source_column` is always `None`.

- [x] **Step 3: Update `_build_column` in `src/tableau2pbir/stages/_build_data_model.py`**

Change the function signature and the RAW branch to accept and store `source_column`:

```python
def _build_column(col: dict[str, Any], col_id: str,
                  calc_by_host: dict[str, Any],
                  source_column: str | None = None) -> Column:
    calc = calc_by_host.get(col["name"])
    if calc is not None:
        return Column(
            id=col_id, name=col["name"],
            datatype=col["datatype"], role=_column_role(col["role"]),
            kind=ColumnKind.CALCULATED,
            tableau_expr=calc["tableau_expr"],
            dax_expr=None,
        )
    return Column(
        id=col_id, name=col["name"],
        datatype=col["datatype"], role=_column_role(col["role"]),
        kind=ColumnKind.RAW,
        source_column=source_column if source_column is not None else col["name"],
    )
```

- [x] **Step 4: Pass `source_column` in both paths inside `build_tables`**

In the **federated** path (inside the `if relations:` block), change the `_build_column` call:

```python
for col in raw.get("columns", []):
    col_prefix = stable_id("tbl", raw["name"])
    col_id = f"{col_prefix}__{stable_id('col', col['name'])}"
    owner_entry = col_map.get(col["name"], (primary_rel_name, col["name"]))
    owner_table = owner_entry[0]
    phys_col    = owner_entry[1]
    if owner_table not in cols_by_table:
        owner_table = primary_rel_name
    cols_by_table[owner_table].append(col_id)
    columns.append(_build_column(col, col_id, calc_by_host, source_column=phys_col))
```

In the **plain** path (inside the `else:` block), change the `_build_column` call:

```python
for col in raw.get("columns", []):
    col_id = f"{table_id}__{stable_id('col', col['name'])}"
    col_ids.append(col_id)
    columns.append(_build_column(col, col_id, calc_by_host, source_column=col["name"]))
```

- [x] **Step 5: Run the new tests**

```
pytest tests/unit/stages/test_s02_tables.py -v
```

Expected: all tests PASS (including the 2 new ones).

- [x] **Step 6: Run full suite**

```
pytest -q
```

Expected: green.

- [x] **Step 7: Commit**

```
git add src/tableau2pbir/stages/_build_data_model.py tests/unit/stages/test_s02_tables.py
git commit -m "fix(stage2): populate source_column from col_map in build_tables"
```

---

### Task 3: Add `columns` to `DataModel` IR and preserve through Stage 2

Currently `DataModel` has no `columns` field, so Column objects can't be serialised into the IR JSON and never reach Stage 6.

**Files:**
- Modify: `src/tableau2pbir/ir/workbook.py`
- Modify: `src/tableau2pbir/stages/s02_canonicalize.py`
- Modify: `tests/unit/stages/test_s02_datasources.py`

- [x] **Step 1: Add a failing test to `tests/unit/stages/test_s02_datasources.py`**

Append after the last existing test in that file:

```python
def test_stage2_datamodel_preserves_columns():
    """DataModel.columns must be non-empty after Stage 2 runs on a datasource with columns."""
    from lxml import etree
    from tableau2pbir.extract.datasources import extract_datasources
    from tableau2pbir.stages._build_data_model import build_tables
    from tableau2pbir.ir.workbook import DataModel
    from tableau2pbir.ir.datasource import ConnectorTier

    raw_ds = [{
        "name": "orders",
        "connection": {"class": "sqlserver", "server": "srv", "dbname": "db"},
        "named_connections": [], "extract": None, "relations": [], "col_map": {},
        "columns": [
            {"name": "order_id", "datatype": "string", "role": "dimension", "type": "nominal"},
            {"name": "sales",    "datatype": "real",   "role": "measure",   "type": "quantitative"},
        ],
        "calculations": [],
    }]
    tables, columns = build_tables(raw_ds)
    # DataModel must accept and store the columns tuple
    dm = DataModel(tables=tables, columns=columns)
    assert len(dm.columns) == 2
    assert any(c.name == "order_id" for c in dm.columns)
```

- [x] **Step 2: Run to confirm failure**

```
pytest tests/unit/stages/test_s02_datasources.py::test_stage2_datamodel_preserves_columns -v
```

Expected: FAIL — `DataModel` does not accept a `columns` keyword argument.

- [x] **Step 3: Add `columns` field to `DataModel` in `src/tableau2pbir/ir/workbook.py`**

Add the `Column` import and the new field:

```python
from tableau2pbir.ir.model import Column, Relationship, Table   # add Column


class DataModel(IRBase):
    datasources: tuple[Datasource, ...] = ()
    tables: tuple[Table, ...] = ()
    columns: tuple[Column, ...] = ()              # NEW — all Column objects across all tables
    relationships: tuple[Relationship, ...] = ()
    calculations: tuple[Calculation, ...] = ()
    parameters: tuple[Parameter, ...] = ()
    hierarchies: tuple[Hierarchy, ...] = ()
    sets: tuple[Set, ...] = ()
```

- [x] **Step 4: Preserve columns in `src/tableau2pbir/stages/s02_canonicalize.py`**

Change line 97 and the `DataModel(...)` constructor call:

```python
# Line 97 — keep both return values (was: tables, _columns = ...)
tables, columns = build_tables(input_json.get("datasources", []))
```

In the `DataModel(...)` constructor (around line 151), add `columns=columns`:

```python
data_model = DataModel(
    datasources=datasources, tables=tables,
    columns=columns,
    relationships=relationships,
    calculations=calculations, parameters=parameters,
)
```

- [x] **Step 5: Run the new test**

```
pytest tests/unit/stages/test_s02_datasources.py::test_stage2_datamodel_preserves_columns -v
```

Expected: PASS.

- [x] **Step 6: Run full suite**

```
pytest -q
```

Expected: green.

- [x] **Step 7: Commit**

```
git add src/tableau2pbir/ir/workbook.py src/tableau2pbir/stages/s02_canonicalize.py tests/unit/stages/test_s02_datasources.py
git commit -m "fix(ir): add DataModel.columns field; Stage 2 preserves Column objects through pipeline"
```

---

### Task 4: Stage 6 passes actual columns to `render_table`

Stage 6 currently hardcodes `columns=[]`. This task makes it look up the Column objects from `wb.data_model.columns` and pass the correct subset to each table's `render_table` call.

**Files:**
- Modify: `src/tableau2pbir/emit/tmdl/render.py`
- Modify: `tests/unit/emit/tmdl/test_table.py`

- [x] **Step 1: Read the existing test file to understand current test structure**

Read `tests/unit/emit/tmdl/test_table.py` — note the existing tests so you don't break them.

- [x] **Step 2: Add a failing integration test to `tests/unit/emit/tmdl/test_table.py`**

Append this test (it calls `render_table` directly with actual columns):

```python
def test_render_table_emits_column_blocks():
    from tableau2pbir.ir.model import Column, ColumnKind, ColumnRole
    from tableau2pbir.ir.datasource import Datasource, ConnectorTier

    ds = Datasource(
        id="ds1", name="orders",
        tableau_kind="postgres",
        connector_tier=ConnectorTier.TIER_1,
        pbi_m_connector="PostgreSQL.Database",
        connection_params={"server": "srv", "dbname": "db"},
        user_action_required=(),
        table_ids=(),
        extract_ignored=False,
    )
    cols = [
        Column(id="c1", name="order_id", datatype="string",  role=ColumnRole.DIMENSION,
               kind=ColumnKind.RAW, source_column="order_id"),
        Column(id="c2", name="sales",    datatype="real",    role=ColumnRole.MEASURE,
               kind=ColumnKind.RAW, source_column="sales"),
    ]
    out = render_table(name="orders", columns=cols, measures=[], datasource=ds)
    assert "column order_id" in out
    assert "dataType: string" in out
    assert "sourceColumn: order_id" in out
    assert "column sales" in out
    assert "dataType: double" in out
    assert "sourceColumn: sales" in out
```

- [x] **Step 3: Run to confirm it passes already** (render_table already accepts columns, just was called with `[]`)

```
pytest tests/unit/emit/tmdl/test_table.py::test_render_table_emits_column_blocks -v
```

Expected: PASS — `render_table` already wires columns through to `render_column`; the issue is only in how `render.py` calls it. If it fails for another reason, diagnose before continuing.

- [x] **Step 4: Update `src/tableau2pbir/emit/tmdl/render.py` to wire columns per table**

Add the `Column` and `ColumnKind` import at the top of the file:

```python
from tableau2pbir.ir.model import Column, ColumnKind
```

Replace the two lines immediately before the `for t in wb.data_model.tables:` loop (the lines that set `primary_table_id` and build `measures_for_table`) with this expanded block:

```python
primary_table_id = wb.data_model.tables[0].id if wb.data_model.tables else None
measures_for_table: dict[str, list] = {t.id: [] for t in wb.data_model.tables}
for calc in wb.data_model.calculations:
    if calc.scope == CalculationScope.MEASURE and calc.dax_expr and primary_table_id:
        measures_for_table[primary_table_id].append(calc)

# Build per-table column lookup from the DataModel columns tuple.
col_by_id: dict[str, Column] = {c.id: c for c in wb.data_model.columns}
cols_for_table: dict[str, list[Column]] = {}
for t in wb.data_model.tables:
    cols_for_table[t.id] = [col_by_id[cid] for cid in t.column_ids if cid in col_by_id]
```

In the `for t in wb.data_model.tables:` loop, change the `render_table` call from `columns=[]` to:

```python
body = render_table(
    name=t.name,
    columns=cols_for_table.get(t.id, []),
    measures=measures_for_table.get(t.id, []),
    datasource=ds,
    physical_schema=t.physical_schema,
    physical_table=t.physical_table,
)
```

Also update the `render_database` call to pass `compatibility_level=1600`:

```python
write_text(sm / "database.tmdl", render_database(name=db_name, compatibility_level=1600))
```

- [x] **Step 5: Run full unit suite**

```
pytest -q
```

Expected: green.

- [x] **Step 6: Quick smoke-check — regenerate simple_join and inspect orders.tmdl**

```
python -m tableau2pbir.cli convert tests/golden/real/simple_join.twb --out out/simple_join
```

Then verify:

```
python -c "
content = open('out/simple_join/SemanticModel/definition/tables/orders.tmdl', encoding='utf-8').read()
assert 'column order_id' in content, 'missing column order_id'
assert 'sourceColumn: order_id' in content, 'missing sourceColumn'
assert 'dataType: string' in content, 'missing dataType string'
assert 'dataType: int64' in content, 'missing int64 (row_id)'
assert 'dataType: double' in content, 'missing double (profit)'
assert 'dateTime' in content, 'missing dateTime (order_date)'
assert '__tableau_internal' not in content, 'internal column leaked'
print('ALL CHECKS PASSED')
"
```

Expected: `ALL CHECKS PASSED`.

- [x] **Step 7: Commit**

```
git add src/tableau2pbir/emit/tmdl/render.py tests/unit/emit/tmdl/test_table.py
git commit -m "fix(stage6): emit column blocks in TMDL; bump compatibilityLevel to 1600"
```

---

### Task 5: E2E gate — real workbooks produce valid column blocks

Run the full integration suite against all real workbooks to confirm the column emission doesn't break any existing workbook and that `simple_join` now produces TMDL column blocks that match what PBI Desktop requires.

**Files:**
- Modify: `tests/integration/test_real_workbooks_e2e.py`

- [x] **Step 1: Run the existing E2E suite and confirm it passes**

```
pytest tests/integration/test_real_workbooks_e2e.py -v
```

Expected: all 18 tests PASS (9 workbooks × 2 test types). If any fail, diagnose before continuing.

- [x] **Step 2: Add a column-block assertion to the E2E test for simple_join**

Read `tests/integration/test_real_workbooks_e2e.py` and locate the test that processes `simple_join`. Add these assertions after the existing file-existence checks for `simple_join`:

```python
# simple_join must have column blocks (fixes the PBI Desktop relationship resolution error)
orders_tmdl = out_dir / "SemanticModel" / "definition" / "tables" / "orders.tmdl"
assert orders_tmdl.is_file(), "orders.tmdl missing"
orders_text = orders_tmdl.read_text(encoding="utf-8")
assert "column order_id" in orders_text, "orders.tmdl missing column order_id"
assert "sourceColumn: order_id" in orders_text, "orders.tmdl missing sourceColumn"
assert "dataType: int64" in orders_text, "orders.tmdl missing int64 column (row_id)"
assert "dataType: double" in orders_text, "orders.tmdl missing double column (profit/sales)"
assert "dataType: dateTime" in orders_text, "orders.tmdl missing dateTime column (order_date)"
assert "__tableau_internal" not in orders_text, "Tableau internal column leaked into TMDL"
```

- [x] **Step 3: Run the extended E2E suite**

```
pytest tests/integration/test_real_workbooks_e2e.py -v
```

Expected: all tests PASS including the new column-block assertions.

- [x] **Step 4: Manually verify the generated `orders.tmdl` against the working MVP**

Compare the first 30 lines of the generated file with the MVP reference:

```
python -c "
with open('out/simple_join/SemanticModel/definition/tables/orders.tmdl', encoding='utf-8') as f:
    for i, line in enumerate(f):
        if i >= 40: break
        print(repr(line), end='')
"
```

Confirm each column block has the format:
```
\tcolumn <name>\n\t\tdataType: <tmdl_type>\n\t\tsourceColumn: <phys_name>\n
```

- [x] **Step 5: Commit**

```
git add tests/integration/test_real_workbooks_e2e.py
git commit -m "test(e2e): assert TMDL column blocks present for simple_join after column emission fix"
```

---

## Self-Review Checklist

Run this after writing the plan but before implementation:

- [ ] **Issue #1 covered?** Task 3 adds `DataModel.columns`, Task 4 passes them to `render_table`. ✅
- [ ] **Issue #2 covered?** Task 1 adds `sourceColumn` emission to `render_column`. ✅
- [ ] **Issue #3 covered?** Task 1 adds `_DATATYPE_MAP`. ✅
- [ ] **Issue #4 covered?** Task 1 guards `datatype == "table"` → return `""`. ✅
- [ ] **Compatibility level?** Task 4 updates the `render_database` call to `1600`. ✅
- [ ] **`source_column` field wired?** Task 1 adds it to IR; Task 2 populates from `col_map`; Task 4 reads it in render. ✅
- [ ] **Existing tests still green?** `test_raw_column` still passes (string→string, no `expression`). `test_database_tmdl_basic` still passes (still accepts explicit `1567`). ✅
- [ ] **No placeholders?** Every step has exact code and commands. ✅
- [ ] **Type consistency?** `Column.source_column` named identically across `ir/model.py`, `_build_data_model.py`, `column.py`. ✅
- [ ] **`col_by_id` lookup in Task 4 uses `c.id` as key** — matches `t.column_ids` which stores Column IDs. ✅
