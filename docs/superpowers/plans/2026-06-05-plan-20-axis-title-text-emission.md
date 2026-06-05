# Axis Title Text Emission — Y-Axis Label Parity

> **For agentic workers:** REQUIRED SUB-SKILL: Use **superpowers:subagent-driven-development** to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract Tableau `<style-rule element='axis'><format attr='title' scope='rows'>` custom Y-axis titles from TWB files and emit them as `objects.valueAxis[0].properties.titleText` in PBIR `visual.json`, closing the gap between Tableau and Power BI axis label rendering.

**Architecture:** Four files are touched in pipeline order — extract → IR → build → emit. The extraction adds an `axis_titles` list to the raw style dict. A new `AxisTitle` Pydantic model carries the data through the IR. `_build_visual_format()` wires it into `VisualFormat`. `render_visual()` resolves the field slug to a queryRef using the already-built `queryref_by_source_id` map (same pattern as Plan 19 pane colors), then passes the resolved title text to `build_format_objects()`, which merges `titleText` into the existing `valueAxis` properties dict alongside any axis font properties from Plan 16. For multi-measure charts, the first `<format>` entry by document order is used — confirmed from the reference PBIR output at `C:/vibe_coding/tabToPbi/output/`.

**Tech Stack:** Python 3.11, Pydantic v2, lxml, pytest.

---

## Evidence Summary (verified before writing this plan)

| Claim | Source | Verified |
|---|---|---|
| Tableau stores axis titles in `<style-rule element='axis'><format attr='title' scope='rows'>` | `tests/golden/real/simple_join_calculated_line_dashboard.twb` lines 579–583, 655–658 | ✅ |
| PBI expects `objects.valueAxis[0].properties.titleText` with `expr/Literal` wrapper | `C:/vibe_coding/tabToPbi/output/.../visual_1/visual.json` and `visual_2/visual.json` | ✅ |
| Current PBI output has no `valueAxis` entry at all | `out/simple_join_calculated_line_dashboard/Report/definition/pages/ReportSection*/visuals/*/visual.json` | ✅ |
| `_sheet_style()` skips `element='axis'` — no branch exists | `extract/worksheets.py` lines 407–441 | ✅ |
| `AxisTitleFormat` has no `title_text` field | `ir/sheet.py` lines 92–95 | ✅ |
| `slug_id("sum:profit:qk")` → `"sum_profit_qk"` matches `FieldRef.column_id` pattern | `util/ids.py` + `stages/_build_sheets.py` `_ref()` | ✅ |
| `class='0'` is always constant — safe to ignore; filter by `attr == "title"` only | grep across 5 TWBs in `/vibe_coding/tabToPbi/input/` | ✅ |
| `scope='cols'` never used with `attr='title'` in any real workbook | grep across all 10 input TWBs | ✅ |
| First `<format>` by document order = title to use; no `selector` on `valueAxis` | Reference output `visual_1/visual.json` lines 120–143 | ✅ |
| `showAxisTitle` not needed in PBIR visual.json | Reference output does NOT include it | ✅ |

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Modify | `src/tableau2pbir/ir/sheet.py` | Add `AxisTitle` model; add `axis_titles` field to `VisualFormat` |
| Modify | `src/tableau2pbir/extract/worksheets.py` | In `_sheet_style()`, add branch for `element='axis'` / `attr='title'` / `scope='rows'` |
| Modify | `src/tableau2pbir/stages/_build_sheets.py` | In `_build_visual_format()`, build `axis_titles` tuple; update early-exit guard and `VisualFormat(...)` call |
| Modify | `src/tableau2pbir/visualmap/format_map.py` | Add `row_axis_title` parameter; restructure `_CHART_TYPES` block to merge `titleText` into `val_props` |
| Modify | `src/tableau2pbir/emit/pbir/visual.py` | Resolve first `scope='rows'` axis title slug → queryRef; pass to `build_format_objects` |
| Modify | `tests/unit/ir/test_sheet.py` | Tests for `AxisTitle` model and `VisualFormat.axis_titles` field |
| Modify | `tests/unit/extract/test_worksheets.py` | Tests for `_sheet_style()` axis title extraction |
| Modify | `tests/unit/stages/test_s02_sheets.py` | Tests for `_build_visual_format()` wiring |
| Modify | `tests/unit/visualmap/test_format_map.py` | Tests for `build_format_objects()` with `row_axis_title` |
| Modify | `tests/unit/emit/pbir/test_visual.py` | Tests for `render_visual()` axis title resolution and emission |

---

## Task 1 — IR: Add `AxisTitle` model and extend `VisualFormat`

**Files:**
- Modify: `src/tableau2pbir/ir/sheet.py`
- Modify: `tests/unit/ir/test_sheet.py`

- [x] **Step 1: Write the failing tests**

Add to the bottom of `tests/unit/ir/test_sheet.py`:

```python
from tableau2pbir.ir.sheet import AxisTitle, VisualFormat


def test_axis_title_model_fields():
    at = AxisTitle(field_id="sum_profit_qk", scope="rows", title="#  Profit")
    assert at.field_id == "sum_profit_qk"
    assert at.scope == "rows"
    assert at.title == "#  Profit"


def test_visual_format_axis_titles_defaults_empty():
    vf = VisualFormat()
    assert vf.axis_titles == ()


def test_visual_format_axis_titles_accepts_tuple():
    at = AxisTitle(field_id="sum_sales_qk", scope="rows", title="#  Revenue")
    vf = VisualFormat(axis_titles=(at,))
    assert len(vf.axis_titles) == 1
    assert vf.axis_titles[0].title == "#  Revenue"
```

- [x] **Step 2: Run tests to confirm they fail**

```
pytest tests/unit/ir/test_sheet.py::test_axis_title_model_fields tests/unit/ir/test_sheet.py::test_visual_format_axis_titles_defaults_empty tests/unit/ir/test_sheet.py::test_visual_format_axis_titles_accepts_tuple -v
```

Expected: FAIL — `cannot import name 'AxisTitle'`

- [x] **Step 3: Add `AxisTitle` model and extend `VisualFormat` in `src/tableau2pbir/ir/sheet.py`**

Add `AxisTitle` class immediately after `TableFormat` (before `VisualFormat`):

```python
class AxisTitle(IRBase):
    field_id: str   # slug form, e.g. "sum_profit_qk" — matches FieldRef.column_id
    scope: str      # "rows" → Y-axis; "cols" → X-axis (rare, captured for future use)
    title: str      # literal axis title text as typed in Tableau, e.g. "#  Revenue"
```

In `VisualFormat`, add after `pane_colors`:

```python
    axis_titles: tuple[AxisTitle, ...] = ()
```

`VisualFormat` after the change:

```python
class VisualFormat(IRBase):
    title: TitleFormat | None = None
    mark_color: str | None = None
    labels_show: bool = False
    axis: AxisTitleFormat | None = None        # chart axis title font (both axes same)
    table: TableFormat | None = None           # table cell and header font
    number_formats: dict[str, str] = {}        # column_id → DAX format string
    pane_colors: dict[str, str] = {}           # slug_field_id → hex color string
    axis_titles: tuple[AxisTitle, ...] = ()    # per-field custom axis title text
```

- [x] **Step 4: Run tests to confirm they pass**

```
pytest tests/unit/ir/test_sheet.py -v
```

Expected: All pass.

- [x] **Step 5: Run full unit suite to confirm no regressions**

```
pytest tests/unit/ -x -q
```

Expected: All pass.

- [x] **Step 6: Commit**

```
git add src/tableau2pbir/ir/sheet.py tests/unit/ir/test_sheet.py
git commit -m "feat(ir): add AxisTitle model; add axis_titles field to VisualFormat"
```

---

## Task 2 — Extract: parse `<style-rule element='axis'>` axis title text

**Files:**
- Modify: `src/tableau2pbir/extract/worksheets.py`
- Modify: `tests/unit/extract/test_worksheets.py`

- [x] **Step 1: Write the failing tests**

Add to `tests/unit/extract/test_worksheets.py`:

```python
_XML_SINGLE_AXIS_TITLE = b"""<?xml version='1.0'?>
<workbook><worksheets>
  <worksheet name='Sales Year'>
    <table>
      <view>
        <datasources><datasource name='ds1'/></datasources>
      </view>
      <style>
        <style-rule element='axis'>
          <format attr='title' class='0' field='[ds1].[sum:sales:qk]' scope='rows' value='#  Revenue' />
        </style-rule>
      </style>
      <panes>
        <pane><mark class='Line'/></pane>
      </panes>
      <rows>[ds1].[sum:sales:qk]</rows>
      <cols>[ds1].[yr:order_date:ok]</cols>
    </table>
  </worksheet>
</worksheets></workbook>
"""

_XML_MULTI_MEASURE_AXIS_TITLES = b"""<?xml version='1.0'?>
<workbook><worksheets>
  <worksheet name='Sales Profit'>
    <table>
      <view>
        <datasources><datasource name='ds1'/></datasources>
      </view>
      <style>
        <style-rule element='axis'>
          <format attr='title' class='0' field='[ds1].[sum:profit:qk]' scope='rows' value='#  Profit' />
          <format attr='title' class='0' field='[ds1].[sum:sales:qk]' scope='rows' value='#  Sales' />
        </style-rule>
      </style>
      <panes>
        <pane><mark class='Automatic'/></pane>
      </panes>
      <rows>([ds1].[sum:profit:qk]+[ds1].[sum:sales:qk])</rows>
      <cols>[ds1].[none:region:nk]</cols>
    </table>
  </worksheet>
</worksheets></workbook>
"""

_XML_AXIS_FONT_ONLY = b"""<?xml version='1.0'?>
<workbook><worksheets>
  <worksheet name='Styled'>
    <table>
      <view>
        <datasources><datasource name='ds1'/></datasources>
      </view>
      <style>
        <style-rule element='axis'>
          <format attr='font-family' scope='cols' value='Verdana' />
          <format attr='font-size' scope='cols' value='22' />
        </style-rule>
      </style>
      <panes>
        <pane><mark class='Bar'/></pane>
      </panes>
      <rows>[ds1].[sum:sales:qk]</rows>
      <cols>[ds1].[none:region:nk]</cols>
    </table>
  </worksheet>
</worksheets></workbook>
"""

_XML_NO_AXIS_RULE = b"""<?xml version='1.0'?>
<workbook><worksheets>
  <worksheet name='Plain'>
    <table>
      <view>
        <datasources><datasource name='ds1'/></datasources>
      </view>
      <panes>
        <pane><mark class='Bar'/></pane>
      </panes>
      <rows>[ds1].[sum:sales:qk]</rows>
      <cols>[ds1].[none:region:nk]</cols>
    </table>
  </worksheet>
</worksheets></workbook>
"""


def test_axis_title_extracted_single_measure():
    root = parse_workbook_xml(_XML_SINGLE_AXIS_TITLE)
    ws = extract_worksheets(root)
    titles = ws[0]["sheet_style"]["axis_titles"]
    assert len(titles) == 1
    assert titles[0]["field"] == "sum_sales_qk"   # slug_id("sum:sales:qk")
    assert titles[0]["scope"] == "rows"
    assert titles[0]["title"] == "#  Revenue"


def test_axis_title_extracted_multi_measure_order_preserved():
    root = parse_workbook_xml(_XML_MULTI_MEASURE_AXIS_TITLES)
    ws = extract_worksheets(root)
    titles = ws[0]["sheet_style"]["axis_titles"]
    assert len(titles) == 2
    assert titles[0]["field"] == "sum_profit_qk"
    assert titles[0]["title"] == "#  Profit"
    assert titles[1]["field"] == "sum_sales_qk"
    assert titles[1]["title"] == "#  Sales"


def test_axis_title_absent_for_font_only_rule():
    """font-family / font-size on scope='cols' must not appear in axis_titles."""
    root = parse_workbook_xml(_XML_AXIS_FONT_ONLY)
    ws = extract_worksheets(root)
    titles = ws[0]["sheet_style"].get("axis_titles", [])
    assert titles == []


def test_axis_title_absent_when_no_axis_rule():
    root = parse_workbook_xml(_XML_NO_AXIS_RULE)
    ws = extract_worksheets(root)
    titles = ws[0]["sheet_style"].get("axis_titles", [])
    assert titles == []
```

- [x] **Step 2: Run tests to confirm they fail**

```
pytest tests/unit/extract/test_worksheets.py::test_axis_title_extracted_single_measure tests/unit/extract/test_worksheets.py::test_axis_title_extracted_multi_measure_order_preserved tests/unit/extract/test_worksheets.py::test_axis_title_absent_for_font_only_rule tests/unit/extract/test_worksheets.py::test_axis_title_absent_when_no_axis_rule -v
```

Expected: FAIL — `axis_titles` key missing from `sheet_style`.

- [x] **Step 3: Implement in `src/tableau2pbir/extract/worksheets.py`**

In `_sheet_style()`, inside the `for rule in table.findall("style/style-rule"):` loop, add a new `elif` branch after the existing `elif element == "header" ...` block:

```python
                elif element == "axis":
                    fmt_field = optional_attr(fmt, "field")
                    scope = optional_attr(fmt, "scope")
                    if a == "title" and fmt_field and v:
                        field_slug = slug_id(_parse_filter_column(fmt_field))
                        style.setdefault("axis_titles", []).append(
                            {"field": field_slug, "scope": scope or "rows", "title": v}
                        )
```

The full updated block (lines 406–441) becomes:

```python
    if table is not None:
        for rule in table.findall("style/style-rule"):
            element = optional_attr(rule, "element")
            field = optional_attr(rule, "field")
            for fmt in rule.findall("format"):
                a = optional_attr(fmt, "attr")
                v = optional_attr(fmt, "value")
                if not a or v is None:
                    continue
                if element == "field-labels" and field is None:
                    if a == "font-family":
                        style["axis_font_name"] = v
                    elif a == "font-size":
                        try:
                            style["axis_font_size"] = int(v)
                        except ValueError:
                            pass
                elif element == "cell":
                    fmt_field = optional_attr(fmt, "field")
                    if a == "text-format" and fmt_field is not None:
                        style["number_formats"][fmt_field] = v
                    elif a == "font-family" and field is None:
                        style["cell_font_name"] = v
                    elif a == "font-size" and field is None:
                        try:
                            style["cell_font_size"] = int(v)
                        except ValueError:
                            pass
                elif element == "header" and field is None:
                    if a == "font-family":
                        style["header_font_name"] = v
                    elif a == "font-size":
                        try:
                            style["header_font_size"] = int(v)
                        except ValueError:
                            pass
                elif element == "axis":
                    fmt_field = optional_attr(fmt, "field")
                    scope = optional_attr(fmt, "scope")
                    if a == "title" and fmt_field and v:
                        field_slug = slug_id(_parse_filter_column(fmt_field))
                        style.setdefault("axis_titles", []).append(
                            {"field": field_slug, "scope": scope or "rows", "title": v}
                        )
```

No new imports needed — `slug_id` and `_parse_filter_column` are already in scope.

- [x] **Step 4: Run tests to confirm they pass**

```
pytest tests/unit/extract/test_worksheets.py -v
```

Expected: All pass.

- [x] **Step 5: Run full unit suite to confirm no regressions**

```
pytest tests/unit/ -x -q
```

Expected: All pass.

- [x] **Step 6: Commit**

```
git add src/tableau2pbir/extract/worksheets.py tests/unit/extract/test_worksheets.py
git commit -m "feat(extract): parse axis title text from style-rule element=axis scope=rows"
```

---

## Task 3 — Build: wire `AxisTitle` from raw style dict through to `VisualFormat`

**Files:**
- Modify: `src/tableau2pbir/stages/_build_sheets.py`
- Modify: `tests/unit/stages/test_s02_sheets.py`

- [x] **Step 1: Write the failing tests**

Add to `tests/unit/stages/test_s02_sheets.py`:

```python
def _raw_with_style(style_extra: dict) -> dict:
    """Build a minimal raw worksheet dict with the given sheet_style overrides."""
    return {
        "name": "S", "datasource_refs": ("ds",), "mark_type": "line",
        "encodings": {"rows": ("sum:sales:qk",), "columns": ("yr:order_date:ok",),
                      "color": None, "size": None, "label": None, "tooltip": None,
                      "detail": (), "shape": None, "angle": None, "text": None},
        "filters": [], "sort": [], "dual_axis": False, "reference_lines": [],
        "quick_table_calcs": [],
        "sheet_style": style_extra,
    }


def test_axis_titles_single_wired_to_visual_format():
    raw = _raw_with_style({
        "axis_titles": [{"field": "sum_sales_qk", "scope": "rows", "title": "#  Revenue"}],
    })
    sheets, _ = build_sheets([raw], calc_names=set(), table_id_for_ref={"ds": "tbl__ds"})
    vf = sheets[0].visual_format
    assert vf is not None
    assert len(vf.axis_titles) == 1
    assert vf.axis_titles[0].field_id == "sum_sales_qk"
    assert vf.axis_titles[0].scope == "rows"
    assert vf.axis_titles[0].title == "#  Revenue"


def test_axis_titles_multi_measure_order_preserved():
    raw = _raw_with_style({
        "axis_titles": [
            {"field": "sum_profit_qk", "scope": "rows", "title": "#  Profit"},
            {"field": "sum_sales_qk", "scope": "rows", "title": "#  Sales"},
        ],
    })
    sheets, _ = build_sheets([raw], calc_names=set(), table_id_for_ref={"ds": "tbl__ds"})
    vf = sheets[0].visual_format
    assert vf is not None
    assert len(vf.axis_titles) == 2
    assert vf.axis_titles[0].title == "#  Profit"
    assert vf.axis_titles[1].title == "#  Sales"


def test_axis_titles_absent_produces_no_visual_format():
    """A raw dict with no sheet_style at all → visual_format remains None."""
    raw = {
        "name": "S", "datasource_refs": ("ds",), "mark_type": "bar",
        "encodings": {"rows": ("amount",), "columns": ("month",),
                      "color": None, "size": None, "label": None, "tooltip": None,
                      "detail": (), "shape": None, "angle": None, "text": None},
        "filters": [], "sort": [], "dual_axis": False, "reference_lines": [],
        "quick_table_calcs": [],
    }
    sheets, _ = build_sheets([raw], calc_names=set(), table_id_for_ref={"ds": "tbl__ds"})
    assert sheets[0].visual_format is None
```

- [x] **Step 2: Run tests to confirm they fail**

```
pytest tests/unit/stages/test_s02_sheets.py::test_axis_titles_single_wired_to_visual_format tests/unit/stages/test_s02_sheets.py::test_axis_titles_multi_measure_order_preserved tests/unit/stages/test_s02_sheets.py::test_axis_titles_absent_produces_no_visual_format -v
```

Expected: FAIL — `VisualFormat` has no `axis_titles` populated (import error or missing field).

- [x] **Step 3: Implement in `src/tableau2pbir/stages/_build_sheets.py`**

Add `AxisTitle` to the import from `tableau2pbir.ir.sheet`:

```python
from tableau2pbir.ir.sheet import (
    AxisTitle, AxisTitleFormat, CategoricalFilter, ConditionalFilter, ContextFilter,
    Encoding, Filter, RangeFilter, ReferenceLine, Sheet, SortSpec, TableFormat,
    TitleFormat, TopNFilter, VisualFormat,
)
```

In `_build_visual_format()`, add axis_titles construction after the `number_formats` block (before the early-exit guard):

```python
    axis_titles: tuple[AxisTitle, ...] = tuple(
        AxisTitle(field_id=at["field"], scope=at["scope"], title=at["title"])
        for at in raw_style.get("axis_titles", [])
    )
```

Update the early-exit guard to include `axis_titles`:

```python
    if (title is None and not raw_style.get("mark_color")
            and not raw_style.get("labels_show")
            and axis is None and table_fmt is None
            and not number_formats
            and not raw_style.get("pane_colors")
            and not axis_titles):
        return None
```

Update `VisualFormat(...)` to pass `axis_titles`:

```python
    return VisualFormat(
        title=title,
        mark_color=raw_style.get("mark_color"),
        labels_show=bool(raw_style.get("labels_show", False)),
        axis=axis,
        table=table_fmt,
        number_formats=number_formats,
        pane_colors=raw_style.get("pane_colors") or {},
        axis_titles=axis_titles,
    )
```

- [x] **Step 4: Run tests to confirm they pass**

```
pytest tests/unit/stages/test_s02_sheets.py -v
```

Expected: All pass.

- [x] **Step 5: Run full unit suite to confirm no regressions**

```
pytest tests/unit/ -x -q
```

Expected: All pass.

- [x] **Step 6: Commit**

```
git add src/tableau2pbir/stages/_build_sheets.py tests/unit/stages/test_s02_sheets.py
git commit -m "feat(stages): wire AxisTitle from raw style dict through to VisualFormat.axis_titles"
```

---

## Task 4 — Emit: `titleText` in `valueAxis` via `format_map` + `render_visual`

**Files:**
- Modify: `src/tableau2pbir/visualmap/format_map.py`
- Modify: `src/tableau2pbir/emit/pbir/visual.py`
- Modify: `tests/unit/visualmap/test_format_map.py`
- Modify: `tests/unit/emit/pbir/test_visual.py`

- [x] **Step 1: Write the failing `format_map` tests**

Add to `tests/unit/visualmap/test_format_map.py`:

```python
def test_value_axis_title_text_emitted_alone():
    """titleText alone (no axis font) produces a valueAxis entry."""
    vf = VisualFormat()
    objects, _ = build_format_objects(vf, "lineChart", row_axis_title="#  Revenue")
    assert "valueAxis" in objects
    props = objects["valueAxis"][0]["properties"]
    assert props["titleText"] == _lit("'#  Revenue'")
    assert "selector" not in objects["valueAxis"][0]


def test_value_axis_title_merged_with_axis_font():
    """titleText and titleFontFamily/titleFontSize appear in the same valueAxis entry."""
    vf = VisualFormat(axis=AxisTitleFormat(font_name="Verdana", font_size=16))
    objects, _ = build_format_objects(vf, "columnChart", row_axis_title="#  Profit")
    props = objects["valueAxis"][0]["properties"]
    assert props["titleText"] == _lit("'#  Profit'")
    assert props["titleFontFamily"] == _lit("'Verdana'")
    assert props["titleFontSize"] == _lit("16D")


def test_no_row_axis_title_no_valueaxis_added():
    """If no row_axis_title is provided and no axis font, no valueAxis is emitted."""
    vf = VisualFormat()
    objects, _ = build_format_objects(vf, "columnChart")
    assert "valueAxis" not in objects


def test_row_axis_title_not_emitted_for_table():
    """tableEx visuals must not get valueAxis even when row_axis_title is set."""
    vf = VisualFormat()
    objects, _ = build_format_objects(vf, "tableEx", row_axis_title="#  Revenue")
    assert "valueAxis" not in objects
```

- [x] **Step 2: Write the failing `render_visual` tests**

Add to `tests/unit/emit/pbir/test_visual.py`:

```python
from tableau2pbir.ir.sheet import AxisTitle, VisualFormat


def test_render_visual_emits_value_axis_title_single_measure():
    vf = VisualFormat(
        axis_titles=(AxisTitle(field_id="sum_sales_qk", scope="rows", title="#  Revenue"),)
    )
    pv = PbirVisual(
        visual_type="lineChart",
        encoding_bindings=(
            EncodingBinding(channel="Category", source_field_id="yr_order_date_ok"),
            EncodingBinding(channel="Y", source_field_id="sum_sales_qk"),
        ),
        visual_format=vf,
    )
    lookup = {
        "yr_order_date_ok": {"table_name": "orders", "col_name": "Year order_date", "is_measure": False},
        "sum_sales_qk": {"table_name": "orders", "measure_name": "Sum sales",
                         "col_name": "Sum sales", "is_measure": True},
    }
    pos = Position(x=0, y=0, w=400, h=300)
    obj = json.loads(render_visual("v2", pv, pos, 0, field_lookup=lookup))
    val_axis = obj["visual"]["objects"]["valueAxis"]
    assert len(val_axis) == 1
    assert "selector" not in val_axis[0]
    assert val_axis[0]["properties"]["titleText"] == {
        "expr": {"Literal": {"Value": "'#  Revenue'"}}
    }


def test_render_visual_first_axis_title_wins_for_multi_measure():
    """Multi-measure: first AxisTitle by tuple order → single valueAxis, no selector."""
    vf = VisualFormat(
        axis_titles=(
            AxisTitle(field_id="sum_profit_qk", scope="rows", title="#  Profit"),
            AxisTitle(field_id="sum_sales_qk", scope="rows", title="#  Sales"),
        )
    )
    pv = PbirVisual(
        visual_type="columnChart",
        encoding_bindings=(
            EncodingBinding(channel="Category", source_field_id="none_region_nk"),
            EncodingBinding(channel="Y", source_field_id="sum_profit_qk"),
            EncodingBinding(channel="Y", source_field_id="sum_sales_qk"),
        ),
        visual_format=vf,
    )
    lookup = {
        "none_region_nk": {"table_name": "people", "col_name": "region", "is_measure": False},
        "sum_profit_qk": {"table_name": "orders", "measure_name": "Sum profit",
                          "col_name": "Sum profit", "is_measure": True},
        "sum_sales_qk": {"table_name": "orders", "measure_name": "Sum sales",
                         "col_name": "Sum sales", "is_measure": True},
    }
    pos = Position(x=0, y=0, w=400, h=300)
    obj = json.loads(render_visual("v1", pv, pos, 0, field_lookup=lookup))
    val_axis = obj["visual"]["objects"]["valueAxis"]
    assert len(val_axis) == 1
    assert "selector" not in val_axis[0]
    assert val_axis[0]["properties"]["titleText"]["expr"]["Literal"]["Value"] == "'#  Profit'"


def test_render_visual_no_axis_title_when_field_not_in_lookup():
    """If the axis title field_id is not in field_lookup, no valueAxis is emitted."""
    vf = VisualFormat(
        axis_titles=(AxisTitle(field_id="unknown_field", scope="rows", title="#  Revenue"),)
    )
    pv = PbirVisual(
        visual_type="lineChart",
        encoding_bindings=(
            EncodingBinding(channel="Y", source_field_id="sum_sales_qk"),
        ),
        visual_format=vf,
    )
    lookup = {
        "sum_sales_qk": {"table_name": "orders", "measure_name": "Sum sales",
                         "col_name": "Sum sales", "is_measure": True},
    }
    pos = Position(x=0, y=0, w=400, h=300)
    obj = json.loads(render_visual("v2", pv, pos, 0, field_lookup=lookup))
    # "unknown_field" not in queryref_by_source_id → no valueAxis for title
    assert "valueAxis" not in obj["visual"]["objects"]
```

- [x] **Step 3: Run tests to confirm they fail**

```
pytest tests/unit/visualmap/test_format_map.py::test_value_axis_title_text_emitted_alone tests/unit/visualmap/test_format_map.py::test_value_axis_title_merged_with_axis_font tests/unit/emit/pbir/test_visual.py::test_render_visual_emits_value_axis_title_single_measure -v
```

Expected: FAIL — `build_format_objects()` does not accept `row_axis_title` kwarg.

- [x] **Step 4: Update `src/tableau2pbir/visualmap/format_map.py`**

Update the `build_format_objects` signature to add `row_axis_title`:

```python
def build_format_objects(
    vf: VisualFormat | None,
    visual_type: str,
    per_series_colors: list[tuple[str, str]] | None = None,
    row_axis_title: str | None = None,
) -> tuple[dict[str, list[dict]], dict[str, list[dict]]]:
```

Replace the existing `if visual_type in _CHART_TYPES and vf.axis:` block (lines 66–79) with a restructured version that handles both axis font and axis title text:

```python
    if visual_type in _CHART_TYPES:
        cat_props: dict = {}
        val_props: dict = {}
        if vf.axis:
            ax = vf.axis
            if ax.font_name:
                cat_props["titleFontFamily"] = _font_name_lit(ax.font_name)
                val_props["titleFontFamily"] = _font_name_lit(ax.font_name)
            if ax.font_size:
                cat_props["titleFontSize"] = _font_size_lit(ax.font_size)
                val_props["titleFontSize"] = _font_size_lit(ax.font_size)
        if row_axis_title is not None:
            val_props["titleText"] = _lit(f"'{row_axis_title}'")
        if cat_props:
            objects["categoryAxis"] = [{"properties": cat_props}]
        if val_props:
            objects["valueAxis"] = [{"properties": val_props}]
```

- [x] **Step 5: Update `src/tableau2pbir/emit/pbir/visual.py`**

After the `queryref_by_source_id` dict is fully populated (after the `for b in pbir_visual.encoding_bindings:` loop, before the per-series-colors block), add:

```python
    # Resolve Y-axis title: first scope='rows' AxisTitle whose field_id is in the query.
    row_axis_title: str | None = None
    if vf is not None:
        for at in vf.axis_titles:
            if at.scope == "rows" and row_axis_title is None:
                if queryref_by_source_id.get(at.field_id):
                    row_axis_title = at.title
```

Update the `build_format_objects(...)` call to pass `row_axis_title`:

```python
    if vf is not None:
        objects, container_objects = build_format_objects(
            vf, pbir_visual.visual_type,
            per_series_colors=per_series_colors or None,
            row_axis_title=row_axis_title,
        )
```

The full `render_visual` function after the changes:

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

    # Build projections; capture queryRef per source_field_id for later resolution.
    query_state: dict[str, dict] = {}
    queryref_by_source_id: dict[str, str] = {}
    for b in pbir_visual.encoding_bindings:
        proj = _make_projection(b.source_field_id, fl,
                                number_formats if vf is not None else {})
        query_state.setdefault(b.channel, {"projections": []})
        query_state[b.channel]["projections"].append(proj)
        queryref_by_source_id[b.source_field_id] = proj["queryRef"]

    # Resolve Y-axis title: first scope='rows' AxisTitle whose field_id is in the query.
    row_axis_title: str | None = None
    if vf is not None:
        for at in vf.axis_titles:
            if at.scope == "rows" and row_axis_title is None:
                if queryref_by_source_id.get(at.field_id):
                    row_axis_title = at.title

    # Resolve per-series colors: pane_colors (dual-axis) or mark_color (single-series).
    per_series_colors: list[tuple[str, str]] = []
    if vf is not None and (vf.pane_colors or vf.mark_color):
        for b in pbir_visual.encoding_bindings:
            if b.channel != "Y":
                continue
            qr = queryref_by_source_id.get(b.source_field_id)
            if not qr:
                continue
            color = (vf.pane_colors.get(b.source_field_id) or vf.mark_color
                     if vf.pane_colors else vf.mark_color)
            if color:
                per_series_colors.append((qr, color))

    if vf is not None:
        objects, container_objects = build_format_objects(
            vf, pbir_visual.visual_type,
            per_series_colors=per_series_colors or None,
            row_axis_title=row_axis_title,
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

- [x] **Step 6: Run all new tests**

```
pytest tests/unit/visualmap/test_format_map.py tests/unit/emit/pbir/test_visual.py -v
```

Expected: All pass.

- [x] **Step 7: Run full unit suite**

```
pytest tests/unit/ -x -q
```

Expected: All pass.

- [x] **Step 8: Commit**

```
git add src/tableau2pbir/visualmap/format_map.py src/tableau2pbir/emit/pbir/visual.py tests/unit/visualmap/test_format_map.py tests/unit/emit/pbir/test_visual.py
git commit -m "feat(emit): emit valueAxis.titleText from AxisTitle IR via render_visual and format_map"
```

---

## Task 5 — E2E Gate + Output Verification

**Files:**
- Read: `out/simple_join_calculated_line_dashboard/Report/definition/pages/ReportSection1/visuals/visual_1/visual.json`
- Read: `out/simple_join_calculated_line_dashboard/Report/definition/pages/ReportSection2/visuals/visual_2/visual.json`
- Read: `out/simple_join_calculated_line_dashboard/Report/definition/pages/ReportSection3/visuals/visual_3/visual.json`

- [x] **Step 1: Run real-workbook E2E gate**

```
pytest tests/integration/test_real_workbooks_e2e.py -v
```

Expected: All pass.

- [x] **Step 2: Re-convert `simple_join_calculated_line_dashboard.twb`**

```
python -m tableau2pbir convert tests/golden/real/simple_join_calculated_line_dashboard.twb out/simple_join_calculated_line_dashboard
```

Expected: completes without error.

- [x] **Step 3: Verify 'Sales Year' axis title (single-measure)**

```
python -c "import json; d=json.load(open('out/simple_join_calculated_line_dashboard/Report/definition/pages/ReportSection2/visuals/visual_2/visual.json')); print(json.dumps(d['visual']['objects'].get('valueAxis'), indent=2))"
```

Expected output:
```json
[
  {
    "properties": {
      "titleText": {
        "expr": {
          "Literal": {
            "Value": "'#  Revenue'"
          }
        }
      }
    }
  }
]
```

- [x] **Step 4: Verify 'Sales Profit' axis title (multi-measure, first wins)**

```
python -c "import json; d=json.load(open('out/simple_join_calculated_line_dashboard/Report/definition/pages/ReportSection1/visuals/visual_1/visual.json')); print(json.dumps(d['visual']['objects'].get('valueAxis'), indent=2))"
```

Expected output (first title `'#  Profit'`, no `selector`):
```json
[
  {
    "properties": {
      "titleText": {
        "expr": {
          "Literal": {
            "Value": "'#  Profit'"
          }
        }
      }
    }
  }
]
```

- [x] **Step 5: Verify dashboard visual (ReportSection3/visual_3) has the same axis title**

```
python -c "import json; d=json.load(open('out/simple_join_calculated_line_dashboard/Report/definition/pages/ReportSection3/visuals/visual_3/visual.json')); print(json.dumps(d['visual']['objects'].get('valueAxis'), indent=2))"
```

Expected: Same `'#  Profit'` output as Step 4 (dashboard embeds the same sheet).

- [x] **Step 6: Commit**

```
git add -A
git commit -m "test(e2e): verify axis title text emission for simple_join_calculated_line_dashboard"
```

---

## Self-Review

### Spec Coverage

| Requirement | Task |
|---|---|
| Y-axis label on 'Sales Profit' sheet matches Tableau | Task 4 + Task 5 Step 4 |
| Y-axis label on 'Sales Year' sheet matches Tableau | Task 4 + Task 5 Step 3 |
| Company Dashboard visual Y-axis label matches | Task 5 Step 5 |
| All future visuals with axis titles handled | Extract runs per worksheet; emit runs per visual — automatic |
| `class='0'` safely ignored | Task 2 Step 3 — filter by `a == "title"` only |
| Multi-measure: first title wins | Task 4 tests + Task 5 Step 4 |
| No `selector` on `valueAxis` | Task 4 test assertions + Task 5 verification |
| `showAxisTitle` not emitted | Not in any emit code — confirmed unnecessary |
| `scope='cols'` not needed for real workbooks | Captured by extraction but only `scope=='rows'` used in emit |

### Placeholder Scan

None found. Every step has exact code, exact commands, expected output.

### Type Consistency

| Symbol | Defined in | Used in |
|---|---|---|
| `AxisTitle` (model) | Task 1 `ir/sheet.py` | Task 2 tests, Task 3 `_build_sheets.py`, Task 4 tests |
| `VisualFormat.axis_titles` | Task 1 `ir/sheet.py` | Task 3 `_build_visual_format()`, Task 4 `render_visual()` |
| `at.field_id` | Task 1 `AxisTitle.field_id: str` | Task 2 extraction (slug form), Task 4 `render_visual` lookup |
| `row_axis_title: str | None` | Task 4 `format_map.py` parameter | Task 4 `render_visual.py` call site |
| `_lit(f"'{row_axis_title}'")`  | Task 4 `format_map.py` | wraps title text in existing `_lit()` helper — consistent |
| `slug_id(_parse_filter_column(fmt_field))` | Task 2 extraction | produces same slug as `FieldRef.column_id` via `stable_id("", name).lstrip("_")` — verified in `util/ids.py` |
