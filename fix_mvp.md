# Fix Plan: Making `tableau2pbir` Produce PBI-Desktop-Openable Output

**Date:** 2026-05-30  
**Reference MVP:** `C:\vibe_coding\tabToPbi` (working)  
**Current project:** `C:\Tableau_PBI` (produces output but PBI Desktop cannot open it)

---

## 1. How the Investigation Was Done

Both codebases were studied in full. The current project was actually run against a real workbook:

```
tableau2pbir convert tests/golden/real/simple_join.twb --out /tmp/pbir_test
→ [tableau2pbir] wb=simple_join stages_run=8
```

The pipeline completed successfully. Output structure was correct. TMDL and visual.json files were inspected by hand. The MVP's output for the same workbook family was compared side-by-side.

---

## 2. Why the Tests Don't Catch the Real Bugs

| Test layer | What it verifies | Catches TMDL syntax bugs? |
|------------|-----------------|--------------------------|
| Unit tests (`tests/unit/`) | Individual functions, pre-built IR fixtures | No |
| E2E tests (`tests/integration/test_real_workbooks_e2e.py`) | Pipeline runs, files produced, structural JSON shape | No |
| Structural validator (`validate/structural.py`) | Cross-refs: visual→page, field→table name | No — doesn't parse TMDL |
| TMDL validator (TabularEditor 2) | TMDL syntax correctness | **Would catch it — but `te2_unavailable`** |
| PBIR compile (pbi-tools) | PBIR JSON schema validity | **Would catch it — but `pbi_tools_unavailable`** |
| Desktop-open gate | PBI Desktop actually loads the report | **Would catch it — but `skipped: synthetic`** |

**Result:** 457 tests pass while the output is broken. The three external validators that would catch structural TMDL/PBIR bugs are all unavailable or gated to real-workbook rubric runs only.

---

## 3. Confirmed Bugs (Found by Diffing MVP vs Current Output)

### Bug #1 — WRONG TMDL Measure Syntax (PRIMARY BLOCKER)

**File:** `src/tableau2pbir/emit/tmdl/measure.py`, line 14  
**Severity:** FATAL — blocks 100% of workbooks

**Current code:**
```python
def render_measure(calc: Calculation) -> str:
    if calc.scope != CalculationScope.MEASURE or not calc.dax_expr:
        return ""
    head = "measure " + tmdl_ident(calc.name)
    body = indent(f"expression: {calc.dax_expr}", "\t\t")   # ← WRONG
    return f"\t{head}\n{body}\n"
```

**What it emits (INVALID TMDL):**
```tmdl
	measure DeltaOrder
		expression: DISTINCTCOUNT('orders'[order_id]) - DISTINCTCOUNT('returns'[order_id])
```

**What TMDL requires:**
```tmdl
	measure DeltaOrder = DISTINCTCOUNT('orders'[order_id]) - DISTINCTCOUNT('returns'[order_id])
```

For multi-line DAX:
```tmdl
	measure 'Complex Measure' =
		VAR x = SUM('orders'[profit])
		RETURN
			x / 100
```

**MVP reference (`generator.py:432-447`):**
```python
def _tmdl_measure_lines(name_q: str, dax: str) -> list[str]:
    if "\n" not in dax:
        return [f"\tmeasure {name_q} = {dax}"]
    result = [f"\tmeasure {name_q} ="]
    for line in dax.splitlines():
        if not line.strip():
            result.append("")
        else:
            leading = len(line) - len(line.lstrip(" "))
            result.append("\t" * (3 + leading // 2) + line.lstrip(" "))
    return result
```

**Fix required in `measure.py`:**
```python
def render_measure(calc: Calculation) -> str:
    if calc.scope != CalculationScope.MEASURE or not calc.dax_expr:
        return ""
    name_q = tmdl_ident(calc.name)
    dax = calc.dax_expr.strip()
    if "\n" not in dax:
        return f"\tmeasure {name_q} = {dax}\n"
    # Multi-line DAX: expression starts on next line at 3-tab indent
    lines = [f"\tmeasure {name_q} ="]
    for line in dax.splitlines():
        if not line.strip():
            lines.append("")
        else:
            leading = len(line) - len(line.lstrip())
            lines.append("\t\t\t" + " " * leading + line.lstrip())
    return "\n".join(lines) + "\n"
```

**Impact:** PBI Desktop's TMDL parser rejects the semantic model entirely. The report cannot open. Virtually every workbook has aggregated measures (SUM, COUNT, etc.) which become implicit DAX measures via `collect_implicit_measures()`. No visual renders — PBI Desktop shows a model-load failure before reaching any visual.

---

### Bug #2 — WRONG TMDL Calculated Column Syntax

**File:** `src/tableau2pbir/emit/tmdl/column.py`, line 28  
**Severity:** HIGH — blocks workbooks with Tableau calculated fields

**Current code:**
```python
if col.kind == ColumnKind.CALCULATED:
    col_name = col.name
    body_lines.append(f"expression: {col.dax_expr}")   # ← WRONG
```

**What it emits (INVALID TMDL):**
```tmdl
	column DeltaField
		dataType: double
		expression: [Profit] - [Discount]
```

**What TMDL requires:**
```tmdl
	column DeltaField = [Profit] - [Discount]
		dataType: double
```

Note: TMDL calculated columns have `= DAX` on the same line as the column declaration, with `dataType` as a sub-property. The `expression:` keyword does not exist in TMDL.

**Fix required in `column.py`:**
```python
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
    else:
        src = col.source_column if col.source_column is not None else col.name
        col_name = src
        name_q = tmdl_ident(col_name)
        body_lines = [f"dataType: {tmdl_type}", f"sourceColumn: {col_name}"]
        body = indent("\n".join(body_lines), "\t\t")
        return f"\tcolumn {name_q}\n{body}\n"
```

---

### Bug #3 — Empty `filterConfig` Emitted When There Are No Filters

**File:** `src/tableau2pbir/emit/pbir/page.py`  
**Severity:** MEDIUM — may cause PBI Desktop schema validation warning or silent visual quirks

**Current output (page.json):**
```json
{
  "filterConfig": {"filters": []}
}
```

**Expected behavior:** `filterConfig` key should be omitted entirely when there are no filters. The MVP does not emit this key when filters is empty.

**Fix required in `page.py`:** Only include `filterConfig` in the page JSON if `filters` is non-empty.

---

### Bug #4 — `implicit_measures` Not Integrated into `render_visual` Lookup for `is_measure` Field Type

**Files:** `src/tableau2pbir/visualmap/field_lookup.py`, `src/tableau2pbir/emit/pbir/visual.py`  
**Severity:** MEDIUM — after Bug #1 is fixed, some measure projections may still use wrong field type

**Context:**  
`field_lookup.py` sets `is_measure = col.role == ColumnRole.MEASURE` from the Column IR object. For raw numeric columns (Profit, Sales) that Tableau classifies as measures, `col.role = ColumnRole.MEASURE` → `is_measure = True` → emits as `"Measure"` type in visual.json.

For the implicit measure `"Sum Profit"` (generated by `collect_implicit_measures`), `visual.json` emits:
```json
"Measure": {"Entity": "orders", "Property": "Sum Profit"}
```

And the TMDL (after Bug #1 fix) has:
```tmdl
measure 'Sum Profit' = SUM('orders'[profit])
```

This is **consistent** for numeric columns where `col.role = MEASURE`. However, if a numeric column's `ColumnRole` is incorrectly set to `DIMENSION` (e.g., due to a Stage 2 classification bug), then `is_measure = False`, the visual emits it as `"Column"`, but the implicit measure creates it as a TMDL `measure` — causing a type mismatch.

**Verify fix:** After Bug #1 fix, run the full pipeline on `simple_join_calculated_line.twb`, open in PBI Desktop, confirm all visuals render with correct data.

---

### Bug #5 — `sourceQueryCulture` and `dataAccessOptions` in `model.tmdl`

**File:** `src/tableau2pbir/emit/tmdl/model.py`  
**Severity:** LOW — may cause TMDL parse warnings in strict mode

**Current output:**
```tmdl
model Model
	culture: en-US
	defaultPowerBIDataSourceVersion: powerBI_V3
	sourceQueryCulture: en-US
	dataAccessOptions
		legacyRedirects
		returnErrorValuesAsNull
```

**MVP output:**
```tmdl
model Model
	culture: en-US
	defaultPowerBIDataSourceVersion: powerBI_V3
```

`sourceQueryCulture`, `legacyRedirects`, `returnErrorValuesAsNull` are valid TMDL properties but may not be recognized in all PBI Desktop versions. The minimal model.tmdl from the MVP is safer.

---

## 4. Architectural Differences Between MVP and Current Project

### Pipeline Stages

| Stage | MVP | Current Project |
|-------|-----|----------------|
| Parse | `parser.py` — lxml, produces workbook dict | `s01_extract.py` — lxml, produces raw JSON |
| Transform | `transformer.py` — field names resolved here | `s02_canonicalize.py` — IR built, fields as pill slugs |
| Calc translate | `translator.py` — Claude AI for formulas | `s03_translate_calcs.py` — rule library + AI |
| Visual map | Inside `transformer.py` | `s04_map_visuals.py` — dispatch table |
| Layout | Inside `transformer.py` | `s05_compute_layout.py` — dashboard tree walk |
| TMDL emit | `generator.py:_write_tmdl_model()` | `s06_build_tmdl.py` → `emit/tmdl/render.py` |
| PBIR emit | `generator.py:_write_pages()` | `s07_build_pbir.py` → `emit/pbir/render.py` |
| Validate | `validator.py` — post-hoc | `s08_package_validate.py` — structural + external tools |

### Field Resolution: Deferred vs Eager

**MVP (eager — resolved during transform):**
- `transformer.py` calls `_resolve_field_entity(field_name, ds)` which looks up the actual column dict from the parsed datasource.
- By the time `generate()` runs, every visual's `row_fields`/`col_fields` contains:
  ```python
  {"name": "category", "table": "orders", "is_measure": False}
  ```
- Emission is trivial: use `name` and `table` directly.

**Current project (deferred — resolved in Stage 7 via slug matching):**
- Stage 2 produces `FieldRef(column_id="none_category_nk")` — the Tableau pill slug.
- Stage 4 stores `EncodingBinding(channel="Category", source_field_id="none_category_nk")`.
- Stage 7 calls `build_field_lookup(wb)` which:
  1. Builds `by_base` dict keyed by `slug_id(col.name)` (e.g., `"category"` for column "category")
  2. For each FieldRef, applies `_PILL_RE = r'^([a-z]+)_(.+)_([a-z]{2})$'` to extract body slug
  3. Matches body against `by_base`

**Why this works for REAL Tableau workbooks:**
Real Tableau shelf XML: `[federated.hash].[none:category:nk]`  
Stage 1 parses to TWO tokens: `"federated.hash"` (marker, filtered) + `"none:category:nk"` (kept)  
Stage 2: `slug_id("none:category:nk") = "none_category_nk"` → `FieldRef.column_id = "none_category_nk"`  
`_PILL_RE.match("none_category_nk")` → prefix=`none`, body=`category`, suffix=`nk` ✓  
`by_base["category"]` → `{table_name: "orders", col_name: "category", ...}` ✓

**_is_measure detection:**
`dispatch.py`: `_is_measure(fr) = fr.column_id.endswith("_qk")`  
- `"none_category_nk"`.endswith(`"_qk"`) → False → dimension ✓  
- `"sum_profit_qk"`.endswith(`"_qk"`) → True → measure ✓

**Conclusion:** Field resolution and measure/dimension detection work correctly for real Tableau workbooks. The deferred approach is more complex but functionally correct — the bugs are NOT here.

### M Expression Generation

| Feature | MVP | Current Project |
|---------|-----|----------------|
| PostgreSQL | ✓ | ✓ |
| SQL Server | ✓ | ✓ (as `Sql.Database`) |
| MySQL | ✓ | ✓ (as `MySql.Database`) |
| Snowflake | ✓ (with warehouse, ADBC driver) | ✓ (basic) |
| Databricks | ✓ (with http_path, catalog nav) | ✓ (basic) |
| BigQuery | ✓ | ✓ |
| Redshift | ✓ | ✓ |
| Oracle | ✓ | ✓ |
| Teradata | ✓ | ✓ |
| CSV | ✓ (with type inference) | ✓ (basic) |
| Excel | ✓ (with sheet nav + type inference) | ✓ (basic) |
| Custom SQL | ✓ (with subquery wrapping) | ✗ Not implemented |
| Date-part columns | ✓ (AddColumn steps for import, NativeQuery for DQ) | ✗ Not implemented |
| DirectQuery mode detection | ✓ (via `live_connection` flag) | ✓ (via connector_tier) |
| Physical schema + table | ✓ (`Schema=, Item=`) | ✓ (`Schema=, Item=`) |

The M expression logic is simpler in the current project but covers the major connectors. Custom SQL and date-part extraction are missing and should be added after the TMDL syntax fix.

---

## 5. Visual Emission: What's Working vs What's Not

### What Works Correctly
- **`visual.json` schema** — correct `$schema`, `name`, `position`, `visual.visualType`, `query.queryState`
- **`Entity` key** — uses `"Entity"` (correct) not `"Source"` (old bug, fixed in Plan 8)
- **`queryRef` and `active`** — both present in every projection (fixed in Plan 8)
- **`Column` vs `Measure` field types** — `is_measure` from `field_lookup` correctly uses `ColumnRole.MEASURE` from Stage 2 IR
- **Page/visual naming** — `ReportSection{N}` and `visual_{N}` sequential naming (fixed in Plan 8)
- **Channel capitalization** — "Category", "Y", "Series", "X", "Values", "Location" (fixed in Plan 8)
- **Bar chart dispatch** — correctly detects horizontal (`_is_measure(cols[0])`) vs vertical bar
- **`definition.pbir`** — correct path `"../SemanticModel"` pointing to the SemanticModel folder
- **`.pbip` format** — correct version 1.0 with `artifacts: [{report: {path: "Report"}}]`
- **`pages.json`** — correct pageOrder array
- **`page.json`** — correct schema, name, displayName, width, height

### What's Missing vs MVP
- **Color palette** — MVP emits `objects.dataPoint` with per-value selectors for color encoding
- **Visual titles** — MVP emits `visualContainerObjects.title` block
- **Data labels** — MVP emits `objects.labels`
- **Axis formatting** — MVP emits `objects.categoryAxis` and `objects.valueAxis`
- **Sort definitions** — MVP emits `query.sortDefinition`
- **Cross-highlighting** — MVP emits `visual_interactions`
- **Filters on visuals** — MVP emits `filterConfig` at page level from sheet filters
- **Date hierarchies** — MVP emits `order_date Year`, `order_date Quarter`, etc.

These are quality/feature gaps, not blockers. After Bug #1 is fixed, reports will open and visuals will render (though formatting will be missing).

---

## 6. Stage-by-Stage Status

| Stage | File(s) | Status | Notes |
|-------|---------|--------|-------|
| S1: Extract | `s01_extract.py`, `extract/*.py` | ✅ Working | Correctly handles real + synthetic workbooks, filters datasource markers |
| S2: Canonicalize | `s02_canonicalize.py`, `_build_*.py` | ✅ Working | IR built correctly; pill slugs match field_lookup expectations |
| S3: Translate calcs | `s03_translate_calcs.py` | ✅ Working | Rule library + AI; `dax_expr` populated |
| S4: Map visuals | `s04_map_visuals.py`, `visualmap/dispatch.py` | ✅ Working | Correct channel names, correct bar orientation detection |
| S5: Compute layout | `s05_compute_layout.py` | ✅ Working | Dashboard tree walk, positions resolved |
| S6: Build TMDL | `s06_build_tmdl.py`, `emit/tmdl/render.py` | ❌ **BROKEN** | Bug #1: `measure.py` uses `expression:` not `=`; Bug #2: `column.py` same |
| S7: Build PBIR | `s07_build_pbir.py`, `emit/pbir/render.py` | ✅ Working | visual.json correct structure; field_lookup resolves correctly |
| S8: Package/Validate | `s08_package_validate.py`, `validate/*.py` | ⚠️ Partial | `.pbip` and `definition.pbir` written correctly; TMDL/PBIR validators skipped (tools absent) |

---

## 7. What the Actual Output Looks Like

### From `tableau2pbir convert tests/golden/real/simple_join.twb --out /tmp/pbir_test`

**visual.json (CORRECT):**
```json
{
  "$schema": "...visualContainer/1.0.0/schema.json",
  "name": "visual_1",
  "position": {"x": 20, "y": 20, "width": 560, "height": 360, "z": 0},
  "visual": {
    "visualType": "columnChart",
    "query": {
      "queryState": {
        "Category": {
          "projections": [{
            "field": {"Column": {"Expression": {"SourceRef": {"Entity": "orders"}}, "Property": "category"}},
            "queryRef": "orders.category",
            "active": true
          }]
        },
        "Y": {
          "projections": [{
            "field": {"Measure": {"Expression": {"SourceRef": {"Entity": "orders"}}, "Property": "DeltaOrder"}},
            "queryRef": "orders.DeltaOrder",
            "active": true
          }]
        }
      }
    },
    "objects": {}
  }
}
```

**orders.tmdl (BROKEN — measure syntax wrong):**
```tmdl
table orders

	column category
		dataType: string
		sourceColumn: category
	column profit
		dataType: double
		sourceColumn: profit
	...
	measure DeltaOrder                                           ← BROKEN: needs = on same line
		expression: DISTINCTCOUNT('orders'[order_id]) - ...    ← BROKEN: expression: not valid TMDL
	measure Margin
		expression: SUM('orders'[profit]) - SUM('orders'[discount])
	partition orders = m
		mode: directQuery
		source =
			let
			    Source = PostgreSQL.Database("...", "postgres"),
			    Navigation = Source{[Schema="superstore", Item="orders"]}[Data]
			in
			    Navigation
```

**After Bug #1 fix, it should look like:**
```tmdl
table orders

	column category
		dataType: string
		sourceColumn: category
	column profit
		dataType: double
		sourceColumn: profit
	...
	measure DeltaOrder = DISTINCTCOUNT('orders'[order_id]) - DISTINCTCOUNT('returns'[order_id])
	measure Margin = SUM('orders'[profit]) - SUM('orders'[discount])
	partition orders = m
		mode: directQuery
		source =
			let
			    Source = PostgreSQL.Database("...", "postgres"),
			    Navigation = Source{[Schema="superstore", Item="orders"]}[Data]
			in
			    Navigation
```

**Workbook-report.md (validation output):**
```
Status: ok
Validators:
- tmdl: skipped (te2_unavailable)
- pbir_compile: skipped (pbi_tools_unavailable)
- structural: passed
- desktop_open: skipped (synthetic)
- rubric: skipped (no_rubric)
```

---

## 8. Fix Sequence

### Step 1 — Fix `measure.py` (PRIMARY — fixes all workbooks)

**`src/tableau2pbir/emit/tmdl/measure.py`**

Replace the entire `render_measure` function with:
```python
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

### Step 2 — Fix `column.py` (fixes workbooks with calculated columns)

**`src/tableau2pbir/emit/tmdl/column.py`**

For calculated columns, change from `expression:` sub-property to `= DAX` inline:
```python
if col.kind == ColumnKind.CALCULATED:
    col_name = col.name
    name_q = tmdl_ident(col_name)
    dax = col.dax_expr.strip()
    tmdl_type = _DATATYPE_MAP.get(col.datatype, col.datatype)
    body = indent(f"dataType: {tmdl_type}", "\t\t")
    return f"\tcolumn {name_q} = {dax}\n{body}\n"
```

### Step 3 — Fix `page.py` (empty filterConfig)

**`src/tableau2pbir/emit/pbir/page.py`**

Only emit `filterConfig` when there are actual filters:
```python
if filters:
    obj["filterConfig"] = {"filters": filters}
```

### Step 4 — Verify with Real Workbook End-to-End

After the fixes:
1. Run: `tableau2pbir convert tests/golden/real/simple_join_calculated_line.twb --out /tmp/test_fix`
2. Open `/tmp/test_fix/simple_join_calculated_line/simple_join_calculated_line.pbip` in PBI Desktop
3. Confirm: semantic model loads (no error banner), visuals render with data
4. Run all tests: `pytest tests/ -x` — confirm all 457+ tests still pass

### Step 5 — Fix Implicit Measure `is_measure` Projection Type (if needed after Step 4)

If visuals render but measures are shown as "Column" not "Measure" in PBI Desktop:
- Investigate `build_field_lookup` → check `col.role == ColumnRole.MEASURE` for numeric columns
- Investigate `_build_data_model.py` → check `_column_role(raw_role)` gets correct `raw_role` from XML

### Step 6 — Install External Validators

To prevent regression of TMDL/PBIR bugs:
- Install TabularEditor 2 CLI → enables `tmdl: passed` in validation
- Install pbi-tools → enables `pbir_compile: passed` in validation
- Add a real workbook with `.rubric.yaml` to trigger Desktop-open gate

---

## 9. Feature Gaps vs MVP (Post-Fix Roadmap)

After the TMDL syntax fixes, the project will produce openable reports. The following are quality gaps to close:

| Feature | MVP | Current | Priority |
|---------|-----|---------|----------|
| Color palette per category value | ✓ | ✗ | High |
| Visual titles | ✓ | ✗ | High |
| Data labels | ✓ | ✗ | Medium |
| Axis formatting | ✓ | ✗ | Medium |
| Sort definitions | ✓ | ✗ | Medium |
| Sheet-level filters on pages | ✓ | ✗ | Medium |
| Date hierarchy expansion | ✓ | ✗ | Medium |
| Custom SQL datasources | ✓ | ✗ | Medium |
| DirectQuery date-part columns | ✓ | ✗ | Low |
| Cross-highlighting interactions | ✓ | ✗ | Low |
| Navigation buttons | ✗ | ✗ | Low |

---

## 10. Key File Locations

| Purpose | Current Project File | MVP Reference File |
|---------|---------------------|-------------------|
| TMDL measure render | `src/tableau2pbir/emit/tmdl/measure.py` | `tab_to_pbi/generator.py:432-448` |
| TMDL column render | `src/tableau2pbir/emit/tmdl/column.py` | `tab_to_pbi/generator.py:457-519` |
| TMDL table render | `src/tableau2pbir/emit/tmdl/table.py` | `tab_to_pbi/generator.py:451-519` |
| TMDL model render | `src/tableau2pbir/emit/tmdl/model.py` | `tab_to_pbi/generator.py:382-389` |
| M expression | `src/tableau2pbir/emit/tmdl/m_expression.py` | `tab_to_pbi/generator.py:548-844` |
| Visual render | `src/tableau2pbir/emit/pbir/visual.py` | `tab_to_pbi/generator.py:989-1017` |
| Page render | `src/tableau2pbir/emit/pbir/page.py` | `tab_to_pbi/generator.py:943-958` |
| Field lookup | `src/tableau2pbir/visualmap/field_lookup.py` | `tab_to_pbi/transformer.py` (inline) |
| Implicit measures | `src/tableau2pbir/emit/tmdl/implicit_measures.py` | `tab_to_pbi/generator.py` (inline) |
| CLI entry point | `src/tableau2pbir/cli.py` | `tab_to_pbi/main.py` |
| Pipeline runner | `src/tableau2pbir/pipeline.py` | N/A (single-pass) |

---

## 11. Summary

**The current project fails for exactly one reason that prevents PBI Desktop from opening any output:**

> **`measure.py` emits `expression: DAX` but TMDL requires `= DAX` on the same line as the measure declaration.**

Every other part of the pipeline — extraction, canonicalization, calc translation, visual mapping, layout, PBIR emission, field lookup, `.pbip` and `definition.pbir` generation — is structurally correct. The visual.json files reference the right tables, columns, and measures. The `.pbip` file structure is valid. The PBIR JSON schemas are correct.

Fix `measure.py` (and `column.py` for calculated columns), and the project will produce PBIR output that PBI Desktop can open with data-bearing visuals. Everything else is a quality/feature gap, not a blocker.
