# Plan 8: Fix Visual Emission — Markers, Channel Names, Field Resolution & Naming

> **Execution mode: INLINE** — Use `superpowers:executing-plans` in the same session. Tasks execute sequentially with review checkpoints between them. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Fix PBIR visual emission so PBI Desktop can render all visuals in converted workbooks — currently all visuals are broken due to five compounding bugs.

**Architecture:** Four-stage fix. (1) Stage 2 filters Tableau datasource marker pills before they pollute the encoding IR. (2) Stage 4 catalog and dispatch are updated to use PBI's actual capitalized channel names and fix the bar-chart shelf assignment (Tableau vertical bar puts the MEASURE on ROWS and DIMENSION on COLUMNS — the opposite of what dispatch was assuming). (3) A new `field_lookup` module bridges FieldRef pill slugs (e.g. `none_category_nk`) to semantic model names (table=`orders`, col=`category`, role=dim) so Stage 7 can emit correct `Entity`, `queryRef`, `active`, and `Column`/`Measure` type. (4) Page/visual folder naming is changed from hex hashes to `ReportSection{N}` / `visual_{N}` to match the working MVP pattern.

**Tech Stack:** Python 3.11+, pydantic v2, re (stdlib), pytest

---

## Root Cause Summary

| # | Bug | Symptom | Source File |
|---|-----|---------|-------------|
| 1 | Datasource marker pill `federated.xxx` not filtered | dispatch picks it as `rows[0]`/`cols[0]` | `_build_sheets.py` |
| 2 | Bar chart shelf assignment reversed | Category gets the measure, Y gets the dimension | `dispatch.py` |
| 3 | Channel names lowercase (`category`, `value`) | PBI rejects unknown channel names | `catalog.py`, `dispatch.py` |
| 4 | `SourceRef.Source` instead of `SourceRef.Entity` | PBI cannot locate table in semantic model | `visual.py` |
| 5 | Raw IR column IDs used as `Property` | PBI cannot find columns (e.g. `federated_17kv...`) | `visual.py`, no lookup exists |
| 6 | `queryRef` and `active` missing from projections | PBI cannot bind projections to semantic model | `visual.py` |
| 7 | Hex-hash page/visual folder names | Cosmetic mismatch vs. working MVP | `render.py` |

---

## File Map

| File | Action | Change |
|------|--------|--------|
| `src/tableau2pbir/stages/_build_sheets.py` | Modify | Add `_is_datasource_marker()` filter in `_build_encoding` |
| `src/tableau2pbir/visualmap/catalog.py` | Modify | Capitalize all channel names to PBI-required form |
| `src/tableau2pbir/visualmap/dispatch.py` | Modify | Fix channel names; fix bar chart shelf assignment |
| `src/tableau2pbir/visualmap/field_lookup.py` | **Create** | New module: pill slug → `{table_name, col_name, is_measure}` |
| `src/tableau2pbir/emit/pbir/visual.py` | Modify | Accept lookup; emit `Entity`, `queryRef`, `active`, correct type |
| `src/tableau2pbir/emit/pbir/render.py` | Modify | Build lookup from wb; pass to `render_visual`; fix naming |
| `tests/unit/stages/test_s02_sheets.py` | Modify | Add marker-filter test |
| `tests/unit/visualmap/test_catalog.py` | Modify | Update slot assertions to capitalized names |
| `tests/unit/visualmap/test_dispatch.py` | Modify | Update channel assertions; add bar shelf test |
| `tests/unit/visualmap/test_field_lookup.py` | **Create** | Tests for new lookup module |
| `tests/unit/emit/pbir/test_visual.py` | Modify | Add Entity/queryRef/active tests |
| `tests/unit/emit/pbir/test_render.py` | Modify | Add naming + queryRef integration tests |

---

## Task 1: Filter datasource marker pills in Stage 2 encoding

**Files:**
- Modify: `src/tableau2pbir/stages/_build_sheets.py`
- Modify: `tests/unit/stages/test_s02_sheets.py`

Tableau shelves contain a hidden `[federated.{hash}]` pill as the first item on every shelf. It uses a `class.hash` format with a dot separator and no colon. All real Tableau field pills use `prefix:field:type` colon format. Filtering these out at Stage 2 means dispatch never sees them.

- [x] **Step 1: Write the failing test**

Add to `tests/unit/stages/test_s02_sheets.py`:

```python
def test_datasource_marker_pills_are_filtered_from_encoding():
    """Pills that are class.hash (dot-separated, no colon) must be dropped."""
    raw = [{
        "name": "Sheet 1",
        "datasource_refs": ("fed.ds",),
        "mark_type": "bar",
        "encodings": {
            "rows": ("federated.17kv7r10vp81pc1g60xgp0re1it8", "usr:DeltaOrder:qk"),
            "columns": ("federated.17kv7r10vp81pc1g60xgp0re1it8", "none:category:nk"),
            "color": None, "size": None, "label": None, "tooltip": None,
            "detail": (), "shape": None, "angle": None,
        },
        "filters": [], "sort": [], "dual_axis": False,
        "reference_lines": [], "quick_table_calcs": [],
    }]
    sheets, _ = build_sheets(raw, calc_names=set(), table_id_for_ref={"fed.ds": "tbl__fed"})
    enc = sheets[0].encoding
    col_ids = {fr.column_id for fr in enc.rows} | {fr.column_id for fr in enc.columns}
    assert not any("federated" in cid for cid in col_ids), "marker must be absent"
    assert len(enc.rows) == 1, "only the real field must remain on rows"
    assert len(enc.columns) == 1, "only the real field must remain on columns"
```

- [x] **Step 2: Run test to confirm it fails**

```
pytest tests/unit/stages/test_s02_sheets.py::test_datasource_marker_pills_are_filtered_from_encoding -v
```

Expected: FAIL — both rows and columns will still have 2 items.

- [x] **Step 3: Add the filter to `_build_encoding` in `_build_sheets.py`**

Add this function just before `_build_encoding`, and update `_build_encoding` to use it:

```python
def _is_datasource_marker(name: str) -> bool:
    """Tableau datasource markers use 'class.hash' format: contains '.' but no ':'."""
    return "." in name and ":" not in name


def _build_encoding(raw_enc: dict[str, Any], table_id: str) -> Encoding:
    def r(name: str | None) -> FieldRef | None:
        if not name or _is_datasource_marker(name):
            return None
        return _ref(name, table_id)
    return Encoding(
        rows=tuple(_ref(n, table_id) for n in raw_enc.get("rows", ()) if not _is_datasource_marker(n)),
        columns=tuple(_ref(n, table_id) for n in raw_enc.get("columns", ()) if not _is_datasource_marker(n)),
        color=r(raw_enc.get("color")),
        size=r(raw_enc.get("size")),
        label=r(raw_enc.get("label")),
        tooltip=r(raw_enc.get("tooltip")),
        detail=tuple(_ref(n, table_id) for n in raw_enc.get("detail", ()) if not _is_datasource_marker(n)),
        shape=r(raw_enc.get("shape")),
        angle=r(raw_enc.get("angle")),
    )
```

- [x] **Step 4: Run test to confirm it passes**

```
pytest tests/unit/stages/test_s02_sheets.py::test_datasource_marker_pills_are_filtered_from_encoding -v
```

Expected: PASS.

- [x] **Step 5: Run full Stage 2 sheets test suite**

```
pytest tests/unit/stages/test_s02_sheets.py -v
```

Expected: all existing tests still pass (they use plain names like `"amount"` with no dot, which are kept).

- [x] **Step 6: Commit**

```bash
git add src/tableau2pbir/stages/_build_sheets.py tests/unit/stages/test_s02_sheets.py
git commit -m "fix(stage2): filter Tableau datasource marker pills from sheet encoding"
```

---

## Task 2: Update visual catalog to PBI's capitalized channel names

**Files:**
- Modify: `src/tableau2pbir/visualmap/catalog.py`
- Modify: `tests/unit/visualmap/test_catalog.py`

The catalog currently uses lowercase names (`"category"`, `"value"`) but PBI requires capitalized names (`"Category"`, `"Y"`). The catalog gates both dispatch validation and the AI fallback's tool schema.

- [x] **Step 1: Write the failing test**

Update `tests/unit/visualmap/test_catalog.py`:

```python
def test_slots_for_clustered_bar():
    s = slots_for("clusteredBarChart")
    assert "Category" in s
    assert "Y" in s
    assert "category" not in s   # old lowercase name must be gone
    assert "value" not in s      # old lowercase name must be gone
```

- [x] **Step 2: Run test to confirm it fails**

```
pytest tests/unit/visualmap/test_catalog.py::test_slots_for_clustered_bar -v
```

Expected: FAIL (current catalog has `"category"` not `"Category"`).

- [x] **Step 3: Replace `_SLOTS` in `catalog.py`**

```python
_SLOTS: dict[str, frozenset[str]] = {
    "clusteredBarChart": frozenset({"Category", "Y", "Series", "Tooltips"}),
    "stackedBarChart":   frozenset({"Category", "Y", "Series", "Tooltips"}),
    "lineChart":         frozenset({"Category", "Y", "Series", "Tooltips"}),
    "areaChart":         frozenset({"Category", "Y", "Series", "Tooltips"}),
    "scatterChart":      frozenset({"X", "Y", "Size", "Color", "Details", "Tooltips"}),
    "tableEx":           frozenset({"Values", "Tooltips"}),
    "pieChart":          frozenset({"Category", "Y", "Tooltips"}),
    "filledMap":         frozenset({"Location", "Y", "Color", "Tooltips"}),
}
```

- [x] **Step 4: Run all catalog tests**

```
pytest tests/unit/visualmap/test_catalog.py -v
```

Expected: all pass.

- [x] **Step 5: Check if the AI fallback's prompt or tool schema embeds channel names**

```
grep -r "category\|value\|\"slots\"\|channel" src/tableau2pbir/llm/ src/tableau2pbir/visualmap/ai_fallback.py
```

If the LLM prompt or tool schema hard-codes lowercase channel names, update those too to match the new catalog.

- [x] **Step 6: Commit**

```bash
git add src/tableau2pbir/visualmap/catalog.py tests/unit/visualmap/test_catalog.py
git commit -m "fix(catalog): update visual channel names to PBI-required capitalized form"
```

---

## Task 3: Fix dispatch channel names and bar chart shelf assignment

**Files:**
- Modify: `src/tableau2pbir/visualmap/dispatch.py`
- Modify: `tests/unit/visualmap/test_dispatch.py`

Two bugs: (1) all channels use wrong lowercase names that now fail catalog validation; (2) for `bar`/`automatic`, dispatch used `_bind("category", rows[0])` — but in a Tableau vertical bar chart, ROWS holds the MEASURE (Y axis) and COLUMNS holds the DIMENSION (X axis categories). The binding must be swapped: `Category ← cols[0]`, `Y ← rows[0]`.

- [x] **Step 1: Write the failing tests**

Add to `tests/unit/visualmap/test_dispatch.py`:

```python
def test_bar_emits_pbi_channel_names():
    sh = _sheet("bar", rows=(_fr("sales"),), cols=(_fr("region"),))
    pv = dispatch_visual(sh)
    assert pv is not None
    channels = {b.channel for b in pv.encoding_bindings}
    assert "Category" in channels and "Y" in channels
    assert "category" not in channels and "value" not in channels


def test_bar_assigns_cols_to_category_and_rows_to_y():
    """Tableau vertical bar: COLUMNS=dimension→Category, ROWS=measure→Y."""
    sh = _sheet("bar", rows=(_fr("sales"),), cols=(_fr("region"),))
    pv = dispatch_visual(sh)
    cat = next(b.source_field_id for b in pv.encoding_bindings if b.channel == "Category")
    y_val = next(b.source_field_id for b in pv.encoding_bindings if b.channel == "Y")
    assert cat == "region"
    assert y_val == "sales"


def test_line_emits_pbi_channel_names():
    sh = _sheet("line", rows=(_fr("sales"),), cols=(_fr("date"),))
    pv = dispatch_visual(sh)
    assert pv is not None
    channels = {b.channel for b in pv.encoding_bindings}
    assert "Category" in channels and "Y" in channels


def test_scatter_emits_pbi_channel_names():
    sh = _sheet("circle", rows=(_fr("profit"),), cols=(_fr("sales"),))
    pv = dispatch_visual(sh)
    assert pv is not None
    channels = {b.channel for b in pv.encoding_bindings}
    assert "X" in channels and "Y" in channels
```

- [x] **Step 2: Run tests to confirm they fail**

```
pytest tests/unit/visualmap/test_dispatch.py::test_bar_emits_pbi_channel_names tests/unit/visualmap/test_dispatch.py::test_bar_assigns_cols_to_category_and_rows_to_y -v
```

Expected: FAIL.

- [x] **Step 3: Replace the full body of `dispatch_visual` in `dispatch.py`**

```python
def dispatch_visual(sheet: Sheet) -> PbirVisual | None:
    mark = sheet.mark_type
    enc = sheet.encoding
    rows = enc.rows
    cols = enc.columns
    color = enc.color

    if mark in ("bar", "automatic") and rows and cols:
        # Tableau vertical bar: ROWS=measure (Y axis), COLUMNS=dimension (X axis)
        bindings = [_bind("Category", cols[0]), _bind("Y", rows[0])]
        if color:
            bindings.append(_bind("Series", color))
        return PbirVisual(visual_type="clusteredBarChart", encoding_bindings=tuple(bindings), format={})

    if mark == "line" and rows and cols:
        bindings = [_bind("Category", cols[0]), _bind("Y", rows[0])]
        if color:
            bindings.append(_bind("Series", color))
        return PbirVisual(visual_type="lineChart", encoding_bindings=tuple(bindings), format={})

    if mark == "area" and rows and cols:
        return PbirVisual(
            visual_type="areaChart",
            encoding_bindings=(_bind("Category", cols[0]), _bind("Y", rows[0])),
            format={},
        )

    if mark in ("circle", "shape", "scatter") and rows and cols:
        bindings = [_bind("X", cols[0]), _bind("Y", rows[0])]
        if enc.size:
            bindings.append(_bind("Size", enc.size))
        if color:
            bindings.append(_bind("Color", color))
        return PbirVisual(visual_type="scatterChart", encoding_bindings=tuple(bindings), format={})

    if mark == "pie" and rows:
        bindings = [_bind("Y", rows[0])]
        if color:
            bindings.insert(0, _bind("Category", color))
        return PbirVisual(visual_type="pieChart", encoding_bindings=tuple(bindings), format={})

    if mark == "text":
        bindings = [_bind("Values", r) for r in rows] + [_bind("Values", c) for c in cols]
        if not bindings:
            return None
        return PbirVisual(visual_type="tableEx", encoding_bindings=tuple(bindings), format={})

    if mark == "map" and rows and cols:
        return PbirVisual(
            visual_type="filledMap",
            encoding_bindings=(_bind("Location", cols[0]), _bind("Y", rows[0])),
            format={},
        )

    return None
```

- [x] **Step 4: Update the old dispatch test assertions that check lowercase names**

In `test_dispatch.py`, update `test_bar_with_dim_on_rows_and_measure_on_cols`:

```python
def test_bar_with_dim_on_rows_and_measure_on_cols():
    sh = _sheet("bar", rows=(_fr("sales"),), cols=(_fr("region"),))
    pv = dispatch_visual(sh)
    assert pv is not None
    assert pv.visual_type == "clusteredBarChart"
    channels = {b.channel for b in pv.encoding_bindings}
    assert "Category" in channels and "Y" in channels
```

- [x] **Step 5: Run all dispatch and visualmap tests**

```
pytest tests/unit/visualmap/ -v
```

Expected: all pass. If the AI fallback test checks channel names, update those assertions too.

- [x] **Step 6: Commit**

```bash
git add src/tableau2pbir/visualmap/dispatch.py tests/unit/visualmap/test_dispatch.py
git commit -m "fix(dispatch): PBI capitalized channel names; fix bar chart shelf→channel assignment"
```

---

## Task 4: Build field resolution lookup

**Files:**
- Create: `src/tableau2pbir/visualmap/field_lookup.py`
- Create: `tests/unit/visualmap/test_field_lookup.py`

FieldRef.column_ids in `EncodingBinding.source_field_id` are slugs of Tableau pill names (e.g. `none_category_nk`) that do NOT match DataModel column IDs (e.g. `tbl__orders__col__category`). The bridge: extract the base slug from the pill (regex strips the `{prefix}_` and `_{2-char-suffix}`) and match against `slug_id(col.name)` in the data model. For calculations, the user display name from `Calculation.name` (e.g. `DeltaOrder`) overrides the internal name stored in `Column.name` (e.g. `Calculation_0390937790091264`).

- [x] **Step 1: Write the failing tests**

Create `tests/unit/visualmap/test_field_lookup.py`:

```python
from __future__ import annotations

from tableau2pbir.ir.calculation import Calculation, CalculationKind, CalculationPhase, CalculationScope
from tableau2pbir.ir.common import FieldRef
from tableau2pbir.ir.datasource import ConnectorTier, Datasource
from tableau2pbir.ir.model import Column, ColumnKind, ColumnRole, Table
from tableau2pbir.ir.sheet import Encoding, Sheet
from tableau2pbir.ir.workbook import DataModel, Workbook
from tableau2pbir.visualmap.field_lookup import build_field_lookup


def _make_wb() -> Workbook:
    col_cat = Column(
        id="tbl__orders__col__category", name="category",
        datatype="string", role=ColumnRole.DIMENSION, kind=ColumnKind.RAW,
    )
    col_calc = Column(
        id="tbl__orders__col__calculation_01", name="Calculation_01",
        datatype="double", role=ColumnRole.MEASURE, kind=ColumnKind.CALCULATED,
    )
    table = Table(
        id="tbl__orders", name="orders", datasource_id="ds1",
        column_ids=("tbl__orders__col__category", "tbl__orders__col__calculation_01"),
    )
    calc = Calculation(
        id="calc__calculation_01", name="Revenue",
        scope=CalculationScope.MEASURE, tableau_expr="SUM([sales])",
        dax_expr="SUM('orders'[sales])",
        kind=CalculationKind.AGGREGATE, phase=CalculationPhase.AGGREGATE,
    )
    ds = Datasource(
        id="ds1", name="DS", tableau_kind="csv",
        connector_tier=ConnectorTier.TIER_1, pbi_m_connector="Csv.Document",
        connection_params={"filename": "x.csv"}, user_action_required=(),
        table_ids=("tbl__orders",), extract_ignored=False,
    )
    sheet = Sheet(
        id="s1", name="Sheet 1", datasource_refs=("ds1",), mark_type="bar",
        encoding=Encoding(
            rows=(FieldRef(table_id="tbl__orders", column_id="usr_calculation_01_qk"),),
            columns=(FieldRef(table_id="tbl__orders", column_id="none_category_nk"),),
        ),
        filters=(), sort=(), dual_axis=False, reference_lines=(), uses_calculations=(),
    )
    return Workbook(
        ir_schema_version="1.1.0", source_path="x.twb", source_hash="a",
        tableau_version="2024.1", config={},
        data_model=DataModel(
            datasources=(ds,), tables=(table,),
            columns=(col_cat, col_calc), calculations=(calc,),
        ),
        sheets=(sheet,), dashboards=(), unsupported=(),
    )


def test_dimension_resolves_to_table_and_col_name():
    lookup = build_field_lookup(_make_wb())
    assert "none_category_nk" in lookup
    info = lookup["none_category_nk"]
    assert info["table_name"] == "orders"
    assert info["col_name"] == "category"
    assert info["is_measure"] is False


def test_calculation_resolves_to_user_display_name():
    """col_name must be the user-given Calculation.name, not the internal Column.name."""
    lookup = build_field_lookup(_make_wb())
    assert "usr_calculation_01_qk" in lookup
    info = lookup["usr_calculation_01_qk"]
    assert info["table_name"] == "orders"
    assert info["col_name"] == "Revenue"   # Calculation.name, not "Calculation_01"
    assert info["is_measure"] is True


def test_datasource_marker_not_in_lookup():
    lookup = build_field_lookup(_make_wb())
    # Markers end in a digit, not a 2-char alpha suffix, so pill regex won't match
    assert "federated_17kv7r10vp81pc1g60xgp0re1it8" not in lookup


def test_returns_empty_for_workbook_with_no_sheets():
    wb = _make_wb()
    wb2 = wb.model_copy(update={"sheets": ()})
    assert build_field_lookup(wb2) == {}
```

- [x] **Step 2: Run tests to confirm they fail (module doesn't exist)**

```
pytest tests/unit/visualmap/test_field_lookup.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [x] **Step 3: Create `src/tableau2pbir/visualmap/field_lookup.py`**

```python
"""Map FieldRef.column_id (Tableau pill slug) → PBI field info for visual emission.

Tableau pill slugs use the format {prefix}_{body}_{2char_suffix} after slugification,
e.g. none_category_nk, usr_calculation_0390937790091264_qk.
DataModel column IDs use tbl__{ds}__col__{name}. We bridge them by extracting
the body slug from the pill and matching it against slug_id(col.name).
"""
from __future__ import annotations

import re

from tableau2pbir.ir.model import ColumnRole
from tableau2pbir.ir.workbook import Workbook
from tableau2pbir.util.ids import slug_id

# Matches Tableau pill slugs: {prefix}_{body}_{2_alpha_suffix}
# e.g. none_category_nk, usr_calculation_01_qk
# Does NOT match datasource markers like federated_17kv...8 (end in digit, not alpha)
_PILL_RE = re.compile(r'^[a-z]+_(.+)_[a-z]{2}$')


def build_field_lookup(wb: Workbook) -> dict[str, dict]:
    """Return mapping: FieldRef.column_id → {table_name, col_name, is_measure}."""
    col_by_id = {c.id: c for c in wb.data_model.columns}

    # base_slug → {table_name, col_name, is_measure}
    # base_slug = slug_id(col.name), e.g. "category" or "calculation_0390937790091264"
    by_base: dict[str, dict] = {}
    for table in wb.data_model.tables:
        for col_id in table.column_ids:
            col = col_by_id.get(col_id)
            if col is None:
                continue
            by_base[slug_id(col.name)] = {
                "table_name": table.name,
                "col_name": col.name,
                "is_measure": col.role == ColumnRole.MEASURE,
            }

    # For calculations, replace col_name with the user-facing display name.
    # Column.name stores the internal name (Calculation_0390937790091264),
    # Calculation.name stores what the user named it (DeltaOrder).
    for calc in wb.data_model.calculations:
        internal_slug = slug_id(calc.id.removeprefix("calc__"))
        if internal_slug in by_base:
            by_base[internal_slug] = {**by_base[internal_slug], "col_name": calc.name}

    # Resolve each FieldRef.column_id seen in sheet encodings
    lookup: dict[str, dict] = {}
    for sheet in wb.sheets:
        enc = sheet.encoding
        refs = list(enc.rows) + list(enc.columns) + list(enc.detail)
        for opt in (enc.color, enc.size, enc.label, enc.tooltip, enc.shape, enc.angle):
            if opt:
                refs.append(opt)
        for fr in refs:
            field_id = fr.column_id
            if field_id in lookup:
                continue
            m = _PILL_RE.match(field_id)
            if m and m.group(1) in by_base:
                lookup[field_id] = by_base[m.group(1)]

    return lookup
```

- [x] **Step 4: Run tests to confirm they pass**

```
pytest tests/unit/visualmap/test_field_lookup.py -v
```

Expected: all 4 tests PASS.

- [x] **Step 5: Commit**

```bash
git add src/tableau2pbir/visualmap/field_lookup.py tests/unit/visualmap/test_field_lookup.py
git commit -m "feat(visualmap): add field_lookup to resolve pill slugs to semantic model names"
```

---

## Task 5: Update render_visual() to use field lookup

**Files:**
- Modify: `src/tableau2pbir/emit/pbir/visual.py`
- Modify: `tests/unit/emit/pbir/test_visual.py`

Replace the broken `_field_obj()` with `_make_projection()` that uses the lookup to emit: correct `Entity` key (not `Source`), resolved column name (not raw pill slug), `queryRef`, and `active: true`. Correct `Column` vs `Measure` type from `is_measure`. Fall back gracefully for test fixtures that use dot-qualified names like `"Sales.Region"`.

- [x] **Step 1: Write the failing tests**

Add to `tests/unit/emit/pbir/test_visual.py`:

```python
def test_projection_uses_entity_not_source():
    """SourceRef must use 'Entity' (semantic model table), not 'Source' (query alias)."""
    pv = PbirVisual(
        visual_type="clusteredBarChart",
        encoding_bindings=(
            EncodingBinding(channel="Category", source_field_id="none_category_nk"),
        ),
        format={},
    )
    lookup = {"none_category_nk": {"table_name": "orders", "col_name": "category", "is_measure": False}}
    pos = Position(x=0, y=0, w=400, h=300)
    obj = json.loads(render_visual("v1", pv, pos, 0, field_lookup=lookup))
    proj = obj["visual"]["query"]["queryState"]["Category"]["projections"][0]
    field_def = proj["field"]
    assert "Column" in field_def, "dimension must use Column not Measure"
    src_ref = field_def["Column"]["Expression"]["SourceRef"]
    assert src_ref.get("Entity") == "orders", "must use Entity key"
    assert "Source" not in src_ref, "must not use Source key"
    assert field_def["Column"]["Property"] == "category"


def test_projection_has_query_ref_and_active():
    pv = PbirVisual(
        visual_type="clusteredBarChart",
        encoding_bindings=(
            EncodingBinding(channel="Y", source_field_id="usr_calc_01_qk"),
        ),
        format={},
    )
    lookup = {"usr_calc_01_qk": {"table_name": "orders", "col_name": "DeltaOrder", "is_measure": True}}
    pos = Position(x=0, y=0, w=400, h=300)
    obj = json.loads(render_visual("v1", pv, pos, 0, field_lookup=lookup))
    proj = obj["visual"]["query"]["queryState"]["Y"]["projections"][0]
    assert proj.get("queryRef") == "orders.DeltaOrder"
    assert proj.get("active") is True
    assert "Measure" in proj["field"]
    assert proj["field"]["Measure"]["Expression"]["SourceRef"]["Entity"] == "orders"
    assert proj["field"]["Measure"]["Property"] == "DeltaOrder"
```

- [x] **Step 2: Run tests to confirm they fail**

```
pytest tests/unit/emit/pbir/test_visual.py::test_projection_uses_entity_not_source tests/unit/emit/pbir/test_visual.py::test_projection_has_query_ref_and_active -v
```

Expected: FAIL.

- [x] **Step 3: Replace the full contents of `visual.py`**

```python
"""Render visuals/<vid>/visual.json."""
from __future__ import annotations

import json

from tableau2pbir.ir.dashboard import Position
from tableau2pbir.ir.sheet import PbirVisual


def render_visual(
    visual_id: str,
    pbir_visual: PbirVisual,
    position: Position,
    z_order: int,
    field_lookup: dict[str, dict] | None = None,
) -> str:
    fl = field_lookup or {}
    query_state: dict[str, dict] = {}
    for b in pbir_visual.encoding_bindings:
        query_state.setdefault(b.channel, {"projections": []})
        query_state[b.channel]["projections"].append(_make_projection(b.source_field_id, fl))

    obj = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/1.0.0/schema.json",
        "name": visual_id,
        "position": {"x": position.x, "y": position.y,
                     "width": position.w, "height": position.h, "z": z_order},
        "visual": {
            "visualType": pbir_visual.visual_type,
            "query": {"queryState": query_state},
            "objects": pbir_visual.format or {},
        },
    }
    return json.dumps(obj, indent=2)


def _make_projection(field_id: str, field_lookup: dict) -> dict:
    info = field_lookup.get(field_id)
    if info:
        table_name = info["table_name"]
        col_name = info["col_name"]
        is_measure = info["is_measure"]
    elif "." in field_id:
        # Fallback for dot-qualified test fixtures like "Sales.Region"
        table_name, col_name = field_id.split(".", 1)
        is_measure = False
    else:
        table_name = "Model"
        col_name = field_id
        is_measure = True
    field_type = "Measure" if is_measure else "Column"
    return {
        "field": {
            field_type: {
                "Expression": {"SourceRef": {"Entity": table_name}},
                "Property": col_name,
            }
        },
        "queryRef": f"{table_name}.{col_name}",
        "active": True,
    }
```

- [x] **Step 4: Run all visual tests**

```
pytest tests/unit/emit/pbir/test_visual.py -v
```

Expected: all pass. The existing `test_visual_json_has_position_and_query` checks `"Region" in str(p)` — the fallback produces `Property: "Region"` which contains "Region". ✓

- [x] **Step 5: Commit**

```bash
git add src/tableau2pbir/emit/pbir/visual.py tests/unit/emit/pbir/test_visual.py
git commit -m "fix(emit): render_visual uses Entity, resolved names, queryRef, active, Column/Measure"
```

---

## Task 6: Thread field lookup through render.py + fix page/visual naming

**Files:**
- Modify: `src/tableau2pbir/emit/pbir/render.py`
- Modify: `tests/unit/emit/pbir/test_render.py`

Two changes in one render.py edit: (1) build field lookup from workbook and pass it to every `render_visual` call so projections use real column names; (2) replace hex-hash page/visual folder names with `ReportSection{N}` and `visual_{N}`.

- [x] **Step 1: Write the failing tests**

Add to `tests/unit/emit/pbir/test_render.py`:

```python
def test_page_folder_named_report_section(tmp_path: Path):
    wb = _wb_one_page_one_visual()
    render_report(wb, tmp_path)
    rd = tmp_path / "Report" / "definition"
    page_dirs = [p for p in (rd / "pages").iterdir() if p.is_dir()]
    assert len(page_dirs) == 1
    assert page_dirs[0].name == "ReportSection1", f"got: {page_dirs[0].name}"


def test_visual_folder_named_visual_1(tmp_path: Path):
    wb = _wb_one_page_one_visual()
    render_report(wb, tmp_path)
    rd = tmp_path / "Report" / "definition"
    page_dirs = [p for p in (rd / "pages").iterdir() if p.is_dir()]
    visual_dirs = list((page_dirs[0] / "visuals").iterdir())
    assert len(visual_dirs) == 1
    assert visual_dirs[0].name == "visual_1", f"got: {visual_dirs[0].name}"


def test_visual_projections_have_queryref(tmp_path: Path):
    """render_report must emit queryRef in every projection."""
    wb = _wb_one_page_one_visual()
    render_report(wb, tmp_path)
    rd = tmp_path / "Report" / "definition"
    page_dirs = [p for p in (rd / "pages").iterdir() if p.is_dir()]
    visual_json = json.loads(
        (page_dirs[0] / "visuals" / "visual_1" / "visual.json").read_text(encoding="utf-8")
    )
    projections = [
        p
        for ch in visual_json["visual"]["query"]["queryState"].values()
        for p in ch["projections"]
    ]
    assert all("queryRef" in p for p in projections), "every projection must have queryRef"
    assert all(p.get("active") is True for p in projections), "every projection must be active"
```

- [x] **Step 2: Run tests to confirm they fail**

```
pytest tests/unit/emit/pbir/test_render.py::test_page_folder_named_report_section tests/unit/emit/pbir/test_render.py::test_visual_folder_named_visual_1 tests/unit/emit/pbir/test_render.py::test_visual_projections_have_queryref -v
```

Expected: FAIL.

- [x] **Step 3: Update `render.py`**

Add the import at the top of the imports section:

```python
from tableau2pbir.visualmap.field_lookup import build_field_lookup
```

In `render_report()`, make these changes:

**A. Build the field lookup once before the dashboard loop** (add after `column_to_tier = _column_tier_index(wb)`):

```python
field_lookup = build_field_lookup(wb)
```

**B. Replace `page_id = stable_id("page", dash.id)` with:**

```python
page_id = f"ReportSection{ordinal + 1}"
```

**C. Replace the visual_id line and visual_count increment.** The current code is:
```python
visual_id = stable_id("visual", page_id, str(z))
...
visual_count += 1
```
Replace both with:
```python
visual_count += 1
visual_id = f"visual_{visual_count}"
```
(increment first so the first visual is `visual_1`, matching the MVP)

**D. Pass `field_lookup` to `render_visual`** (the call at render.py line ~57):
```python
write_text(v_dir / "visual.json",
           render_visual(visual_id, sheet.pbir_visual, leaf.position, z, field_lookup))
```

- [x] **Step 4: Run all render tests**

```
pytest tests/unit/emit/pbir/test_render.py -v
```

Expected: all pass. Note: `test_pages_json_contains_page_id` checks `activePageName == pageOrder[0]` which still holds because both will be `"ReportSection1"`. ✓

- [x] **Step 5: Run all PBIR emit tests**

```
pytest tests/unit/emit/pbir/ -v
```

Expected: all pass.

- [x] **Step 6: Commit**

```bash
git add src/tableau2pbir/emit/pbir/render.py tests/unit/emit/pbir/test_render.py
git commit -m "fix(emit): thread field lookup into render_visual; ReportSectionN/visual_N naming"
```

---

## Task 7: Run full test suite and E2E verification

- [x] **Step 1: Run all unit tests**

```
pytest tests/unit/ -x --tb=short 2>&1 | tail -50
```

Expected: all pass. Fix any unexpected failures before continuing.

- [x] **Step 2: Run integration tests**

```
pytest tests/integration/ -v --tb=short 2>&1 | tail -30
```

Expected: pass.

- [x] **Step 3: Re-run the CLI conversion**

```
python -m tableau2pbir.cli convert "tests/golden/real/simple_join.twb"
```

- [x] **Step 4: Verify page/visual naming**

```
find out/simple_join/Report -type d
```

Expected:
```
out/simple_join/Report/definition/pages/ReportSection1
out/simple_join/Report/definition/pages/ReportSection1/visuals/visual_1
out/simple_join/Report/definition/pages/ReportSection2
out/simple_join/Report/definition/pages/ReportSection2/visuals/visual_2
```

- [x] **Step 5: Inspect visual.json for Sheet 1**

```
cat "out/simple_join/Report/definition/pages/ReportSection1/visuals/visual_1/visual.json"
```

Expected structure — `Entity` not `Source`, resolved names, `queryRef`, `active`:

```json
{
  "visual": {
    "visualType": "clusteredBarChart",
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
    }
  }
}
```

- [x] **Step 6: Run real workbook E2E test**

```
pytest tests/integration/test_real_workbooks_e2e.py -v 2>&1 | tail -30
```

- [x] **Step 7: Commit if any final adjustments were made**

```bash
git add -A
git commit -m "fix(visual): all visual emission bugs resolved — E2E simple_join visuals render"
```

---

## Self-Review Checklist

- [x] **Bug 1 covered** — Task 1 filters datasource markers in Stage 2
- [x] **Bug 2 covered** — Task 3 swaps bar chart shelf assignment
- [x] **Bug 3 covered** — Tasks 2 & 3 update channel names throughout catalog + dispatch
- [x] **Bug 4 covered** — Task 5 changes `Source` → `Entity` in `_make_projection`
- [x] **Bug 5 covered** — Task 4 builds the lookup; Task 5 uses it for resolved `Property`
- [x] **Bug 6 covered** — Task 5 adds `queryRef` and `active` in `_make_projection`
- [x] **Bug 7 covered** — Task 6 replaces hex hashes with `ReportSection{N}` / `visual_{N}`
- [x] **Type consistency** — `render_visual` gains optional `field_lookup: dict[str, dict] | None = None`; all callers updated in Task 6
- [x] **No placeholders** — all code blocks are complete and runnable
- [x] **TDD** — every implementation step preceded by a failing test
- [x] **E2E gate** — Task 7 runs `test_real_workbooks_e2e.py` per project rule
