# Plan 19: Per-Series Color Emission and Dashboard Slicer Fix

> **For agentic workers:** REQUIRED SUB-SKILL: Use **superpowers:subagent-driven-development** to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix two independent bugs: (1) multi-pane Tableau charts lose per-axis colors because `_sheet_style` uses last-write-wins across panes, and single-series charts also lack the PBI-required `selector` on `dataPoint`; (2) the dashboard filter-card slicer is broken because `dashboards.py` cannot parse the real-workbook double-bracket `param` format, and `slicer.py` omits `drillFilterOtherVisuals` and slicer `objects`.

**Architecture:** Two independent tracks. Track A (Tasks 1–3): widen the `VisualFormat` IR to carry `pane_colors: dict[str, str]` (pill-slug → hex), thread it through `_build_visual_format`, then resolve it to per-series `(queryRef, hex)` pairs in `render_visual` and emit selector-keyed `dataPoint` entries. Track B (Tasks 4–5): reuse the already-correct `_parse_filter_column` in `dashboards.py`, add a pill-slug→bare-name fallback in `_build_dashboards.py`, and add `drillFilterOtherVisuals`/`objects` to `slicer.py`. All evidence is sourced from `tests/twbs/simple_join_calculated_line_dashboard.twb` (Tableau XML) and `C:\vibe_coding\tabToPbi\output\simple_join_calculated_line_dashboard.Report` (manual PBI reference).

**Tech Stack:** Python 3.11+, pydantic v2, lxml, pytest

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `src/tableau2pbir/extract/worksheets.py` | Collect per-pane colors keyed by y-axis-name |
| Modify | `src/tableau2pbir/ir/sheet.py` | Add `pane_colors` field to `VisualFormat` |
| Modify | `src/tableau2pbir/stages/_build_sheets.py` | Pass `pane_colors` through `_build_visual_format` |
| Modify | `src/tableau2pbir/emit/pbir/visual.py` | Build `per_series_colors` list; pass to `build_format_objects` |
| Modify | `src/tableau2pbir/visualmap/format_map.py` | Emit selector-keyed `dataPoint` entries |
| Modify | `src/tableau2pbir/extract/dashboards.py` | Use `_parse_filter_column` instead of `_unbracket` for filter_card param |
| Modify | `src/tableau2pbir/stages/_build_dashboards.py` | Add pill-slug→bare-name fallback for `field_id_for_name` lookup |
| Modify | `src/tableau2pbir/emit/pbir/slicer.py` | Accept `field_lookup`; add `drillFilterOtherVisuals`; add `objects` |
| Modify | `src/tableau2pbir/emit/pbir/render.py` | Pass `field_lookup` to `render_filter_slicer` |
| Modify | `tests/unit/extract/test_sheet_style.py` | Tests for multi-pane color extraction |
| Modify | `tests/unit/stages/test_s02_visual_format.py` | Tests for pane_colors pass-through |
| Modify | `tests/unit/visualmap/test_format_map.py` | Tests for per-series selector emission |
| Modify | `tests/unit/emit/pbir/test_visual.py` | Integration test for dual-axis color in render_visual |
| Modify | `tests/unit/extract/test_dashboards.py` | Test for double-bracket param parsing |
| Modify | `tests/unit/stages/test_s02_dashboards.py` | Test for pill-slug fallback resolution |
| Modify | `tests/unit/emit/pbir/test_slicer.py` | Tests for corrected slicer emission |

---

## Task 1: Extract per-pane mark colors in `_sheet_style`

**Files:**
- Modify: `src/tableau2pbir/extract/worksheets.py:442-451`
- Modify: `tests/unit/extract/test_sheet_style.py`

### Background

`_sheet_style` currently iterates all `<pane>` elements and overwrites `style["mark_color"]` on every pass — the last pane wins. For a dual-axis chart the Tableau XML looks like:

```xml
<!-- Default pane (no y-axis-name): colour #72b966 -->
<pane>
  <style><style-rule element='mark'><format attr='mark-color' value='#72b966'/></style-rule></style>
</pane>
<!-- Profit axis pane -->
<pane id='1' y-axis-name='[federated.xxx].[sum:profit:qk]'>
  <style><style-rule element='mark'><format attr='mark-color' value='#f28e2b'/></style-rule></style>
</pane>
<!-- Sales axis pane -->
<pane id='2' y-axis-name='[federated.xxx].[sum:sales:qk]'>
  <style><style-rule element='mark'><format attr='mark-color' value='#e15759'/></style-rule></style>
</pane>
```

`_parse_filter_column('[federated.xxx].[sum:profit:qk]')` (already defined in the same file at line 161) returns `'sum:profit:qk'`. We must use it to build a `pane_colors` dict.

- [x] **Step 1.1: Write the failing test for dual-pane color collection**

Add to `tests/unit/extract/test_sheet_style.py`:

```python
def test_dual_pane_with_y_axis_name_collects_pane_colors():
    ws, table, pp = _ws("""
    <worksheet name="Sales Profit">
      <table>
        <panes>
          <pane>
            <style><style-rule element='mark'>
              <format attr='mark-color' value='#72b966'/>
            </style-rule></style>
          </pane>
          <pane id='1' y-axis-name='[federated.xxx].[sum:profit:qk]'>
            <style><style-rule element='mark'>
              <format attr='mark-color' value='#f28e2b'/>
            </style-rule></style>
          </pane>
          <pane id='2' y-axis-name='[federated.xxx].[sum:sales:qk]'>
            <style><style-rule element='mark'>
              <format attr='mark-color' value='#e15759'/>
            </style-rule></style>
          </pane>
        </panes>
      </table>
    </worksheet>
    """)
    result = _sheet_style(ws, table, pp)
    assert "pane_colors" in result
    assert result["pane_colors"]["sum:profit:qk"] == "#f28e2b"
    assert result["pane_colors"]["sum:sales:qk"] == "#e15759"
    # Default pane (no y-axis-name) still populates mark_color as fallback
    assert result.get("mark_color") == "#72b966"


def test_single_pane_no_y_axis_name_uses_mark_color_only():
    ws, table, pp = _ws("""
    <worksheet name="Sales Year">
      <table>
        <panes>
          <pane id='4'>
            <style><style-rule element='mark'>
              <format attr='mark-color' value='#e15759'/>
            </style-rule></style>
          </pane>
        </panes>
      </table>
    </worksheet>
    """)
    result = _sheet_style(ws, table, pp)
    assert result.get("mark_color") == "#e15759"
    assert result.get("pane_colors", {}) == {}
```

- [x] **Step 1.2: Run to confirm RED**

```
pytest tests/unit/extract/test_sheet_style.py::test_dual_pane_with_y_axis_name_collects_pane_colors tests/unit/extract/test_sheet_style.py::test_single_pane_no_y_axis_name_uses_mark_color_only -v
```

Expected: FAIL — `pane_colors` key not in result.

- [x] **Step 1.3: Replace the pane-loop in `_sheet_style`**

In `src/tableau2pbir/extract/worksheets.py`, replace lines 442–451:

```python
    # --- Pane-level mark styles ---
    panes = pane_parent.findall("panes/pane") or pane_parent.findall("pane")
    for pane in panes:
        for fmt in pane.findall("style/style-rule[@element='mark']/format"):
            a = optional_attr(fmt, "attr")
            v = optional_attr(fmt, "value")
            if a == "mark-color":
                style["mark_color"] = v
            elif a == "mark-labels-show":
                style["labels_show"] = (v == "true")
```

with:

```python
    # --- Pane-level mark styles ---
    panes = pane_parent.findall("panes/pane") or pane_parent.findall("pane")
    pane_colors: dict[str, str] = {}   # pill_slug → hex; one entry per named y-axis pane
    for pane in panes:
        y_axis_raw = optional_attr(pane, "y-axis-name")
        for fmt in pane.findall("style/style-rule[@element='mark']/format"):
            a = optional_attr(fmt, "attr")
            v = optional_attr(fmt, "value")
            if a == "mark-color":
                if y_axis_raw:
                    pane_colors[_parse_filter_column(y_axis_raw)] = v
                else:
                    style["mark_color"] = v
            elif a == "mark-labels-show":
                style["labels_show"] = (v == "true")
    if pane_colors:
        style["pane_colors"] = pane_colors
```

- [x] **Step 1.4: Run to confirm GREEN**

```
pytest tests/unit/extract/test_sheet_style.py -v
```

Expected: all pass.

- [x] **Step 1.5: Run full unit suite to confirm no regressions**

```
pytest tests/unit/ -q
```

Expected: same pass count as before (all green).

- [x] **Step 1.6: Commit**

```
git add src/tableau2pbir/extract/worksheets.py tests/unit/extract/test_sheet_style.py
git commit -m "feat: collect per-pane mark colors keyed by y-axis-name in _sheet_style"
```

---

## Task 2: Add `pane_colors` to `VisualFormat` and `_build_visual_format`

**Files:**
- Modify: `src/tableau2pbir/ir/sheet.py:104-110`
- Modify: `src/tableau2pbir/stages/_build_sheets.py:175-188`
- Modify: `tests/unit/stages/test_s02_visual_format.py`

### Background

`VisualFormat` currently has `mark_color: str | None`. We add a parallel `pane_colors: dict[str, str]` field (default empty dict). `_build_visual_format` must pass it through from `raw_style` and include it in the early-return guard.

- [x] **Step 2.1: Write the failing test**

Add to `tests/unit/stages/test_s02_visual_format.py`:

```python
def test_pane_colors_passed_through():
    raw = {
        "mark_color": None, "labels_show": False, "title": None,
        "axis_font_name": None, "axis_font_size": None,
        "cell_font_name": None, "cell_font_size": None,
        "header_font_name": None, "header_font_size": None,
        "number_formats": {},
        "pane_colors": {"sum:profit:qk": "#f28e2b", "sum:sales:qk": "#e15759"},
    }
    vf = _build_visual_format(raw)
    assert isinstance(vf, VisualFormat)
    assert vf.pane_colors == {"sum:profit:qk": "#f28e2b", "sum:sales:qk": "#e15759"}


def test_pane_colors_empty_dict_returns_valid_vf_when_other_fields_set():
    raw = {
        "mark_color": "#e15759", "labels_show": False, "title": None,
        "axis_font_name": None, "axis_font_size": None,
        "cell_font_name": None, "cell_font_size": None,
        "header_font_name": None, "header_font_size": None,
        "number_formats": {},
        "pane_colors": {},
    }
    vf = _build_visual_format(raw)
    assert isinstance(vf, VisualFormat)
    assert vf.pane_colors == {}
    assert vf.mark_color == "#e15759"
```

- [x] **Step 2.2: Run to confirm RED**

```
pytest tests/unit/stages/test_s02_visual_format.py::test_pane_colors_passed_through -v
```

Expected: FAIL — `VisualFormat` has no `pane_colors` attribute.

- [x] **Step 2.3: Add `pane_colors` to `VisualFormat` in `ir/sheet.py`**

In `src/tableau2pbir/ir/sheet.py`, replace the `VisualFormat` class (lines 104–110):

```python
class VisualFormat(IRBase):
    title: TitleFormat | None = None
    mark_color: str | None = None
    labels_show: bool = False
    axis: AxisTitleFormat | None = None        # chart axis title font (both axes same)
    table: TableFormat | None = None           # table cell and header font
    number_formats: dict[str, str] = {}        # column_id → DAX format string
    pane_colors: dict[str, str] = {}           # pill_slug → hex; for dual-axis per-series colors
```

- [x] **Step 2.4: Update `_build_visual_format` in `_build_sheets.py`**

In `src/tableau2pbir/stages/_build_sheets.py`, replace lines 175–188:

```python
    if (title is None and not raw_style.get("mark_color")
            and not raw_style.get("labels_show")
            and axis is None and table_fmt is None
            and not number_formats
            and not raw_style.get("pane_colors")):
        return None

    return VisualFormat(
        title=title,
        mark_color=raw_style.get("mark_color"),
        labels_show=bool(raw_style.get("labels_show", False)),
        axis=axis,
        table=table_fmt,
        number_formats=number_formats,
        pane_colors=raw_style.get("pane_colors") or {},
    )
```

- [x] **Step 2.5: Run to confirm GREEN**

```
pytest tests/unit/stages/test_s02_visual_format.py -v
```

Expected: all pass.

- [x] **Step 2.6: Run full unit suite**

```
pytest tests/unit/ -q
```

Expected: all green.

- [x] **Step 2.7: Commit**

```
git add src/tableau2pbir/ir/sheet.py src/tableau2pbir/stages/_build_sheets.py tests/unit/stages/test_s02_visual_format.py
git commit -m "feat: add pane_colors to VisualFormat IR and _build_visual_format pass-through"
```

---

## Task 3: Emit per-series `dataPoint` with selector

**Files:**
- Modify: `src/tableau2pbir/visualmap/format_map.py:35-58`
- Modify: `src/tableau2pbir/emit/pbir/visual.py:11-35`
- Modify: `tests/unit/visualmap/test_format_map.py`
- Modify: `tests/unit/emit/pbir/test_visual.py`

### Background

Evidence from `C:\vibe_coding\tabToPbi\output\simple_join_calculated_line_dashboard.Report\definition\pages\ReportSection1\visuals\visual_1\visual.json` (the manually created reference):

```json
"dataPoint": [
  {
    "properties": {"fill": {"solid": {"color": {"expr": {"Literal": {"Value": "'#F28E2B'"}}}}}},
    "selector": {"metadata": "orders.Sum profit"}
  },
  {
    "properties": {"fill": {"solid": {"color": {"expr": {"Literal": {"Value": "'#E15759'"}}}}}},
    "selector": {"metadata": "orders.Sum sales"}
  }
]
```

The `selector.metadata` value equals the projection's `queryRef` string (e.g. `"orders.Sum profit"`). This pattern applies to both `columnChart` and `lineChart`.

`build_format_objects` gets a new optional `per_series_colors: list[tuple[str, str]] | None` parameter.  
`render_visual` builds this list by iterating Y-channel bindings after constructing projections (so it has each binding's `queryRef` available).

- [x] **Step 3.1: Write the failing format_map tests**

Add to `tests/unit/visualmap/test_format_map.py`:

```python
def test_per_series_colors_emits_selector_keyed_entries():
    vf = VisualFormat()
    per_series = [("orders.Sum profit", "#F28E2B"), ("orders.Sum sales", "#E15759")]
    objects, _ = build_format_objects(vf, "columnChart", per_series_colors=per_series)
    dp = objects["dataPoint"]
    assert len(dp) == 2
    assert dp[0]["selector"] == {"metadata": "orders.Sum profit"}
    assert dp[0]["properties"]["fill"]["solid"]["color"] == _lit("'#F28E2B'")
    assert dp[1]["selector"] == {"metadata": "orders.Sum sales"}
    assert dp[1]["properties"]["fill"]["solid"]["color"] == _lit("'#E15759'")


def test_per_series_colors_overrides_mark_color():
    vf = VisualFormat(mark_color="#000000")
    per_series = [("orders.Sum sales", "#e15759")]
    objects, _ = build_format_objects(vf, "lineChart", per_series_colors=per_series)
    dp = objects["dataPoint"]
    assert len(dp) == 1
    assert dp[0]["selector"] == {"metadata": "orders.Sum sales"}
    assert dp[0]["properties"]["fill"]["solid"]["color"] == _lit("'#e15759'")


def test_mark_color_fallback_when_no_per_series():
    vf = VisualFormat(mark_color="#f28e2b")
    objects, _ = build_format_objects(vf, "columnChart")   # no per_series_colors
    dp = objects["dataPoint"]
    assert len(dp) == 1
    assert "selector" not in dp[0]   # old behaviour preserved
    assert dp[0]["properties"]["fill"]["solid"]["color"] == _lit("'#f28e2b'")
```

- [x] **Step 3.2: Run to confirm RED**

```
pytest tests/unit/visualmap/test_format_map.py::test_per_series_colors_emits_selector_keyed_entries -v
```

Expected: FAIL — `build_format_objects` does not accept `per_series_colors`.

- [x] **Step 3.3: Update `build_format_objects` in `format_map.py`**

In `src/tableau2pbir/visualmap/format_map.py`, replace the function signature and `dataPoint` block (lines 35–58):

```python
def build_format_objects(
    vf: VisualFormat | None,
    visual_type: str,
    per_series_colors: list[tuple[str, str]] | None = None,
) -> tuple[dict[str, list[dict]], dict[str, list[dict]]]:
    """Return (visual_objects, visual_container_objects) for PBIR emission.

    visual_objects        → visual.visual.objects
    visual_container_objects → visual.visual.visualContainerObjects

    per_series_colors: resolved list of (queryRef, hex_color) for Y-channel measures.
    When provided, emits per-series selector-keyed dataPoint entries (confirmed from
    manual PBI reference at C:/vibe_coding/tabToPbi/output/...).
    Falls back to a single selectorless entry when None and mark_color is set.
    """
    if vf is None:
        return {}, {}

    objects: dict[str, list[dict]] = {}
    container: dict[str, list[dict]] = {}

    # ---------- visual.objects ----------

    if vf.labels_show:
        objects["labels"] = [{"properties": {"show": _lit("true")}}]

    if per_series_colors:
        objects["dataPoint"] = [
            {"properties": {"fill": _color(hex_val)}, "selector": {"metadata": qr}}
            for qr, hex_val in per_series_colors
        ]
    elif vf.mark_color:
        objects["dataPoint"] = [
            {"properties": {"fill": _color(vf.mark_color)}}
        ]
```

The rest of the function body (axis, table, title handling) is **unchanged** from the current file.

- [x] **Step 3.4: Run format_map tests GREEN**

```
pytest tests/unit/visualmap/test_format_map.py -v
```

Expected: all pass.

- [x] **Step 3.5: Write the failing render_visual test**

Add to `tests/unit/emit/pbir/test_visual.py`:

```python
from tableau2pbir.ir.sheet import VisualFormat


def test_dual_axis_pane_colors_emits_per_series_datapoint():
    """When PbirVisual has pane_colors and two Y bindings, render_visual must emit
    two selector-keyed dataPoint entries matching the manual PBI reference output."""
    from tableau2pbir.ir.sheet import VisualFormat
    vf = VisualFormat(pane_colors={
        "sum_profit_qk": "#F28E2B",
        "sum_sales_qk": "#E15759",
    })
    pv = PbirVisual(
        visual_type="columnChart",
        encoding_bindings=(
            EncodingBinding(channel="Category", source_field_id="none_region_nk"),
            EncodingBinding(channel="Y", source_field_id="sum_profit_qk"),
            EncodingBinding(channel="Y", source_field_id="sum_sales_qk"),
        ),
        format={},
        visual_format=vf,
    )
    lookup = {
        "none_region_nk": {"table_name": "orders", "col_name": "region", "is_measure": False},
        "sum_profit_qk": {"table_name": "orders", "col_name": "profit", "is_measure": True,
                          "measure_name": "Sum profit"},
        "sum_sales_qk": {"table_name": "orders", "col_name": "sales", "is_measure": True,
                         "measure_name": "Sum sales"},
    }
    pos = Position(x=0, y=0, w=400, h=300)
    obj = json.loads(render_visual("v1", pv, pos, 0, field_lookup=lookup))
    dp = obj["visual"]["objects"]["dataPoint"]
    assert len(dp) == 2, f"expected 2 dataPoint entries, got {len(dp)}"
    assert dp[0]["selector"] == {"metadata": "orders.Sum profit"}
    assert dp[0]["properties"]["fill"]["solid"]["color"]["expr"]["Literal"]["Value"] == "'#F28E2B'"
    assert dp[1]["selector"] == {"metadata": "orders.Sum sales"}
    assert dp[1]["properties"]["fill"]["solid"]["color"]["expr"]["Literal"]["Value"] == "'#E15759'"


def test_single_series_mark_color_emits_selector_with_queryref():
    """Single-series chart with mark_color only: render_visual emits one selector-keyed
    dataPoint entry (matches manual reference for Sales Year lineChart)."""
    from tableau2pbir.ir.sheet import VisualFormat
    vf = VisualFormat(mark_color="#e15759")
    pv = PbirVisual(
        visual_type="lineChart",
        encoding_bindings=(
            EncodingBinding(channel="Category", source_field_id="yr_order_date_ok"),
            EncodingBinding(channel="Y", source_field_id="sum_sales_qk"),
        ),
        format={},
        visual_format=vf,
    )
    lookup = {
        "yr_order_date_ok": {"table_name": "orders", "col_name": "order_date Year",
                              "is_measure": False},
        "sum_sales_qk": {"table_name": "orders", "col_name": "sales", "is_measure": True,
                         "measure_name": "Sum sales"},
    }
    pos = Position(x=0, y=0, w=400, h=300)
    obj = json.loads(render_visual("v1", pv, pos, 0, field_lookup=lookup))
    dp = obj["visual"]["objects"]["dataPoint"]
    assert len(dp) == 1
    assert dp[0]["selector"] == {"metadata": "orders.Sum sales"}
    assert dp[0]["properties"]["fill"]["solid"]["color"]["expr"]["Literal"]["Value"] == "'#e15759'"
```

- [x] **Step 3.6: Run to confirm RED**

```
pytest tests/unit/emit/pbir/test_visual.py::test_dual_axis_pane_colors_emits_per_series_datapoint tests/unit/emit/pbir/test_visual.py::test_single_series_mark_color_emits_selector_with_queryref -v
```

Expected: FAIL.

- [x] **Step 3.7: Update `render_visual` in `emit/pbir/visual.py`**

Replace the full body of `render_visual` (lines 11–59) with:

```python
def render_visual(
    visual_id: str,
    pbir_visual: PbirVisual,
    position: Position,
    z_order: int,
    field_lookup: dict[str, dict] | None = None,
) -> str:
    fl = field_lookup or {}
    vf = pbir_visual.visual_format

    if vf is not None:
        number_formats = vf.number_formats
    else:
        number_formats = {}

    # Build projections; capture queryRef per source_field_id for color selector resolution.
    query_state: dict[str, dict] = {}
    queryref_by_source_id: dict[str, str] = {}
    for b in pbir_visual.encoding_bindings:
        proj = _make_projection(b.source_field_id, fl,
                                number_formats if vf is not None else {})
        query_state.setdefault(b.channel, {"projections": []})
        query_state[b.channel]["projections"].append(proj)
        queryref_by_source_id[b.source_field_id] = proj["queryRef"]

    # Resolve per-series colors: pane_colors (dual-axis) or mark_color (single-series).
    per_series_colors: list[tuple[str, str]] = []
    if vf is not None and (vf.pane_colors or vf.mark_color):
        for b in pbir_visual.encoding_bindings:
            if b.channel != "Y":
                continue
            qr = queryref_by_source_id.get(b.source_field_id)
            if not qr:
                continue
            color = (vf.pane_colors.get(b.source_field_id)
                     if vf.pane_colors else vf.mark_color)
            if color:
                per_series_colors.append((qr, color))

    if vf is not None:
        objects, container_objects = build_format_objects(
            vf, pbir_visual.visual_type,
            per_series_colors=per_series_colors or None,
        )
    else:
        objects = pbir_visual.format or {}
        container_objects = {}

    query: dict = {"queryState": query_state}
    if pbir_visual.sort_by:
        query["sortDefinition"] = {
            "sort": [_make_sort_entry(s, fl) for s in pbir_visual.sort_by],
            "isDefaultSort": False,
        }

    visual_block: dict = {
        "visualType": pbir_visual.visual_type,
        "query": query,
        "objects": objects,
    }
    if container_objects:
        visual_block["visualContainerObjects"] = container_objects

    obj = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/1.0.0/schema.json",
        "name": visual_id,
        "position": {"x": position.x, "y": position.y,
                     "width": position.w, "height": position.h, "z": z_order},
        "visual": visual_block,
    }
    return json.dumps(obj, indent=2)
```

The helper functions `_make_sort_entry` and `_make_projection` at lines 62–122 are **unchanged**.

- [x] **Step 3.8: Run to confirm GREEN**

```
pytest tests/unit/emit/pbir/test_visual.py -v
```

Expected: all pass.

- [x] **Step 3.9: Run full unit suite**

```
pytest tests/unit/ -q
```

Expected: all green.

- [x] **Step 3.10: Run E2E gate**

```
pytest tests/integration/test_real_workbooks_e2e.py -q
```

Expected: all pass. (E2E tests verify the pipeline runs without crash; golden output changes will be updated in Task 6 after both tracks are done.)

- [x] **Step 3.11: Commit**

```
git add src/tableau2pbir/visualmap/format_map.py src/tableau2pbir/emit/pbir/visual.py tests/unit/visualmap/test_format_map.py tests/unit/emit/pbir/test_visual.py
git commit -m "feat: emit per-series selector-keyed dataPoint entries for chart color fidelity"
```

---

## Task 4: Fix filter-card `param` parsing and pill-slug field lookup

**Files:**
- Modify: `src/tableau2pbir/extract/dashboards.py:91`
- Modify: `src/tableau2pbir/stages/_build_dashboards.py:28-30`
- Modify: `tests/unit/extract/test_dashboards.py`
- Modify: `tests/unit/stages/test_s02_dashboards.py`

### Background

**Bug A** — `dashboards.py` line 91 calls `_unbracket(param)` which cannot handle the real-workbook double-bracket format:

```
param='[federated.1qn8ahk0toq5gp12u1jqd1tw8dv2].[none:region:nk]'
```

`_unbracket` returns the whole string unchanged because `"].[" in s`. The function `_parse_filter_column` (line 161 in `worksheets.py`) already handles this correctly — it strips the datasource-marker token and returns `none:region:nk`.

**Bug B** — `_build_dashboards.py` line 30: `field_id_for_name.get("none:region:nk", "")` → `""` because `field_id_for_name` keys are bare names like `region` (built from `col_id.split("__col__", 1)[-1]`). A second step must split the pill slug on `:` and try the middle token.

- [x] **Step 4.1: Write the failing extract/dashboards test**

Add to `tests/unit/extract/test_dashboards.py` (import `extract_dashboards` and `parse_workbook_xml` are already at the top of this file):

```python
_XML_REAL_FILTER_CARD = b"""<?xml version='1.0'?>
<workbook><dashboards>
  <dashboard name='Company Dashboard'>
    <size maxheight='720' maxwidth='1280' minheight='720' minwidth='1280'/>
    <zones>
      <zone h='100000' id='10' type-v2='layout-basic' w='100000' x='0' y='0'>
        <zone h='21500' id='8' is-fixed='true'
              name='Sales  Profit'
              param='[federated.1qn8ahk0toq5gp12u1jqd1tw8dv2].[none:region:nk]'
              type-v2='filter' w='18300' x='80900' y='1000'>
          <zone-style/>
        </zone>
      </zone>
    </zones>
  </dashboard>
</dashboards></workbook>
"""


def test_filter_card_real_workbook_double_bracket_param():
    """Real Tableau workbooks use [datasource].[field_slug] in the param attribute.
    The extractor must strip the datasource token and return the pill slug."""
    root = parse_workbook_xml(_XML_REAL_FILTER_CARD)
    d = extract_dashboards(root)[0]
    filter_leaves = [lf for lf in d["leaves"] if lf["leaf_kind"] == "filter_card"]
    assert len(filter_leaves) == 1
    assert filter_leaves[0]["payload"]["field"] == "none:region:nk"
```

- [x] **Step 4.2: Run to confirm RED**

```
pytest tests/unit/extract/test_dashboards.py::test_filter_card_real_workbook_double_bracket_param -v
```

Expected: FAIL — payload["field"] is `[federated.1qn8ahk0toq5gp12u1jqd1tw8dv2].[none:region:nk]` not `none:region:nk`.

- [x] **Step 4.3: Fix `dashboards.py` line 91**

In `src/tableau2pbir/extract/dashboards.py`, add an import at the top of the file:

```python
from tableau2pbir.extract.worksheets import _parse_filter_column
```

Then replace line 91:

```python
    if kind == "filter_card":
        return {"field": _parse_filter_column(param) if param else ""}
```

- [x] **Step 4.4: Run to confirm GREEN**

```
pytest tests/unit/extract/test_dashboards.py -v
```

Expected: all pass.

- [x] **Step 4.5: Write the failing stage test for pill-slug fallback**

Add to `tests/unit/stages/test_s02_dashboards.py`:

```python
def test_filter_card_pill_slug_resolves_via_bare_name():
    """After Bug A is fixed, dashboards.py emits 'none:region:nk' as the field.
    _build_dashboards must split on ':' and look up the middle token 'region'."""
    raw = [{
        "name": "D",
        "size": {"w": 1280, "h": 720, "kind": "exact"},
        "leaves": [{
            "leaf_kind": "filter_card",
            "payload": {"field": "none:region:nk"},
            "position": {"x": 0, "y": 0, "w": 200, "h": 100},
            "floating": False,
        }],
    }]
    # field_id_for_name has the bare column name (not the pill slug)
    field_id_for_name = {"region": "people__col__region"}
    dashboards = build_dashboards(
        raw, sheet_id_for_name={}, param_id_for_name={},
        field_id_for_name=field_id_for_name,
    )
    leaf = dashboards[0].layout_tree.children[0]
    assert leaf.kind == LeafKind.FILTER_CARD
    assert leaf.payload["field_id"] == "people__col__region"
```

- [x] **Step 4.6: Run to confirm RED**

```
pytest tests/unit/stages/test_s02_dashboards.py::test_filter_card_pill_slug_resolves_via_bare_name -v
```

Expected: FAIL — `field_id` is `""`.

- [x] **Step 4.7: Add pill-slug fallback in `_build_dashboards.py`**

In `src/tableau2pbir/stages/_build_dashboards.py`, replace the `filter_card` branch (lines 28–30):

```python
    if leaf_kind == "filter_card":
        name = raw_payload.get("field", "")
        field_id = field_id_for_name.get(name, "")
        if not field_id and name.count(":") == 2:
            # pill slug form "none:col_name:nk" → try bare column name
            field_id = field_id_for_name.get(name.split(":")[1], "")
        return {"field_id": field_id}
```

- [x] **Step 4.8: Run to confirm GREEN**

```
pytest tests/unit/stages/test_s02_dashboards.py -v
```

Expected: all pass.

- [x] **Step 4.9: Run full unit suite**

```
pytest tests/unit/ -q
```

Expected: all green.

- [x] **Step 4.10: Commit**

```
git add src/tableau2pbir/extract/dashboards.py src/tableau2pbir/stages/_build_dashboards.py tests/unit/extract/test_dashboards.py tests/unit/stages/test_s02_dashboards.py
git commit -m "fix: parse real-workbook double-bracket filter_card param; add pill-slug bare-name fallback"
```

---

## Task 5: Fix slicer field binding, `drillFilterOtherVisuals`, and `objects`

**Files:**
- Modify: `src/tableau2pbir/emit/pbir/slicer.py`
- Modify: `src/tableau2pbir/emit/pbir/render.py:106`
- Modify: `tests/unit/emit/pbir/test_slicer.py`

### Background

The manual PBI reference `DashboardSection1/visuals/dash_visual_3/visual.json` shows three things our `slicer.py` is missing:

1. **Correct field binding**: `Column` type using `people.region` — requires `_make_projection` to be called with the actual `field_lookup` instead of `{}`.

2. **`drillFilterOtherVisuals: true`**: Without this the slicer displays values but does not filter any other visual on the page. This is the mechanism PBI uses for slicer-driven cross-filtering.

3. **`objects`**: The manual shows:
   ```json
   "objects": {
     "data": [{"properties": {"mode": {"expr": {"Literal": {"Value": "'Basic'"}}}}}],
     "selection": [{"properties": {
       "singleSelect": {"expr": {"Literal": {"Value": "false"}}},
       "strictSingleSelect": {"expr": {"Literal": {"Value": "false"}}},
       "selectAllCheckboxEnabled": {"expr": {"Literal": {"Value": "true"}}}
     }}]
   }
   ```

`render_filter_slicer` needs a new optional `field_lookup` parameter. `render.py` line 106 passes `field_lookup` (already in scope at line 28) to the slicer call.

- [x] **Step 5.1: Write the failing slicer tests**

Replace the full contents of `tests/unit/emit/pbir/test_slicer.py`:

```python
import json

from tableau2pbir.emit.pbir.slicer import render_filter_slicer, render_parameter_slicer
from tableau2pbir.ir.dashboard import Position


def test_filter_slicer_minimal():
    """Backward-compat: no field_lookup still produces a slicer (fallback binding)."""
    pos = Position(x=0, y=0, w=200, h=80)
    out = render_filter_slicer(visual_id="s1", source_field_id="Sales.Region", position=pos, z_order=0)
    obj = json.loads(out)
    assert obj["visual"]["visualType"] == "slicer"
    assert "Region" in json.dumps(obj)


def test_filter_slicer_with_lookup_uses_column_type():
    """With field_lookup, a dimension field must use Column (not Measure) type."""
    pos = Position(x=0, y=0, w=200, h=150)
    lookup = {"people__col__region": {
        "table_name": "people", "col_name": "region", "is_measure": False,
    }}
    out = render_filter_slicer(
        visual_id="s1",
        source_field_id="people__col__region",
        position=pos,
        z_order=2,
        field_lookup=lookup,
    )
    obj = json.loads(out)
    proj = obj["visual"]["query"]["queryState"]["Values"]["projections"][0]
    field = proj["field"]
    assert "Column" in field, "dimension must bind as Column, not Measure"
    assert field["Column"]["Expression"]["SourceRef"]["Entity"] == "people"
    assert field["Column"]["Property"] == "region"
    assert proj["queryRef"] == "people.region"


def test_filter_slicer_drills_other_visuals():
    """drillFilterOtherVisuals must be True — this is what makes the slicer filter the page."""
    pos = Position(x=0, y=0, w=200, h=150)
    out = render_filter_slicer(visual_id="s1", source_field_id="x", position=pos, z_order=0)
    obj = json.loads(out)
    assert obj["visual"].get("drillFilterOtherVisuals") is True


def test_filter_slicer_has_basic_mode_object():
    """Slicer objects must include data.mode = 'Basic'."""
    pos = Position(x=0, y=0, w=200, h=150)
    out = render_filter_slicer(visual_id="s1", source_field_id="x", position=pos, z_order=0)
    obj = json.loads(out)
    data_obj = obj["visual"]["objects"]["data"]
    mode = data_obj[0]["properties"]["mode"]["expr"]["Literal"]["Value"]
    assert mode == "'Basic'"


def test_filter_slicer_has_selection_multiselect_enabled():
    """Slicer selection must allow multi-select with Select All checkbox."""
    pos = Position(x=0, y=0, w=200, h=150)
    out = render_filter_slicer(visual_id="s1", source_field_id="x", position=pos, z_order=0)
    obj = json.loads(out)
    sel = obj["visual"]["objects"]["selection"][0]["properties"]
    assert sel["singleSelect"]["expr"]["Literal"]["Value"] == "false"
    assert sel["selectAllCheckboxEnabled"]["expr"]["Literal"]["Value"] == "true"


def test_parameter_slicer_minimal():
    pos = Position(x=0, y=0, w=200, h=80)
    out = render_parameter_slicer(
        visual_id="ps1", parameter_name="Discount Rate", parameter_intent="numeric_what_if",
        position=pos, z_order=0,
    )
    obj = json.loads(out)
    assert obj["visual"]["visualType"] == "slicer"
    assert "Discount Rate" in json.dumps(obj)
```

- [x] **Step 5.2: Run to confirm RED**

```
pytest tests/unit/emit/pbir/test_slicer.py -v
```

Expected: `test_filter_slicer_with_lookup_uses_column_type`, `test_filter_slicer_drills_other_visuals`, `test_filter_slicer_has_basic_mode_object`, `test_filter_slicer_has_selection_multiselect_enabled` all FAIL.

- [x] **Step 5.3: Rewrite `slicer.py`**

Replace the full contents of `src/tableau2pbir/emit/pbir/slicer.py`:

```python
"""Slicer visuals — filter cards and parameter cards."""
from __future__ import annotations

import json

from tableau2pbir.emit.pbir.visual import _make_projection
from tableau2pbir.ir.dashboard import Position


def _lit(value: str) -> dict:
    return {"expr": {"Literal": {"Value": value}}}


def render_filter_slicer(
    visual_id: str,
    source_field_id: str,
    position: Position,
    z_order: int,
    field_lookup: dict | None = None,
) -> str:
    return _slicer_json(visual_id, source_field_id, position, z_order, field_lookup or {})


def render_parameter_slicer(
    visual_id: str,
    parameter_name: str,
    parameter_intent: str,
    position: Position,
    z_order: int,
) -> str:
    if parameter_intent in ("numeric_what_if", "categorical_selector"):
        source_field_id = f"{parameter_name}.Value"
    else:
        source_field_id = parameter_name
    return _slicer_json(visual_id, source_field_id, position, z_order, {})


def _slicer_json(
    visual_id: str,
    source_field_id: str,
    position: Position,
    z_order: int,
    field_lookup: dict,
) -> str:
    obj = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.0.0/schema.json",
        "name": visual_id,
        "position": {"x": position.x, "y": position.y,
                     "width": position.w, "height": position.h, "z": z_order},
        "visual": {
            "visualType": "slicer",
            "query": {
                "queryState": {
                    "Values": {"projections": [_make_projection(source_field_id, field_lookup)]},
                },
            },
            "objects": {
                "data": [{"properties": {"mode": _lit("'Basic'")}}],
                "selection": [{"properties": {
                    "singleSelect": _lit("false"),
                    "strictSingleSelect": _lit("false"),
                    "selectAllCheckboxEnabled": _lit("true"),
                }}],
            },
            "drillFilterOtherVisuals": True,
        },
    }
    return json.dumps(obj, indent=2)
```

- [x] **Step 5.4: Run to confirm GREEN**

```
pytest tests/unit/emit/pbir/test_slicer.py -v
```

Expected: all pass.

- [x] **Step 5.5: Wire `field_lookup` in `render.py`**

In `src/tableau2pbir/emit/pbir/render.py`, replace line 105–106:

```python
                write_text(s_dir / "visual.json",
                           render_filter_slicer(slicer_id, source_field_id, leaf.position, z))
```

with:

```python
                write_text(s_dir / "visual.json",
                           render_filter_slicer(slicer_id, source_field_id, leaf.position, z,
                                                field_lookup))
```

- [x] **Step 5.6: Run full unit suite**

```
pytest tests/unit/ -q
```

Expected: all green.

- [x] **Step 5.7: Run E2E gate**

```
pytest tests/integration/test_real_workbooks_e2e.py -q
```

Expected: all pass.

- [x] **Step 5.8: Commit**

```
git add src/tableau2pbir/emit/pbir/slicer.py src/tableau2pbir/emit/pbir/render.py tests/unit/emit/pbir/test_slicer.py
git commit -m "fix: slicer field lookup, drillFilterOtherVisuals, and Basic-mode objects emission"
```

---

## Task 6: Regenerate output and verify against manual reference

**Files:**
- Re-run converter on `tests/twbs/simple_join_calculated_line_dashboard.twb`

### Background

After all five fixes, regenerate the PBIR output and manually diff it against the reference at `C:\vibe_coding\tabToPbi\output\simple_join_calculated_line_dashboard.Report` to confirm the four issues from the original bug report are resolved.

- [x] **Step 6.1: Re-run the converter**

```
python -m tableau2pbir convert tests/twbs/simple_join_calculated_line_dashboard.twb out/simple_join_calculated_line_dashboard
```

Expected: exits 0, no schema validation errors.

- [x] **Step 6.2: Verify Sales Profit colors (Issue 1)**

```
python -c "
import json, pathlib
p = pathlib.Path('out/simple_join_calculated_line_dashboard/Report/definition/pages')
for page in sorted(p.iterdir()):
    for vis in (page / 'visuals').iterdir():
        obj = json.loads((vis / 'visual.json').read_text())
        if obj['visual']['visualType'] == 'columnChart':
            dp = obj['visual']['objects'].get('dataPoint', [])
            print(page.name, vis.name)
            for entry in dp:
                print('  selector:', entry.get('selector'))
                print('  color:', entry['properties']['fill']['solid']['color']['expr']['Literal']['Value'])
"
```

Expected output: two `dataPoint` entries for the column chart, with selectors `"orders.Sum profit"` / `"orders.Sum sales"` and colors `'#f28e2b'` / `'#e15759'` respectively.

- [x] **Step 6.3: Verify Sales Year line chart color (Issue 2)**

In the output above, verify the `lineChart` visual has one `dataPoint` entry with `selector: {"metadata": "orders.Sum sales"}` and color `'#e15759'`.

- [x] **Step 6.4: Verify dashboard slicer (Issue 4)**

```
python -c "
import json, pathlib
for vis in pathlib.Path('out/simple_join_calculated_line_dashboard/Report/definition/pages').rglob('visual.json'):
    obj = json.loads(vis.read_text())
    if obj['visual']['visualType'] == 'slicer':
        print(vis)
        print(json.dumps(obj['visual'], indent=2))
"
```

Expected: slicer has `Column` type (not `Measure`), `Entity: "people"`, `Property: "region"`, `drillFilterOtherVisuals: true`, non-empty `objects`.

- [x] **Step 6.5: Run full test suite**

```
pytest tests/ -q
```

Expected: all pass.

- [x] **Step 6.6: Commit**

```
git add out/simple_join_calculated_line_dashboard/
git commit -m "chore: regenerate dashboard output after per-series color and slicer fixes"
```

---

## Self-Review

**Spec coverage check:**

| Issue | Tasks covering it |
|---|---|
| Sales Profit dual-axis wrong colors | Tasks 1 (extract pane_colors) + 2 (IR) + 3 (emit per-series dataPoint) |
| Sales Year single-series wrong color | Task 3 (single-series uses mark_color with selector) |
| Company Dashboard visual colors | Same as above — dashboard visuals are the same sheets embedded |
| Dashboard filter card not working | Task 4 (parse param + pill-slug lookup) + Task 5 (slicer field binding + drillFilterOtherVisuals) |

**Placeholder scan:** None found.

**Type consistency check:**
- `VisualFormat.pane_colors: dict[str, str]` — defined Task 2, used Task 3 ✓
- `build_format_objects(vf, visual_type, per_series_colors=None)` — defined Task 3, called Task 3 ✓
- `render_filter_slicer(..., field_lookup=None)` — defined Task 5, called Task 5 ✓
- `_parse_filter_column` imported from `worksheets` in `dashboards.py` — used Task 4 ✓
