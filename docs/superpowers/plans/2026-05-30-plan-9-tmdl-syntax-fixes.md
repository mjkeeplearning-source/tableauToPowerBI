# Plan 9: TMDL Syntax Fixes — PBI Desktop Openability

> **Execution mode: Inline** — use `superpowers:executing-plans` in the same session. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix four confirmed TMDL/PBIR emission bugs so that PBI Desktop can open the converted output without errors.

**Architecture:** All bugs are isolated to individual emitter modules (`measure.py`, `column.py`, `page.py`, `model.py`). Each fix is a targeted rewrite of a single render function. TDD: update tests to assert correct TMDL syntax first (RED), then fix the emitter (GREEN), then commit.

**Tech Stack:** Python 3.11+, pytest, TMDL spec (Microsoft tabular model definition language)

---

## Background: What's Broken and Why

TMDL requires DAX expressions to appear **inline** on the declaration line, not as a child property:

```
# WRONG (what the code currently emits):
    measure 'Total Sales'
        expression: SUM('Sales'[Sales])

# CORRECT (what TMDL requires):
    measure 'Total Sales' = SUM('Sales'[Sales])
```

The same bug exists in calculated columns. PBI Desktop's TMDL parser rejects the model entirely when `expression:` is used, so no workbook can open. There are four bugs total — two are fatal blockers, two are lower severity.

---

## Files Modified

| File | Change |
|------|--------|
| `src/tableau2pbir/emit/tmdl/measure.py` | Replace `expression:` sub-property with `= DAX` inline syntax |
| `src/tableau2pbir/emit/tmdl/column.py` | Replace `expression:` sub-property with `= DAX` inline for calculated columns |
| `src/tableau2pbir/emit/pbir/page.py` | Omit `filterConfig` key when there are no filters |
| `src/tableau2pbir/emit/tmdl/model.py` | Remove `sourceQueryCulture`, `dataAccessOptions` block |
| `tests/unit/emit/tmdl/test_measure.py` | Rewrite to assert correct TMDL syntax |
| `tests/unit/emit/tmdl/test_column.py` | Update `test_calculated_column` to assert inline `= DAX` |
| `tests/unit/emit/tmdl/test_model.py` | Remove assertion for `sourceQueryCulture`; add negative assertions |
| `tests/unit/emit/pbir/test_page.py` | Add test asserting `filterConfig` is absent when no filters |
| `tests/unit/emit/tmdl/test_render.py` | Strengthen implicit measure assertion to check inline syntax |

---

## Task 1: Fix TMDL Measure Syntax (Bug #1 — PRIMARY BLOCKER)

Measures currently emit `expression: DAX` as a nested property. TMDL requires `= DAX` on the declaration line.

**Files:**
- Modify: `src/tableau2pbir/emit/tmdl/measure.py`
- Modify: `tests/unit/emit/tmdl/test_measure.py`
- Modify: `tests/unit/emit/tmdl/test_render.py` (strengthen one assertion)

- [x] **Step 1: Rewrite `test_measure.py` to assert correct TMDL syntax**

Replace the entire contents of `tests/unit/emit/tmdl/test_measure.py` with:

```python
from tableau2pbir.emit.tmdl.measure import render_measure
from tableau2pbir.ir.calculation import Calculation, CalculationKind, CalculationPhase, CalculationScope


def test_single_line_measure_uses_equals_syntax():
    calc = Calculation(
        id="m1", name="Total Sales", scope=CalculationScope.MEASURE,
        tableau_expr="SUM([Sales])", dax_expr="SUM('Sales'[Sales])",
        kind=CalculationKind.AGGREGATE, phase=CalculationPhase.AGGREGATE,
    )
    out = render_measure(calc)
    assert out == "\tmeasure 'Total Sales' = SUM('Sales'[Sales])\n"


def test_measure_with_no_dax_returns_empty():
    calc = Calculation(
        id="m2", name="Deferred Calc", scope=CalculationScope.MEASURE,
        tableau_expr="WINDOW_SUM(SUM([x]))", dax_expr=None,
        kind=CalculationKind.TABLE_CALC, phase=CalculationPhase.VIZ,
    )
    assert render_measure(calc) == ""


def test_single_line_measure_no_expression_sub_property():
    calc = Calculation(
        id="m3", name="Count Orders", scope=CalculationScope.MEASURE,
        tableau_expr="COUNTD([order_id])", dax_expr="DISTINCTCOUNT('Orders'[order_id])",
        kind=CalculationKind.AGGREGATE, phase=CalculationPhase.AGGREGATE,
    )
    out = render_measure(calc)
    assert out == "\tmeasure 'Count Orders' = DISTINCTCOUNT('Orders'[order_id])\n"
    assert "expression:" not in out


def test_multiline_measure_declaration_line_ends_with_equals():
    dax = "VAR x = SUM('T'[a])\nRETURN x"
    calc = Calculation(
        id="m4", name="Complex", scope=CalculationScope.MEASURE,
        tableau_expr="...", dax_expr=dax,
        kind=CalculationKind.AGGREGATE, phase=CalculationPhase.AGGREGATE,
    )
    out = render_measure(calc)
    lines = out.splitlines()
    assert lines[0] == "\tmeasure Complex ="
    assert lines[1] == "\t\t\tVAR x = SUM('T'[a])"
    assert lines[2] == "\t\t\tRETURN x"
    assert "expression:" not in out


def test_column_scope_is_not_a_measure():
    calc = Calculation(
        id="c1", name="Row Calc", scope=CalculationScope.COLUMN,
        tableau_expr="[A]+[B]", dax_expr="'T'[A]+'T'[B]",
        kind=CalculationKind.ROW, phase=CalculationPhase.ROW,
    )
    assert render_measure(calc) == ""
```

- [x] **Step 2: Strengthen assertion in `test_render.py`**

In `tests/unit/emit/tmdl/test_render.py`, in `test_implicit_measure_emitted_in_tmdl`, add one line asserting the inline `= DAX` form. The function currently ends:

```python
    assert "measure 'Sum profit'" in tmdl, f"Expected quoted 'measure Sum profit', got:\n{tmdl}"
    assert "SUM('orders'[profit])" in tmdl
    assert "measure profit\n" not in tmdl, "Raw column name must not be a measure name"
```

Replace it with:

```python
    assert "measure 'Sum profit' = SUM('orders'[profit])" in tmdl, (
        f"Measure must use inline '= DAX' syntax, got:\n{tmdl}"
    )
    assert "expression:" not in tmdl, "TMDL must not use 'expression:' sub-property for measures"
    assert "measure profit\n" not in tmdl, "Raw column name must not be a measure name"
```

- [x] **Step 3: Run tests to confirm RED**

```
pytest tests/unit/emit/tmdl/test_measure.py tests/unit/emit/tmdl/test_render.py -v
```

Expected: `test_single_line_measure_uses_equals_syntax` FAILS, `test_single_line_measure_no_expression_sub_property` FAILS, `test_multiline_measure_declaration_line_ends_with_equals` FAILS, `test_implicit_measure_emitted_in_tmdl` FAILS.

- [x] **Step 4: Rewrite `measure.py`**

Replace the entire contents of `src/tableau2pbir/emit/tmdl/measure.py` with:

```python
"""Render a measure block (nested under a table)."""
from __future__ import annotations

from tableau2pbir.emit.tmdl.escape import tmdl_ident
from tableau2pbir.ir.calculation import Calculation, CalculationScope


def render_measure(calc: Calculation) -> str:
    if calc.scope != CalculationScope.MEASURE or not calc.dax_expr:
        return ""
    name_q = tmdl_ident(calc.name)
    dax = calc.dax_expr.strip()
    if "\n" not in dax:
        return f"\tmeasure {name_q} = {dax}\n"
    lines = [f"\tmeasure {name_q} ="]
    for line in dax.splitlines():
        if not line.strip():
            lines.append("")
        else:
            leading = len(line) - len(line.lstrip())
            lines.append("\t\t\t" + " " * leading + line.lstrip())
    return "\n".join(lines) + "\n"
```

- [x] **Step 5: Run tests to confirm GREEN**

```
pytest tests/unit/emit/tmdl/test_measure.py tests/unit/emit/tmdl/test_render.py -v
```

Expected: all 8 tests PASS.

- [x] **Step 6: Commit**

```
git add src/tableau2pbir/emit/tmdl/measure.py tests/unit/emit/tmdl/test_measure.py tests/unit/emit/tmdl/test_render.py
git commit -m "fix(tmdl): use '= DAX' inline syntax for measures — replaces invalid 'expression:' sub-property"
```

---

## Task 2: Fix TMDL Calculated Column Syntax (Bug #2)

Calculated columns emit `expression: DAX` as a body property. TMDL requires `= DAX` inline on the column declaration, with `dataType` as the only sub-property.

**Files:**
- Modify: `src/tableau2pbir/emit/tmdl/column.py`
- Modify: `tests/unit/emit/tmdl/test_column.py`

- [x] **Step 1: Update `test_calculated_column` in `test_column.py`**

In `tests/unit/emit/tmdl/test_column.py`, replace the `test_calculated_column` function:

```python
def test_calculated_column():
    col = Column(
        id="c2", name="Region Upper", datatype="string",
        role=ColumnRole.DIMENSION, kind=ColumnKind.CALCULATED,
        tableau_expr="UPPER([Region])",
        dax_expr="UPPER('Sales'[Region])",
    )
    out = render_column(col)
    # TMDL calculated column: declaration line carries = DAX, dataType is sub-property
    assert "\tcolumn 'Region Upper' = UPPER('Sales'[Region])\n" in out
    assert "\t\tdataType: string" in out
    assert "expression:" not in out
```

- [x] **Step 2: Run test to confirm RED**

```
pytest tests/unit/emit/tmdl/test_column.py::test_calculated_column -v
```

Expected: FAIL — `expression: UPPER('Sales'[Region])` is still emitted by current code.

- [x] **Step 3: Rewrite `column.py`**

Replace the entire contents of `src/tableau2pbir/emit/tmdl/column.py` with:

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
    "date":     "dateTime",
    "boolean":  "boolean",
    "string":   "string",
}


def render_column(col: Column) -> str:
    if col.datatype == "table":
        return ""
    if col.kind == ColumnKind.CALCULATED and col.dax_expr is None:
        return ""
    tmdl_type = _DATATYPE_MAP.get(col.datatype, col.datatype)
    if col.kind == ColumnKind.CALCULATED:
        col_name = col.name
        name_q = tmdl_ident(col_name)
        dax = col.dax_expr.strip()
        body = indent(f"dataType: {tmdl_type}", "\t\t")
        return f"\tcolumn {name_q} = {dax}\n{body}\n"
    col_name = col.source_column if col.source_column is not None else col.name
    body_lines = [f"dataType: {tmdl_type}", f"sourceColumn: {col_name}"]
    head = "column " + tmdl_ident(col_name)
    body = indent("\n".join(body_lines), "\t\t")
    return f"\t{head}\n{body}\n"
```

- [x] **Step 4: Run full `test_column.py` to confirm GREEN**

```
pytest tests/unit/emit/tmdl/test_column.py -v
```

Expected: all 11 tests PASS (the RAW column tests are unaffected by the change to the CALCULATED path).

- [x] **Step 5: Commit**

```
git add src/tableau2pbir/emit/tmdl/column.py tests/unit/emit/tmdl/test_column.py
git commit -m "fix(tmdl): use '= DAX' inline syntax for calculated columns — replaces invalid 'expression:' sub-property"
```

---

## Task 3: Fix Empty `filterConfig` in `page.py` (Bug #3)

`page.py` always emits `"filterConfig": {"filters": []}` even when there are no filters. The PBIR page schema does not require this key when filters are absent, and emitting an empty one may cause warnings in strict PBI Desktop schema validation.

**Files:**
- Modify: `src/tableau2pbir/emit/pbir/page.py`
- Modify: `tests/unit/emit/pbir/test_page.py`

- [x] **Step 1: Add failing test to `test_page.py`**

Append to `tests/unit/emit/pbir/test_page.py`:

```python
def test_page_json_no_filter_config_when_no_filters():
    out = render_page(page_id="p1", display_name="Revenue", width=1280, height=720)
    obj = json.loads(out)
    assert "filterConfig" not in obj, (
        f"filterConfig must be omitted when there are no filters, got keys: {list(obj.keys())}"
    )


def test_page_json_filter_config_present_when_filters_given():
    filters = [{"type": "Categorical"}]
    out = render_page(page_id="p1", display_name="Revenue", width=1280, height=720, filters=filters)
    obj = json.loads(out)
    assert "filterConfig" in obj
    assert obj["filterConfig"]["filters"] == filters
```

- [x] **Step 2: Run test to confirm RED**

```
pytest tests/unit/emit/pbir/test_page.py::test_page_json_no_filter_config_when_no_filters -v
```

Expected: FAIL — current code always emits `filterConfig`.

- [x] **Step 3: Fix `page.py`**

Replace the entire contents of `src/tableau2pbir/emit/pbir/page.py` with:

```python
"""Render pages/<page>/page.json."""
from __future__ import annotations

import json


def render_page(page_id: str, display_name: str, width: int, height: int,
                filters: list | None = None) -> str:
    obj = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json",
        "name": page_id,
        "displayName": display_name,
        "displayOption": "FitToPage",
        "width": width,
        "height": height,
    }
    if filters:
        obj["filterConfig"] = {"filters": filters}
    return json.dumps(obj, indent=2)
```

- [x] **Step 4: Run full `test_page.py` to confirm GREEN**

```
pytest tests/unit/emit/pbir/test_page.py -v
```

Expected: all 5 tests PASS.

- [x] **Step 5: Commit**

```
git add src/tableau2pbir/emit/pbir/page.py tests/unit/emit/pbir/test_page.py
git commit -m "fix(pbir): omit filterConfig from page.json when there are no filters"
```

---

## Task 4: Remove Extra Properties from `model.tmdl` (Bug #5)

`model.py` emits `sourceQueryCulture`, `dataAccessOptions`, `legacyRedirects`, `returnErrorValuesAsNull`. These are not in the minimal MVP output and may cause warnings or failures with some PBI Desktop versions.

**Files:**
- Modify: `src/tableau2pbir/emit/tmdl/model.py`
- Modify: `tests/unit/emit/tmdl/test_model.py`

- [x] **Step 1: Update `test_model.py` to assert correct (minimal) output**

Replace the entire contents of `tests/unit/emit/tmdl/test_model.py` with:

```python
from tableau2pbir.emit.tmdl.model import render_model


def test_model_tmdl_includes_culture_and_default_version():
    out = render_model(culture="en-US")
    assert "model Model" in out
    assert "culture: en-US" in out
    assert "defaultPowerBIDataSourceVersion: powerBI_V3" in out


def test_model_tmdl_custom_culture():
    out = render_model(culture="fr-FR")
    assert "culture: fr-FR" in out


def test_model_tmdl_no_extra_properties():
    out = render_model()
    assert "sourceQueryCulture" not in out, "sourceQueryCulture must not be emitted"
    assert "dataAccessOptions" not in out, "dataAccessOptions block must not be emitted"
    assert "legacyRedirects" not in out
    assert "returnErrorValuesAsNull" not in out
```

- [x] **Step 2: Run test to confirm RED**

```
pytest tests/unit/emit/tmdl/test_model.py::test_model_tmdl_no_extra_properties -v
```

Expected: FAIL — current code emits all of those properties.

- [x] **Step 3: Fix `model.py`**

Replace the entire contents of `src/tableau2pbir/emit/tmdl/model.py` with:

```python
"""Render model.tmdl."""
from __future__ import annotations


def render_model(culture: str = "en-US") -> str:
    return (
        "model Model\n"
        f"\tculture: {culture}\n"
        "\tdefaultPowerBIDataSourceVersion: powerBI_V3\n"
    )
```

- [x] **Step 4: Run full `test_model.py` to confirm GREEN**

```
pytest tests/unit/emit/tmdl/test_model.py -v
```

Expected: all 3 tests PASS.

- [x] **Step 5: Commit**

```
git add src/tableau2pbir/emit/tmdl/model.py tests/unit/emit/tmdl/test_model.py
git commit -m "fix(tmdl): remove sourceQueryCulture and dataAccessOptions from model.tmdl"
```

---

## Task 5: Full Suite + E2E Gate

Verify nothing regressed and the real-workbook E2E tests still pass.

**Files:** None modified.

- [x] **Step 1: Run the full test suite**

```
pytest tests/ -x -q
```

Expected: all tests pass. Note the final count — it should be ≥ 457 (the count before this plan). If any test fails unexpectedly, stop and investigate before continuing.

- [x] **Step 2: Run the real-workbook E2E gate**

```
pytest tests/integration/test_real_workbooks_e2e.py -v
```

Expected: all 18 E2E tests pass. These run the full pipeline on real `.twb` files and check structural output.

- [x] **Step 3: Inspect generated TMDL output for one workbook**

```
python -m tableau2pbir convert tests/golden/real/simple_join_calculated_line.twb --out /tmp/plan9_test
```

Then read the table TMDL file:

```
cat /tmp/plan9_test/simple_join_calculated_line/SemanticModel/definition/tables/*.tmdl
```

Confirm:
- Every `measure` line reads `measure Name = DAX` (no `expression:` sub-property)
- Every calculated column reads `column Name = DAX` on the declaration line
- `model.tmdl` contains only `model Model`, `culture:`, `defaultPowerBIDataSourceVersion:`
- Page JSON files do NOT contain `filterConfig` (unless that workbook has sheet filters)

- [x] **Step 4: Update CLAUDE.md to mark Plan 9 complete**

In `CLAUDE.md`, add Plan 9 to the implementation tracking table:

```markdown
| 9 | TMDL Syntax Fixes — PBI Desktop Openability | ✅ DONE | `docs/superpowers/plans/2026-05-30-plan-9-tmdl-syntax-fixes.md` |
```

- [x] **Step 5: Final commit**

```
git add CLAUDE.md
git commit -m "docs: mark Plan 9 complete — TMDL syntax fixes landed"
```

---

## Bug #4 — Not Implemented (Verify After Plan 9)

Bug #4 (`is_measure` field type for implicit measures) is **conditional** — it only manifests if a numeric column is incorrectly classified as `ColumnRole.DIMENSION` in Stage 2. After this plan lands, open `simple_join_calculated_line.pbip` in PBI Desktop and confirm visuals render with data. If a measure appears as a `Column` projection instead of a `Measure` projection (visible in PBI Desktop's field well with a sigma vs table icon), then Bug #4 is active and needs a separate investigation of `_build_data_model.py`'s `_column_role()` function. No code change is needed in this plan.
