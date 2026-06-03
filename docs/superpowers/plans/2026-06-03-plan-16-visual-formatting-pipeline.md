# Visual Formatting Pipeline Implementation Plan

> **Execution mode: SUBAGENT-DRIVEN** â€” REQUIRED SUB-SKILL: `superpowers:subagent-driven-development`. Dispatch one fresh subagent per task, review output between tasks. Do NOT use inline execution. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract Tableau visual formatting (title text/font, mark color, data labels, axis title font, table cell/header font, currency number format) from the TWB XML and emit it into the correct PBIR `visual.objects` and `visual.visualContainerObjects` JSON structures.

**Architecture:** A new `VisualFormat` IR model replaces the thin `MarkStyle` and the always-null `Sheet.format` stub. A new `_sheet_style()` extractor reads all confirmed style-rule elements plus the `<layout-options>/<title>` block. A new `format_map.py` module translates `VisualFormat` â†’ PBI JSON objects at render time (not dispatch time), keeping dispatch decoupled from PBI schema details.

**Tech Stack:** Python 3.11, Pydantic v2, lxml, pytest. No new dependencies.

---

## Evidence Base

Every mapping below is confirmed from actual files â€” no assumptions:

| Tableau XML source | PBI target | Evidence |
|---|---|---|
| `<run fontname='...'>` on `<title>` | `visualContainerObjects.title.fontFamily` | TWB line 515/631/729 + manual PBIR visual_2/visual_3 |
| `<run fontsize='...'>` | `visualContainerObjects.title.fontSize` (`"20D"` form) | Same |
| `<run bold='true'>` | `visualContainerObjects.title.bold` | Schema `Title` def line 841; same pattern as `underline` (confirmed) |
| `<run italic='true'>` | `visualContainerObjects.title.italic` | Schema `Title` def line 842 |
| `<run underline='true'>` | `visualContainerObjects.title.underline` | Manual PBIR visual_1 `visualContainerObjects.title.underline` |
| `<run fontcolor='#...'>` | `visualContainerObjects.title.fontColor` | Schema `Title` def line 837; color encoding pattern from `dataPoint.fill` |
| `<run>` text content | `visualContainerObjects.title.text` | Manual PBIR visual_2 `"'Category and  SubCategory Details'"` |
| `mark-color` pane style-rule | `visual.objects.dataPoint.fill.solid.color` | TWB line 613 + manual PBIR visual_1 |
| `mark-labels-show` pane style-rule | `visual.objects.labels.show` | TWB line 611 + manual PBIR visual_1 |
| `field-labels` font-family/font-size (global) | `visual.objects.categoryAxis.titleFontFamily/titleFontSize` and `valueAxis.*` | Manual PBIR visual_1 `categoryAxis`/`valueAxis` cards |
| `cell` font-family/font-size (global, no field) | `visual.objects.values.fontFamily/fontSize` | Manual PBIR visual_2/visual_3 `values` card |
| `header` font-family/font-size | `visual.objects.columnHeaders.fontFamily/fontSize` | Manual PBIR visual_2/visual_3 `columnHeaders` card |
| `cell` `text-format='C1033%'` (field-scoped) | `projection.format = "\\$#,0.00;(\\$#,0.00);\\$#,0.00"` | TWB lines 559/765 + PBI Desktop UI screenshot + manual PBIR `visual_3` projection |

**Axis line colors and gridlines are NOT in scope** â€” card names unconfirmed. Scoped as Task 9 (discovery).

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `src/tableau2pbir/ir/sheet.py` | Modify | Add `TitleFormat`, `AxisTitleFormat`, `TableFormat`, `VisualFormat`; replace `Sheet.mark_style: MarkStyle` with `Sheet.visual_format: VisualFormat`; add `PbirVisual.visual_format`; remove `MarkStyle` |
| `src/tableau2pbir/visualmap/number_format.py` | Create | Translate Tableau `text-format` codes â†’ DAX format strings |
| `src/tableau2pbir/extract/worksheets.py` | Modify | Replace `_mark_style()` with `_sheet_style()` that reads title, field-labels, cell, header, and mark style-rules |
| `src/tableau2pbir/stages/_build_sheets.py` | Modify | Replace `_build_mark_style()` with `_build_visual_format()` that populates full `VisualFormat` |
| `src/tableau2pbir/visualmap/format_map.py` | Create | `build_format_objects(vf, visual_type)` â†’ `(objects, container_objects)` |
| `src/tableau2pbir/visualmap/dispatch.py` | Modify | Remove `_build_format_objects()`; pass `visual_format=sheet.visual_format` through all `PbirVisual` constructions |
| `src/tableau2pbir/emit/pbir/visual.py` | Modify | Call `build_format_objects()` at render time; emit `visualContainerObjects`; add `projection.format` |
| `tests/unit/visualmap/test_number_format.py` | Create | Unit tests for format code translator |
| `tests/unit/extract/test_sheet_style.py` | Create | Unit tests for `_sheet_style()` extractor |
| `tests/unit/visualmap/test_format_map.py` | Create | Unit tests for `build_format_objects()` |
| `tests/unit/emit/pbir/test_visual.py` | Modify | Add tests for `visualContainerObjects` emission and `projection.format` |
| `tests/integration/test_real_workbooks_e2e.py` | Verify | Regression guard â€” must pass unchanged |

---

## Task 1: VisualFormat IR Models

**Files:**
- Modify: `src/tableau2pbir/ir/sheet.py`

- [x] **Step 1: Write failing tests for new IR models**

```python
# tests/unit/ir/test_sheet_format.py
from tableau2pbir.ir.sheet import TitleFormat, AxisTitleFormat, TableFormat, VisualFormat

def test_title_format_defaults():
    t = TitleFormat()
    assert t.text is None
    assert t.bold is False
    assert t.italic is False
    assert t.underline is False
    assert t.font_color is None

def test_title_format_full():
    t = TitleFormat(
        text="Category Based Profit",
        font_name="Verdana",
        font_size=20,
        bold=True,
        italic=True,
        underline=False,
        font_color="#e15759",
    )
    assert t.text == "Category Based Profit"
    assert t.font_name == "Verdana"
    assert t.font_size == 20
    assert t.bold is True
    assert t.italic is True

def test_visual_format_defaults():
    vf = VisualFormat()
    assert vf.title is None
    assert vf.mark_color is None
    assert vf.labels_show is False
    assert vf.axis is None
    assert vf.table is None
    assert vf.number_formats == {}

def test_visual_format_with_all_fields():
    vf = VisualFormat(
        title=TitleFormat(text="My Chart", font_name="Arial", font_size=14),
        mark_color="#f28e2b",
        labels_show=True,
        axis=AxisTitleFormat(font_name="Verdana", font_size=16),
        table=TableFormat(cell_font_name="Verdana", header_font_name="Arial Black"),
        number_formats={"usr_calc_01_qk": r"\$#,0.00;(\$#,0.00);\$#,0.00"},
    )
    assert vf.title.text == "My Chart"
    assert vf.axis.font_size == 16
    assert vf.table.header_font_name == "Arial Black"
    assert "usr_calc_01_qk" in vf.number_formats
```

- [x] **Step 2: Run to confirm failure**

```
pytest tests/unit/ir/test_sheet_format.py -v
```
Expected: `ImportError` â€” `TitleFormat` does not exist yet.

- [x] **Step 3: Add new IR models and update `Sheet` / `PbirVisual`**

In `src/tableau2pbir/ir/sheet.py`, replace the `MarkStyle` class and update `Sheet` and `PbirVisual`:

```python
# Remove the MarkStyle class entirely (lines 82-84).
# Add these four new classes before the Sheet definition:

class TitleFormat(IRBase):
    text: str | None = None
    font_name: str | None = None
    font_size: int | None = None
    bold: bool = False
    italic: bool = False
    underline: bool = False
    font_color: str | None = None      # hex, e.g. "#e15759"


class AxisTitleFormat(IRBase):
    font_name: str | None = None
    font_size: int | None = None


class TableFormat(IRBase):
    cell_font_name: str | None = None
    cell_font_size: int | None = None
    header_font_name: str | None = None
    header_font_size: int | None = None


class VisualFormat(IRBase):
    title: TitleFormat | None = None
    mark_color: str | None = None
    labels_show: bool = False
    axis: AxisTitleFormat | None = None        # chart axis title font (both axes same)
    table: TableFormat | None = None           # table cell and header font
    number_formats: dict[str, str] = {}        # column_id â†’ DAX format string
```

In `Sheet`, replace:
```python
    mark_style: MarkStyle | None = None
    format: dict[str, str] | None = None
```
with:
```python
    visual_format: VisualFormat | None = None
```

In `PbirVisual`, add one field after `format`:
```python
    visual_format: VisualFormat | None = None   # passed through from Sheet for render-time translation
```

- [x] **Step 4: Run tests**

```
pytest tests/unit/ir/test_sheet_format.py -v
```
Expected: PASS (4 tests).

- [x] **Step 5: Fix broken imports in `_build_sheets.py` and `dispatch.py`**

In `src/tableau2pbir/stages/_build_sheets.py`, update the import:
```python
# Remove MarkStyle from import; add VisualFormat, TitleFormat, AxisTitleFormat, TableFormat
from tableau2pbir.ir.sheet import (
    CategoricalFilter, ConditionalFilter, ContextFilter, Encoding, Filter,
    AxisTitleFormat, TableFormat, TitleFormat, VisualFormat,
    RangeFilter, ReferenceLine, Sheet, SortSpec, TopNFilter,
)
```

In `src/tableau2pbir/visualmap/dispatch.py`, update the import:
```python
from tableau2pbir.ir.sheet import EncodingBinding, VisualFormat, PbirVisual, Sheet, VisualSortEntry
```

- [x] **Step 6: Run full unit test suite to confirm no regressions beyond expected**

```
pytest tests/unit/ -x -q 2>&1 | tail -20
```
Expected: failures only in `_build_sheets.py` (uses `MarkStyle`) and `dispatch.py` (uses `_build_format_objects`). All other tests pass.

- [x] **Step 7: Commit**

```
git add src/tableau2pbir/ir/sheet.py tests/unit/ir/test_sheet_format.py
git commit -m "feat: add VisualFormat IR model replacing MarkStyle"
```

---

## Task 2: Number Format Translator

**Files:**
- Create: `src/tableau2pbir/visualmap/number_format.py`
- Create: `tests/unit/visualmap/test_number_format.py`

- [x] **Step 1: Write failing tests**

```python
# tests/unit/visualmap/test_number_format.py
from tableau2pbir.visualmap.number_format import tableau_format_to_dax

def test_c1033_percent_maps_to_usd():
    """C1033% is Tableau's internal code for US Dollar currency (confirmed from TWB + Tableau Desktop UI)."""
    result = tableau_format_to_dax("C1033%")
    assert result == r"\$#,0.00;(\$#,0.00);\$#,0.00"

def test_none_returns_none():
    assert tableau_format_to_dax(None) is None

def test_empty_returns_none():
    assert tableau_format_to_dax("") is None

def test_unknown_format_returns_none():
    # Unknown codes are not guessed â€” return None so PBI uses its model default.
    assert tableau_format_to_dax("UNKNOWN") is None

def test_c2057_maps_to_gbp():
    """C2057 = en-GB locale = British Pound."""
    result = tableau_format_to_dax("C2057")
    assert result == "Â£#,0.00;(Â£#,0.00);Â£0.00"

def test_c1036_maps_to_eur():
    """C1036 = fr-FR locale = Euro."""
    result = tableau_format_to_dax("C1036")
    assert result == "â‚¬#,0.00;(â‚¬#,0.00);â‚¬0.00"
```

- [x] **Step 2: Run to confirm failure**

```
pytest tests/unit/visualmap/test_number_format.py -v
```
Expected: `ModuleNotFoundError`.

- [x] **Step 3: Implement the translator**

```python
# src/tableau2pbir/visualmap/number_format.py
"""Translate Tableau text-format codes to DAX format strings.

Confirmed mapping (TWB XML line 559/765 + Tableau Desktop UI + PBI Desktop manual):
  C1033%  â†’  \\$#,0.00;(\\$#,0.00);\\$#,0.00   (US Dollar, 2dp, thousands separator)

The C prefix means Currency; the 4-digit number is the Windows LCID.
The trailing % in C1033% is a Tableau-internal format suffix â€” it does NOT
mean the value is a percentage (confirmed: Tableau UI shows "$123,456.00").
"""
from __future__ import annotations
import re

# LCID â†’ currency symbol. Covers LCIDs seen in real Tableau workbooks.
_LCID_SYMBOL: dict[int, str] = {
    1033: "$",   # en-US  (confirmed from simple_join_sorted_test_format.twb)
    2057: "Â£",   # en-GB
    1031: "â‚¬",   # de-DE
    1036: "â‚¬",   # fr-FR
    1041: "Â¥",   # ja-JP
    2052: "Â¥",   # zh-CN
}

_CURRENCY_RE = re.compile(r"^C(\d+)")


def tableau_format_to_dax(tableau_format: str | None) -> str | None:
    """Return a DAX format string for a Tableau text-format code, or None if unknown."""
    if not tableau_format:
        return None
    m = _CURRENCY_RE.match(tableau_format)
    if m:
        lcid = int(m.group(1))
        sym = _LCID_SYMBOL.get(lcid)
        if sym == "$":
            return r"\$#,0.00;(\$#,0.00);\$#,0.00"
        if sym:
            return f"{sym}#,0.00;({sym}#,0.00);{sym}0.00"
    return None
```

- [x] **Step 4: Run tests**

```
pytest tests/unit/visualmap/test_number_format.py -v
```
Expected: PASS (6 tests).

- [x] **Step 5: Commit**

```
git add src/tableau2pbir/visualmap/number_format.py tests/unit/visualmap/test_number_format.py
git commit -m "feat: add Tableau text-format to DAX format string translator"
```

---

## Task 3: Expand Style Extractor

**Files:**
- Modify: `src/tableau2pbir/extract/worksheets.py`
- Create: `tests/unit/extract/test_sheet_style.py`

- [x] **Step 1: Write failing tests**

```python
# tests/unit/extract/test_sheet_style.py
from lxml import etree
from tableau2pbir.extract.worksheets import _sheet_style


def _ws(xml: str) -> tuple:
    """Parse a minimal worksheet XML and return (ws_elem, table_elem, pane_parent)."""
    root = etree.fromstring(xml.encode())
    table = root.find("table")
    return root, table, table if table is not None else root


def test_title_text_and_font_extracted():
    ws, table, pp = _ws("""
    <worksheet name="Sheet 4">
      <layout-options>
        <title>
          <formatted-text>
            <run bold='true' fontname='Verdana' fontsize='20' italic='true'>Category Based  Profit</run>
          </formatted-text>
        </title>
      </layout-options>
      <table><panes><pane><style></style></pane></panes></table>
    </worksheet>
    """)
    result = _sheet_style(ws, table, pp)
    t = result["title"]
    assert t["text"] == "Category Based  Profit"
    assert t["font_name"] == "Verdana"
    assert t["font_size"] == 20
    assert t["bold"] is True
    assert t["italic"] is True
    assert t["underline"] is False
    assert t["font_color"] is None


def test_title_font_color_extracted():
    ws, table, pp = _ws("""
    <worksheet name="Sheet 3">
      <layout-options>
        <title>
          <formatted-text>
            <run fontcolor='#e15759'>Category Details</run>
          </formatted-text>
        </title>
      </layout-options>
      <table><panes><pane><style></style></pane></panes></table>
    </worksheet>
    """)
    result = _sheet_style(ws, table, pp)
    assert result["title"]["font_color"] == "#e15759"


def test_field_labels_font_extracted():
    ws, table, pp = _ws("""
    <worksheet name="S">
      <table>
        <style>
          <style-rule element='field-labels'>
            <format attr='font-family' value='Verdana' />
            <format attr='font-size' value='16' />
          </style-rule>
        </style>
        <panes><pane><style></style></pane></panes>
      </table>
    </worksheet>
    """)
    result = _sheet_style(ws, table, pp)
    assert result["axis_font_name"] == "Verdana"
    assert result["axis_font_size"] == 16


def test_cell_global_font_extracted():
    ws, table, pp = _ws("""
    <worksheet name="S">
      <table>
        <style>
          <style-rule element='cell'>
            <format attr='font-family' value='Verdana' />
            <format attr='font-size' value='9' />
          </style-rule>
        </style>
        <panes><pane><style></style></pane></panes>
      </table>
    </worksheet>
    """)
    result = _sheet_style(ws, table, pp)
    assert result["cell_font_name"] == "Verdana"
    assert result["cell_font_size"] == 9


def test_cell_text_format_field_scoped():
    ws, table, pp = _ws("""
    <worksheet name="S">
      <table>
        <style>
          <style-rule element='cell' field='sum:profit:qk'>
            <format attr='text-format' value='C1033%' />
          </style-rule>
        </style>
        <panes><pane><style></style></pane></panes>
      </table>
    </worksheet>
    """)
    result = _sheet_style(ws, table, pp)
    assert result["number_formats"] == {"sum:profit:qk": "C1033%"}


def test_header_font_extracted():
    ws, table, pp = _ws("""
    <worksheet name="S">
      <table>
        <style>
          <style-rule element='header'>
            <format attr='font-family' value='Arial Black' />
            <format attr='font-size' value='13' />
          </style-rule>
        </style>
        <panes><pane><style></style></pane></panes>
      </table>
    </worksheet>
    """)
    result = _sheet_style(ws, table, pp)
    assert result["header_font_name"] == "Arial Black"
    assert result["header_font_size"] == 13


def test_pane_mark_color_extracted():
    ws, table, pp = _ws("""
    <worksheet name="S">
      <table>
        <panes>
          <pane>
            <style>
              <style-rule element='mark'>
                <format attr='mark-color' value='#f28e2b' />
                <format attr='mark-labels-show' value='true' />
              </style-rule>
            </style>
          </pane>
        </panes>
      </table>
    </worksheet>
    """)
    result = _sheet_style(ws, table, pp)
    assert result["mark_color"] == "#f28e2b"
    assert result["labels_show"] is True


def test_no_style_returns_empty_defaults():
    ws, table, pp = _ws("""
    <worksheet name="S">
      <table><panes><pane><style></style></pane></panes></table>
    </worksheet>
    """)
    result = _sheet_style(ws, table, pp)
    assert result["title"] is None
    assert result["mark_color"] is None
    assert result["labels_show"] is False
    assert result["axis_font_name"] is None
    assert result["number_formats"] == {}
```

- [x] **Step 2: Run to confirm failure**

```
pytest tests/unit/extract/test_sheet_style.py -v
```
Expected: `ImportError` â€” `_sheet_style` does not exist.

- [x] **Step 3: Implement `_sheet_style()` in `worksheets.py`**

Replace the `_mark_style()` function (lines 331â€“343) with:

```python
def _sheet_style(
    ws: etree._Element,
    table: etree._Element | None,
    pane_parent: etree._Element,
) -> dict[str, Any]:
    """Extract all confirmed visual formatting from a worksheet element.

    Reads:
    - <layout-options>/<title>/<formatted-text>/<run> for title font/text
    - <table>/<style>/<style-rule element='field-labels'> for axis title font
    - <table>/<style>/<style-rule element='cell'> for cell font + text-format (number format)
    - <table>/<style>/<style-rule element='header'> for column header font
    - pane <style-rule element='mark'> for mark color and label visibility
    """
    style: dict[str, Any] = {
        "title": None,
        "mark_color": None,
        "labels_show": False,
        "axis_font_name": None,
        "axis_font_size": None,
        "cell_font_name": None,
        "cell_font_size": None,
        "header_font_name": None,
        "header_font_size": None,
        "number_formats": {},   # raw field key â†’ Tableau format code
    }

    # --- Title: formally documented in Tableau XSD (FormattedText-G group) ---
    run = ws.find("layout-options/title/formatted-text/run")
    if run is not None:
        fs_str = optional_attr(run, "fontsize")
        fs_int: int | None = None
        if fs_str is not None:
            try:
                fs_int = int(fs_str)
            except ValueError:
                pass
        style["title"] = {
            "text": run.text or "",
            "font_name": optional_attr(run, "fontname"),
            "font_size": fs_int,
            "bold": optional_attr(run, "bold") == "true",
            "italic": optional_attr(run, "italic") == "true",
            "underline": optional_attr(run, "underline") == "true",
            "font_color": optional_attr(run, "fontcolor"),
        }

    # --- Table-level style rules (NOT in Tableau XSD â€” permissive wildcard area) ---
    if table is not None:
        for rule in table.findall("style/style-rule"):
            element = optional_attr(rule, "element")
            field = optional_attr(rule, "field")   # None = global, value = field-scoped
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
                    if a == "text-format" and field is not None:
                        style["number_formats"][field] = v
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

    return style
```

- [x] **Step 4: Update `extract_worksheets()` to call `_sheet_style()`**

In the `out.append({...})` block (around line 373), replace:
```python
            "mark_style": _mark_style(pane_parent),
```
with:
```python
            "sheet_style": _sheet_style(ws, table, pane_parent),
```

- [x] **Step 5: Run tests**

```
pytest tests/unit/extract/test_sheet_style.py -v
```
Expected: PASS (9 tests).

- [x] **Step 6: Run full unit suite to spot regressions**

```
pytest tests/unit/ -x -q 2>&1 | tail -20
```
Expected: failures only in `_build_sheets.py` (`mark_style` key renamed to `sheet_style`). No other failures.

- [x] **Step 7: Commit**

```
git add src/tableau2pbir/extract/worksheets.py tests/unit/extract/test_sheet_style.py
git commit -m "feat: replace _mark_style() with _sheet_style() â€” title, axis, cell, header, number format"
```

---

## Task 4: Wire `_build_visual_format()` in Stage 2

**Files:**
- Modify: `src/tableau2pbir/stages/_build_sheets.py`

- [x] **Step 1: Write failing tests**

```python
# tests/unit/stages/test_s02_visual_format.py
from tableau2pbir.stages._build_sheets import _build_visual_format
from tableau2pbir.ir.sheet import VisualFormat, TitleFormat, AxisTitleFormat, TableFormat


def test_none_raw_returns_none():
    assert _build_visual_format(None) is None


def test_mark_color_and_labels_show():
    vf = _build_visual_format({"mark_color": "#f28e2b", "labels_show": True,
                                "title": None, "axis_font_name": None, "axis_font_size": None,
                                "cell_font_name": None, "cell_font_size": None,
                                "header_font_name": None, "header_font_size": None,
                                "number_formats": {}})
    assert isinstance(vf, VisualFormat)
    assert vf.mark_color == "#f28e2b"
    assert vf.labels_show is True
    assert vf.title is None
    assert vf.axis is None


def test_title_fields_populated():
    raw = {
        "mark_color": None, "labels_show": False,
        "axis_font_name": None, "axis_font_size": None,
        "cell_font_name": None, "cell_font_size": None,
        "header_font_name": None, "header_font_size": None,
        "number_formats": {},
        "title": {
            "text": "Category Based  Profit",
            "font_name": "Verdana",
            "font_size": 20,
            "bold": True,
            "italic": True,
            "underline": False,
            "font_color": None,
        },
    }
    vf = _build_visual_format(raw)
    assert isinstance(vf.title, TitleFormat)
    assert vf.title.text == "Category Based  Profit"
    assert vf.title.font_name == "Verdana"
    assert vf.title.font_size == 20
    assert vf.title.bold is True


def test_axis_format_populated():
    raw = {
        "mark_color": None, "labels_show": False, "title": None,
        "axis_font_name": "Verdana", "axis_font_size": 16,
        "cell_font_name": None, "cell_font_size": None,
        "header_font_name": None, "header_font_size": None,
        "number_formats": {},
    }
    vf = _build_visual_format(raw)
    assert isinstance(vf.axis, AxisTitleFormat)
    assert vf.axis.font_name == "Verdana"
    assert vf.axis.font_size == 16


def test_number_formats_translated_to_stable_id():
    raw = {
        "mark_color": None, "labels_show": False, "title": None,
        "axis_font_name": None, "axis_font_size": None,
        "cell_font_name": None, "cell_font_size": None,
        "header_font_name": None, "header_font_size": None,
        "number_formats": {"sum:profit:qk": "C1033%"},
    }
    vf = _build_visual_format(raw)
    # stable_id("", "sum:profit:qk") â†’ "sum_profit_qk"
    assert "sum_profit_qk" in vf.number_formats
    assert vf.number_formats["sum_profit_qk"] == r"\$#,0.00;(\$#,0.00);\$#,0.00"


def test_unknown_format_code_not_stored():
    raw = {
        "mark_color": None, "labels_show": False, "title": None,
        "axis_font_name": None, "axis_font_size": None,
        "cell_font_name": None, "cell_font_size": None,
        "header_font_name": None, "header_font_size": None,
        "number_formats": {"some:field:qk": "UNKNOWN"},
    }
    vf = _build_visual_format(raw)
    assert vf.number_formats == {}
```

- [x] **Step 2: Run to confirm failure**

```
pytest tests/unit/stages/test_s02_visual_format.py -v
```
Expected: `ImportError` â€” `_build_visual_format` does not exist.

- [x] **Step 3: Implement `_build_visual_format()` and update `build_sheets()`**

In `src/tableau2pbir/stages/_build_sheets.py`:

Add import at the top:
```python
from tableau2pbir.visualmap.number_format import tableau_format_to_dax
```

Replace the `_build_mark_style()` function with:
```python
def _build_visual_format(raw_style: dict[str, Any] | None) -> VisualFormat | None:
    if raw_style is None:
        return None

    title: TitleFormat | None = None
    if raw_style.get("title"):
        t = raw_style["title"]
        fs = t.get("font_size")
        title = TitleFormat(
            text=t.get("text"),
            font_name=t.get("font_name"),
            font_size=int(fs) if fs is not None else None,
            bold=bool(t.get("bold", False)),
            italic=bool(t.get("italic", False)),
            underline=bool(t.get("underline", False)),
            font_color=t.get("font_color"),
        )

    axis: AxisTitleFormat | None = None
    if raw_style.get("axis_font_name") or raw_style.get("axis_font_size"):
        axis = AxisTitleFormat(
            font_name=raw_style.get("axis_font_name"),
            font_size=raw_style.get("axis_font_size"),
        )

    table_fmt: TableFormat | None = None
    if any(raw_style.get(k) for k in (
        "cell_font_name", "cell_font_size", "header_font_name", "header_font_size"
    )):
        table_fmt = TableFormat(
            cell_font_name=raw_style.get("cell_font_name"),
            cell_font_size=raw_style.get("cell_font_size"),
            header_font_name=raw_style.get("header_font_name"),
            header_font_size=raw_style.get("header_font_size"),
        )

    number_formats: dict[str, str] = {}
    for raw_field, tableau_fmt in raw_style.get("number_formats", {}).items():
        dax = tableau_format_to_dax(tableau_fmt)
        if dax:
            col_id = stable_id("", raw_field).lstrip("_")
            number_formats[col_id] = dax

    return VisualFormat(
        title=title,
        mark_color=raw_style.get("mark_color"),
        labels_show=bool(raw_style.get("labels_show", False)),
        axis=axis,
        table=table_fmt,
        number_formats=number_formats,
    )
```

In `build_sheets()`, replace:
```python
            mark_style=_build_mark_style(raw.get("mark_style")),
            format=None,
```
with:
```python
            visual_format=_build_visual_format(raw.get("sheet_style")),
```

- [x] **Step 4: Run tests**

```
pytest tests/unit/stages/test_s02_visual_format.py -v
```
Expected: PASS (6 tests).

- [x] **Step 5: Run full unit suite**

```
pytest tests/unit/ -x -q 2>&1 | tail -20
```
Expected: failures only in `dispatch.py` tests (still references old `MarkStyle`/`mark_style`).

- [x] **Step 6: Commit**

```
git add src/tableau2pbir/stages/_build_sheets.py tests/unit/stages/test_s02_visual_format.py
git commit -m "feat: wire _build_visual_format() in Stage 2, translating raw sheet_style to VisualFormat IR"
```

---

## Task 5: Format Mapper (`format_map.py`)

**Files:**
- Create: `src/tableau2pbir/visualmap/format_map.py`
- Create: `tests/unit/visualmap/test_format_map.py`

- [x] **Step 1: Write failing tests**

```python
# tests/unit/visualmap/test_format_map.py
from tableau2pbir.visualmap.format_map import build_format_objects
from tableau2pbir.ir.sheet import (
    AxisTitleFormat, TableFormat, TitleFormat, VisualFormat,
)


def _lit(v):
    return {"expr": {"Literal": {"Value": v}}}


def test_none_returns_empty_dicts():
    objects, container = build_format_objects(None, "columnChart")
    assert objects == {}
    assert container == {}


def test_mark_color_emitted_in_objects():
    vf = VisualFormat(mark_color="#f28e2b")
    objects, _ = build_format_objects(vf, "columnChart")
    assert "dataPoint" in objects
    color = objects["dataPoint"][0]["properties"]["fill"]["solid"]["color"]
    assert color == _lit("'#f28e2b'")


def test_labels_show_emitted():
    vf = VisualFormat(labels_show=True)
    objects, _ = build_format_objects(vf, "columnChart")
    assert objects["labels"][0]["properties"]["show"] == _lit("true")


def test_axis_font_emitted_for_column_chart():
    vf = VisualFormat(axis=AxisTitleFormat(font_name="Verdana", font_size=16))
    objects, _ = build_format_objects(vf, "columnChart")
    assert objects["categoryAxis"][0]["properties"]["titleFontFamily"] == _lit("'Verdana'")
    assert objects["categoryAxis"][0]["properties"]["titleFontSize"] == _lit("16D")
    assert objects["valueAxis"][0]["properties"]["titleFontFamily"] == _lit("'Verdana'")


def test_axis_font_not_emitted_for_table():
    vf = VisualFormat(axis=AxisTitleFormat(font_name="Verdana", font_size=16))
    objects, _ = build_format_objects(vf, "tableEx")
    assert "categoryAxis" not in objects
    assert "valueAxis" not in objects


def test_table_fonts_emitted_for_tableex():
    vf = VisualFormat(table=TableFormat(
        cell_font_name="Verdana",
        header_font_name="Arial Black",
        header_font_size=13,
    ))
    objects, _ = build_format_objects(vf, "tableEx")
    assert objects["values"][0]["properties"]["fontFamily"] == _lit("'Verdana'")
    # Arial Black has a space â€” must use triple-quote form
    assert objects["columnHeaders"][0]["properties"]["fontFamily"] == _lit("'''Arial Black'''")
    assert objects["columnHeaders"][0]["properties"]["fontSize"] == _lit("13D")


def test_table_fonts_not_emitted_for_chart():
    vf = VisualFormat(table=TableFormat(cell_font_name="Verdana"))
    objects, _ = build_format_objects(vf, "columnChart")
    assert "values" not in objects


def test_title_text_and_font_in_container():
    vf = VisualFormat(title=TitleFormat(
        text="Category Based  Profit",
        font_name="Verdana",
        font_size=20,
        bold=True,
        italic=True,
    ))
    _, container = build_format_objects(vf, "tableEx")
    title_props = container["title"][0]["properties"]
    assert title_props["show"] == _lit("true")
    assert title_props["text"] == _lit("'Category Based  Profit'")
    assert title_props["fontFamily"] == _lit("'Verdana'")
    assert title_props["fontSize"] == _lit("20D")
    assert title_props["bold"] == _lit("true")
    assert title_props["italic"] == _lit("true")
    assert "underline" not in title_props   # underline=False â†’ not emitted


def test_title_underline_emitted_when_true():
    vf = VisualFormat(title=TitleFormat(text="T", underline=True))
    _, container = build_format_objects(vf, "columnChart")
    assert container["title"][0]["properties"]["underline"] == _lit("true")


def test_title_font_color_emitted():
    vf = VisualFormat(title=TitleFormat(text="T", font_color="#e15759"))
    _, container = build_format_objects(vf, "tableEx")
    color = container["title"][0]["properties"]["fontColor"]
    assert color == {"solid": {"color": _lit("'#e15759'")}}


def test_font_name_with_spaces_triple_quoted():
    vf = VisualFormat(title=TitleFormat(text="T", font_name="Arial Black"))
    _, container = build_format_objects(vf, "columnChart")
    assert container["title"][0]["properties"]["fontFamily"] == _lit("'''Arial Black'''")
```

- [x] **Step 2: Run to confirm failure**

```
pytest tests/unit/visualmap/test_format_map.py -v
```
Expected: `ModuleNotFoundError`.

- [x] **Step 3: Implement `format_map.py`**

```python
# src/tableau2pbir/visualmap/format_map.py
"""Translate VisualFormat IR â†’ PBI PBIR visual.objects and visual.visualContainerObjects.

All card names and property names confirmed from:
- out/simple_join_sorted_test_format_manul.Report PBIR JSON files (PBI Desktop output)
- report-visualContainer-1.0.0.json schema (bundled)
"""
from __future__ import annotations

from tableau2pbir.ir.sheet import VisualFormat

_CHART_TYPES = frozenset({"columnChart", "barChart", "lineChart", "areaChart", "scatterChart"})
_TABLE_TYPES = frozenset({"tableEx"})


def _lit(value: str) -> dict:
    return {"expr": {"Literal": {"Value": value}}}


def _color(hex_color: str) -> dict:
    return {"solid": {"color": _lit(f"'{hex_color}'")}}


def _font_name_lit(name: str) -> dict:
    """Triple-quote font names that contain spaces (confirmed from manual PBIR visual_1)."""
    if " " in name:
        return _lit(f"'''{name}'''")
    return _lit(f"'{name}'")


def _font_size_lit(pt: int) -> dict:
    """PBI stores font sizes as decimal literals with 'D' suffix (confirmed from manual PBIR)."""
    return _lit(f"{pt}D")


def build_format_objects(
    vf: VisualFormat | None,
    visual_type: str,
) -> tuple[dict[str, list[dict]], dict[str, list[dict]]]:
    """Return (visual_objects, visual_container_objects) for PBIR emission.

    visual_objects        â†’ visual.visual.objects
    visual_container_objects â†’ visual.visual.visualContainerObjects
    """
    if vf is None:
        return {}, {}

    objects: dict[str, list[dict]] = {}
    container: dict[str, list[dict]] = {}

    # ---------- visual.objects ----------

    if vf.labels_show:
        objects["labels"] = [{"properties": {"show": _lit("true")}}]

    if vf.mark_color:
        objects["dataPoint"] = [
            {"properties": {"fill": _color(vf.mark_color)}}
        ]

    if visual_type in _CHART_TYPES and vf.axis:
        ax = vf.axis
        cat_props: dict = {}
        val_props: dict = {}
        if ax.font_name:
            cat_props["titleFontFamily"] = _font_name_lit(ax.font_name)
            val_props["titleFontFamily"] = _font_name_lit(ax.font_name)
        if ax.font_size:
            cat_props["titleFontSize"] = _font_size_lit(ax.font_size)
            val_props["titleFontSize"] = _font_size_lit(ax.font_size)
        if cat_props:
            objects["categoryAxis"] = [{"properties": cat_props}]
        if val_props:
            objects["valueAxis"] = [{"properties": val_props}]

    if visual_type in _TABLE_TYPES and vf.table:
        t = vf.table
        val_props = {}
        hdr_props = {}
        if t.cell_font_name:
            val_props["fontFamily"] = _font_name_lit(t.cell_font_name)
        if t.cell_font_size:
            val_props["fontSize"] = _font_size_lit(t.cell_font_size)
        if t.header_font_name:
            hdr_props["fontFamily"] = _font_name_lit(t.header_font_name)
        if t.header_font_size:
            hdr_props["fontSize"] = _font_size_lit(t.header_font_size)
        if val_props:
            objects["values"] = [{"properties": val_props}]
        if hdr_props:
            objects["columnHeaders"] = [{"properties": hdr_props}]

    # ---------- visual.visualContainerObjects ----------

    if vf.title:
        tit = vf.title
        title_props: dict = {}
        if tit.text is not None:
            title_props["show"] = _lit("true")
            title_props["text"] = _lit(f"'{tit.text}'")
        if tit.font_name:
            title_props["fontFamily"] = _font_name_lit(tit.font_name)
        if tit.font_size:
            title_props["fontSize"] = _font_size_lit(tit.font_size)
        if tit.bold:
            title_props["bold"] = _lit("true")
        if tit.italic:
            title_props["italic"] = _lit("true")
        if tit.underline:
            title_props["underline"] = _lit("true")
        if tit.font_color:
            title_props["fontColor"] = _color(tit.font_color)
        if title_props:
            container["title"] = [{"properties": title_props}]

    return objects, container
```

- [x] **Step 4: Run tests**

```
pytest tests/unit/visualmap/test_format_map.py -v
```
Expected: PASS (12 tests).

- [x] **Step 5: Commit**

```
git add src/tableau2pbir/visualmap/format_map.py tests/unit/visualmap/test_format_map.py
git commit -m "feat: add format_map.py â€” VisualFormat to PBI visual.objects and visualContainerObjects"
```

---

## Task 6: Update `dispatch.py`

**Files:**
- Modify: `src/tableau2pbir/visualmap/dispatch.py`

- [x] **Step 1: Update import**

Replace the import line at the top of `dispatch.py`:
```python
from tableau2pbir.ir.sheet import EncodingBinding, MarkStyle, PbirVisual, Sheet, VisualSortEntry
```
with:
```python
from tableau2pbir.ir.sheet import EncodingBinding, PbirVisual, Sheet, VisualSortEntry
```

- [x] **Step 2: Remove `_build_format_objects()` and update `dispatch_visual()`**

Delete the `_build_format_objects()` function (lines 20â€“34 in the current file).

In `dispatch_visual()`, replace the line:
```python
    fmt = _build_format_objects(sheet.mark_style)
```
with nothing (delete it). Then in every `PbirVisual(...)` construction in the function, replace `format=fmt` with `visual_format=sheet.visual_format`. There are 8 occurrences â€” replace all of them. Example for the first one:

```python
        return PbirVisual(
            visual_type="tableEx",
            encoding_bindings=tuple(bindings),
            visual_format=sheet.visual_format,
            sort_by=sort_entries,
        )
```

Repeat for every `PbirVisual(...)` in the function â€” barChart, columnChart, lineChart, areaChart, scatterChart, pieChart, filledMap, and the text/tableEx branch.

- [x] **Step 3: Run dispatch unit tests**

```
pytest tests/unit/visualmap/ -v
```
Expected: PASS (all existing dispatch tests pass â€” they construct `PbirVisual` without `visual_format` which defaults to `None`, producing `{}, {}` at render time, identical to the old `format={}` behavior).

- [x] **Step 4: Run full unit suite**

```
pytest tests/unit/ -x -q 2>&1 | tail -20
```
Expected: all tests pass except render tests (Task 7).

- [x] **Step 5: Commit**

```
git add src/tableau2pbir/visualmap/dispatch.py
git commit -m "refactor: dispatch passes visual_format through PbirVisual instead of computing PBI objects"
```

---

## Task 7: Update Emitter â€” `visual.objects`, `visualContainerObjects`, `projection.format`

**Files:**
- Modify: `src/tableau2pbir/emit/pbir/visual.py`
- Modify: `tests/unit/emit/pbir/test_visual.py`

- [x] **Step 1: Write failing tests**

Add to `tests/unit/emit/pbir/test_visual.py`:

```python
import json
from tableau2pbir.emit.pbir.visual import render_visual
from tableau2pbir.ir.dashboard import Position
from tableau2pbir.ir.sheet import (
    AxisTitleFormat, EncodingBinding, PbirVisual, TableFormat, TitleFormat, VisualFormat,
)


def _pos():
    return Position(x=0, y=0, w=400, h=300)


def test_visual_container_objects_emitted_when_title_set():
    vf = VisualFormat(title=TitleFormat(
        text="Category Based  Profit",
        font_name="Verdana",
        font_size=20,
    ))
    pv = PbirVisual(
        visual_type="tableEx",
        encoding_bindings=(EncodingBinding(channel="Values", source_field_id="orders.category"),),
        visual_format=vf,
    )
    obj = json.loads(render_visual("v1", pv, _pos(), 0))
    vco = obj["visual"]["visualContainerObjects"]
    assert vco["title"][0]["properties"]["text"]["expr"]["Literal"]["Value"] == "'Category Based  Profit'"
    assert vco["title"][0]["properties"]["fontSize"]["expr"]["Literal"]["Value"] == "20D"


def test_visual_container_objects_absent_when_no_title():
    pv = PbirVisual(
        visual_type="columnChart",
        encoding_bindings=(EncodingBinding(channel="Category", source_field_id="orders.category"),),
        visual_format=None,
    )
    obj = json.loads(render_visual("v1", pv, _pos(), 0))
    assert "visualContainerObjects" not in obj["visual"]


def test_projection_format_added_when_number_format_present():
    vf = VisualFormat(number_formats={"orders_profit_qk": r"\$#,0.00;(\$#,0.00);\$#,0.00"})
    pv = PbirVisual(
        visual_type="tableEx",
        encoding_bindings=(EncodingBinding(channel="Values", source_field_id="orders_profit_qk"),),
        visual_format=vf,
    )
    lookup = {"orders_profit_qk": {"table_name": "orders", "col_name": "profit", "is_measure": True}}
    obj = json.loads(render_visual("v1", pv, _pos(), 0, field_lookup=lookup))
    proj = obj["visual"]["query"]["queryState"]["Values"]["projections"][0]
    assert proj["format"] == r"\$#,0.00;(\$#,0.00);\$#,0.00"


def test_projection_format_absent_when_no_number_format():
    pv = PbirVisual(
        visual_type="columnChart",
        encoding_bindings=(EncodingBinding(channel="Y", source_field_id="orders.revenue"),),
        visual_format=None,
    )
    obj = json.loads(render_visual("v1", pv, _pos(), 0))
    proj = obj["visual"]["query"]["queryState"]["Y"]["projections"][0]
    assert "format" not in proj


def test_category_axis_objects_emitted_for_chart():
    vf = VisualFormat(axis=AxisTitleFormat(font_name="Verdana", font_size=16))
    pv = PbirVisual(
        visual_type="columnChart",
        encoding_bindings=(EncodingBinding(channel="Category", source_field_id="orders.category"),),
        visual_format=vf,
    )
    obj = json.loads(render_visual("v1", pv, _pos(), 0))
    objects = obj["visual"]["objects"]
    assert "categoryAxis" in objects
    assert "valueAxis" in objects


def test_table_column_headers_emitted_for_tableex():
    vf = VisualFormat(table=TableFormat(header_font_name="Arial Black", header_font_size=13))
    pv = PbirVisual(
        visual_type="tableEx",
        encoding_bindings=(EncodingBinding(channel="Values", source_field_id="orders.category"),),
        visual_format=vf,
    )
    obj = json.loads(render_visual("v1", pv, _pos(), 0))
    assert "columnHeaders" in obj["visual"]["objects"]


def test_existing_format_dict_still_works():
    """Backward compat: PbirVisual.format={...} still emitted when visual_format is None."""
    pv = PbirVisual(
        visual_type="clusteredBarChart",
        encoding_bindings=(EncodingBinding(channel="Category", source_field_id="orders.region"),),
        format={"labels": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}]},
        visual_format=None,
    )
    obj = json.loads(render_visual("v1", pv, _pos(), 0))
    assert obj["visual"]["objects"]["labels"][0]["properties"]["show"]["expr"]["Literal"]["Value"] == "true"
```

- [x] **Step 2: Run to confirm failure**

```
pytest tests/unit/emit/pbir/test_visual.py -v -k "visual_container or projection_format or category_axis or table_column or existing_format"
```
Expected: FAIL on the new tests.

- [x] **Step 3: Update `render_visual()` in `emit/pbir/visual.py`**

```python
"""Render visuals/<vid>/visual.json."""
from __future__ import annotations

import json

from tableau2pbir.ir.dashboard import Position
from tableau2pbir.ir.sheet import PbirVisual
from tableau2pbir.visualmap.format_map import build_format_objects


def render_visual(
    visual_id: str,
    pbir_visual: PbirVisual,
    position: Position,
    z_order: int,
    field_lookup: dict[str, dict] | None = None,
) -> str:
    fl = field_lookup or {}

    # Compute PBI formatting objects from VisualFormat IR (new path) or
    # fall back to the pre-computed format dict (backward compat with tests).
    if pbir_visual.visual_format is not None:
        objects, container_objects = build_format_objects(
            pbir_visual.visual_format, pbir_visual.visual_type
        )
        number_formats = pbir_visual.visual_format.number_formats
    else:
        objects = pbir_visual.format or {}
        container_objects = {}
        number_formats = {}

    query_state: dict[str, dict] = {}
    for b in pbir_visual.encoding_bindings:
        query_state.setdefault(b.channel, {"projections": []})
        query_state[b.channel]["projections"].append(
            _make_projection(b.source_field_id, fl, number_formats)
        )

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


def _make_sort_entry(s, field_lookup: dict) -> dict:
    info = field_lookup.get(s.field_id, {})
    if info:
        table_name = info.get("table_name", "Model")
        prop_name = info.get("measure_name") or info.get("col_name", s.field_id)
        is_measure = info.get("is_measure", True)
    elif "." in s.field_id:
        table_name, prop_name = s.field_id.split(".", 1)
        is_measure = False
    else:
        table_name = "Model"
        prop_name = s.field_id
        is_measure = True
    field_type = "Measure" if is_measure else "Column"
    direction = "Descending" if s.direction.lower() in ("desc", "descending") else "Ascending"
    return {
        "direction": direction,
        "field": {
            field_type: {
                "Expression": {"SourceRef": {"Entity": table_name}},
                "Property": prop_name,
            }
        },
    }


def _make_projection(
    field_id: str,
    field_lookup: dict,
    number_formats: dict[str, str] | None = None,
) -> dict:
    info = field_lookup.get(field_id)
    if info:
        table_name = info["table_name"]
        is_measure = info["is_measure"]
        prop_name = info.get("measure_name") or info["col_name"]
    elif "." in field_id:
        table_name, prop_name = field_id.split(".", 1)
        is_measure = False
    else:
        table_name = "Model"
        prop_name = field_id
        is_measure = True
    field_type = "Measure" if is_measure else "Column"
    proj: dict = {
        "field": {
            field_type: {
                "Expression": {"SourceRef": {"Entity": table_name}},
                "Property": prop_name,
            }
        },
        "queryRef": f"{table_name}.{prop_name}",
        "active": True,
    }
    if number_formats:
        dax_fmt = number_formats.get(field_id)
        if dax_fmt:
            proj["format"] = dax_fmt
    return proj
```

- [x] **Step 4: Run new tests**

```
pytest tests/unit/emit/pbir/test_visual.py -v
```
Expected: PASS (all tests including new ones).

- [x] **Step 5: Run full unit suite**

```
pytest tests/unit/ -q 2>&1 | tail -5
```
Expected: all pass.

- [x] **Step 6: Commit**

```
git add src/tableau2pbir/emit/pbir/visual.py tests/unit/emit/pbir/test_visual.py
git commit -m "feat: emit visualContainerObjects (title) and projection.format (currency) in render_visual"
```

---

## Task 8: End-to-End Verification

**Files:**
- Verify: `tests/integration/test_real_workbooks_e2e.py`
- Verify: output at `out/simple_join_sorted_test_format/`

- [ ] **Step 1: Run regression test suite**

```
pytest tests/integration/test_real_workbooks_e2e.py -v 2>&1 | tail -30
```
Expected: all existing E2E tests pass (zero regressions). The regression snapshots were taken before formatting â€” existing golden files do not assert on `objects` or `visualContainerObjects` so they will still match.

- [ ] **Step 2: Run the full pipeline on `simple_join_sorted_test_format.twb`**

```
python -m tableau2pbir convert tests/workbooks/simple_join_sorted_test_format.twb --out out/simple_join_sorted_test_format
```

- [ ] **Step 3: Inspect visual.json for Sheet 4 (Category Based Profit)**

```
python -c "import json,pathlib; d=json.loads(pathlib.Path('out/simple_join_sorted_test_format/Report/definition/pages/ReportSection3/visuals/visual_3/visual.json').read_text()); print(json.dumps(d['visual'].get('visualContainerObjects',{}), indent=2)); print('---'); print(json.dumps(d['visual']['objects'], indent=2))"
```

Expected output must contain:
- `visualContainerObjects.title.text` = `"'Category Based  Profit'"`
- `visualContainerObjects.title.fontFamily` = `"'Verdana'"`
- `visualContainerObjects.title.fontSize` = `"20D"`
- `visualContainerObjects.title.bold` = `"true"`
- `visualContainerObjects.title.italic` = `"true"`
- `objects.labels.show` = `"true"` (Sheet 4 has `mark-labels-show='true'`)
- The `Sum profit` projection must contain `"format": "\\$#,0.00;(\\$#,0.00);\\$#,0.00"`

- [ ] **Step 4: Inspect Sheet 1 (Delta Order By Category) for axis and mark color**

```
python -c "import json,pathlib; d=json.loads(pathlib.Path('out/simple_join_sorted_test_format/Report/definition/pages/ReportSection1/visuals/visual_1/visual.json').read_text()); print(json.dumps(d['visual']['objects'], indent=2)); print(json.dumps(d['visual'].get('visualContainerObjects',{}), indent=2))"
```

Expected:
- `objects.dataPoint.fill.solid.color` = `"'#f28e2b'"`
- `objects.labels.show` = `"true"`
- `objects.categoryAxis.titleFontFamily` = `"'Verdana'"` (from Sheet 1 `field-labels` style-rule)
- `visualContainerObjects.title.text` = `"'Delta  Order By Category'"`
- `visualContainerObjects.title.fontFamily` = `"'''Arial Black'''"`
- `visualContainerObjects.title.underline` = `"true"`

- [ ] **Step 5: Run full unit + regression suite one final time**

```
pytest tests/unit/ tests/integration/test_real_workbooks_e2e.py -q 2>&1 | tail -10
```
Expected: all pass.

- [ ] **Step 6: Commit**

```
git commit -m "test: verify formatting pipeline E2E on simple_join_sorted_test_format"
```

---

## Task 9: Discovery â€” Axis Line Colors and Gridlines (Phase 2)

**Scope:** Tableau `stroke-color`/`tick-color` on `<style-rule element='axis'>` and `<style-rule element='gridline'>` are confirmed in the TWB. The PBI `visual.objects` card names for these are **not yet confirmed** â€” no manual PBIR sample demonstrated them.

**This task must be done before implementation of axis colors and gridlines.**

- [ ] **Step 1: Create a minimal PBI Desktop report**

Open PBI Desktop. Create a column chart with any data. Apply these formatting changes in the Format pane:
1. X-axis â†’ Line â†’ set a color (e.g. red)
2. X-axis â†’ Line â†’ set line width to 3
3. Y-axis â†’ Line â†’ set a different color (e.g. blue)
4. Gridlines â†’ Horizontal â†’ turn on, set a color (e.g. green)
5. Save as PBIR format to `out/axis_color_discovery/`

- [ ] **Step 2: Read the visual.json**

```
python -c "import json,pathlib; files=list(pathlib.Path('out/axis_color_discovery').rglob('visual.json')); print(json.dumps(json.loads(files[0].read_text())['visual']['objects'], indent=2))"
```

Record the exact card key names and property names for axis line color, axis line width, gridline color, and gridline visibility.

- [ ] **Step 3: Document findings and implement**

Update `format_map.py` with:
- New Tableau-to-PBI mappings for `axis` style-rule `stroke-color`/`tick-color` â†’ confirmed card properties
- New Tableau-to-PBI mappings for `gridline` style-rule â†’ confirmed card properties

Add `VisualFormat` fields:
- `axis_stroke_color: dict[str, str] = {}` (keyed by `"rows"`/`"cols"`)
- `axis_tick_color: dict[str, str] = {}`
- `gridline_color: dict[str, str] = {}`
- `gridline_visible: dict[str, bool] = {}`

Update `_sheet_style()` to extract these from `<style-rule element='axis'>` and `<style-rule element='gridline'>`.

Write tests against the confirmed card/property names before implementing.

- [ ] **Step 4: Commit when confirmed and implemented**

```
git commit -m "feat: emit axis line colors and gridline styling from Tableau style-rules"
```

---

## Self-Review

**Spec coverage check:**

| Formatting item | Task that covers it |
|----------------|-------------------|
| Title text, font, size, bold, italic, underline, color | Tasks 1, 3, 5, 7 |
| Mark color â†’ `dataPoint.fill` | Tasks 1, 3, 4, 5, 7 |
| Data labels show â†’ `labels.show` | Tasks 1, 3, 4, 5, 7 |
| Chart axis title font â†’ `categoryAxis`/`valueAxis` | Tasks 1, 3, 4, 5, 7 |
| Table cell font â†’ `values` | Tasks 1, 3, 4, 5, 7 |
| Table header font â†’ `columnHeaders` | Tasks 1, 3, 4, 5, 7 |
| Number/currency format â†’ `projection.format` | Tasks 2, 3, 4, 7 |
| Axis line colors / gridlines | Task 9 (discovery first) |

**No placeholders present.** Every step has exact code or exact commands.

**Type consistency confirmed:** `VisualFormat` defined in Task 1, imported in Tasks 3/4/5/6/7. `_sheet_style()` returns `dict[str, Any]` with exact keys consumed by `_build_visual_format()` in Task 4. `build_format_objects()` signature `(VisualFormat | None, str) -> tuple[dict, dict]` consistent across Tasks 5 and 7.

