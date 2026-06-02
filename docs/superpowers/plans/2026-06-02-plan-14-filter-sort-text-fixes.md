# Plan 14 — Filter Aggregation, Text Encoding & Computed Sort Fixes

> **Execution approach: Subagent-Driven Development.**
> When implementing, use the `superpowers:subagent-driven-development` skill — dispatch a fresh subagent per task with review checkpoints between tasks. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Fix three root-cause gaps that cause Sheet 1's profit filter to apply at the wrong semantic level and Sheet 4 to be missing its Profit column and sort.

**Architecture:** All three fixes are in Stage 1 extraction (with lightweight IR and emission extensions for sort). Fix 1 is a pure extraction fix — the emission layer already handles `agg_prefix`. Fix 2 adds `text` encoding channel through the full pipeline. Fix 3 adds `<computed-sort>` support in extraction, a new `sort_by_field` IR field, a new `VisualSortEntry` type on `PbirVisual`, and `sortBy` emission in `render_visual`.

**Tech Stack:** Python 3.11+, lxml, pydantic v2, pytest.

---

## File Map

| Action | File |
|--------|------|
| Modify | `src/tableau2pbir/extract/worksheets.py` |
| Modify | `src/tableau2pbir/ir/sheet.py` |
| Modify | `src/tableau2pbir/stages/_build_sheets.py` |
| Modify | `src/tableau2pbir/visualmap/dispatch.py` |
| Modify | `src/tableau2pbir/emit/pbir/visual.py` |
| Modify | `tests/unit/extract/test_extract_filters.py` |
| Modify | `tests/unit/extract/test_worksheets.py` |
| Modify | `tests/unit/visualmap/test_dispatch.py` |
| Modify | `tests/unit/emit/pbir/test_visual.py` |

---

## Task 1 — Parse `agg_prefix` from aggregated filter column-instance names

**Root cause:** `_filters()` in `worksheets.py` hardcodes `"agg_prefix": None` for every range filter. Tableau column-instance names encode the aggregation in their prefix (e.g., `max:profit:qk` → agg = `max`). The emission layer at `_emit_range()` already emits an `"Advanced"` PBI filter when `agg_prefix` is set — the fix is purely in extraction.

**Files:**
- Modify: `src/tableau2pbir/extract/worksheets.py` (add `_parse_agg_prefix` helper, use it in `_filters`)
- Modify: `tests/unit/extract/test_extract_filters.py` (add two test cases)

---

- [x] **Step 1.1 — Write failing tests for `agg_prefix` parsing**

Add these two tests to `tests/unit/extract/test_extract_filters.py`:

```python
def test_quantitative_with_max_agg_prefix():
    """Column-instance '[max:profit:qk]' must set agg_prefix='max'."""
    v = _view(
        "<filter class='quantitative'"
        " column='[federated.17kv7r10vp81pc1g60xgp0re1it8].[max:profit:qk]'>"
        "<min>1013.13</min><max>6719.98</max>"
        "</filter>"
    )
    f = _filters(v)[0]
    assert f["kind"] == "range"
    assert f["agg_prefix"] == "max"
    assert f["min_val"] == "1013.13"
    assert f["max_val"] == "6719.98"


def test_quantitative_with_none_agg_prefix_returns_none():
    """Column-instance '[none:category:nk]' has 'none' prefix → agg_prefix=None (row-level)."""
    v = _view(
        "<filter class='quantitative'"
        " column='[federated.17kv7r10vp81pc1g60xgp0re1it8].[none:category:nk]'>"
        "<min>0</min><max>10</max>"
        "</filter>"
    )
    f = _filters(v)[0]
    assert f["agg_prefix"] is None
```

- [x] **Step 1.2 — Run tests to confirm they fail**

```
pytest tests/unit/extract/test_extract_filters.py::test_quantitative_with_max_agg_prefix tests/unit/extract/test_extract_filters.py::test_quantitative_with_none_agg_prefix_returns_none -v
```

Expected: FAIL — `AssertionError: assert None == 'max'`

- [x] **Step 1.3 — Add `_parse_agg_prefix` helper and wire it into `_filters`**

In `src/tableau2pbir/extract/worksheets.py`, add the helper right after `_parse_filter_column` (after line 171):

```python
_KNOWN_AGGS: frozenset[str] = frozenset({
    "sum", "avg", "average", "min", "max",
    "cntd", "ctd", "countd", "cnt", "count", "median",
    "attr", "year", "quarter", "month", "week", "day",
})


def _parse_agg_prefix(column_instance: str) -> str | None:
    """Extract the aggregation prefix from a Tableau column-instance name.

    Format: 'aggregation:field:type'  e.g. 'max:profit:qk' → 'max'.
    Returns None for 'none' prefix or unrecognised tokens (treats as row-level).
    """
    parts = column_instance.split(":")
    if len(parts) < 2:
        return None
    prefix = parts[0].lower()
    if prefix == "none":
        return None
    return prefix if prefix in _KNOWN_AGGS else None
```

Then in `_filters()`, replace the hardcoded `"agg_prefix": None` (line 218) with a call to the new helper:

Find this block:
```python
        if kind == "range":
            out.append({
                "kind": "range",
                "column": column,
                "min_val": f.findtext("min"),
                "max_val": f.findtext("max"),
                "agg_prefix": None,
            })
```

Replace with:
```python
        if kind == "range":
            out.append({
                "kind": "range",
                "column": column,
                "min_val": f.findtext("min"),
                "max_val": f.findtext("max"),
                "agg_prefix": _parse_agg_prefix(column),
            })
```

Also update the module-level docstring (line 31) from `"agg_prefix": None` to `"agg_prefix": str | None`:

```python
      # range:
      {"kind": "range", "column": str, "min_val": str | None,
       "max_val": str | None, "agg_prefix": str | None},
```

Also remove the stale inline comment in `ir/sheet.py` for `RangeFilter.agg_prefix` — find:
```python
    agg_prefix: str | None = None  # reserved for v1.1; always None from extraction
```
Replace with:
```python
    agg_prefix: str | None = None
```

- [x] **Step 1.4 — Run tests to confirm they pass**

```
pytest tests/unit/extract/test_extract_filters.py -v
```

Expected: all PASS, including the two new tests.

- [x] **Step 1.5 — Run full unit suite to check no regressions**

```
pytest tests/unit/ -x -q
```

Expected: all PASS.

- [x] **Step 1.6 — Commit**

```bash
git add src/tableau2pbir/extract/worksheets.py src/tableau2pbir/ir/sheet.py tests/unit/extract/test_extract_filters.py
git commit -m "fix: parse agg_prefix from Tableau column-instance names in range filters"
```

---

## Task 2 — Extract `<text>` marks card encoding channel

**Root cause:** `_encodings()` in `worksheets.py` extracts `color`, `size`, `label`, `tooltip`, `shape`, `angle` from pane `<encodings>` children but silently drops `<text>`. In text tables, Tableau places the value measure on the Text marks card (`<encodings><text column="..."/>`). This means Profit never reaches the visual's `Values` channel.

**Files:**
- Modify: `src/tableau2pbir/extract/worksheets.py` (`_encodings` dict + extraction loop)
- Modify: `src/tableau2pbir/ir/sheet.py` (`Encoding` — add `text` field)
- Modify: `src/tableau2pbir/stages/_build_sheets.py` (`_build_encoding` + calc tracking)
- Modify: `src/tableau2pbir/visualmap/dispatch.py` (text mark branch + dim-only bar branch)
- Modify: `tests/unit/extract/test_worksheets.py` (add `<text>` extraction test)
- Modify: `tests/unit/visualmap/test_dispatch.py` (add test: text encoding appears in Values)

---

- [x] **Step 2.1 — Write failing tests**

Add to `tests/unit/extract/test_worksheets.py`:

```python
_XML_TEXT_ENCODING = b"""<?xml version='1.0'?>
<workbook><worksheets>
  <worksheet name='TextTable'>
    <table>
      <view>
        <datasources><datasource name='ds1'/></datasources>
      </view>
      <panes>
        <pane>
          <mark class='Text'/>
          <encodings>
            <text column='[profit]'/>
          </encodings>
        </pane>
      </panes>
      <rows>[category]</rows>
      <cols />
    </table>
  </worksheet>
</worksheets></workbook>
"""


def test_text_encoding_extracted():
    root = parse_workbook_xml(_XML_TEXT_ENCODING)
    ws = extract_worksheets(root)
    assert ws[0]["encodings"]["text"] == "profit"
```

Add to `tests/unit/visualmap/test_dispatch.py`:

```python
def test_text_mark_with_text_encoding_includes_text_field_in_values():
    """Text mark with <text> encoding: the text-encoded field must appear in Values."""
    sh = Sheet(
        id="s1", name="S", datasource_refs=("ds1",),
        mark_type="text",
        encoding=Encoding(
            rows=(_fr("category_nk"),),
            text=_fr("profit_qk"),
        ),
        filters=(), sort=(), dual_axis=False, reference_lines=(),
        uses_calculations=(),
    )
    pv = dispatch_visual(sh)
    assert pv is not None
    assert pv.visual_type == "tableEx"
    field_ids = {b.source_field_id for b in pv.encoding_bindings}
    assert "profit_qk" in field_ids, "Text encoding field must appear in Values"
    assert "category_nk" in field_ids
```

- [x] **Step 2.2 — Run tests to confirm they fail**

```
pytest tests/unit/extract/test_worksheets.py::test_text_encoding_extracted tests/unit/visualmap/test_dispatch.py::test_text_mark_with_text_encoding_includes_text_field_in_values -v
```

Expected: FAIL — `KeyError: 'text'` and `AssertionError: 'profit_qk' not in field_ids`

- [x] **Step 2.3 — Add `text` to `_encodings()` in `worksheets.py`**

In `src/tableau2pbir/extract/worksheets.py`, update the `enc` dict initialiser inside `_encodings()` (around line 96–99) to add `"text": None`:

```python
    enc: dict[str, Any] = {
        "rows": _parse_shelf(rows),
        "columns": _parse_shelf(cols),
        "color": None, "size": None, "label": None, "tooltip": None,
        "detail": (), "shape": None, "angle": None, "text": None,
    }
```

Then update the extraction loop (around line 110) to include `"text"`:

```python
            elif ch.tag in {"color", "size", "label", "tooltip", "shape", "angle", "text"}:
                enc[ch.tag] = col
```

Also update the module-level docstring (around line 18–21) to add `"text"`:
```python
      "encodings": {
          "rows": tuple[str, ...],
          "columns": tuple[str, ...],
          "color": str | None,
          "size": str | None,
          "label": str | None,
          "tooltip": str | None,
          "detail": tuple[str, ...],
          "shape": str | None,
          "angle": str | None,
          "text": str | None,
      },
```

- [x] **Step 2.4 — Add `text` field to `Encoding` IR in `ir/sheet.py`**

In `src/tableau2pbir/ir/sheet.py`, update `Encoding`:

```python
class Encoding(IRBase):
    """Visual encoding channels. Only channels actually bound are populated."""
    rows: tuple[FieldRef, ...] = ()
    columns: tuple[FieldRef, ...] = ()
    color: FieldRef | None = None
    size: FieldRef | None = None
    label: FieldRef | None = None
    tooltip: FieldRef | None = None
    detail: tuple[FieldRef, ...] = ()
    shape: FieldRef | None = None
    angle: FieldRef | None = None
    text: FieldRef | None = None
```

- [x] **Step 2.5 — Wire `text` through `_build_encoding()` in `_build_sheets.py`**

In `src/tableau2pbir/stages/_build_sheets.py`, update `_build_encoding()`:

```python
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
        text=r(raw_enc.get("text")),
    )
```

Also add `"text"` to the calc-usage tracking loop in `build_sheets()` (around line 146):

```python
        for channel in ("color", "size", "label", "tooltip", "shape", "angle", "text"):
            name = raw["encodings"].get(channel)
            if name and name in calc_names and name not in used_names:
                used_names.append(name)
```

- [x] **Step 2.6 — Update `dispatch_visual()` to include `enc.text` in Values**

In `src/tableau2pbir/visualmap/dispatch.py`, update the `mark == "text"` branch and the dim-only bar branch:

Find the `text` mark branch (around line 91):
```python
    if mark == "text":
        bindings = [_bind("Values", r) for r in rows] + [_bind("Values", c) for c in cols]
        if not bindings:
            return None
        return PbirVisual(visual_type="tableEx", encoding_bindings=tuple(bindings), format=fmt)
```
Replace with:
```python
    if mark == "text":
        bindings = [_bind("Values", r) for r in rows] + [_bind("Values", c) for c in cols]
        if enc.text:
            bindings.append(_bind("Values", enc.text))
        if not bindings:
            return None
        return PbirVisual(visual_type="tableEx", encoding_bindings=tuple(bindings), format=fmt)
```

Find the dim-only bar branch (around line 45):
```python
    if mark in ("bar", "automatic") and rows and not cols:
        # Dimension-only rows (Tableau nested-header / cross-tab): map to Table visual.
        if all(not _is_measure(r) for r in rows):
            bindings = [_bind("Values", r) for r in rows]
            return PbirVisual(visual_type="tableEx", encoding_bindings=tuple(bindings), format=fmt)
```
Replace with:
```python
    if mark in ("bar", "automatic") and rows and not cols:
        # Dimension-only rows (Tableau nested-header / cross-tab): map to Table visual.
        if all(not _is_measure(r) for r in rows):
            bindings = [_bind("Values", r) for r in rows]
            if enc.text:
                bindings.append(_bind("Values", enc.text))
            return PbirVisual(visual_type="tableEx", encoding_bindings=tuple(bindings), format=fmt)
```

- [x] **Step 2.7 — Run new tests to confirm they pass**

```
pytest tests/unit/extract/test_worksheets.py::test_text_encoding_extracted tests/unit/visualmap/test_dispatch.py::test_text_mark_with_text_encoding_includes_text_field_in_values -v
```

Expected: both PASS.

- [x] **Step 2.8 — Run full unit suite**

```
pytest tests/unit/ -x -q
```

Expected: all PASS.

- [x] **Step 2.9 — Commit**

```bash
git add src/tableau2pbir/extract/worksheets.py src/tableau2pbir/ir/sheet.py src/tableau2pbir/stages/_build_sheets.py src/tableau2pbir/visualmap/dispatch.py tests/unit/extract/test_worksheets.py tests/unit/visualmap/test_dispatch.py
git commit -m "feat: extract Tableau <text> marks card encoding and include in tableEx Values"
```

---

## Task 3 — Extract `<computed-sort>` and emit PBI `sortBy`

**Root cause (2A):** `_sort()` only finds `<sort>` elements. Tableau uses a distinct `<computed-sort column="..." direction="..." using="...">` element when a dimension is sorted by a different measure. The `using` field is the measure used as the sort key. Neither the `SortSpec` IR nor the dispatch layer nor the visual emitter knows about sort-by-another-field.

**Files:**
- Modify: `src/tableau2pbir/extract/worksheets.py` (`_sort` — add `<computed-sort>` loop)
- Modify: `src/tableau2pbir/ir/sheet.py` (`SortSpec` — add `sort_by_field`; add `VisualSortEntry`; add `sort_by` to `PbirVisual`)
- Modify: `src/tableau2pbir/stages/_build_sheets.py` (`_build_sort` — wire `sort_by_field`)
- Modify: `src/tableau2pbir/visualmap/dispatch.py` (text + dim-only-bar branches — add sort_by to PbirVisual)
- Modify: `src/tableau2pbir/emit/pbir/visual.py` (`render_visual` — emit `sortBy` in query)
- Modify: `tests/unit/extract/test_worksheets.py` (add computed-sort extraction test)
- Modify: `tests/unit/emit/pbir/test_visual.py` (add sortBy emission test)

---

- [x] **Step 3.1 — Write failing tests**

Add to `tests/unit/extract/test_worksheets.py`:

```python
_XML_COMPUTED_SORT = b"""<?xml version='1.0'?>
<workbook><worksheets>
  <worksheet name='SortedTable'>
    <table>
      <view>
        <datasources><datasource name='ds1'/></datasources>
        <computed-sort
            column='[federated.ds1].[none:category:nk]'
            direction='DESC'
            using='[federated.ds1].[sum:profit:qk]' />
      </view>
      <panes><pane><mark class='Text'/></pane></panes>
      <rows>[category]</rows>
      <cols />
    </table>
  </worksheet>
</worksheets></workbook>
"""


def test_computed_sort_extracted():
    root = parse_workbook_xml(_XML_COMPUTED_SORT)
    ws = extract_worksheets(root)
    sorts = ws[0]["sort"]
    assert len(sorts) == 1
    s = sorts[0]
    assert s["column"] == "none:category:nk"
    assert s["direction"] == "desc"
    assert s["sort_by"] == "sum:profit:qk"
```

Add to `tests/unit/emit/pbir/test_visual.py` (read this file first to find a good place to add):

```python
from tableau2pbir.ir.sheet import EncodingBinding, PbirVisual, VisualSortEntry


def test_render_visual_emits_sort_by_when_present():
    """When PbirVisual.sort_by is set, visual.query.sortBy must be emitted."""
    from tableau2pbir.ir.dashboard import Position
    from tableau2pbir.emit.pbir.visual import render_visual
    import json

    pv = PbirVisual(
        visual_type="tableEx",
        encoding_bindings=(
            EncodingBinding(channel="Values", source_field_id="category_nk"),
            EncodingBinding(channel="Values", source_field_id="profit_qk"),
        ),
        sort_by=(
            VisualSortEntry(field_id="profit_qk", direction="desc"),
        ),
    )
    pos = Position(x=0, y=0, w=800, h=600)
    field_lookup = {
        "category_nk": {"table_name": "orders", "col_name": "category", "is_measure": False},
        "profit_qk": {"table_name": "orders", "col_name": "profit", "is_measure": True,
                      "measure_name": "Sum profit"},
    }
    obj = json.loads(render_visual("v1", pv, pos, 0, field_lookup))
    sort_by = obj["visual"]["query"].get("sortBy")
    assert sort_by is not None, "sortBy must be present in query"
    assert len(sort_by) == 1
    entry = sort_by[0]
    assert entry["direction"] == "Descending"
    assert entry["field"]["Measure"]["Property"] == "Sum profit"
    assert entry["field"]["Measure"]["Expression"]["SourceRef"]["Entity"] == "orders"


def test_render_visual_no_sort_by_when_empty():
    """When PbirVisual.sort_by is empty, sortBy must not appear in query."""
    from tableau2pbir.ir.dashboard import Position
    from tableau2pbir.emit.pbir.visual import render_visual
    import json

    pv = PbirVisual(
        visual_type="columnChart",
        encoding_bindings=(
            EncodingBinding(channel="Category", source_field_id="region_nk"),
            EncodingBinding(channel="Y", source_field_id="sales_qk"),
        ),
    )
    pos = Position(x=0, y=0, w=800, h=600)
    obj = json.loads(render_visual("v1", pv, pos, 0, {}))
    assert "sortBy" not in obj["visual"]["query"]
```

- [x] **Step 3.2 — Run tests to confirm they fail**

```
pytest tests/unit/extract/test_worksheets.py::test_computed_sort_extracted tests/unit/emit/pbir/test_visual.py::test_render_visual_emits_sort_by_when_present tests/unit/emit/pbir/test_visual.py::test_render_visual_no_sort_by_when_empty -v
```

Expected: all FAIL.

- [x] **Step 3.3 — Extend `_sort()` to handle `<computed-sort>`**

In `src/tableau2pbir/extract/worksheets.py`, replace `_sort()` (around line 250):

```python
def _sort(view: etree._Element) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for s in view.findall("sort"):
        col = optional_attr(s, "column")
        if col is None:
            continue
        out.append({
            "column": _unbracket(col),
            "direction": attr(s, "direction", default="asc").lower(),
            "sort_by": None,
        })
    for s in view.findall("computed-sort"):
        col = optional_attr(s, "column")
        if col is None:
            continue
        using = optional_attr(s, "using")
        out.append({
            "column": _parse_filter_column(col),
            "direction": attr(s, "direction", default="asc").lower(),
            "sort_by": _parse_filter_column(using) if using else None,
        })
    return out
```

Also update the module-level docstring (around line 36):
```python
  "sort": [ {"column": str, "direction": 'asc'|'desc', "sort_by": str | None} ],
```

- [x] **Step 3.4 — Extend `SortSpec` IR and add `VisualSortEntry` + `sort_by` to `PbirVisual`**

In `src/tableau2pbir/ir/sheet.py`:

Replace `SortSpec`:
```python
class SortSpec(IRBase):
    field: FieldRef
    direction: str                            # "asc" | "desc"
    sort_by_field: FieldRef | None = None     # for <computed-sort>: the measure to sort by
```

Add `VisualSortEntry` right before `PbirVisual`:
```python
class VisualSortEntry(IRBase):
    """One sort directive to emit into visual.query.sortBy."""
    field_id: str
    direction: str   # "asc" | "desc"
```

Update `PbirVisual` to add `sort_by`:
```python
class PbirVisual(IRBase):
    """Stage 4 annotation attached to a Sheet."""
    visual_type: str
    encoding_bindings: tuple[EncodingBinding, ...]
    format: dict[str, list[dict]] = {}
    sort_by: tuple[VisualSortEntry, ...] = ()
```

- [x] **Step 3.5 — Wire `sort_by_field` through `_build_sort()` in `_build_sheets.py`**

In `src/tableau2pbir/stages/_build_sheets.py`, replace `_build_sort()`:

```python
def _build_sort(raw_sorts: list[dict[str, Any]], table_id: str) -> tuple[SortSpec, ...]:
    return tuple(
        SortSpec(
            field=_ref(s["column"], table_id),
            direction=s["direction"],
            sort_by_field=_ref(s["sort_by"], table_id) if s.get("sort_by") else None,
        )
        for s in raw_sorts
    )
```

- [x] **Step 3.6 — Update `dispatch_visual()` to wire sort into `PbirVisual.sort_by`**

In `src/tableau2pbir/visualmap/dispatch.py`:

Add `VisualSortEntry` to the import:
```python
from tableau2pbir.ir.sheet import EncodingBinding, MarkStyle, PbirVisual, Sheet, VisualSortEntry
```

Add a helper before `dispatch_visual`:
```python
def _build_sort_entries(sheet: Sheet, existing_bindings: list[EncodingBinding]) -> tuple[tuple[EncodingBinding, ...], tuple[VisualSortEntry, ...]]:
    """Return (extra_bindings, sort_entries) from computed sorts.

    Extra bindings add the sort-by measure to Values if not already present.
    """
    extra: list[EncodingBinding] = []
    entries: list[VisualSortEntry] = []
    for s in sheet.sort:
        if s.sort_by_field is None:
            continue
        fid = s.sort_by_field.column_id
        if not any(b.source_field_id == fid for b in existing_bindings) and \
           not any(b.source_field_id == fid for b in extra):
            extra.append(_bind("Values", s.sort_by_field))
        entries.append(VisualSortEntry(field_id=fid, direction=s.direction))
    return tuple(extra), tuple(entries)
```

Update the `mark == "text"` branch to use `_build_sort_entries`:
```python
    if mark == "text":
        bindings = [_bind("Values", r) for r in rows] + [_bind("Values", c) for c in cols]
        if enc.text:
            bindings.append(_bind("Values", enc.text))
        extra_sort, sort_entries = _build_sort_entries(sheet, bindings)
        bindings.extend(extra_sort)
        if not bindings:
            return None
        return PbirVisual(
            visual_type="tableEx",
            encoding_bindings=tuple(bindings),
            format=fmt,
            sort_by=sort_entries,
        )
```

Update the dim-only bar branch:
```python
    if mark in ("bar", "automatic") and rows and not cols:
        if all(not _is_measure(r) for r in rows):
            bindings = [_bind("Values", r) for r in rows]
            if enc.text:
                bindings.append(_bind("Values", enc.text))
            extra_sort, sort_entries = _build_sort_entries(sheet, bindings)
            bindings.extend(extra_sort)
            return PbirVisual(
                visual_type="tableEx",
                encoding_bindings=tuple(bindings),
                format=fmt,
                sort_by=sort_entries,
            )
```

- [x] **Step 3.7 — Emit `sortBy` in `render_visual()`**

In `src/tableau2pbir/emit/pbir/visual.py`, update `render_visual()`:

```python
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

    query: dict = {"queryState": query_state}
    if pbir_visual.sort_by:
        query["sortBy"] = [_make_sort_entry(s, fl) for s in pbir_visual.sort_by]

    obj = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/1.0.0/schema.json",
        "name": visual_id,
        "position": {"x": position.x, "y": position.y,
                     "width": position.w, "height": position.h, "z": z_order},
        "visual": {
            "visualType": pbir_visual.visual_type,
            "query": query,
            "objects": pbir_visual.format or {},
        },
    }
    return json.dumps(obj, indent=2)
```

Add `_make_sort_entry` helper after `_make_projection`:

```python
def _make_sort_entry(s, field_lookup: dict) -> dict:
    from tableau2pbir.ir.sheet import VisualSortEntry
    info = field_lookup.get(s.field_id, {})
    table_name = info.get("table_name", "Model")
    prop_name = info.get("measure_name") or info.get("col_name", s.field_id)
    is_measure = info.get("is_measure", True)
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
```

- [x] **Step 3.8 — Run new tests to confirm they pass**

```
pytest tests/unit/extract/test_worksheets.py::test_computed_sort_extracted tests/unit/emit/pbir/test_visual.py::test_render_visual_emits_sort_by_when_present tests/unit/emit/pbir/test_visual.py::test_render_visual_no_sort_by_when_empty -v
```

Expected: all PASS.

- [x] **Step 3.9 — Run full unit suite**

```
pytest tests/unit/ -x -q
```

Expected: all PASS.

- [x] **Step 3.10 — Commit**

```bash
git add src/tableau2pbir/extract/worksheets.py src/tableau2pbir/ir/sheet.py src/tableau2pbir/stages/_build_sheets.py src/tableau2pbir/visualmap/dispatch.py src/tableau2pbir/emit/pbir/visual.py tests/unit/extract/test_worksheets.py tests/unit/emit/pbir/test_visual.py
git commit -m "feat: extract <computed-sort> and emit PBI sortBy for sort-by-measure"
```

---

## Task 4 — Integration & E2E verification

- [x] **Step 4.1 — Re-convert `simple_join_sorted_test.twb`**

```
python -m tableau2pbir.cli convert tests/golden/real/simple_join_sorted_test.twb --out out/
```

Expected: exit 0.

- [x] **Step 4.2 — Verify Sheet 1 filter is now "Advanced" (not "Range")**

Read `out/simple_join_sorted_test/Report/definition/pages/ReportSection1/page.json`.

The profit filter must now look like:
```json
{
  "type": "Advanced",
  "filter": {
    "Where": [
      {"Condition": {"Comparison": {"ComparisonKind": 2, "Left": {"Aggregation": {...}}, ...}}},
      {"Condition": {"Comparison": {"ComparisonKind": 4, "Left": {"Aggregation": {...}}, ...}}}
    ]
  }
}
```

It must NOT be `"type": "Range"` with a `Between` condition.

- [x] **Step 4.3 — Verify Sheet 4 visual has Profit in Values and sortBy**

Read `out/simple_join_sorted_test/Report/definition/pages/ReportSection3/visuals/visual_3/visual.json`.

Assert:
- `visual.query.queryState.Values.projections` contains both `category` and `profit` / `Sum profit`
- `visual.query.sortBy` exists and has one entry with `direction: "Descending"` pointing to the profit measure

- [x] **Step 4.4 — Run real-workbook E2E integration tests**

```
pytest tests/integration/test_real_workbooks_e2e.py -v -m integration
```

Expected: all PASS (or skip if no ANTHROPIC_API_KEY).

- [x] **Step 4.5 — Run regression check**

```
python -m tableau2pbir.cli regression-check
```

Expected: no regressions reported for `simple_join`, `simple_join_dashboard`, `simple_join_few_filter`.

- [x] **Step 4.6 — Commit**

```bash
git add -A
git commit -m "test: verify simple_join_sorted_test filter and sort fixes end-to-end"
```

---

## Self-Review

**Spec coverage:**
- Issue 1 (profit filter wrong level) → Task 1 ✓
- Issue 2B (missing Profit in Sheet 4 visual) → Task 2 ✓
- Issue 2A (no sort) → Task 3 ✓
- E2E verification → Task 4 ✓

**Type consistency check:**
- `VisualSortEntry` defined in Task 3 Step 3.4 (ir/sheet.py), imported in dispatch.py (Step 3.6) and visual.py (Step 3.7) ✓
- `sort_by: tuple[VisualSortEntry, ...]` added to `PbirVisual` in Step 3.4, used in visual.py Step 3.7 ✓
- `sort_by_field: FieldRef | None` added to `SortSpec` in Step 3.4, populated in `_build_sort` Step 3.5, read in dispatch Step 3.6 ✓
- `enc.text: FieldRef | None` added to `Encoding` in Step 2.4, populated in `_build_encoding` Step 2.5, read in dispatch Step 2.6 ✓
- `_parse_agg_prefix` defined in Step 1.3, used in same function ✓
- All existing test helpers (`_fr`, `_sheet`, `_view`) are already in existing test files ✓

**No placeholders:** All steps contain full code. ✓

**Existing test that changes meaning:** `test_quantitative_mapped_to_range` in `test_extract_filters.py` asserts `f["agg_prefix"] is None` for `column='[Amount]'` (no aggregation prefix). After Task 1, `_parse_agg_prefix("Amount")` returns `None` (no `:` separator), so this test continues to pass without modification. ✓
