# Mark Style Emission — Data Labels & Static Color

> **Execution approach: Subagent-Driven.** Use **superpowers:subagent-driven-development** — dispatch a fresh subagent per task, review between tasks. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Extract Tableau `<style-rule element='mark'>` formatting (static fill color, label visibility) from the TWB, carry it through the IR, and emit the correct PBIR `objects.dataPoint` / `objects.labels` entries in `visual.json`.

**Architecture:** Four files touched in pipeline order — extract → IR → build_sheets → dispatch. The emission layer (`render_visual`) already writes `"objects": pbir_visual.format`, so no change is needed there. A new `MarkStyle` Pydantic model holds the two properties extracted from Tableau. `PbirVisual.format` type is corrected from `dict[str, str]` to `dict[str, list[dict]]` to match the PBIR `DataViewObjectDefinitions` schema. Ground truth for PBIR property names is the manually created `C:\vibe_coding\tabToPbi\output\simple_join_n.Report` visual JSON files.

**Tech Stack:** Python 3.11, Pydantic v2, lxml, pytest.

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Modify | `src/tableau2pbir/ir/sheet.py` | Add `MarkStyle` model; add `mark_style` to `Sheet`; fix `PbirVisual.format` type |
| Modify | `src/tableau2pbir/extract/worksheets.py` | Add `_mark_style()` that reads `<style-rule element='mark'>/<format>`; include in output dict |
| Modify | `src/tableau2pbir/stages/_build_sheets.py` | Build `MarkStyle` from raw dict; pass to `Sheet` |
| Modify | `src/tableau2pbir/visualmap/dispatch.py` | Add `_build_format_objects()`; pass result as `format=` in every `PbirVisual(...)` call |
| Modify | `tests/unit/ir/test_sheet.py` | Tests for `MarkStyle` model |
| Modify | `tests/unit/extract/test_worksheets.py` | Tests for `_mark_style()` via `extract_worksheets()` |
| Modify | `tests/unit/stages/test_s02_sheets.py` | Test mark_style passthrough in `build_sheets()` |
| Modify | `tests/unit/visualmap/test_dispatch.py` | Tests for `_build_format_objects()` via `dispatch_visual()` |
| Modify | `tests/unit/emit/pbir/test_visual.py` | Test that non-empty format renders into `"objects"` |

---

## Task 1 — MarkStyle IR model + PbirVisual.format type fix

**Files:**
- Modify: `src/tableau2pbir/ir/sheet.py`
- Modify: `tests/unit/ir/test_sheet.py`

- [x] **Step 1: Write the failing tests**

Add to `tests/unit/ir/test_sheet.py`:

```python
from tableau2pbir.ir.sheet import MarkStyle, PbirVisual, EncodingBinding


def test_mark_style_defaults():
    ms = MarkStyle()
    assert ms.mark_color is None
    assert ms.labels_show is False


def test_mark_style_with_values():
    ms = MarkStyle(mark_color="#ffaa7f", labels_show=True)
    assert ms.mark_color == "#ffaa7f"
    assert ms.labels_show is True


def test_sheet_mark_style_defaults_to_none():
    from tableau2pbir.ir.common import FieldRef
    from tableau2pbir.ir.sheet import Sheet, Encoding
    s = Sheet(
        id="s1", name="T", datasource_refs=("ds",), mark_type="bar",
        encoding=Encoding(), filters=(), sort=(), dual_axis=False,
        reference_lines=(), uses_calculations=(),
    )
    assert s.mark_style is None


def test_pbir_visual_format_accepts_objects_structure():
    """PbirVisual.format must accept the PBIR DataViewObjectDefinitions shape."""
    pv = PbirVisual(
        visual_type="barChart",
        encoding_bindings=(EncodingBinding(channel="Y", source_field_id="sales"),),
        format={
            "labels": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}],
            "dataPoint": [{"properties": {"fill": {"solid": {"color": {"expr": {"Literal": {"Value": "'#ffaa7f'"}}}}}}}],
        },
    )
    assert "labels" in pv.format
    assert "dataPoint" in pv.format
```

- [x] **Step 2: Run tests to confirm they fail**

```
pytest tests/unit/ir/test_sheet.py::test_mark_style_defaults tests/unit/ir/test_sheet.py::test_mark_style_with_values tests/unit/ir/test_sheet.py::test_sheet_mark_style_defaults_to_none tests/unit/ir/test_sheet.py::test_pbir_visual_format_accepts_objects_structure -v
```

Expected: FAIL — `MarkStyle` does not exist.

- [x] **Step 3: Implement in `src/tableau2pbir/ir/sheet.py`**

Add `MarkStyle` class after `ReferenceLine` and before `Sheet`. Add `mark_style` field to `Sheet`. Change `PbirVisual.format` type:

```python
class MarkStyle(IRBase):
    mark_color: str | None = None
    labels_show: bool = False
```

In `Sheet`, add after `reference_lines`:
```python
mark_style: MarkStyle | None = None
```

Change `PbirVisual.format` line from:
```python
format: dict[str, str] = {}
```
to:
```python
format: dict[str, list[dict]] = {}
```

Full resulting `ir/sheet.py` (complete replacement of the relevant classes):

```python
class MarkStyle(IRBase):
    mark_color: str | None = None
    labels_show: bool = False


class Sheet(IRBase):
    id: str
    name: str
    datasource_refs: tuple[str, ...]
    mark_type: str
    encoding: Encoding
    filters: tuple[Filter, ...]
    sort: tuple[SortSpec, ...]
    dual_axis: bool
    reference_lines: tuple[ReferenceLine, ...]
    mark_style: MarkStyle | None = None
    format: dict[str, str] | None = None
    uses_calculations: tuple[str, ...]
    pbir_visual: PbirVisual | None = None


class EncodingBinding(IRBase):
    """One channel→field binding in a PBIR visual."""
    channel: str
    source_field_id: str


class PbirVisual(IRBase):
    """Stage 4 annotation attached to a Sheet."""
    visual_type: str
    encoding_bindings: tuple[EncodingBinding, ...]
    format: dict[str, list[dict]] = {}
```

`Sheet.model_rebuild()` remains at the end of the file (no change needed — `MarkStyle` is defined in the same file above `Sheet`).

- [x] **Step 4: Run tests to confirm they pass**

```
pytest tests/unit/ir/test_sheet.py -v
```

Expected: All pass, including the four new tests.

- [x] **Step 5: Run full unit suite to confirm no regressions**

```
pytest tests/unit/ -x -q
```

Expected: All pass (existing tests use `format={}` which remains valid under `dict[str, list[dict]]`).

- [x] **Step 6: Commit**

```
git add src/tableau2pbir/ir/sheet.py tests/unit/ir/test_sheet.py
git commit -m "feat(ir): add MarkStyle model; fix PbirVisual.format type to dict[str, list[dict]]"
```

---

## Task 2 — Extractor: parse `<style-rule element='mark'>`

**Files:**
- Modify: `src/tableau2pbir/extract/worksheets.py`
- Modify: `tests/unit/extract/test_worksheets.py`

- [x] **Step 1: Write the failing tests**

Add to `tests/unit/extract/test_worksheets.py`:

```python
_XML_WITH_MARK_STYLE = b"""<?xml version='1.0'?>
<workbook><worksheets>
  <worksheet name='Sales'>
    <table>
      <view>
        <datasources><datasource name='ds1'/></datasources>
      </view>
      <panes>
        <pane>
          <mark class='Bar'/>
          <style>
            <style-rule element='mark'>
              <format attr='mark-color' value='#ffaa7f'/>
              <format attr='mark-labels-show' value='true'/>
              <format attr='mark-labels-cull' value='true'/>
            </style-rule>
          </style>
        </pane>
      </panes>
      <rows>[amount]</rows>
      <cols>[month]</cols>
    </table>
  </worksheet>
</worksheets></workbook>
"""

_XML_NO_MARK_STYLE = b"""<?xml version='1.0'?>
<workbook><worksheets>
  <worksheet name='Sales'>
    <table>
      <view>
        <datasources><datasource name='ds1'/></datasources>
      </view>
      <panes>
        <pane><mark class='Bar'/></pane>
      </panes>
      <rows>[amount]</rows>
      <cols>[month]</cols>
    </table>
  </worksheet>
</worksheets></workbook>
"""


def test_mark_style_extracted_when_present():
    root = parse_workbook_xml(_XML_WITH_MARK_STYLE)
    ws = extract_worksheets(root)
    ms = ws[0]["mark_style"]
    assert ms["mark_color"] == "#ffaa7f"
    assert ms["labels_show"] is True


def test_mark_style_defaults_when_absent():
    root = parse_workbook_xml(_XML_NO_MARK_STYLE)
    ws = extract_worksheets(root)
    ms = ws[0]["mark_style"]
    assert ms["mark_color"] is None
    assert ms["labels_show"] is False


def test_mark_style_labels_cull_not_propagated():
    """mark-labels-cull has no PBI equivalent — it must not appear in mark_style output."""
    root = parse_workbook_xml(_XML_WITH_MARK_STYLE)
    ws = extract_worksheets(root)
    ms = ws[0]["mark_style"]
    assert "labels_cull" not in ms
```

- [x] **Step 2: Run tests to confirm they fail**

```
pytest tests/unit/extract/test_worksheets.py::test_mark_style_extracted_when_present tests/unit/extract/test_worksheets.py::test_mark_style_defaults_when_absent tests/unit/extract/test_worksheets.py::test_mark_style_labels_cull_not_propagated -v
```

Expected: FAIL — `mark_style` key not present in extracted dict.

- [x] **Step 3: Implement in `src/tableau2pbir/extract/worksheets.py`**

Add the `_mark_style` function after `_quick_table_calcs` and before `extract_worksheets`:

```python
def _mark_style(pane_parent: etree._Element) -> dict[str, Any]:
    """Read <style-rule element='mark'>/<format> from the first pane that has one."""
    style: dict[str, Any] = {"mark_color": None, "labels_show": False}
    panes = pane_parent.findall("panes/pane") or pane_parent.findall("pane")
    for pane in panes:
        for fmt in pane.findall("style/style-rule[@element='mark']/format"):
            attr_name = optional_attr(fmt, "attr")
            value = optional_attr(fmt, "value")
            if attr_name == "mark-color":
                style["mark_color"] = value
            elif attr_name == "mark-labels-show":
                style["labels_show"] = (value == "true")
    return style
```

In `extract_worksheets()`, add `"mark_style"` to the output dict (after `"quick_table_calcs"`):

```python
        out.append({
            "name": attr(ws, "name"),
            "datasource_refs": _datasource_refs(view),
            "mark_type": mark_type,
            "encodings": _encodings(shelf_elem, pane_parent),
            "filters": _filters(view),
            "sort": _sort(view),
            "dual_axis": _dual_axis(search_root),
            "reference_lines": _reference_lines(search_root),
            "quick_table_calcs": _quick_table_calcs(search_root),
            "mark_style": _mark_style(pane_parent),
        })
```

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
git commit -m "feat(extract): parse mark-color and mark-labels-show from style-rule element"
```

---

## Task 3 — Build sheets: wire MarkStyle from raw dict to Sheet

**Files:**
- Modify: `src/tableau2pbir/stages/_build_sheets.py`
- Modify: `tests/unit/stages/test_s02_sheets.py`

- [x] **Step 1: Write the failing tests**

Add to `tests/unit/stages/test_s02_sheets.py`:

```python
def _raw(extra=None):
    base = {
        "name": "T", "datasource_refs": ("ds",), "mark_type": "bar",
        "encodings": {"rows": (), "columns": (), "color": None, "size": None,
                      "label": None, "tooltip": None, "detail": (),
                      "shape": None, "angle": None},
        "filters": [], "sort": [], "dual_axis": False, "reference_lines": [],
        "quick_table_calcs": [],
    }
    if extra:
        base.update(extra)
    return base


def test_mark_style_none_when_key_absent():
    """Existing raw dicts without mark_style key must produce Sheet.mark_style=None."""
    sheets, _ = build_sheets([_raw()], calc_names=set(), table_id_for_ref={"ds": "tbl__ds"})
    assert sheets[0].mark_style is None


def test_mark_style_color_and_labels_propagated():
    raw = _raw({"mark_style": {"mark_color": "#e15759", "labels_show": True}})
    sheets, _ = build_sheets([raw], calc_names=set(), table_id_for_ref={"ds": "tbl__ds"})
    ms = sheets[0].mark_style
    assert ms is not None
    assert ms.mark_color == "#e15759"
    assert ms.labels_show is True


def test_mark_style_color_none_labels_false():
    raw = _raw({"mark_style": {"mark_color": None, "labels_show": False}})
    sheets, _ = build_sheets([raw], calc_names=set(), table_id_for_ref={"ds": "tbl__ds"})
    ms = sheets[0].mark_style
    assert ms is not None
    assert ms.mark_color is None
    assert ms.labels_show is False
```

- [x] **Step 2: Run tests to confirm they fail**

```
pytest tests/unit/stages/test_s02_sheets.py::test_mark_style_none_when_key_absent tests/unit/stages/test_s02_sheets.py::test_mark_style_color_and_labels_propagated tests/unit/stages/test_s02_sheets.py::test_mark_style_color_none_labels_false -v
```

Expected: FAIL — `Sheet` receives no `mark_style` argument.

- [x] **Step 3: Implement in `src/tableau2pbir/stages/_build_sheets.py`**

Add `MarkStyle` to the import from `tableau2pbir.ir.sheet`:

```python
from tableau2pbir.ir.sheet import (
    CategoricalFilter, ConditionalFilter, ContextFilter, Encoding, Filter,
    MarkStyle, RangeFilter, ReferenceLine, Sheet, SortSpec, TopNFilter,
)
```

Add `_build_mark_style` function after `_build_reference_lines` and before `build_sheets`:

```python
def _build_mark_style(raw_style: dict[str, Any] | None) -> MarkStyle | None:
    if raw_style is None:
        return None
    return MarkStyle(
        mark_color=raw_style.get("mark_color"),
        labels_show=bool(raw_style.get("labels_show", False)),
    )
```

In `build_sheets()`, add `mark_style=_build_mark_style(raw.get("mark_style"))` to the `Sheet(...)` constructor call. The full call becomes:

```python
        sheets.append(Sheet(
            id=sheet_id,
            name=raw["name"],
            datasource_refs=tuple(stable_id("ds", d) for d in ds_refs),
            mark_type=raw["mark_type"],
            encoding=_build_encoding(raw["encodings"], table_id),
            filters=filters,
            sort=_build_sort(raw["sort"], table_id),
            dual_axis=raw["dual_axis"],
            reference_lines=_build_reference_lines(raw["reference_lines"], idx, table_id),
            mark_style=_build_mark_style(raw.get("mark_style")),
            format=None,
            uses_calculations=uses_calculations,
        ))
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
git commit -m "feat(stages): wire MarkStyle from raw extract dict through to Sheet IR"
```

---

## Task 4 — Dispatch: build PBIR format objects + E2E gate

**Files:**
- Modify: `src/tableau2pbir/visualmap/dispatch.py`
- Modify: `tests/unit/visualmap/test_dispatch.py`
- Modify: `tests/unit/emit/pbir/test_visual.py`

- [x] **Step 1: Write the failing dispatch tests**

Add to `tests/unit/visualmap/test_dispatch.py`:

```python
from tableau2pbir.ir.sheet import MarkStyle


def _sheet_with_style(mark: str, *, rows=(), cols=(), color=None,
                      mark_style: MarkStyle | None = None) -> Sheet:
    return Sheet(
        id="s1", name="S", datasource_refs=("ds1",),
        mark_type=mark,
        encoding=Encoding(rows=rows, columns=cols, color=color),
        filters=(), sort=(), dual_axis=False, reference_lines=(),
        uses_calculations=(), mark_style=mark_style,
    )


def test_dispatch_no_mark_style_produces_empty_format():
    sh = _sheet_with_style("bar", rows=(_fr("sales"),), cols=(_fr("region"),))
    pv = dispatch_visual(sh)
    assert pv is not None
    assert pv.format == {}


def test_dispatch_labels_show_emits_labels_object():
    ms = MarkStyle(labels_show=True)
    sh = _sheet_with_style("bar", rows=(_fr("sales"),), cols=(_fr("region"),),
                           mark_style=ms)
    pv = dispatch_visual(sh)
    assert pv is not None
    assert "labels" in pv.format
    labels = pv.format["labels"]
    assert len(labels) == 1
    assert labels[0]["properties"]["show"]["expr"]["Literal"]["Value"] == "true"


def test_dispatch_mark_color_emits_data_point_object():
    ms = MarkStyle(mark_color="#e15759")
    sh = _sheet_with_style("bar", rows=(_fr("sales"),), cols=(_fr("region"),),
                           mark_style=ms)
    pv = dispatch_visual(sh)
    assert pv is not None
    assert "dataPoint" in pv.format
    dp = pv.format["dataPoint"]
    assert len(dp) == 1
    color_val = dp[0]["properties"]["fill"]["solid"]["color"]["expr"]["Literal"]["Value"]
    assert color_val == "'#e15759'"


def test_dispatch_both_labels_and_color():
    ms = MarkStyle(mark_color="#ffaa7f", labels_show=True)
    sh = _sheet_with_style("automatic", rows=(_fr("sales_qk"),), cols=(_fr("region_nk"),),
                           mark_style=ms)
    pv = dispatch_visual(sh)
    assert pv is not None
    assert "labels" in pv.format
    assert "dataPoint" in pv.format


def test_dispatch_labels_false_does_not_emit_labels_object():
    ms = MarkStyle(labels_show=False, mark_color=None)
    sh = _sheet_with_style("bar", rows=(_fr("sales"),), cols=(_fr("region"),),
                           mark_style=ms)
    pv = dispatch_visual(sh)
    assert pv is not None
    assert "labels" not in pv.format


def test_dispatch_color_none_does_not_emit_data_point():
    ms = MarkStyle(labels_show=False, mark_color=None)
    sh = _sheet_with_style("bar", rows=(_fr("sales"),), cols=(_fr("region"),),
                           mark_style=ms)
    pv = dispatch_visual(sh)
    assert pv is not None
    assert "dataPoint" not in pv.format
```

- [x] **Step 2: Write the failing visual emission test**

Add to `tests/unit/emit/pbir/test_visual.py`:

```python
def test_visual_objects_populated_from_format():
    """When PbirVisual.format is non-empty, render_visual must emit it under 'objects'."""
    pv = PbirVisual(
        visual_type="barChart",
        encoding_bindings=(EncodingBinding(channel="Y", source_field_id="sales"),),
        format={
            "labels": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}],
            "dataPoint": [{"properties": {"fill": {"solid": {"color": {"expr": {"Literal": {"Value": "'#e15759'"}}}}}}}],
        },
    )
    pos = Position(x=0, y=0, w=400, h=300)
    obj = json.loads(render_visual("v1", pv, pos, 0))
    objects = obj["visual"]["objects"]
    assert "labels" in objects
    assert "dataPoint" in objects
    assert objects["labels"][0]["properties"]["show"]["expr"]["Literal"]["Value"] == "true"
    assert objects["dataPoint"][0]["properties"]["fill"]["solid"]["color"]["expr"]["Literal"]["Value"] == "'#e15759'"
```

- [x] **Step 3: Run tests to confirm they fail**

```
pytest tests/unit/visualmap/test_dispatch.py::test_dispatch_labels_show_emits_labels_object tests/unit/visualmap/test_dispatch.py::test_dispatch_mark_color_emits_data_point_object tests/unit/emit/pbir/test_visual.py::test_visual_objects_populated_from_format -v
```

Expected: dispatch tests FAIL — format is always `{}`; visual test may PASS if `render_visual` already passes format through (confirm either way).

- [x] **Step 4: Implement in `src/tableau2pbir/visualmap/dispatch.py`**

Add `MarkStyle` to the import:

```python
from tableau2pbir.ir.sheet import EncodingBinding, MarkStyle, PbirVisual, Sheet
```

Add `_build_format_objects` function after `_is_measure` and before `dispatch_visual`:

```python
def _build_format_objects(mark_style: MarkStyle | None) -> dict[str, list[dict]]:
    if mark_style is None:
        return {}
    objects: dict[str, list[dict]] = {}
    if mark_style.labels_show:
        objects["labels"] = [
            {"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}
        ]
    if mark_style.mark_color:
        objects["dataPoint"] = [
            {"properties": {"fill": {"solid": {"color": {
                "expr": {"Literal": {"Value": f"'{mark_style.mark_color}'"}}
            }}}}}
        ]
    return objects
```

Replace every `format={}` in `dispatch_visual` with `format=_build_format_objects(sheet.mark_style)`. The function has 7 return points — each `PbirVisual(...)` call must use the new format. Full replacement:

```python
def dispatch_visual(sheet: Sheet) -> PbirVisual | None:
    mark = sheet.mark_type
    enc = sheet.encoding
    rows = enc.rows
    cols = enc.columns
    color = enc.color
    fmt = _build_format_objects(sheet.mark_style)

    if mark in ("bar", "automatic") and rows and cols:
        if _is_measure(cols[0]) and not _is_measure(rows[0]):
            bindings = [_bind("Category", rows[0])] + [_bind("Y", c) for c in cols]
            if color:
                bindings.append(_bind("Series", color))
            return PbirVisual(visual_type="barChart", encoding_bindings=tuple(bindings), format=fmt)
        bindings = [_bind("Category", cols[0])] + [_bind("Y", r) for r in rows]
        if color:
            bindings.append(_bind("Series", color))
        return PbirVisual(visual_type="columnChart", encoding_bindings=tuple(bindings), format=fmt)

    if mark == "line" and rows and cols:
        bindings = [_bind("Category", cols[0])] + [_bind("Y", r) for r in rows]
        if color:
            bindings.append(_bind("Series", color))
        return PbirVisual(visual_type="lineChart", encoding_bindings=tuple(bindings), format=fmt)

    if mark == "area" and rows and cols:
        return PbirVisual(
            visual_type="areaChart",
            encoding_bindings=(_bind("Category", cols[0]), _bind("Y", rows[0])),
            format=fmt,
        )

    if mark in ("circle", "shape", "scatter") and rows and cols:
        bindings = [_bind("X", cols[0]), _bind("Y", rows[0])]
        if enc.size:
            bindings.append(_bind("Size", enc.size))
        if color:
            bindings.append(_bind("Color", color))
        return PbirVisual(visual_type="scatterChart", encoding_bindings=tuple(bindings), format=fmt)

    if mark == "pie" and rows:
        bindings = [_bind("Y", rows[0])]
        if color:
            bindings.insert(0, _bind("Category", color))
        return PbirVisual(visual_type="pieChart", encoding_bindings=tuple(bindings), format=fmt)

    if mark == "text":
        bindings = [_bind("Values", r) for r in rows] + [_bind("Values", c) for c in cols]
        if not bindings:
            return None
        return PbirVisual(visual_type="tableEx", encoding_bindings=tuple(bindings), format=fmt)

    if mark == "map" and rows and cols:
        return PbirVisual(
            visual_type="filledMap",
            encoding_bindings=(_bind("Location", cols[0]), _bind("Y", rows[0])),
            format=fmt,
        )

    return None
```

- [x] **Step 5: Run all new tests**

```
pytest tests/unit/visualmap/test_dispatch.py tests/unit/emit/pbir/test_visual.py -v
```

Expected: All pass.

- [x] **Step 6: Run full unit suite**

```
pytest tests/unit/ -x -q
```

Expected: All pass.

- [x] **Step 7: Commit**

```
git add src/tableau2pbir/visualmap/dispatch.py tests/unit/visualmap/test_dispatch.py tests/unit/emit/pbir/test_visual.py
git commit -m "feat(dispatch): emit dataPoint fill color and labels.show from MarkStyle into PBIR objects"
```

- [x] **Step 8: Run real-workbook E2E gate**

```
pytest tests/integration/test_real_workbooks_e2e.py -v
```

Expected: All pass.

- [x] **Step 9: Verify output for simple_join**

Re-run the pipeline on `simple_join.twb` and confirm the output `visual.json` files now contain `objects.labels` and `objects.dataPoint`:

```
python -m tableau2pbir convert tests/golden/real/simple_join.twb out/simple_join
```

Then inspect:
```
python -c "import json; d=json.load(open('out/simple_join/Report/definition/pages/ReportSection1/visuals/visual_1/visual.json')); print(json.dumps(d['visual']['objects'], indent=2))"
```

Expected output:
```json
{
  "labels": [
    {
      "properties": {
        "show": {
          "expr": {
            "Literal": {
              "Value": "true"
            }
          }
        }
      }
    }
  ],
  "dataPoint": [
    {
      "properties": {
        "fill": {
          "solid": {
            "color": {
              "expr": {
                "Literal": {
                  "Value": "'#ffaa7f'"
                }
              }
            }
          }
        }
      }
    }
  ]
}
```

---

## Self-Review

**Spec coverage:**
- ✅ `mark-color` → `objects.dataPoint[].properties.fill` (ground truth: `simple_join_n.Report/visual_1`)
- ✅ `mark-labels-show=true` → `objects.labels[].properties.show=true` (ground truth: both visuals)
- ✅ `mark-labels-cull` explicitly dropped — no PBI equivalent confirmed
- ✅ All 4 pipeline layers touched in order
- ✅ E2E gate in Task 4

**Placeholder scan:** None found.

**Type consistency:**
- `MarkStyle` defined in Task 1, imported in Tasks 3 and 4 ✅
- `_build_format_objects` returns `dict[str, list[dict]]`, matches `PbirVisual.format` type ✅
- `_build_mark_style` returns `MarkStyle | None`, matches `Sheet.mark_style` type ✅
- `raw.get("mark_style")` returns `dict | None` — handled by `_build_mark_style` ✅
