# Plan 18 — Date-Part Derivation: DAX Calculated Columns

> **For agentic workers:** REQUIRED SUB-SKILL: Use **superpowers:subagent-driven-development** to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Fix the line-chart date granularity mismatch by synthesizing a DAX calculated column (`YEAR(table[col])`, etc.) in the PBI semantic model for every Tableau date-part pill (`yr:`, `qr:`, `mn:`, etc.) referenced in any visual encoding.

**Architecture:** Four files change in order — (1) Stage 1 extract captures `<column-instance derivation='Year'>` XML into the worksheet dict; (2) a new `build_date_part_columns()` in Stage 2 reads those instances and synthesizes `Column(kind=CALCULATED, dax_expr="YEAR(...)")` IR objects appended to the owning table; (3) `field_lookup.py` is taught to resolve date-part pill slugs (`yr_order_date_ok`) to the synthesized column name ("Year order_date") rather than the raw date column; (4) Stage 6 TMDL emission requires no changes — it already emits `ColumnKind.CALCULATED` columns, and Stage 7 visual emission requires no changes — it uses field_lookup automatically.

**Tech Stack:** Python 3.11, pydantic v2, lxml, pytest. No new dependencies.

---

## File Map

| Action | Path | What changes |
|--------|------|--------------|
| Modify | `src/tableau2pbir/extract/worksheets.py` | Add `_DATE_DERIVATIONS` constant, `_column_instances()` function, `"column_instances"` key in output dict |
| Modify | `src/tableau2pbir/stages/_build_data_model.py` | Add `_DERIVATION_TO_DAX` constant, `build_date_part_columns()` function |
| Modify | `src/tableau2pbir/stages/s02_canonicalize.py` | Import and call `build_date_part_columns()`, merge results into DataModel |
| Modify | `src/tableau2pbir/visualmap/field_lookup.py` | Add `_DATE_PART_PREFIX`, add `datatype` to `by_base` entries, route date-part pills to synthesized columns |
| Create | `tests/unit/test_extract_column_instances.py` | Unit tests for `_column_instances()` |
| Create | `tests/unit/test_build_date_part_columns.py` | Unit tests for `build_date_part_columns()` |
| Create | `tests/unit/test_field_lookup_date_parts.py` | Unit tests for date-part pill resolution in `build_field_lookup()` |
| Modify | `tests/golden/test_real_stage2.py` | Add synthesized-column assertions to `test_simple_join_calculated_line_counts()` and `test_snowflake_counts()` |
| Create | `tests/integration/test_date_part_derivation.py` | End-to-end: Stage 2 IR column, TMDL calculated column, visual JSON binding |

---

## Background: the pill slug encoding (read this before coding)

Tableau's `<cols>` shelf text contains pill references like `[federated.xxx].[yr:order_date:ok]`.
`_parse_shelf()` strips the datasource marker and returns `"yr:order_date:ok"`.
`stable_id("", "yr:order_date:ok").lstrip("_")` → `"yr_order_date_ok"` — this becomes the `FieldRef.column_id` stored in the IR encoding.

`_PILL_RE` in `field_lookup.py` matches `yr_order_date_ok` as: prefix=`yr`, body=`order_date`, suffix=`ok`.

The body (`order_date`) indexes into `by_base` which maps `slug_id(col.name)` → column info. After this plan, Stage 2 synthesizes a Column named `"Year order_date"`, which gets `slug_id("Year order_date") = "year_order_date"` as its `by_base` key. The field lookup then routes `yr_order_date_ok` to that synthesized column.

---

## Task 1 — Stage 1: extract date-part column instances

**Files:**
- Modify: `src/tableau2pbir/extract/worksheets.py`
- Create: `tests/unit/test_extract_column_instances.py`

### Background

In the TWB, date-part pills appear as `<column-instance>` inside `<view>/<datasource-dependencies>`:
```xml
<datasource-dependencies datasource='federated.1qn8ahk0...'>
  <column-instance column='[order_date]' derivation='Year'
                   name='[yr:order_date:ok]' pivot='key' type='ordinal' />
</datasource-dependencies>
```

`column` is the base field; `derivation` is the date part (Year/Quarter/Month/Week/Day/Hour/Minute/Second); `name` is the pill slug. We collect only date-part derivations — `Sum`, `None`, `Count`, etc. are handled by existing logic and must be excluded.

- [x] **Step 1.1: Write the failing unit test**

Create `tests/unit/test_extract_column_instances.py`:

```python
"""Unit tests for _column_instances() in extract/worksheets.py."""
from __future__ import annotations

import pathlib

import pytest
from lxml import etree

from tableau2pbir.extract.worksheets import _column_instances, extract_worksheets


def _view(xml_body: str) -> etree._Element:
    return etree.fromstring(f"<view>{xml_body}</view>")


# ── _column_instances ──────────────────────────────────────────────────────────

def test_extracts_year_derivation():
    view = _view("""
      <datasource-dependencies datasource="federated.abc">
        <column-instance column="[order_date]" derivation="Year"
                         name="[yr:order_date:ok]" pivot="key" type="ordinal" />
      </datasource-dependencies>
    """)
    result = _column_instances(view)
    assert len(result) == 1
    assert result[0]["slug"] == "yr:order_date:ok"
    assert result[0]["base_column"] == "order_date"
    assert result[0]["derivation"] == "Year"


def test_skips_sum_derivation():
    view = _view("""
      <datasource-dependencies datasource="federated.abc">
        <column-instance column="[sales]" derivation="Sum" name="[sum:sales:qk]" />
      </datasource-dependencies>
    """)
    assert _column_instances(view) == []


def test_skips_none_derivation():
    view = _view("""
      <datasource-dependencies datasource="federated.abc">
        <column-instance column="[region]" derivation="None" name="[none:region:nk]" />
      </datasource-dependencies>
    """)
    assert _column_instances(view) == []


def test_extracts_all_eight_date_derivations():
    view = _view("""
      <datasource-dependencies datasource="federated.abc">
        <column-instance column="[dt]" derivation="Quarter" name="[qr:dt:ok]" />
        <column-instance column="[dt]" derivation="Month"   name="[mn:dt:ok]" />
        <column-instance column="[dt]" derivation="Week"    name="[wk:dt:ok]" />
        <column-instance column="[dt]" derivation="Day"     name="[dy:dt:ok]" />
        <column-instance column="[dt]" derivation="Hour"    name="[hr:dt:ok]" />
        <column-instance column="[dt]" derivation="Minute"  name="[mi:dt:ok]" />
        <column-instance column="[dt]" derivation="Second"  name="[sc:dt:ok]" />
      </datasource-dependencies>
    """)
    result = _column_instances(view)
    assert len(result) == 7
    assert {r["derivation"] for r in result} == {
        "Quarter", "Month", "Week", "Day", "Hour", "Minute", "Second"
    }


def test_ignores_count_and_attribute_derivations():
    view = _view("""
      <datasource-dependencies datasource="federated.abc">
        <column-instance column="[x]" derivation="Count"     name="[cnt:x:qk]" />
        <column-instance column="[x]" derivation="CountD"    name="[ctd:x:qk]" />
        <column-instance column="[x]" derivation="Attribute" name="[attr:x:nk]" />
      </datasource-dependencies>
    """)
    assert _column_instances(view) == []


# ── extract_worksheets integration ────────────────────────────────────────────

def test_extract_worksheets_includes_column_instances_key():
    """Smoke test: every worksheet dict has a column_instances key."""
    _REAL = pathlib.Path(__file__).resolve().parents[2] / "golden" / "real"
    twb = _REAL / "simple_join_calculated_line.twb"
    if not twb.exists():
        pytest.skip("simple_join_calculated_line.twb not present")
    from lxml import etree as ET
    root = ET.parse(str(twb)).getroot()
    worksheets = extract_worksheets(root)
    for ws in worksheets:
        assert "column_instances" in ws, f"column_instances missing for {ws['name']}"


def test_extract_worksheets_sheet2_has_year_order_date():
    _REAL = pathlib.Path(__file__).resolve().parents[2] / "golden" / "real"
    twb = _REAL / "simple_join_calculated_line.twb"
    if not twb.exists():
        pytest.skip("simple_join_calculated_line.twb not present")
    from lxml import etree as ET
    root = ET.parse(str(twb)).getroot()
    worksheets = extract_worksheets(root)
    sheet2 = next(ws for ws in worksheets if ws["name"] == "Sheet 2")
    ci_list = sheet2["column_instances"]
    assert len(ci_list) == 1
    assert ci_list[0]["slug"] == "yr:order_date:ok"
    assert ci_list[0]["base_column"] == "order_date"
    assert ci_list[0]["derivation"] == "Year"
```

- [x] **Step 1.2: Run tests to confirm they fail**

```
pytest tests/unit/test_extract_column_instances.py -v
```

Expected: `ImportError` or `AttributeError: module has no attribute '_column_instances'` — confirms the function does not exist yet.

- [x] **Step 1.3: Implement `_column_instances()` in `extract/worksheets.py`**

Add these two blocks to `src/tableau2pbir/extract/worksheets.py`.

**After the `_KNOWN_AGGS` constant (around line 175), add:**

```python
_DATE_DERIVATIONS: frozenset[str] = frozenset({
    "Year", "Quarter", "Month", "Week", "Day", "Hour", "Minute", "Second",
})


def _column_instances(view: etree._Element) -> list[dict[str, Any]]:
    """Collect date-part <column-instance> elements from <datasource-dependencies>.

    Only derivations in _DATE_DERIVATIONS are returned. Aggregation derivations
    (Sum, Count, CountD, etc.) and None are handled elsewhere in the pipeline.
    """
    out: list[dict[str, Any]] = []
    for dep in view.findall("datasource-dependencies"):
        for ci in dep.findall("column-instance"):
            derivation = optional_attr(ci, "derivation") or "None"
            if derivation not in _DATE_DERIVATIONS:
                continue
            slug = _parse_filter_column(optional_attr(ci, "name") or "")
            base_col = _parse_filter_column(optional_attr(ci, "column") or "")
            if not slug or not base_col:
                continue
            out.append({
                "slug": slug,             # "yr:order_date:ok"
                "base_column": base_col,  # "order_date"
                "derivation": derivation, # "Year"
            })
    return out
```

**In `extract_worksheets()` (around line 454), add `"column_instances"` as the last key in the appended dict:**

```python
        out.append({
            "name": attr(ws, "name"),
            "datasource_refs": _datasource_refs(view),
            "mark_type": mark_type,
            "encodings": _encodings(shelf_elem, pane_parent),
            "filters": _filters(view, shared_view_filters),
            "sort": _sort(view),
            "dual_axis": _dual_axis(search_root),
            "reference_lines": _reference_lines(search_root),
            "quick_table_calcs": _quick_table_calcs(search_root),
            "sheet_style": _sheet_style(ws, table, pane_parent),
            "column_instances": _column_instances(view),
        })
```

- [x] **Step 1.4: Run tests to confirm they pass**

```
pytest tests/unit/test_extract_column_instances.py -v
```

Expected: all 7 tests PASS.

- [x] **Step 1.5: Run the full unit suite to check for regressions**

```
pytest tests/unit/ -v --tb=short
```

Expected: all existing unit tests PASS.

- [x] **Step 1.6: Commit**

```
git add src/tableau2pbir/extract/worksheets.py tests/unit/test_extract_column_instances.py
git commit -m "feat(stage1): extract date-part column-instance derivations from TWB XML"
```

---

## Task 2 — Stage 2: synthesize DAX calculated columns

**Files:**
- Modify: `src/tableau2pbir/stages/_build_data_model.py`
- Create: `tests/unit/test_build_date_part_columns.py`

### Background

`build_date_part_columns()` iterates all `column_instances` from all raw worksheets. For each unique `(base_column, derivation)` pair it:
1. Locates the owning physical table via `col_map` (federated) or by scanning table column names (plain single-table).
2. Verifies the base column has `datatype` in `("date", "datetime")`.
3. Creates a `Column(kind=CALCULATED, dax_expr="YEAR(orders[order_date])")`.
4. Returns the new columns plus updated `Table` tuples with the new column ID appended to `column_ids`.

The column ID prefix is derived from the table's existing column IDs so it stays consistent with `build_tables()`.

Derivation → DAX function mapping:
| Derivation | DAX |
|---|---|
| Year | YEAR |
| Quarter | QUARTER |
| Month | MONTH |
| Week | WEEKNUM |
| Day | DAY |
| Hour | HOUR |
| Minute | MINUTE |
| Second | SECOND |

- [x] **Step 2.1: Write the failing unit test**

Create `tests/unit/test_build_date_part_columns.py`:

```python
"""Unit tests for build_date_part_columns() in _build_data_model.py."""
from __future__ import annotations

import pytest

from tableau2pbir.stages._build_data_model import build_date_part_columns
from tableau2pbir.ir.model import Column, ColumnKind, ColumnRole, Table


# ── Test fixtures ─────────────────────────────────────────────────────────────

def _date_col(name: str = "order_date", table_prefix: str = "tbl__ds1") -> Column:
    return Column(
        id=f"{table_prefix}__col__{name}",
        name=name,
        datatype="date",
        role=ColumnRole.DIMENSION,
        kind=ColumnKind.RAW,
        source_column=name,
    )


def _real_col(name: str = "sales", table_prefix: str = "tbl__ds1") -> Column:
    return Column(
        id=f"{table_prefix}__col__{name}",
        name=name,
        datatype="real",
        role=ColumnRole.MEASURE,
        kind=ColumnKind.RAW,
        source_column=name,
    )


def _string_col(name: str = "category", table_prefix: str = "tbl__ds1") -> Column:
    return Column(
        id=f"{table_prefix}__col__{name}",
        name=name,
        datatype="string",
        role=ColumnRole.DIMENSION,
        kind=ColumnKind.RAW,
        source_column=name,
    )


def _orders_table(col_ids: tuple[str, ...]) -> Table:
    return Table(
        id="tbl__orders",
        name="orders",
        datasource_id="ds__ds1",
        column_ids=col_ids,
    )


def _raw_ds(col_map: dict | None = None) -> list[dict]:
    return [{"name": "ds1", "col_map": col_map or {"order_date": ["orders", "order_date"]}}]


def _raw_ws(*column_instances) -> list[dict]:
    return [{"column_instances": list(column_instances)}]


def _ci(base: str, derivation: str, slug: str | None = None) -> dict:
    return {
        "slug": slug or f"x:{base}:ok",
        "base_column": base,
        "derivation": derivation,
    }


# ── Core behaviour ────────────────────────────────────────────────────────────

def test_year_creates_dax_column():
    col = _date_col()
    table = _orders_table((col.id,))
    new_cols, updated_tables = build_date_part_columns(
        _raw_ws(_ci("order_date", "Year")), _raw_ds(), (table,), (col,)
    )
    assert len(new_cols) == 1
    c = new_cols[0]
    assert c.name == "Year order_date"
    assert c.datatype == "integer"
    assert c.kind == ColumnKind.CALCULATED
    assert c.dax_expr == "YEAR(orders[order_date])"
    assert c.role == ColumnRole.DIMENSION
    assert c.source_column is None


def test_all_derivations_produce_correct_dax_function():
    expected = {
        "Year":    "YEAR",
        "Quarter": "QUARTER",
        "Month":   "MONTH",
        "Week":    "WEEKNUM",
        "Day":     "DAY",
        "Hour":    "HOUR",
        "Minute":  "MINUTE",
        "Second":  "SECOND",
    }
    col = _date_col()
    table = _orders_table((col.id,))
    for derivation, dax_fn in expected.items():
        new_cols, _ = build_date_part_columns(
            [{"column_instances": [_ci("order_date", derivation)]}],
            _raw_ds(), (table,), (col,),
        )
        assert len(new_cols) == 1
        assert new_cols[0].dax_expr == f"{dax_fn}(orders[order_date])", (
            f"Wrong DAX for {derivation}: got {new_cols[0].dax_expr!r}"
        )


def test_duplicate_across_two_worksheets_creates_one_column():
    col = _date_col()
    table = _orders_table((col.id,))
    raw_ws = [
        {"column_instances": [_ci("order_date", "Year")]},
        {"column_instances": [_ci("order_date", "Year")]},
    ]
    new_cols, _ = build_date_part_columns(raw_ws, _raw_ds(), (table,), (col,))
    assert len(new_cols) == 1


def test_non_date_base_column_is_skipped():
    col = _string_col("category")
    table = _orders_table((col.id,))
    raw_ds = [{"name": "ds1", "col_map": {"category": ["orders", "category"]}}]
    new_cols, _ = build_date_part_columns(
        _raw_ws(_ci("category", "Year")), raw_ds, (table,), (col,)
    )
    assert len(new_cols) == 0


def test_real_type_base_column_is_skipped():
    col = _real_col("sales")
    table = _orders_table((col.id,))
    raw_ds = [{"name": "ds1", "col_map": {"sales": ["orders", "sales"]}}]
    new_cols, _ = build_date_part_columns(
        _raw_ws(_ci("sales", "Year")), raw_ds, (table,), (col,)
    )
    assert len(new_cols) == 0


def test_unknown_base_column_in_col_map_is_skipped():
    col = _date_col()
    table = _orders_table((col.id,))
    # col_map has a different name — base_column "no_such" not in col_map
    raw_ds = [{"name": "ds1", "col_map": {"order_date": ["orders", "order_date"]}}]
    new_cols, _ = build_date_part_columns(
        _raw_ws(_ci("no_such", "Year")), raw_ds, (table,), (col,)
    )
    assert len(new_cols) == 0


def test_empty_column_instances_list():
    col = _date_col()
    table = _orders_table((col.id,))
    new_cols, updated_tables = build_date_part_columns(
        [{"column_instances": []}], _raw_ds(), (table,), (col,)
    )
    assert len(new_cols) == 0
    assert updated_tables[0].column_ids == table.column_ids


def test_synthesized_column_id_appended_to_table():
    col = _date_col()
    table = _orders_table((col.id,))
    _, updated_tables = build_date_part_columns(
        _raw_ws(_ci("order_date", "Year")), _raw_ds(), (table,), (col,)
    )
    orders = next(t for t in updated_tables if t.name == "orders")
    assert any("year_order_date" in cid for cid in orders.column_ids)
    assert len(orders.column_ids) == len(table.column_ids) + 1


def test_original_table_not_mutated():
    col = _date_col()
    table = _orders_table((col.id,))
    original_ids = table.column_ids
    _, updated_tables = build_date_part_columns(
        _raw_ws(_ci("order_date", "Year")), _raw_ds(), (table,), (col,)
    )
    assert table.column_ids == original_ids  # pydantic immutable, original unchanged


def test_no_col_map_falls_back_to_table_scan():
    """Plain (non-federated) datasource with empty col_map."""
    col = _date_col("order_date", "tbl__ds1")
    table = _orders_table((col.id,))
    raw_ds = [{"name": "ds1", "col_map": {}}]  # empty col_map
    new_cols, _ = build_date_part_columns(
        _raw_ws(_ci("order_date", "Year")), raw_ds, (table,), (col,)
    )
    assert len(new_cols) == 1
    assert new_cols[0].dax_expr == "YEAR(orders[order_date])"


def test_dax_uses_physical_col_name_from_col_map():
    """Physical column name in DB differs from logical Tableau name."""
    col = Column(
        id="tbl__ds1__col__order_date",
        name="order_date",
        datatype="date",
        role=ColumnRole.DIMENSION,
        kind=ColumnKind.RAW,
        source_column="OrderDate",  # different physical name
    )
    table = _orders_table((col.id,))
    raw_ds = [{"name": "ds1", "col_map": {"order_date": ["orders", "OrderDate"]}}]
    new_cols, _ = build_date_part_columns(
        _raw_ws(_ci("order_date", "Year")), raw_ds, (table,), (col,)
    )
    assert len(new_cols) == 1
    assert new_cols[0].dax_expr == "YEAR(orders[OrderDate])"


def test_two_different_derivations_of_same_column():
    col = _date_col()
    table = _orders_table((col.id,))
    raw_ws = [{"column_instances": [
        _ci("order_date", "Year"),
        _ci("order_date", "Month"),
    ]}]
    new_cols, updated_tables = build_date_part_columns(raw_ws, _raw_ds(), (table,), (col,))
    assert len(new_cols) == 2
    names = {c.name for c in new_cols}
    assert names == {"Year order_date", "Month order_date"}
    orders = next(t for t in updated_tables if t.name == "orders")
    assert len(orders.column_ids) == len(table.column_ids) + 2
```

- [x] **Step 2.2: Run tests to confirm they fail**

```
pytest tests/unit/test_build_date_part_columns.py -v
```

Expected: `ImportError: cannot import name 'build_date_part_columns'`.

- [x] **Step 2.3: Implement `build_date_part_columns()` in `_build_data_model.py`**

Add the following two blocks to `src/tableau2pbir/stages/_build_data_model.py`.

**After the `_LOD_HEADER` constant block (around line 293), add:**

```python
_DERIVATION_TO_DAX: dict[str, str] = {
    "Year":    "YEAR",
    "Quarter": "QUARTER",
    "Month":   "MONTH",
    "Week":    "WEEKNUM",
    "Day":     "DAY",
    "Hour":    "HOUR",
    "Minute":  "MINUTE",
    "Second":  "SECOND",
}


def build_date_part_columns(
    raw_worksheets: list[dict[str, Any]],
    raw_datasources: list[dict[str, Any]],
    tables: tuple[Table, ...],
    columns: tuple[Column, ...],
) -> tuple[tuple[Column, ...], tuple[Table, ...]]:
    """Synthesize DAX calculated columns for Tableau date-part pills.

    For each unique (base_column, derivation) pair referenced in worksheet
    column_instances, creates a Column(kind=CALCULATED) with the appropriate
    DAX YEAR/MONTH/… expression and appends its ID to the owning Table.

    Returns (new_columns, updated_tables). The caller merges new_columns into
    DataModel.columns and replaces the tables tuple with updated_tables.
    """
    col_by_id: dict[str, Column] = {c.id: c for c in columns}
    table_by_name: dict[str, Table] = {t.name: t for t in tables}

    # Merge col_map entries from all raw datasources.
    # col_map: logical_col_name → [physical_table_name, physical_col_name]
    merged_col_map: dict[str, tuple[str, str]] = {}
    for raw_ds in raw_datasources:
        for k, v in (raw_ds.get("col_map") or {}).items():
            merged_col_map[k] = (v[0], v[1])

    seen: set[tuple[str, str]] = set()
    new_columns: list[Column] = []
    extra_col_ids: dict[str, list[str]] = {t.name: [] for t in tables}

    for raw_ws in raw_worksheets:
        for ci in raw_ws.get("column_instances", []):
            base_col_name: str = ci["base_column"]   # "order_date"
            derivation: str = ci["derivation"]        # "Year"
            key = (base_col_name, derivation)
            if key in seen:
                continue

            dax_fn = _DERIVATION_TO_DAX.get(derivation)
            if dax_fn is None:
                continue

            # Locate owning physical table.
            # For federated joins col_map has the answer directly.
            # For plain single-table datasources col_map is empty — scan tables.
            phys: tuple[str, str] | None = merged_col_map.get(base_col_name)
            if phys is None:
                for t in tables:
                    for cid in t.column_ids:
                        c = col_by_id.get(cid)
                        if c and c.name == base_col_name:
                            phys = (t.name, c.source_column or c.name)
                            break
                    if phys:
                        break
            if phys is None:
                continue
            phys_table_name, phys_col_name = phys

            table = table_by_name.get(phys_table_name)
            if table is None:
                continue

            # Guard: only synthesize for date/datetime columns.
            base_col_ir = next(
                (col_by_id[cid] for cid in table.column_ids
                 if cid in col_by_id and col_by_id[cid].name == base_col_name),
                None,
            )
            if base_col_ir is None or base_col_ir.datatype not in ("date", "datetime"):
                continue

            seen.add(key)

            # Derive the column ID prefix from existing column IDs in this table
            # (consistent with how build_tables() constructs them).
            existing_ids = [cid for cid in table.column_ids if "__col__" in cid]
            col_prefix = (
                existing_ids[0].rsplit("__col__", 1)[0]
                if existing_ids else stable_id("tbl", table.name)
            )

            derived_name = f"{derivation} {base_col_name}"          # "Year order_date"
            dax_expr = f"{dax_fn}({phys_table_name}[{phys_col_name}])"  # "YEAR(orders[order_date])"
            derived_col_id = f"{col_prefix}__{stable_id('col', derived_name)}"

            new_columns.append(Column(
                id=derived_col_id,
                name=derived_name,
                datatype="integer",
                role=ColumnRole.DIMENSION,
                kind=ColumnKind.CALCULATED,
                dax_expr=dax_expr,
            ))
            extra_col_ids[phys_table_name].append(derived_col_id)

    # Return immutable updated tables (pydantic model_copy preserves immutability).
    updated_tables = tuple(
        t.model_copy(update={"column_ids": t.column_ids + tuple(extra_col_ids[t.name])})
        for t in tables
    )
    return tuple(new_columns), updated_tables
```

- [x] **Step 2.4: Run tests to confirm they pass**

```
pytest tests/unit/test_build_date_part_columns.py -v
```

Expected: all 12 tests PASS.

- [x] **Step 2.5: Run full unit suite for regressions**

```
pytest tests/unit/ -v --tb=short
```

Expected: all existing tests PASS.

- [x] **Step 2.6: Commit**

```
git add src/tableau2pbir/stages/_build_data_model.py tests/unit/test_build_date_part_columns.py
git commit -m "feat(stage2): synthesize DAX calculated columns for date-part derivation pills"
```

---

## Task 3 — Wire Stage 2 orchestrator + update counts assertion

**Files:**
- Modify: `src/tableau2pbir/stages/s02_canonicalize.py`
- Modify: `tests/golden/test_real_stage2.py`

- [x] **Step 3.1: Update the import in `s02_canonicalize.py`**

In `src/tableau2pbir/stages/s02_canonicalize.py`, change the `_build_data_model` import line from:

```python
from tableau2pbir.stages._build_data_model import (
    build_calculations, build_datasources, build_parameters, build_relationships, build_tables,
)
```

to:

```python
from tableau2pbir.stages._build_data_model import (
    build_calculations, build_datasources, build_date_part_columns,
    build_parameters, build_relationships, build_tables,
)
```

- [x] **Step 3.2: Call `build_date_part_columns()` in the `run()` function**

In `src/tableau2pbir/stages/s02_canonicalize.py`, inside `run()`, find the line:

```python
    tables, columns = build_tables(input_json.get("datasources", []))
```

Replace it with:

```python
    tables, columns = build_tables(input_json.get("datasources", []))
    date_part_columns, tables = build_date_part_columns(
        input_json.get("worksheets", []),
        input_json.get("datasources", []),
        tables,
        columns,
    )
    columns = columns + date_part_columns
```

- [x] **Step 3.3: Write the failing golden counts assertion**

In `tests/golden/test_real_stage2.py`, add these assertions inside `test_simple_join_calculated_line_counts()` **after** the existing lines:

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
    people_orders = next(
        r for r in dm["relationships"]
        if {r["from_ref"]["table_id"], r["to_ref"]["table_id"]} == {"tbl__people", "tbl__orders"}
    )
    assert people_orders["cardinality"] == "many_to_many"
    assert people_orders["cross_filter"] == "both"
    orders_returns = next(
        r for r in dm["relationships"]
        if {r["from_ref"]["table_id"], r["to_ref"]["table_id"]} == {"tbl__orders", "tbl__returns"}
    )
    assert orders_returns["cardinality"] == "many_to_many"
    assert orders_returns["cross_filter"] == "both"
    # Plan 18: date-part synthesized column
    year_col = next(
        (c for c in dm["columns"] if c["name"] == "Year order_date"), None
    )
    assert year_col is not None, "Year order_date column not synthesized"
    assert year_col["kind"] == "calculated"
    assert year_col["dax_expr"] == "YEAR(orders[order_date])"
    assert year_col["datatype"] == "integer"
    orders_table = next(t for t in dm["tables"] if t["name"] == "orders")
    assert year_col["id"] in orders_table["column_ids"], (
        "Year order_date column ID not in orders table column_ids"
    )
```

Also update `test_snowflake_counts()` to assert a Year-derived column exists:

```python
def test_snowflake_counts():
    out = _run_pipeline("snowflkake.twb")
    dm = out["data_model"]
    assert len(dm["datasources"]) == 1
    assert len(dm["tables"]) == 2  # two physical tables: CUSTOMER, ORDERS
    assert len(dm["calculations"]) == 0
    assert len(out["sheets"]) == 3
    # Plan 18: Snowflake workbook has yr:O_ORDERDATE:ok in Sheet 1
    year_cols = [c for c in dm["columns"]
                 if c["name"].startswith("Year ") and c["kind"] == "calculated"]
    assert len(year_cols) >= 1, "No Year-derived column synthesized for Snowflake workbook"
    assert year_cols[0]["dax_expr"].startswith("YEAR("), (
        f"Expected YEAR() DAX, got {year_cols[0]['dax_expr']!r}"
    )
```

- [x] **Step 3.4: Run the golden counts tests to confirm failures**

```
pytest tests/golden/test_real_stage2.py::test_simple_join_calculated_line_counts tests/golden/test_real_stage2.py::test_snowflake_counts -v
```

Expected: both fail — `Year order_date` not found (the wiring isn't applied yet until step 3.2 is done; if already done, they should pass).

- [x] **Step 3.5: Run Stage 2 smoke tests (all workbooks)**

```
pytest tests/golden/test_real_stage2.py -v --tb=short
```

Expected: all tests PASS including the updated counts.

- [x] **Step 3.6: Commit**

```
git add src/tableau2pbir/stages/s02_canonicalize.py tests/golden/test_real_stage2.py
git commit -m "feat(stage2): wire build_date_part_columns into Stage 2 orchestrator"
```

---

## Task 4 — `field_lookup.py`: resolve date-part pills to synthesized columns

**Files:**
- Modify: `src/tableau2pbir/visualmap/field_lookup.py`
- Create: `tests/unit/test_field_lookup_date_parts.py`

### Background

Currently `field_lookup.py` routes `yr_order_date_ok` → raw `order_date` column (silent drop of year derivation). After this task it routes to the synthesized "Year order_date" column synthesized in Task 2/3.

The key change is:
1. Add `datatype` to each `by_base` entry (needed to guard the date-part branch).
2. Before the aggregation block, check `if prefix in _DATE_PART_PREFIX and datatype in ("date","datetime")`, compute `slug_id("Year order_date")`, look up `by_base["year_order_date"]`.

- [x] **Step 4.1: Write the failing unit test**

Create `tests/unit/test_field_lookup_date_parts.py`:

```python
"""Unit tests for date-part pill resolution in build_field_lookup()."""
from __future__ import annotations

from tableau2pbir.visualmap.field_lookup import build_field_lookup
from tableau2pbir.ir.model import Column, ColumnKind, ColumnRole, Table
from tableau2pbir.ir.sheet import Encoding, Sheet
from tableau2pbir.ir.common import FieldRef
from tableau2pbir.ir.workbook import DataModel, Workbook
from tableau2pbir.ir.version import IR_SCHEMA_VERSION


# ── Helpers ───────────────────────────────────────────────────────────────────

def _wb(tables, columns, sheets):
    dm = DataModel(datasources=(), tables=tables, columns=columns,
                   relationships=(), calculations=(), parameters=())
    return Workbook(
        ir_schema_version=IR_SCHEMA_VERSION,
        source_path="test.twb", source_hash="a" * 64,
        tableau_version="2026.1", config={},
        data_model=dm, sheets=sheets, dashboards=(), unsupported=(),
    )


def _col(col_id, name, datatype="string", role=ColumnRole.DIMENSION,
         kind=ColumnKind.RAW, dax_expr=None, source_column=None):
    return Column(id=col_id, name=name, datatype=datatype, role=role,
                  kind=kind, dax_expr=dax_expr,
                  source_column=source_column or (name if kind == ColumnKind.RAW else None))


def _table(table_id, name, col_ids):
    return Table(id=table_id, name=name, datasource_id="ds__ds",
                 column_ids=tuple(col_ids))


def _sheet_with_col_encoding(field_id: str, table_id: str) -> Sheet:
    enc = Encoding(columns=(FieldRef(table_id=table_id, column_id=field_id),))
    return Sheet(id="sheet__s", name="S", datasource_refs=(), mark_type="line",
                 encoding=enc, filters=(), sort=(), dual_axis=False,
                 reference_lines=(), uses_calculations=(), visual_format=None)


def _sheet_with_row_encoding(field_id: str, table_id: str) -> Sheet:
    enc = Encoding(rows=(FieldRef(table_id=table_id, column_id=field_id),))
    return Sheet(id="sheet__s2", name="S2", datasource_refs=(), mark_type="bar",
                 encoding=enc, filters=(), sort=(), dual_axis=False,
                 reference_lines=(), uses_calculations=(), visual_format=None)


# ── Date-part resolution ──────────────────────────────────────────────────────

def test_year_pill_resolves_to_synthesized_column():
    raw = _col("tbl__ds__col__order_date", "order_date", datatype="date")
    derived = _col("tbl__ds__col__year_order_date", "Year order_date",
                   datatype="integer", kind=ColumnKind.CALCULATED, dax_expr="YEAR(orders[order_date])")
    table = _table("tbl__orders", "orders",
                   ["tbl__ds__col__order_date", "tbl__ds__col__year_order_date"])
    sheet = _sheet_with_col_encoding("yr_order_date_ok", "tbl__orders")
    wb = _wb((table,), (raw, derived), (sheet,))
    lookup = build_field_lookup(wb)
    assert "yr_order_date_ok" in lookup
    info = lookup["yr_order_date_ok"]
    assert info["col_name"] == "Year order_date"
    assert info["table_name"] == "orders"
    assert info["is_measure"] is False


def test_month_pill_resolves_to_synthesized_column():
    raw = _col("tbl__ds__col__order_date", "order_date", datatype="date")
    derived = _col("tbl__ds__col__month_order_date", "Month order_date",
                   datatype="integer", kind=ColumnKind.CALCULATED, dax_expr="MONTH(orders[order_date])")
    table = _table("tbl__orders", "orders",
                   ["tbl__ds__col__order_date", "tbl__ds__col__month_order_date"])
    sheet = _sheet_with_col_encoding("mn_order_date_ok", "tbl__orders")
    wb = _wb((table,), (raw, derived), (sheet,))
    lookup = build_field_lookup(wb)
    assert lookup["mn_order_date_ok"]["col_name"] == "Month order_date"


def test_date_part_pill_without_synthesized_column_falls_back_to_raw():
    """If Stage 2 did not synthesize the column (edge case), fall back gracefully."""
    raw = _col("tbl__ds__col__order_date", "order_date", datatype="date")
    table = _table("tbl__orders", "orders", ["tbl__ds__col__order_date"])
    sheet = _sheet_with_col_encoding("yr_order_date_ok", "tbl__orders")
    wb = _wb((table,), (raw,), (sheet,))
    lookup = build_field_lookup(wb)
    # Fallback: raw column info (same as pre-fix behaviour for robustness)
    info = lookup.get("yr_order_date_ok")
    assert info is not None
    assert info["col_name"] == "order_date"  # graceful fallback


# ── Regression: existing pill types still resolve correctly ───────────────────

def test_sum_measure_pill_still_resolves():
    sales = _col("tbl__ds__col__sales", "sales", datatype="real", role=ColumnRole.MEASURE)
    table = _table("tbl__orders", "orders", ["tbl__ds__col__sales"])
    sheet = _sheet_with_row_encoding("sum_sales_qk", "tbl__orders")
    wb = _wb((table,), (sales,), (sheet,))
    lookup = build_field_lookup(wb)
    info = lookup["sum_sales_qk"]
    assert info["measure_name"] == "Sum sales"
    assert info["is_measure"] is True


def test_none_dimension_pill_still_resolves():
    cat = _col("tbl__ds__col__category", "category", datatype="string")
    table = _table("tbl__orders", "orders", ["tbl__ds__col__category"])
    sheet = _sheet_with_col_encoding("none_category_nk", "tbl__orders")
    wb = _wb((table,), (cat,), (sheet,))
    lookup = build_field_lookup(wb)
    info = lookup["none_category_nk"]
    assert info["col_name"] == "category"
    assert info["is_measure"] is False


def test_string_column_with_yr_prefix_is_not_treated_as_date_part():
    """A column named 'yr_something' that is string type must not trigger date-part logic."""
    str_col = _col("tbl__ds__col__region", "region", datatype="string")
    table = _table("tbl__orders", "orders", ["tbl__ds__col__region"])
    sheet = _sheet_with_col_encoding("none_region_nk", "tbl__orders")
    wb = _wb((table,), (str_col,), (sheet,))
    lookup = build_field_lookup(wb)
    info = lookup["none_region_nk"]
    assert info["col_name"] == "region"
```

- [x] **Step 4.2: Run tests to confirm failures**

```
pytest tests/unit/test_field_lookup_date_parts.py -v
```

Expected: `test_year_pill_resolves_to_synthesized_column` and `test_month_pill_resolves_to_synthesized_column` FAIL — they return `col_name="order_date"` not "Year order_date".

- [x] **Step 4.3: Add `_DATE_PART_PREFIX` constant to `field_lookup.py`**

In `src/tableau2pbir/visualmap/field_lookup.py`, add after `_MEASURE_SUFFIX = "qk"`:

```python
_DATE_PART_PREFIX: dict[str, str] = {
    "yr": "Year",
    "qr": "Quarter",
    "mn": "Month",
    "wk": "Week",
    "dy": "Day",
    "hr": "Hour",
    "mi": "Minute",
    "sc": "Second",
}
```

- [x] **Step 4.4: Add `datatype` to `by_base` entries in `build_field_lookup()`**

In `src/tableau2pbir/visualmap/field_lookup.py`, inside `build_field_lookup()`, find the block:

```python
            by_base[slug_id(col.name)] = {
                "table_name": table.name,
                "col_name": col.name,
                "is_measure": col.role == ColumnRole.MEASURE,
            }
```

Replace with:

```python
            by_base[slug_id(col.name)] = {
                "table_name": table.name,
                "col_name": col.name,
                "is_measure": col.role == ColumnRole.MEASURE,
                "datatype": col.datatype,
            }
```

- [x] **Step 4.5: Add the date-part routing block in the pill resolution loop**

In `src/tableau2pbir/visualmap/field_lookup.py`, inside the `for fr in refs:` loop, find these lines:

```python
            prefix, body, suffix = m.group(1), m.group(2), m.group(3)
            if body not in by_base:
                continue
            base = by_base[body]
            col_name = base["col_name"]
```

Replace with:

```python
            prefix, body, suffix = m.group(1), m.group(2), m.group(3)
            if body not in by_base:
                continue
            base = by_base[body]

            # Route date-part derivation pills to the synthesized calculated column.
            # e.g. yr_order_date_ok → "Year order_date" column, not raw "order_date".
            if prefix in _DATE_PART_PREFIX and base.get("datatype") in ("date", "datetime"):
                part_label = _DATE_PART_PREFIX[prefix]
                derived_col_name = f"{part_label} {base['col_name']}"
                derived_body_slug = slug_id(derived_col_name)
                if derived_body_slug in by_base:
                    derived = by_base[derived_body_slug]
                    lookup[field_id] = {**derived, "measure_name": derived["col_name"]}
                    continue
                # Synthesized column not present (edge case) — fall through to raw column.

            col_name = base["col_name"]
```

- [x] **Step 4.6: Run tests to confirm they pass**

```
pytest tests/unit/test_field_lookup_date_parts.py -v
```

Expected: all 7 tests PASS.

- [x] **Step 4.7: Run full unit suite for regressions**

```
pytest tests/unit/ -v --tb=short
```

Expected: all tests PASS.

- [x] **Step 4.8: Commit**

```
git add src/tableau2pbir/visualmap/field_lookup.py tests/unit/test_field_lookup_date_parts.py
git commit -m "fix(field_lookup): resolve date-part pills to synthesized DAX columns"
```

---

## Task 5 — Integration test: Stage 2 IR (no LLM required)

**Files:**
- Create: `tests/integration/test_date_part_derivation.py`

This test runs Stages 1–2 only (via `--gate canonicalize`) on `simple_join_calculated_line.twb` to assert that the Stage 2 IR contains the synthesized "Year order_date" column with the correct structure. No LLM is needed.

- [x] **Step 5.1: Write the test**

Create `tests/integration/test_date_part_derivation.py`:

```python
"""Integration tests for Plan 18 — date-part derivation DAX column synthesis.

Tests run stages 1-2 (no LLM) and 1-7 (no LLM needed — no calculations in
simple_join_calculated_line.twb) against the real workbook.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_REAL_DIR = Path(__file__).resolve().parents[1] / "golden" / "real"
_WB = _REAL_DIR / "simple_join_calculated_line.twb"


def _run(args: list[str], tmp: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "tableau2pbir.cli", *args],
        capture_output=True, text=True, env=os.environ,
        cwd=str(tmp),
    )


def _stage_json(out: Path, n: int, name: str) -> dict:
    return json.loads(
        (out / "simple_join_calculated_line" / "stages" / f"{n:02d}_{name}.json")
        .read_text(encoding="utf-8")
    )


@pytest.mark.integration
def test_stage2_synthesizes_year_order_date_column(tmp_path: Path):
    """Stage 1→2 produces Year order_date column with correct DAX."""
    if not _WB.exists():
        pytest.skip(f"{_WB.name} not present")
    out = tmp_path / "out"
    result = subprocess.run(
        [sys.executable, "-m", "tableau2pbir.cli", "convert",
         str(_WB), "--out", str(out), "--gate", "canonicalize"],
        capture_output=True, text=True, env=os.environ,
    )
    assert result.returncode == 0, result.stderr

    ir2 = _stage_json(out, 2, "canonicalize")
    columns = ir2["data_model"]["columns"]

    year_col = next((c for c in columns if c["name"] == "Year order_date"), None)
    assert year_col is not None, (
        f"Year order_date not in Stage 2 columns. Got names: {[c['name'] for c in columns]}"
    )
    assert year_col["kind"] == "calculated"
    assert year_col["dax_expr"] == "YEAR(orders[order_date])"
    assert year_col["datatype"] == "integer"
    assert year_col["source_column"] is None  # not a raw physical column


@pytest.mark.integration
def test_stage2_year_column_in_orders_table_column_ids(tmp_path: Path):
    """The synthesized column ID appears in the orders table's column_ids."""
    if not _WB.exists():
        pytest.skip(f"{_WB.name} not present")
    out = tmp_path / "out"
    result = subprocess.run(
        [sys.executable, "-m", "tableau2pbir.cli", "convert",
         str(_WB), "--out", str(out), "--gate", "canonicalize"],
        capture_output=True, text=True, env=os.environ,
    )
    assert result.returncode == 0, result.stderr

    ir2 = _stage_json(out, 2, "canonicalize")
    year_col = next(c for c in ir2["data_model"]["columns"] if c["name"] == "Year order_date")
    orders_table = next(t for t in ir2["data_model"]["tables"] if t["name"] == "orders")
    assert year_col["id"] in orders_table["column_ids"], (
        f"Year order_date column id {year_col['id']!r} not in "
        f"orders table column_ids: {orders_table['column_ids']}"
    )


@pytest.mark.integration
def test_stage2_raw_order_date_still_present(tmp_path: Path):
    """The raw order_date column must remain unchanged alongside the derived one."""
    if not _WB.exists():
        pytest.skip(f"{_WB.name} not present")
    out = tmp_path / "out"
    result = subprocess.run(
        [sys.executable, "-m", "tableau2pbir.cli", "convert",
         str(_WB), "--out", str(out), "--gate", "canonicalize"],
        capture_output=True, text=True, env=os.environ,
    )
    assert result.returncode == 0, result.stderr

    ir2 = _stage_json(out, 2, "canonicalize")
    raw_col = next(
        (c for c in ir2["data_model"]["columns"]
         if c["name"] == "order_date" and c["kind"] == "raw"),
        None,
    )
    assert raw_col is not None, "Raw order_date column must still be in data_model.columns"
```

- [x] **Step 5.2: Run the tests to confirm they pass**

```
pytest tests/integration/test_date_part_derivation.py -v -k "stage2"
```

Expected: all three Stage-2 tests PASS.

- [x] **Step 5.3: Commit**

```
git add tests/integration/test_date_part_derivation.py
git commit -m "test(integration): assert Stage 2 synthesizes Year order_date column"
```

---

## Task 6 — Integration test: full pipeline — TMDL + visual JSON

**Files:**
- Modify: `tests/integration/test_date_part_derivation.py`

These tests run the full 8-stage pipeline on `simple_join_calculated_line.twb`. Since this workbook has no calculations, Stage 3 is a no-op and no LLM key is required.

- [x] **Step 6.1: Add TMDL and visual JSON tests to the integration file**

Append to `tests/integration/test_date_part_derivation.py`:

```python
def _full_pipeline(wb: Path, out: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "tableau2pbir.cli", "convert",
         str(wb), "--out", str(out)],
        capture_output=True, text=True, env=os.environ,
    )


@pytest.mark.integration
def test_tmdl_orders_has_year_calculated_column(tmp_path: Path):
    """orders.tmdl must contain the YEAR() calculated column block."""
    if not _WB.exists():
        pytest.skip(f"{_WB.name} not present")
    out = tmp_path / "out"
    result = _full_pipeline(_WB, out)
    if result.returncode != 0 and any(
        x in result.stderr for x in ("ANTHROPIC_API_KEY not set", "authentication_error", "invalid x-api-key")
    ):
        pytest.skip("ANTHROPIC_API_KEY needed for Stage 3 (unexpected — workbook has no calcs)")
    assert result.returncode == 0, result.stderr

    orders_tmdl = (
        out / "simple_join_calculated_line" /
        "SemanticModel" / "definition" / "tables" / "orders.tmdl"
    )
    assert orders_tmdl.is_file(), "orders.tmdl not generated"
    text = orders_tmdl.read_text(encoding="utf-8")

    assert "Year order_date" in text, (
        "Calculated column 'Year order_date' not found in orders.tmdl"
    )
    assert "YEAR(orders[order_date])" in text, (
        "DAX expression YEAR(orders[order_date]) not found in orders.tmdl"
    )
    assert "dataType: int64" in text, "int64 dataType not found in orders.tmdl"


@pytest.mark.integration
def test_visual_json_sheet2_category_uses_year_column(tmp_path: Path):
    """Sheet 2 visual.json Category projection must bind to Year order_date, not order_date."""
    if not _WB.exists():
        pytest.skip(f"{_WB.name} not present")
    out = tmp_path / "out"
    result = _full_pipeline(_WB, out)
    if result.returncode != 0 and any(
        x in result.stderr for x in ("ANTHROPIC_API_KEY not set", "authentication_error", "invalid x-api-key")
    ):
        pytest.skip("ANTHROPIC_API_KEY needed for Stage 3")
    assert result.returncode == 0, result.stderr

    visual_path = (
        out / "simple_join_calculated_line" / "Report" / "definition" /
        "pages" / "ReportSection2" / "visuals" / "visual_2" / "visual.json"
    )
    assert visual_path.is_file(), "visual_2/visual.json not generated for Sheet 2"
    visual = json.loads(visual_path.read_text(encoding="utf-8"))

    projections = visual["visual"]["query"]["queryState"]["Category"]["projections"]
    assert len(projections) == 1
    field = projections[0]["field"]
    assert "Column" in field, (
        f"Expected Column binding for Category, got: {list(field.keys())}"
    )
    prop = field["Column"]["Property"]
    assert prop == "Year order_date", (
        f"Expected 'Year order_date' but got {prop!r} — date truncation is still lost"
    )
    assert projections[0]["queryRef"] == "orders.Year order_date"


@pytest.mark.integration
def test_visual_json_sheet2_raw_order_date_not_used(tmp_path: Path):
    """Regression guard: the raw 'order_date' property must NOT appear in Sheet 2 Category."""
    if not _WB.exists():
        pytest.skip(f"{_WB.name} not present")
    out = tmp_path / "out"
    result = _full_pipeline(_WB, out)
    if result.returncode != 0 and any(
        x in result.stderr for x in ("ANTHROPIC_API_KEY not set", "authentication_error", "invalid x-api-key")
    ):
        pytest.skip("ANTHROPIC_API_KEY needed for Stage 3")
    assert result.returncode == 0, result.stderr

    visual_path = (
        out / "simple_join_calculated_line" / "Report" / "definition" /
        "pages" / "ReportSection2" / "visuals" / "visual_2" / "visual.json"
    )
    visual = json.loads(visual_path.read_text(encoding="utf-8"))
    projections = visual["visual"]["query"]["queryState"]["Category"]["projections"]
    prop = projections[0]["field"]["Column"]["Property"]
    assert prop != "order_date", (
        "BUG STILL PRESENT: Category binding is 'order_date' (raw daily) not 'Year order_date'"
    )
```

- [x] **Step 6.2: Run all integration tests for this plan**

```
pytest tests/integration/test_date_part_derivation.py -v
```

Expected: all 6 tests PASS.

- [x] **Step 6.3: Commit**

```
git add tests/integration/test_date_part_derivation.py
git commit -m "test(integration): assert TMDL calculated column and visual.json Year binding"
```

---

## Task 7 — Run the full real-workbook E2E gate

**Files:** None (read-only run)

This is the mandatory gate from `CLAUDE.md`: run `tests/integration/test_real_workbooks_e2e.py` after every task, here for a final overall health check.

- [x] **Step 7.1: Run the full real-workbook E2E suite**

```
pytest tests/integration/test_real_workbooks_e2e.py -v --tb=short
```

Expected: all tests PASS (or skip with "requires ANTHROPIC_API_KEY" for workbooks with calculations — that is acceptable). The `simple_join_calculated_line.twb` test must PASS without skipping since it has no calculations.

- [x] **Step 7.2: Run the full unit suite one final time**

```
pytest tests/unit/ tests/golden/ -v --tb=short
```

Expected: all tests PASS.

- [x] **Step 7.3: Commit if there are any staged changes**

If the E2E run revealed any fixable regressions, fix them now, then:

```
git add -p
git commit -m "fix: address E2E regressions found in Plan 18 gate run"
```

- [x] **Step 7.4: Update CLAUDE.md implementation tracking table**

In `CLAUDE.md`, add a row for Plan 18:

```markdown
| 18 | Date-Part Derivation — `YEAR()`/`MONTH()`/… DAX Columns | ✅ DONE | `docs/superpowers/plans/2026-06-04-plan-18-date-part-derivation-dax-columns.md` |
```

- [x] **Step 7.5: Final commit**

```
git add CLAUDE.md
git commit -m "docs: mark Plan 18 date-part derivation as DONE in CLAUDE.md"
```

---

## Self-Review

### Spec coverage

| Requirement | Covered by |
|---|---|
| `yr:order_date:ok` → `YEAR(orders[order_date])` DAX column | Task 2 + Task 3 |
| Column appears in `orders` table `column_ids` | Task 2 (`extra_col_ids`) + Task 3 |
| TMDL emits calculated column (no TMDL code change needed) | Verified in Task 6 — `emit/tmdl/column.py` already handles `ColumnKind.CALCULATED` |
| Visual JSON binds `"Year order_date"` not `"order_date"` | Task 4 + Task 6 |
| All 8 date granularities (Year/Quarter/Month/Week/Day/Hour/Minute/Second) | Task 2 test covers all 8 |
| Deduplication across sheets | Task 2 test `test_duplicate_across_two_worksheets` |
| Non-date base columns skipped | Task 2 test `test_non_date_base_column_is_skipped` |
| Plain (non-federated) datasource fallback | Task 2 test `test_no_col_map_falls_back_to_table_scan` |
| Physical col name from `col_map` used in DAX | Task 2 test `test_dax_uses_physical_col_name_from_col_map` |
| Existing pill types (sum_, none_) unbroken | Task 4 regression tests |
| Snowflake workbook (yr:O_ORDERDATE:ok) | Task 3 `test_snowflake_counts` |
| Database-agnostic (no connector changes) | `m_expression.py`/`connector_tier.py` untouched |

### Placeholder scan

No "TBD", "TODO", "implement later", or "similar to" patterns — all steps include complete code.

### Type consistency

- `build_date_part_columns` returns `tuple[tuple[Column, ...], tuple[Table, ...]]` — matches how `s02_canonicalize.py` uses it in Task 3.
- `_column_instances` returns `list[dict[str, Any]]` — matches how `build_date_part_columns` reads `raw_ws.get("column_instances", [])` in Task 2.
- `Column(kind=ColumnKind.CALCULATED, dax_expr=...)` — matches `column.py:render_column()` which checks `col.kind == ColumnKind.CALCULATED` and `col.dax_expr`.
- `by_base` dict gains `"datatype"` key — all reads via `.get("datatype")` in Task 4 (safe if key absent in edge cases).
