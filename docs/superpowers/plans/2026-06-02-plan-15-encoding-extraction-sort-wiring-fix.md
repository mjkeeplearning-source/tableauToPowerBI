# Plan 15 — Encoding Extraction & Sort Wiring Fix

> **Execution approach: Subagent-Driven Development.**
> When implementing, use the `superpowers:subagent-driven-development` skill — dispatch a fresh subagent per task with review checkpoints between tasks. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix two residual conversion bugs in `simple_join_sorted_test.twb`: (1) Sheet 1's column chart shows no sort because `_build_sort_entries` was never wired into the bar/column chart dispatch path; (2) Sheet 4's Profit figure is blank because pane encoding channels use `_unbracket` instead of `_parse_filter_column`, producing garbage slugs for real Tableau qualified column refs, and `build_field_lookup` omits `enc.text` and sort-by fields from its resolution loop.

**Architecture:** Three surgical fixes in three files. Fix A corrects the extraction layer (`worksheets.py`) to use `_parse_filter_column` for all pane encoding channels — the same function already used for filters and computed-sorts. Fix B patches `field_lookup.py` to include `enc.text` and sort-by-field refs so the emit layer can resolve them to real table names. Fix C wires `_build_sort_entries()` into the `columnChart` and `barChart` dispatch branches so computed sorts reach the PBIR `sortDefinition`.

**Tech Stack:** Python 3.11+, lxml, pydantic v2, pytest.

---

## File Map

| Action | File |
|--------|------|
| Modify | `src/tableau2pbir/extract/worksheets.py` |
| Modify | `src/tableau2pbir/visualmap/field_lookup.py` |
| Modify | `src/tableau2pbir/visualmap/dispatch.py` |
| Modify | `tests/unit/extract/test_worksheets.py` |
| Modify | `tests/unit/visualmap/test_field_lookup.py` |
| Modify | `tests/unit/visualmap/test_dispatch.py` |

---

## Background: Why Plan 14 Did Not Fix These Issues

### Root cause 1 — Sort missing from Sheet 1 (column chart)

Sheet 1 has ROWS=DeltaOrder (measure), COLS=Category (dimension), mark=Automatic, and a `<computed-sort>` on Category using DeltaOrder. In `dispatch.py`, the computed sort extraction and `VisualSortEntry` wiring added in Plan 14 were only connected to two branches:

- `mark == "text"` → tableEx
- `mark in ("bar", "automatic") and rows and NOT cols` (dim-only bar) → tableEx

Sheet 1 has both rows AND cols, so it takes the **vertical bar / columnChart** path:

```python
# dispatch.py, ~line 90
bindings = [_bind("Category", cols[0])] + [_bind("Y", r) for r in rows]
return PbirVisual(visual_type="columnChart", encoding_bindings=tuple(bindings), format=fmt)
```

This branch never calls `_build_sort_entries()`, so `PbirVisual.sort_by` is always empty and no `sortDefinition` is written to `visual_1.json`.

**Why the test didn't catch it:** The Plan 14 test for `<computed-sort>` extraction built a worksheet with rows-only (no cols), so it went through the `dim-only bar` path that was updated. The `columnChart` path was never exercised by any computed-sort test.

### Root cause 2 — Profit blank in Sheet 4 (wrong entity/property)

Sheet 4 has ROWS=category, COLS empty, mark=Automatic, a `<text>` encoding for `sum:profit:qk`, and a `<computed-sort>` on category using `sum:profit:qk`.

**The extraction bug in `_encodings()` (`worksheets.py` line 108):**

```python
col = optional_attr(ch, "column")   # e.g. "[federated.17kv7r10...it8].[sum:profit:qk]"
col = _unbracket(col)               # ← returns string unchanged because it contains "].[" 
enc[ch.tag] = col                   # stores the whole qualified ref, not just "sum:profit:qk"
```

`_unbracket` handles simple refs (`[profit]` → `profit`) but returns qualified refs unchanged. The correct function is `_parse_filter_column`, already used for filters and computed-sorts, which correctly extracts `sum:profit:qk` from `[federated.xxx].[sum:profit:qk]`.

With the wrong full string stored, `stable_id("", "[federated.xxx].[sum:profit:qk]")` produces the slug `"federated_17kv7r10vp81pc1g60xgp0re1it8_sum_profit_qk"` — a 47-char garbage key.

**The field_lookup gap in `field_lookup.py` line 67:**

```python
for opt in (enc.color, enc.size, enc.label, enc.tooltip, enc.shape, enc.angle):
    if opt:
        refs.append(opt)
```

`enc.text` (added in Plan 14) is absent. Even after fixing extraction, `sum_profit_qk` would never be registered in the lookup, causing `_make_projection` to fall back to `Entity: "Model", Property: "sum_profit_qk"` — not a real PBI measure reference.

Sort-by fields are also absent from this loop, meaning if a sort-by measure doesn't appear in any other channel, its projection also falls back to "Model".

**Why Plan 14's test didn't catch it:** The test used `<text column='[profit]'/>` — a simple unqualified ref. `_unbracket("[profit]") = "profit"` works correctly. The test never used a real Tableau qualified ref like `[federated.xxx].[sum:profit:qk]`.

---

## Task 1 — Fix pane encoding channel extraction for qualified refs

**Root cause:** `_encodings()` uses `col = _unbracket(col)` for all pane encoding channels. For qualified Tableau column refs like `[federated.17kv7r10vp81pc1g60xgp0re1it8].[sum:profit:qk]`, `_unbracket` returns the full string unchanged. `_parse_filter_column` is already the correct function for this and is used by filters and computed-sorts.

**Files:**
- Modify: `src/tableau2pbir/extract/worksheets.py` (one-line change in `_encodings()`)
- Modify: `tests/unit/extract/test_worksheets.py` (add qualified-ref test for text channel)

---

- [x] **Step 1.1 — Write a failing test for qualified text encoding extraction**

Add to `tests/unit/extract/test_worksheets.py`. Read the existing test file first to see the helpers (`parse_workbook_xml`, `extract_worksheets`) already in use.

```python
_XML_TEXT_ENCODING_QUALIFIED = b"""<?xml version='1.0'?>
<workbook><worksheets>
  <worksheet name='QualifiedText'>
    <table>
      <view>
        <datasources><datasource name='federated.17kv7r10vp81pc1g60xgp0re1it8'/></datasources>
      </view>
      <panes>
        <pane>
          <mark class='Automatic'/>
          <encodings>
            <text column='[federated.17kv7r10vp81pc1g60xgp0re1it8].[sum:profit:qk]'/>
          </encodings>
        </pane>
      </panes>
      <rows>[federated.17kv7r10vp81pc1g60xgp0re1it8].[none:category:nk]</rows>
      <cols />
    </table>
  </worksheet>
</worksheets></workbook>
"""


def test_qualified_text_encoding_extracts_instance_only():
    """Real Tableau XML uses qualified refs for pane encodings.
    _encodings must strip the datasource prefix and return only the column-instance name."""
    root = parse_workbook_xml(_XML_TEXT_ENCODING_QUALIFIED)
    ws = extract_worksheets(root)
    assert ws[0]["encodings"]["text"] == "sum:profit:qk"
```

- [x] **Step 1.2 — Run test to confirm it fails**

```
pytest tests/unit/extract/test_worksheets.py::test_qualified_text_encoding_extracts_instance_only -v
```

Expected: FAIL — `AssertionError: assert '[federated.17kv7r10vp81pc1g60xgp0re1it8].[sum:profit:qk]' == 'sum:profit:qk'`

- [x] **Step 1.3 — Replace `_unbracket` with `_parse_filter_column` in `_encodings()`**

In `src/tableau2pbir/extract/worksheets.py`, find the `_encodings` function and the pane loop (around line 103–112). Change one line:

```python
# BEFORE
col = _unbracket(col)

# AFTER
col = _parse_filter_column(col)
```

The full updated loop block looks like this:

```python
    panes = pane_parent.findall("panes/pane") or pane_parent.findall("pane")
    for pane in panes:
        for ch in pane.findall("encodings/*"):
            col = optional_attr(ch, "column")
            if col is None:
                continue
            col = _parse_filter_column(col)
            if ch.tag == "detail":
                enc["detail"] = (*enc["detail"], col)
            elif ch.tag in {"color", "size", "label", "tooltip", "shape", "angle", "text"}:
                enc[ch.tag] = col
```

No other changes needed — `_parse_filter_column` already exists in the same file.

- [x] **Step 1.4 — Run the new test to confirm it passes**

```
pytest tests/unit/extract/test_worksheets.py::test_qualified_text_encoding_extracts_instance_only -v
```

Expected: PASS.

- [x] **Step 1.5 — Run full unit suite to check no regressions**

```
pytest tests/unit/ -x -q
```

Expected: all PASS.

- [x] **Step 1.6 — Commit**

```bash
git add src/tableau2pbir/extract/worksheets.py tests/unit/extract/test_worksheets.py
git commit -m "fix: use _parse_filter_column for pane encoding channels to handle qualified refs"
```

---

## Task 2 — Add `enc.text` and sort-by fields to `build_field_lookup`

**Root cause:** `build_field_lookup()` in `field_lookup.py` iterates over encoding channel refs to build the slug→PBI mapping, but the loop omits `enc.text` (added in Plan 14) and sort-by fields from `sheet.sort`. Without these entries, `_make_projection` falls back to `Entity: "Model"` for any measure that only appears via text encoding or a computed sort.

**Files:**
- Modify: `src/tableau2pbir/visualmap/field_lookup.py` (two additions to the refs loop)
- Modify: `tests/unit/visualmap/test_field_lookup.py` (add tests for text + sort_by resolution)

---

- [x] **Step 2.1 — Write failing tests for text-encoding and sort_by-field resolution**

Read `tests/unit/visualmap/test_field_lookup.py` first to understand existing helpers.

Add these two tests:

```python
def test_text_encoding_field_resolved_in_lookup():
    """enc.text field ref must appear in build_field_lookup result."""
    from tableau2pbir.ir.sheet import Encoding, Sheet, SortSpec
    from tableau2pbir.ir.common import FieldRef
    from tableau2pbir.visualmap.field_lookup import build_field_lookup

    # Build a minimal Workbook with one table, one column, one sheet where
    # profit only appears via the text encoding (not in rows/cols).
    wb = _make_wb_with_text_encoding("sum_profit_qk")
    result = build_field_lookup(wb)
    assert "sum_profit_qk" in result, "text-encoding field must be in lookup"
    entry = result["sum_profit_qk"]
    assert entry["table_name"] == "orders"
    assert entry["is_measure"] is True


def test_sort_by_field_resolved_in_lookup():
    """sort_by_field ref must appear in build_field_lookup result even if not
    bound to any encoding channel directly."""
    wb = _make_wb_with_sort_by_only("sum_profit_qk")
    result = build_field_lookup(wb)
    assert "sum_profit_qk" in result, "sort_by_field must be in lookup"
```

Add these helpers below the tests (not as test functions):

```python
def _make_wb_with_text_encoding(text_field_id: str):
    """Minimal Workbook where profit only appears in enc.text."""
    from tableau2pbir.ir.common import FieldRef
    from tableau2pbir.ir.model import Column, ColumnRole, DataModel, Table
    from tableau2pbir.ir.sheet import Encoding, Sheet
    from tableau2pbir.ir.workbook import Workbook

    col = Column(
        id="tbl__orders__col__profit",
        name="profit",
        role=ColumnRole.MEASURE,
        data_type="real",
        expr=None,
        source_table="orders",
    )
    table = Table(id="tbl__orders", name="orders", column_ids=("tbl__orders__col__profit",))
    dm = DataModel(tables=(table,), columns=(col,), calculations=())
    fr = FieldRef(table_id="tbl__orders", column_id=text_field_id)
    sheet = Sheet(
        id="sheet__s1", name="S1", datasource_refs=("ds1",),
        mark_type="automatic",
        encoding=Encoding(rows=(), columns=(), text=fr),
        filters=(), sort=(), dual_axis=False, reference_lines=(),
        uses_calculations=(),
    )
    return Workbook(data_model=dm, sheets=(sheet,), dashboards=(), unsupported=())


def _make_wb_with_sort_by_only(sort_by_field_id: str):
    """Minimal Workbook where profit only appears as a sort_by_field."""
    from tableau2pbir.ir.common import FieldRef
    from tableau2pbir.ir.model import Column, ColumnRole, DataModel, Table
    from tableau2pbir.ir.sheet import Encoding, Sheet, SortSpec
    from tableau2pbir.ir.workbook import Workbook

    col = Column(
        id="tbl__orders__col__profit",
        name="profit",
        role=ColumnRole.MEASURE,
        data_type="real",
        expr=None,
        source_table="orders",
    )
    cat_col = Column(
        id="tbl__orders__col__category",
        name="category",
        role=ColumnRole.DIMENSION,
        data_type="string",
        expr=None,
        source_table="orders",
    )
    table = Table(
        id="tbl__orders", name="orders",
        column_ids=("tbl__orders__col__profit", "tbl__orders__col__category"),
    )
    dm = DataModel(tables=(table,), columns=(col, cat_col), calculations=())
    cat_fr = FieldRef(table_id="tbl__orders", column_id="none_category_nk")
    profit_fr = FieldRef(table_id="tbl__orders", column_id=sort_by_field_id)
    sort = SortSpec(field=cat_fr, direction="desc", sort_by_field=profit_fr)
    sheet = Sheet(
        id="sheet__s1", name="S1", datasource_refs=("ds1",),
        mark_type="automatic",
        encoding=Encoding(rows=(cat_fr,), columns=()),
        filters=(), sort=(sort,), dual_axis=False, reference_lines=(),
        uses_calculations=(),
    )
    return Workbook(data_model=dm, sheets=(sheet,), dashboards=(), unsupported=())
```

- [x] **Step 2.2 — Run tests to confirm they fail**

```
pytest tests/unit/visualmap/test_field_lookup.py::test_text_encoding_field_resolved_in_lookup tests/unit/visualmap/test_field_lookup.py::test_sort_by_field_resolved_in_lookup -v
```

Expected: both FAIL — `AssertionError: "sum_profit_qk" not in result`

- [x] **Step 2.3 — Add `enc.text` and sort-by fields to `build_field_lookup`**

In `src/tableau2pbir/visualmap/field_lookup.py`, find the sheet-scanning loop (around line 62–93). Make two additions:

1. Add `enc.text` to the optional-channel loop (line 67).
2. Add sort-by fields after the filter loop.

```python
    # Resolve each FieldRef.column_id seen in sheet encodings and filters
    lookup: dict[str, dict] = {}
    for sheet in wb.sheets:
        enc = sheet.encoding
        refs = list(enc.rows) + list(enc.columns) + list(enc.detail)
        for opt in (enc.color, enc.size, enc.label, enc.tooltip, enc.shape, enc.angle, enc.text):
            if opt:
                refs.append(opt)
        # Also include filter fields so filter emission can resolve pill slugs.
        for f in sheet.filters:
            refs.append(f.field)
        # Include sort-by measure refs so computed-sort emission resolves correctly.
        for s in sheet.sort:
            if s.sort_by_field:
                refs.append(s.sort_by_field)
        for fr in refs:
            field_id = fr.column_id
            if field_id in lookup:
                continue
            m = _PILL_RE.match(field_id)
            if not m:
                continue
            prefix, body, suffix = m.group(1), m.group(2), m.group(3)
            if body not in by_base:
                continue
            base = by_base[body]
            col_name = base["col_name"]
            if suffix == _MEASURE_SUFFIX and prefix in _AGG_PREFIX_DISPLAY:
                measure_name = f"{_AGG_PREFIX_DISPLAY[prefix]} {col_name}"
            else:
                measure_name = col_name
            lookup[field_id] = {**base, "measure_name": measure_name}

    return lookup
```

- [x] **Step 2.4 — Run new tests to confirm they pass**

```
pytest tests/unit/visualmap/test_field_lookup.py::test_text_encoding_field_resolved_in_lookup tests/unit/visualmap/test_field_lookup.py::test_sort_by_field_resolved_in_lookup -v
```

Expected: both PASS.

- [x] **Step 2.5 — Run full unit suite**

```
pytest tests/unit/ -x -q
```

Expected: all PASS.

- [x] **Step 2.6 — Commit**

```bash
git add src/tableau2pbir/visualmap/field_lookup.py tests/unit/visualmap/test_field_lookup.py
git commit -m "fix: add enc.text and sort_by_field refs to build_field_lookup resolution loop"
```

---

## Task 3 — Wire sort into columnChart and barChart dispatch branches

**Root cause:** `_build_sort_entries()` was only wired into the `text` mark and `dim-only bar` branches of `dispatch_visual()`. Sheet 1 is a column chart (ROWS=measure, COLS=dimension, mark=Automatic), which takes the `columnChart` branch. That branch never calls `_build_sort_entries()`, so `PbirVisual.sort_by` is always empty and no `sortDefinition` is emitted.

**Files:**
- Modify: `src/tableau2pbir/visualmap/dispatch.py` (add sort wiring to columnChart + barChart branches)
- Modify: `tests/unit/visualmap/test_dispatch.py` (add sort test for column chart)

---

- [x] **Step 3.1 — Write a failing test for columnChart sort wiring**

Read `tests/unit/visualmap/test_dispatch.py` first to find existing helpers (`_fr`, `Sheet`, `Encoding`, etc.) already imported.

Add this test:

```python
def test_column_chart_with_computed_sort_emits_sort_by():
    """Sheet with ROWS=measure, COLS=dimension, automatic mark and a computed-sort
    must emit a PbirVisual with sort_by populated."""
    from tableau2pbir.ir.sheet import SortSpec

    sh = Sheet(
        id="s1", name="S1", datasource_refs=("ds1",),
        mark_type="automatic",
        encoding=Encoding(
            rows=(_fr("delta_order_qk"),),
            columns=(_fr("none_category_nk"),),
        ),
        filters=(),
        sort=(
            SortSpec(
                field=_fr("none_category_nk"),
                direction="desc",
                sort_by_field=_fr("delta_order_qk"),
            ),
        ),
        dual_axis=False, reference_lines=(), uses_calculations=(),
    )
    pv = dispatch_visual(sh)
    assert pv is not None
    assert pv.visual_type == "columnChart"
    assert pv.sort_by, "sort_by must not be empty for a computed-sort column chart"
    assert len(pv.sort_by) == 1
    entry = pv.sort_by[0]
    assert entry.field_id == "delta_order_qk"
    assert entry.direction == "desc"
    # The sort field is already in Y — no duplicate binding added
    field_ids = [b.source_field_id for b in pv.encoding_bindings]
    assert field_ids.count("delta_order_qk") == 1, "sort field must not appear twice"
```

- [x] **Step 3.2 — Run test to confirm it fails**

```
pytest tests/unit/visualmap/test_dispatch.py::test_column_chart_with_computed_sort_emits_sort_by -v
```

Expected: FAIL — `AssertionError: sort_by must not be empty for a computed-sort column chart`

- [x] **Step 3.3 — Add sort wiring to columnChart and barChart branches**

In `src/tableau2pbir/visualmap/dispatch.py`, find the `mark in ("bar", "automatic") and rows and cols` block (around line 82–93). Replace it:

```python
    if mark in ("bar", "automatic") and rows and cols:
        # Horizontal bar: Tableau places measure on COLUMNS shelf, dimension on ROWS
        if _is_measure(cols[0]) and not _is_measure(rows[0]):
            bindings = [_bind("Category", rows[0])] + [_bind("Y", c) for c in cols]
            if color:
                bindings.append(_bind("Series", color))
            extra_sort, sort_entries = _build_sort_entries(sheet, bindings)
            bindings.extend(extra_sort)
            return PbirVisual(
                visual_type="barChart",
                encoding_bindings=tuple(bindings),
                format=fmt,
                sort_by=sort_entries,
            )
        # Vertical bar (default): COLUMNS=dimension→Category, ROWS=measure(s)→Y
        bindings = [_bind("Category", cols[0])] + [_bind("Y", r) for r in rows]
        if color:
            bindings.append(_bind("Series", color))
        extra_sort, sort_entries = _build_sort_entries(sheet, bindings)
        bindings.extend(extra_sort)
        return PbirVisual(
            visual_type="columnChart",
            encoding_bindings=tuple(bindings),
            format=fmt,
            sort_by=sort_entries,
        )
```

- [x] **Step 3.4 — Run new test to confirm it passes**

```
pytest tests/unit/visualmap/test_dispatch.py::test_column_chart_with_computed_sort_emits_sort_by -v
```

Expected: PASS.

- [x] **Step 3.5 — Run full unit suite**

```
pytest tests/unit/ -x -q
```

Expected: all PASS.

- [x] **Step 3.6 — Commit**

```bash
git add src/tableau2pbir/visualmap/dispatch.py tests/unit/visualmap/test_dispatch.py
git commit -m "fix: wire _build_sort_entries into columnChart and barChart dispatch branches"
```

---

## Task 4 — Integration & E2E verification

- [x] **Step 4.1 — Re-convert `simple_join_sorted_test.twb`**

```
python -m tableau2pbir.cli convert tests/golden/real/simple_join_sorted_test.twb --out out/
```

Expected: exit 0, no errors.

- [x] **Step 4.2 — Verify Sheet 1 visual now has a sortDefinition**

Read `out/simple_join_sorted_test/Report/definition/pages/ReportSection1/visuals/visual_1/visual.json`.

Assert:
- `visual.query.sortDefinition` exists
- `sortDefinition.sort[0].direction` == `"Descending"`
- `sortDefinition.sort[0].field.Measure.Property` == `"DeltaOrder"` (the user-facing calc name)
- `sortDefinition.isDefaultSort` == `false`

- [x] **Step 4.3 — Verify Sheet 4 visual has exactly two Values projections with correct entity**

Read `out/simple_join_sorted_test/Report/definition/pages/ReportSection3/visuals/visual_3/visual.json`.

Assert:
- `visual.query.queryState.Values.projections` has exactly **2** entries (not 3)
- Entry 1: `field.Column.Property` == `"category"`, `Entity` == `"orders"`
- Entry 2: `field.Measure.Property` == `"Sum profit"`, `Entity` == `"orders"`
- `visual.query.sortDefinition.sort[0].field.Measure.Property` == `"Sum profit"`
- `visual.query.sortDefinition.sort[0].direction` == `"Descending"`

- [x] **Step 4.4 — Run real-workbook E2E integration tests**

```
pytest tests/integration/test_real_workbooks_e2e.py -v -m integration
```

Expected: all PASS (or SKIP if no ANTHROPIC_API_KEY).

- [x] **Step 4.5 — Run regression check**

```
python -m tableau2pbir.cli regression-check
```

Expected: `No regressions found` for all corpus entries (`simple_join`, `simple_join_dashboard`, `simple_join_few_filter`).

- [x] **Step 4.6 — Commit**

```bash
git add -A
git commit -m "test: verify Sheet 1 sort and Sheet 4 profit emission after encoding/dispatch fixes"
```

---

## Self-Review

**Spec coverage:**
- Issue 1 (Sheet 1 no sort) → Task 3 ✓
- Issue 2 (Sheet 4 profit blank / wrong entity) → Task 1 (extraction) + Task 2 (field_lookup) ✓
- E2E verification → Task 4 ✓

**Placeholder scan:** None found — all steps contain full code.

**Type consistency check:**
- `_parse_filter_column` already defined in `worksheets.py` — no import changes needed ✓
- `VisualSortEntry`, `_build_sort_entries` already defined from Plan 14 — no new types ✓
- `SortSpec.sort_by_field: FieldRef | None` already in `ir/sheet.py` from Plan 14 ✓
- `Encoding.text: FieldRef | None` already in `ir/sheet.py` from Plan 14 ✓
- `PbirVisual.sort_by: tuple[VisualSortEntry, ...]` already in `ir/sheet.py` from Plan 14 ✓
- `build_field_lookup` signature unchanged — returns `dict[str, dict]` ✓

**Test helper scope:** The `_make_wb_with_text_encoding` and `_make_wb_with_sort_by_only` helpers in Task 2 reference `Column`, `ColumnRole`, `DataModel`, `Table` from `tableau2pbir.ir.model` and `Workbook` from `tableau2pbir.ir.workbook`. Read the existing test file first to confirm what's already imported before adding these helpers.
