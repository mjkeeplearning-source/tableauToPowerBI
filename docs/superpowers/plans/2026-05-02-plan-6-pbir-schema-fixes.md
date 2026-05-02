# PBIR Schema Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use  superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all PBIR schema version mismatches, structural gaps, and calculation naming/formula bugs identified by comparing our output to the working MVP at `C:\vibe_coding\tabToPbi`, so that `simple_join.twb` opens without errors in PBI Desktop and measures have correct human-readable names.

**Architecture:** Eleven targeted fixes — no new files except `pages.json` manifest logic (added to `report.py`). Every fix is backed by a failing test first. The MVP at `C:\vibe_coding\tabToPbi\tab_to_pbi\generator.py` is the reference for all schema versions and file structure.

**Tech Stack:** Python 3.11+, pytest, pathlib, json stdlib only.

---

## Root-cause summary (reference)

| # | File | Problem | Fix |
|---|------|---------|-----|
| 1 | `emit/pbir/report.py` | Schema `1.0.0` + embeds `pageOrder` in `report.json` | Schema `3.2.0`, strip `pages` key |
| 2 | `emit/pbir/render.py` | Never writes `pages/pages.json` | Add `render_pages_manifest()` call |
| 3 | `emit/pbir/page.py` | Schema `2.0.0` | Schema `2.1.0` |
| 4 | `emit/pbir/visual.py` | Schema `2.0.0` | Schema `1.0.0` |
| 5 | `emit/pbir/render.py` | `version.json` has `"version": "1.0"` | `"version": "2.0.0"` |
| 6 | `validate/pbip.py` | `definition.pbir` has `$schema` + `byConnection: null` | Remove both |
| 7 | `emit/tmdl/table.py` | Partition always `mode: import` | `import` for file-based, `directQuery` for DB |
| 8 | `validate/structural.py` | Page-order check reads `report.json["pageOrder"]` | Read `pages/pages.json["pageOrder"]` instead |
| 9 | `extract/datasources.py:114` + `stages/_build_data_model.py:302` | Calc name uses internal ID (`Calculation_039…`) — `caption` attr never read | Read `caption`; use it as `Calculation.name` |
| 10 | `translate/rules/aggregate.py` | `_OUTER_RE` rejects compound exprs (`AGG(x) - AGG(y)`) → AI fallback → broken DAX | Add compound arithmetic path; rename all `COUNTD` → `DISTINCTCOUNT` |
| 11 | Pipeline E2E | Stale artifacts in `out/` mix with new output | Full re-run + verify file structure |

---

## File map

**Modified files only — no new files:**

| File | Change |
|------|--------|
| `src/tableau2pbir/emit/pbir/report.py` | Schema 3.2.0; remove `pages` block; add `render_pages_manifest()` |
| `src/tableau2pbir/emit/pbir/render.py` | Call `render_pages_manifest()`; fix `version.json` value |
| `src/tableau2pbir/emit/pbir/page.py` | Schema `2.1.0` |
| `src/tableau2pbir/emit/pbir/visual.py` | Schema `1.0.0` |
| `src/tableau2pbir/validate/pbip.py` | Strip `$schema` + `byConnection: null` from `_DEFINITION_PBIR_PAYLOAD` |
| `src/tableau2pbir/emit/tmdl/table.py` | Partition mode derived from `tableau_kind` |
| `src/tableau2pbir/validate/structural.py` | Page-order check reads `pages/pages.json` |
| `tests/unit/emit/pbir/test_report.py` | Update for 3.2.0 + `render_pages_manifest` |
| `tests/unit/emit/pbir/test_render.py` | Update version assertion; add `pages.json` assertion |
| `tests/unit/emit/pbir/test_page.py` | Assert schema `2.1.0` |
| `tests/unit/emit/pbir/test_visual.py` | Assert schema `1.0.0` |
| `tests/unit/validate/test_pbip.py` | Remove `byConnection` + `$schema` assertions |
| `tests/unit/emit/tmdl/test_table.py` | Add DB-connector → `directQuery` test |
| `tests/unit/validate/test_structural.py` | Scaffold writes `pages.json`; update page-order test |
| `src/tableau2pbir/extract/datasources.py` | Capture `caption` attr in `_columns_and_calculations` |
| `src/tableau2pbir/stages/_build_data_model.py` | Use caption as `Calculation.name` |
| `src/tableau2pbir/translate/rules/aggregate.py` | Add compound arithmetic path + `re.IGNORECASE` |
| `tests/unit/stages/test_s02_datasources.py` | Assert caption captured and used as calc name |
| `tests/unit/translate/rules/test_aggregate.py` | Assert compound expressions translate correctly |

---

## Task 1: Fix `report.json` — schema 3.2.0, remove embedded pageOrder

**Files:**
- Modify: `src/tableau2pbir/emit/pbir/report.py`
- Test: `tests/unit/emit/pbir/test_report.py`

Current `report.py` uses schema `1.0.0` and embeds `"pages": {"pageOrder": [...]}` inside `report.json`. MVP uses schema `3.2.0` with no pages key — page order goes in a separate `pages/pages.json` file (Task 2).

- [x] **Step 1: Write failing tests**

Replace the entire content of `tests/unit/emit/pbir/test_report.py`:

```python
import json

from tableau2pbir.emit.pbir.report import render_pages_manifest, render_report


def test_report_json_schema_is_3_2_0():
    out = render_report()
    obj = json.loads(out)
    assert "/3.2.0/" in obj["$schema"], f"Expected schema 3.2.0, got: {obj['$schema']}"


def test_report_json_has_no_pages_key():
    """Schema 3.2.0 puts page order in pages/pages.json, not in report.json."""
    out = render_report()
    obj = json.loads(out)
    assert "pages" not in obj, "report.json must not embed page order — use pages.json instead"


def test_report_json_has_theme():
    out = render_report()
    obj = json.loads(out)
    assert obj["themeCollection"]["baseTheme"]["name"] == "CY26SU02"


def test_pages_manifest_page_order():
    out = render_pages_manifest(page_order=["pageA", "pageB"])
    obj = json.loads(out)
    assert obj["pageOrder"] == ["pageA", "pageB"]
    assert obj["activePageName"] == "pageA"


def test_pages_manifest_schema():
    out = render_pages_manifest(page_order=["p1"])
    obj = json.loads(out)
    assert "pagesMetadata/1.0.0" in obj["$schema"]


def test_pages_manifest_empty_list():
    out = render_pages_manifest(page_order=[])
    obj = json.loads(out)
    assert obj["pageOrder"] == []
    assert obj["activePageName"] == ""
```

- [x] **Step 2: Run tests to verify they fail**

```
pytest tests/unit/emit/pbir/test_report.py -v
```

Expected: multiple FAILs — `render_report` takes args it shouldn't, no `render_pages_manifest`, schema mismatch.

- [x] **Step 3: Rewrite `src/tableau2pbir/emit/pbir/report.py`**

```python
"""Render Report/definition/report.json and pages/pages.json."""
from __future__ import annotations

import json

_SCHEMA_BASE = "https://developer.microsoft.com/json-schemas/fabric/item/report"


def render_report() -> str:
    """Render Report/definition/report.json (schema 3.2.0).

    Page order is NOT embedded here — it lives in pages/pages.json (render_pages_manifest).
    """
    obj = {
        "$schema": f"{_SCHEMA_BASE}/definition/report/3.2.0/schema.json",
        "themeCollection": {
            "baseTheme": {
                "name": "CY26SU02",
                "reportVersionAtImport": {
                    "visual": "2.6.0",
                    "report": "3.1.0",
                    "page": "2.3.0",
                },
                "type": "SharedResources",
            }
        },
        "objects": {
            "section": [
                {
                    "properties": {
                        "verticalAlignment": {
                            "expr": {"Literal": {"Value": "'Top'"}}
                        }
                    }
                }
            ]
        },
        "settings": {
            "useStylableVisualContainerHeader": True,
            "exportDataMode": "AllowSummarized",
            "defaultDrillFilterOtherVisuals": True,
            "allowChangeFilterTypes": True,
            "useEnhancedTooltips": True,
            "useDefaultAggregateDisplayName": True,
        },
    }
    return json.dumps(obj, indent=2)


def render_pages_manifest(page_order: list[str]) -> str:
    """Render pages/pages.json — the pagesMetadata manifest required by schema 3.2.0."""
    obj = {
        "$schema": f"{_SCHEMA_BASE}/definition/pagesMetadata/1.0.0/schema.json",
        "pageOrder": list(page_order),
        "activePageName": page_order[0] if page_order else "",
    }
    return json.dumps(obj, indent=2)
```

- [x] **Step 4: Run tests to verify they pass**

```
pytest tests/unit/emit/pbir/test_report.py -v
```

Expected: all PASS.

- [x] **Step 5: Commit**

```
git add src/tableau2pbir/emit/pbir/report.py tests/unit/emit/pbir/test_report.py
git commit -m "fix(pbir): report.json schema 3.2.0 + separate pages manifest"
```

---

## Task 2: Write `pages/pages.json` in Stage 7 render

**Files:**
- Modify: `src/tableau2pbir/emit/pbir/render.py`
- Test: `tests/unit/emit/pbir/test_render.py`

`render_report()` in `render.py` must now: (a) call `render_report_json()` with no args, (b) call `render_pages_manifest(page_ids)` and write to `rd / "pages" / "pages.json"`, (c) update `version.json` to `"2.0.0"`.

- [x] **Step 1: Write failing tests**

Replace the entire content of `tests/unit/emit/pbir/test_render.py`:

```python
import json
from pathlib import Path

from tableau2pbir.emit.pbir.render import render_report
from tableau2pbir.ir.dashboard import (
    Container, ContainerKind, Dashboard, DashboardSize, Leaf, LeafKind, Position,
)
from tableau2pbir.ir.datasource import ConnectorTier, Datasource
from tableau2pbir.ir.model import Column, ColumnKind, ColumnRole, Table
from tableau2pbir.ir.sheet import EncodingBinding, Encoding, PbirVisual, Sheet
from tableau2pbir.ir.workbook import DataModel, Workbook


def _wb_one_page_one_visual() -> Workbook:
    sheet = Sheet(
        id="s1", name="Bars", datasource_refs=("d1",), mark_type="bar",
        encoding=Encoding(), filters=(), sort=(), dual_axis=False, reference_lines=(),
        uses_calculations=(),
        pbir_visual=PbirVisual(
            visual_type="clusteredBarChart",
            encoding_bindings=(
                EncodingBinding(channel="Category", source_field_id="Sales.Region"),
                EncodingBinding(channel="Y", source_field_id="Total Sales"),
            ),
        ),
    )
    leaf = Leaf(kind=LeafKind.SHEET, payload={"sheet_id": "s1"},
                position=Position(x=0, y=0, w=1280, h=720))
    dash = Dashboard(
        id="d1", name="Page 1",
        size=DashboardSize(w=1280, h=720, kind="exact"),
        layout_tree=Container(kind=ContainerKind.H, children=(leaf,)),
    )
    ds = Datasource(
        id="d1", name="DS", tableau_kind="csv", connector_tier=ConnectorTier.TIER_1,
        pbi_m_connector="Csv.Document", connection_params={"filename": "C:/x.csv"},
        user_action_required=(), table_ids=("t1",), extract_ignored=False,
    )
    table = Table(id="t1", name="Sales", datasource_id="d1", column_ids=("c1",))
    col = Column(id="c1", name="Region", datatype="string", role=ColumnRole.DIMENSION,
                 kind=ColumnKind.RAW)
    return Workbook(
        ir_schema_version="1.1.0", source_path="x.twb", source_hash="a",
        tableau_version="2024.1", config={},
        data_model=DataModel(datasources=(ds,), tables=(table,)),
        sheets=(sheet,), dashboards=(dash,), unsupported=(),
    )


def test_render_writes_required_files(tmp_path: Path):
    wb = _wb_one_page_one_visual()
    render_report(wb, tmp_path)
    rd = tmp_path / "Report" / "definition"

    assert (rd / "report.json").is_file(), "report.json required"
    assert (rd / "version.json").is_file(), "version.json required"
    assert (rd / "pages" / "pages.json").is_file(), "pages/pages.json required by schema 3.2.0"


def test_version_json_is_2_0_0(tmp_path: Path):
    wb = _wb_one_page_one_visual()
    render_report(wb, tmp_path)
    rd = tmp_path / "Report" / "definition"
    ver = json.loads((rd / "version.json").read_text(encoding="utf-8"))
    assert ver["version"] == "2.0.0", f"version.json must be '2.0.0', got: {ver['version']}"


def test_pages_json_contains_page_id(tmp_path: Path):
    wb = _wb_one_page_one_visual()
    render_report(wb, tmp_path)
    rd = tmp_path / "Report" / "definition"
    pages_manifest = json.loads((rd / "pages" / "pages.json").read_text(encoding="utf-8"))
    assert len(pages_manifest["pageOrder"]) == 1
    assert pages_manifest["activePageName"] == pages_manifest["pageOrder"][0]


def test_render_writes_page_and_visual(tmp_path: Path):
    wb = _wb_one_page_one_visual()
    manifest = render_report(wb, tmp_path)
    rd = tmp_path / "Report" / "definition"
    pages = list((rd / "pages").iterdir())
    # pages/ has pages.json + one page folder
    page_dirs = [p for p in pages if p.is_dir()]
    assert len(page_dirs) == 1
    visuals = list((page_dirs[0] / "visuals").iterdir())
    assert len(visuals) == 1
    assert (visuals[0] / "visual.json").is_file()
    assert manifest["counts"]["pages"] == 1
    assert manifest["counts"]["visuals"] == 1
    assert manifest["blocked_visuals"] == []
```

- [x] **Step 2: Run tests to verify they fail**

```
pytest tests/unit/emit/pbir/test_render.py -v
```

Expected: `test_render_writes_required_files` FAILS (no `pages.json`), `test_version_json_is_2_0_0` FAILS (version is `"1.0"`).

- [x] **Step 3: Update `src/tableau2pbir/emit/pbir/render.py`**

Change the import at the top of `render.py`:

```python
from tableau2pbir.emit.pbir.report import render_pages_manifest, render_report as render_report_json
```

Replace the two `write_text` calls near the bottom of `render_report()` (the `report.json` and `version.json` writes) with:

```python
    write_text(rd / "pages" / "pages.json",
               render_pages_manifest(page_order=page_ids))
    write_text(rd / "report.json", render_report_json())
    write_text(rd / "version.json", json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
        "version": "2.0.0",
    }, indent=2))
```

The old call was:
```python
    write_text(rd / "report.json",
               render_report_json(report_name=Path(wb.source_path).stem, page_order=page_ids))
    write_text(rd / "version.json", json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
        "version": "1.0",
    }, indent=2))
```

Also remove the now-unused `Path` import from `render.py` if it becomes unused (check first).

- [x] **Step 4: Run tests to verify they pass**

```
pytest tests/unit/emit/pbir/test_render.py -v
```

Expected: all PASS.

- [x] **Step 5: Run the full unit suite to check for regressions**

```
pytest tests/unit/ -v --tb=short 2>&1 | head -60
```

Expected: only failures are in tasks we haven't fixed yet (page, visual, pbip, structural, table).

- [x] **Step 6: Commit**

```
git add src/tableau2pbir/emit/pbir/render.py tests/unit/emit/pbir/test_render.py
git commit -m "fix(pbir): write pages/pages.json manifest; version.json 2.0.0"
```

---

## Task 3: Fix `page.json` schema to `2.1.0`

**Files:**
- Modify: `src/tableau2pbir/emit/pbir/page.py`
- Test: `tests/unit/emit/pbir/test_page.py`

- [x] **Step 1: Write failing test**

Add to `tests/unit/emit/pbir/test_page.py`:

```python
def test_page_json_schema_is_2_1_0():
    out = render_page(page_id="p1", display_name="Revenue", ordinal=0, width=1280, height=720)
    obj = json.loads(out)
    assert "/2.1.0/" in obj["$schema"], f"Expected schema 2.1.0, got: {obj['$schema']}"
```

- [x] **Step 2: Run test to verify it fails**

```
pytest tests/unit/emit/pbir/test_page.py::test_page_json_schema_is_2_1_0 -v
```

Expected: FAIL — schema is `2.0.0`.

- [x] **Step 3: Fix `src/tableau2pbir/emit/pbir/page.py`**

Change line 10 from:
```python
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.0.0/schema.json",
```
to:
```python
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json",
```

- [x] **Step 4: Run tests to verify they pass**

```
pytest tests/unit/emit/pbir/test_page.py -v
```

Expected: all PASS.

- [x] **Step 5: Commit**

```
git add src/tableau2pbir/emit/pbir/page.py tests/unit/emit/pbir/test_page.py
git commit -m "fix(pbir): page.json schema 2.1.0"
```

---

## Task 4: Fix `visual.json` schema to `1.0.0`

**Files:**
- Modify: `src/tableau2pbir/emit/pbir/visual.py`
- Test: `tests/unit/emit/pbir/test_visual.py`

- [x] **Step 1: Write failing test**

Add to `tests/unit/emit/pbir/test_visual.py`:

```python
def test_visual_json_schema_is_1_0_0():
    from tableau2pbir.ir.dashboard import Position
    pos = Position(x=0, y=0, w=400, h=300)
    out = render_visual(visual_id="v1", pbir_visual=_bar_visual(), position=pos, z_order=0)
    obj = json.loads(out)
    assert "/1.0.0/" in obj["$schema"], f"Expected schema 1.0.0, got: {obj['$schema']}"
```

- [x] **Step 2: Run test to verify it fails**

```
pytest tests/unit/emit/pbir/test_visual.py::test_visual_json_schema_is_1_0_0 -v
```

Expected: FAIL — schema is `2.0.0`.

- [x] **Step 3: Fix `src/tableau2pbir/emit/pbir/visual.py`**

Change line 17 from:
```python
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.0.0/schema.json",
```
to:
```python
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/1.0.0/schema.json",
```

- [x] **Step 4: Run tests to verify they pass**

```
pytest tests/unit/emit/pbir/test_visual.py -v
```

Expected: all PASS.

- [x] **Step 5: Commit**

```
git add src/tableau2pbir/emit/pbir/visual.py tests/unit/emit/pbir/test_visual.py
git commit -m "fix(pbir): visualContainer schema 1.0.0"
```

---

## Task 5: Fix `definition.pbir` — remove `$schema` and `byConnection: null`

**Files:**
- Modify: `src/tableau2pbir/validate/pbip.py`
- Test: `tests/unit/validate/test_pbip.py`

The working MVP's `definition.pbir` is minimal — just `version` + `datasetReference.byPath`. Our version adds `$schema` and `byConnection: null` which are not part of the real format.

- [x] **Step 1: Write failing test**

Add to `tests/unit/validate/test_pbip.py`:

```python
def test_definition_pbir_has_no_schema_key(tmp_path: Path):
    (tmp_path / "Report" / "definition").mkdir(parents=True)
    write_pbip_root(tmp_path, "Superstore")
    data = json.loads((tmp_path / "Report" / "definition.pbir").read_text(encoding="utf-8"))
    assert "$schema" not in data, "definition.pbir must not have $schema — not in working PBIR format"


def test_definition_pbir_has_no_by_connection(tmp_path: Path):
    (tmp_path / "Report" / "definition").mkdir(parents=True)
    write_pbip_root(tmp_path, "Superstore")
    data = json.loads((tmp_path / "Report" / "definition.pbir").read_text(encoding="utf-8"))
    assert "byConnection" not in data.get("datasetReference", {}), \
        "definition.pbir must not have byConnection — causes Desktop connection resolver confusion"
```

- [x] **Step 2: Run tests to verify they fail**

```
pytest tests/unit/validate/test_pbip.py::test_definition_pbir_has_no_schema_key tests/unit/validate/test_pbip.py::test_definition_pbir_has_no_by_connection -v
```

Expected: both FAIL.

- [x] **Step 3: Fix the stale tests that assert the wrong behavior**

In `tests/unit/validate/test_pbip.py`, remove or update:
- `test_writes_definition_pbir`: remove the `assert data["datasetReference"]["byConnection"] is None` line
- `test_definition_pbir_schema_key_present`: delete this entire test (it asserts the wrong behavior)

- [x] **Step 4: Fix `src/tableau2pbir/validate/pbip.py`**

Replace `_DEFINITION_PBIR_PAYLOAD` with:

```python
_DEFINITION_PBIR_PAYLOAD = {
    "version": "4.0",
    "datasetReference": {
        "byPath": {"path": "../SemanticModel"},
    },
}
```

- [x] **Step 5: Run all pbip tests to verify they pass**

```
pytest tests/unit/validate/test_pbip.py -v
```

Expected: all PASS.

- [x] **Step 6: Commit**

```
git add src/tableau2pbir/validate/pbip.py tests/unit/validate/test_pbip.py
git commit -m "fix(pbir): definition.pbir remove extra schema + byConnection fields"
```

---

## Task 6: Fix partition mode — file-based → `import`, database → `directQuery`

**Files:**
- Modify: `src/tableau2pbir/emit/tmdl/table.py`
- Test: `tests/unit/emit/tmdl/test_table.py`

Currently `render_table` always writes `mode: import`. File-based connectors (`textscan`, `csv`, `excel-direct`) should use `import`; all database connectors should use `directQuery`. This is what the MVP does via `conn.get("storage_mode", "import")`.

- [x] **Step 1: Write failing test**

Add to `tests/unit/emit/tmdl/test_table.py`:

```python
def test_db_table_uses_direct_query_mode():
    ds = Datasource(
        id="d2", name="PG", tableau_kind="postgres", connector_tier=ConnectorTier.TIER_2,
        pbi_m_connector="PostgreSQL.Database",
        connection_params={"server": "localhost", "dbname": "sales", "schema": "public", "table": "orders"},
        user_action_required=("enter credentials",), table_ids=("t2",), extract_ignored=False,
    )
    out = render_table(name="orders", columns=[], measures=[], datasource=ds)
    assert "mode: directQuery" in out, "DB-backed tables must use directQuery partition mode"


def test_csv_table_uses_import_mode():
    ds = Datasource(
        id="d1", name="DS", tableau_kind="csv", connector_tier=ConnectorTier.TIER_1,
        pbi_m_connector="Csv.Document",
        connection_params={"filename": "C:/data.csv"},
        user_action_required=(), table_ids=("t1",), extract_ignored=False,
    )
    out = render_table(name="Sales", columns=[], measures=[], datasource=ds)
    assert "mode: import" in out, "File-based tables must use import partition mode"
```

- [x] **Step 2: Run tests to verify they fail**

```
pytest tests/unit/emit/tmdl/test_table.py::test_db_table_uses_direct_query_mode -v
```

Expected: FAIL — output contains `mode: import` instead of `mode: directQuery`.

- [x] **Step 3: Fix `src/tableau2pbir/emit/tmdl/table.py`**

Add a module-level constant and a helper just before `render_table`:

```python
_FILE_BASED_KINDS = frozenset({"textscan", "csv", "excel-direct"})


def _partition_mode(datasource: Datasource) -> str:
    return "import" if datasource.tableau_kind in _FILE_BASED_KINDS else "directQuery"
```

Change the `partition` block inside `render_table` from:
```python
    partition = (
        f"\tpartition {tmdl_ident(name)} = m\n"
        f"\t\tmode: import\n"
        f"\t\tsource =\n"
        f"{indent(m_body, chr(9) * 3)}"
    )
```
to:
```python
    mode = _partition_mode(datasource)
    partition = (
        f"\tpartition {tmdl_ident(name)} = m\n"
        f"\t\tmode: {mode}\n"
        f"\t\tsource =\n"
        f"{indent(m_body, chr(9) * 3)}"
    )
```

- [x] **Step 4: Run tests to verify they pass**

```
pytest tests/unit/emit/tmdl/test_table.py -v
```

Expected: all PASS.

- [x] **Step 5: Commit**

```
git add src/tableau2pbir/emit/tmdl/table.py tests/unit/emit/tmdl/test_table.py
git commit -m "fix(tmdl): partition mode directQuery for DB connectors, import for file-based"
```

---

## Task 7: Fix structural validator — read page order from `pages.json`

**Files:**
- Modify: `src/tableau2pbir/validate/structural.py`
- Test: `tests/unit/validate/test_structural.py`

`structural.py` line 67 reads `report_json.get("pageOrder", [])` from `report.json`. After the schema 3.2.0 fix, `report.json` has no `pageOrder`. The validator must read from `pages/pages.json` instead.

- [x] **Step 1: Write failing test**

Add this test to `tests/unit/validate/test_structural.py` — it uses `pages.json` for the order mismatch, which the current validator does NOT read:

```python
def test_fails_when_pages_json_order_disagrees_with_disk(tmp_path):
    """Validator must read page order from pages/pages.json, not report.json."""
    out = tmp_path
    sm = out / "SemanticModel" / "definition"
    (sm / "tables").mkdir(parents=True)
    (sm / "tables" / "Sales.tmdl").write_text("table Sales\n\tmeasure Total = 1", encoding="utf-8")

    rd = out / "Report" / "definition"
    # report.json has no pageOrder (schema 3.2.0 format)
    rd.mkdir(parents=True)
    (rd / "report.json").write_text(json.dumps({"$schema": "...report/3.2.0/..."}), encoding="utf-8")

    pages_dir = rd / "pages"
    pages_dir.mkdir()
    # pages.json says ["p1", "ghost"] but only p1 exists on disk
    (pages_dir / "pages.json").write_text(
        json.dumps({"pageOrder": ["p1", "ghost_page"], "activePageName": "p1"}),
        encoding="utf-8"
    )
    (pages_dir / "p1").mkdir()
    (pages_dir / "p1" / "page.json").write_text(json.dumps({"name": "p1"}), encoding="utf-8")

    r = run_structural(out)
    codes = {f.code for f in r.findings}
    assert "report.page_order_mismatch" in codes
```

- [x] **Step 2: Run test to verify it fails**

```
pytest tests/unit/validate/test_structural.py::test_fails_when_pages_json_order_disagrees_with_disk -v
```

Expected: FAIL — validator reads `report.json["pageOrder"]` which is `[]`, so it never detects the mismatch.

- [x] **Step 3: Fix `src/tableau2pbir/validate/structural.py`**

Replace the page-order check block (lines 64–74) with:

```python
    # Page-order check — reads pages/pages.json (schema 3.2.0 format).
    pages_manifest = rd / "pages" / "pages.json"
    if pages_manifest.is_file():
        order = json.loads(pages_manifest.read_text(encoding="utf-8")).get("pageOrder", [])
        disk_pages = {p.name for p in pages_dir.iterdir() if p.is_dir()} if pages_dir.is_dir() else set()
        if set(order) != disk_pages:
            findings.append(StructuralFinding(
                code="report.page_order_mismatch", severity="error",
                message=f"pageOrder {order!r} != on-disk pages {sorted(disk_pages)!r}",
                location="Report/definition/pages/pages.json",
            ))
```

- [ ] **Step 4: Update the existing scaffold helper and old page-order test**

In `tests/unit/validate/test_structural.py`, update `_scaffold` to write `pages.json` instead of embedding `pageOrder` in `report.json`:

```python
def _scaffold(tmp_path: Path, *, pages: list[str], visuals: dict[str, list[tuple[str, list[str]]]],
              tables: dict[str, list[str]], page_order: list[str] | None = None,
              relationships: list[tuple[str, str]] = ()) -> Path:
    out = tmp_path
    sm = out / "SemanticModel" / "definition"
    (sm / "tables").mkdir(parents=True)
    for tname, fields in tables.items():
        body = "\n".join([f"table {tname}"] + [f"\tmeasure {f} = 1" for f in fields])
        (sm / "tables" / f"{tname}.tmdl").write_text(body, encoding="utf-8")
    (sm / "relationships").mkdir()
    for i, (a, b) in enumerate(relationships):
        (sm / "relationships" / f"r{i}.tmdl").write_text(
            f"relationship r{i}\n\tfromTable: {a}\n\ttoTable: {b}\n", encoding="utf-8")

    rd = out / "Report" / "definition"
    rd.mkdir(parents=True)
    # schema 3.2.0: report.json has no pageOrder
    (rd / "report.json").write_text(json.dumps({"$schema": "...report/3.2.0/..."}), encoding="utf-8")

    pages_dir = rd / "pages"
    pages_dir.mkdir()
    effective_order = page_order if page_order is not None else pages
    (pages_dir / "pages.json").write_text(
        json.dumps({"pageOrder": effective_order, "activePageName": effective_order[0] if effective_order else ""}),
        encoding="utf-8"
    )
    for p in pages:
        pdir = pages_dir / p
        pdir.mkdir(exist_ok=True)
        (pdir / "page.json").write_text(json.dumps({"name": p}), encoding="utf-8")
        for vid, refs in visuals.get(p, []):
            vdir = pdir / "visuals" / vid
            vdir.mkdir(parents=True, exist_ok=True)
            (vdir / "visual.json").write_text(json.dumps({
                "name": vid, "fieldRefs": refs,
            }), encoding="utf-8")
    return out
```

Also update `test_fails_when_page_order_disagrees_with_disk` to use the new scaffold (it already uses `page_order=["p1", "ghost_page"]` which now flows to `pages.json`).

- [x] **Step 4: Update the existing scaffold helper and old page-order test**

- [x] **Step 5: Run all structural tests to verify they pass**

```
pytest tests/unit/validate/test_structural.py -v
```

Expected: all PASS.

- [x] **Step 6: Commit**

```
git add src/tableau2pbir/validate/structural.py tests/unit/validate/test_structural.py
git commit -m "fix(validate): structural page-order check reads pages/pages.json"
```

---

## Task 9: Fix calculation names — use `caption` attribute, not internal ID

**Files:**
- Modify: `src/tableau2pbir/extract/datasources.py`
- Modify: `src/tableau2pbir/stages/_build_data_model.py`
- Test: `tests/unit/stages/test_s02_datasources.py`

Every Tableau `<column>` element has two attributes: `name` (machine ID like `[Calculation_0390937790091264]`) and `caption` (user-defined name like `DeltaOrder`). The current code reads only `name`. The fix: capture `caption` in extraction and prefer it when building `Calculation.name`.

- [x] **Step 1: Write failing test**

Add to `tests/unit/stages/test_s02_datasources.py`:

```python
from lxml import etree
from tableau2pbir.extract.datasources import extract_datasources


def test_calculation_uses_caption_as_name():
    xml = b"""<workbook>
      <datasources>
        <datasource name="DS">
          <connection class="postgres" server="localhost" dbname="sales" />
          <column caption="DeltaOrder" datatype="integer"
                  name="[Calculation_0390937790091264]" role="measure" type="quantitative">
            <calculation class="tableau" formula="COUNTD([order_id]) - COUNTD([order_id (returns)])" />
          </column>
        </datasource>
      </datasources>
    </workbook>"""
    root = etree.fromstring(xml)
    result = extract_datasources(root)
    assert len(result) == 1
    calcs = result[0]["calculations"]
    assert len(calcs) == 1
    assert calcs[0]["caption"] == "DeltaOrder", "caption attribute must be captured"
    assert calcs[0]["host_column_name"] == "Calculation_0390937790091264"


def test_calculation_falls_back_to_internal_name_when_no_caption():
    xml = b"""<workbook>
      <datasources>
        <datasource name="DS">
          <connection class="postgres" server="localhost" dbname="sales" />
          <column datatype="integer" name="[MyCalc]" role="measure" type="quantitative">
            <calculation class="tableau" formula="SUM([x])" />
          </column>
        </datasource>
      </datasources>
    </workbook>"""
    root = etree.fromstring(xml)
    result = extract_datasources(root)
    calcs = result[0]["calculations"]
    assert calcs[0].get("caption") is None
    assert calcs[0]["host_column_name"] == "MyCalc"
```

- [x] **Step 2: Run tests to verify they fail**

```
pytest tests/unit/stages/test_s02_datasources.py::test_calculation_uses_caption_as_name tests/unit/stages/test_s02_datasources.py::test_calculation_falls_back_to_internal_name_when_no_caption -v
```

Expected: FAIL — `calcs[0]` has no `"caption"` key.

- [x] **Step 3: Fix `src/tableau2pbir/extract/datasources.py`**

In `_columns_and_calculations`, add caption extraction. Change the calc append block (lines 119–126) from:

```python
        calc = col.find("calculation")
        if calc is not None:
            calcs.append({
                "host_column_name": name,
                "tableau_expr": attr(calc, "formula"),
                "datatype": datatype,
                "role": role,
            })
```

to:

```python
        caption = optional_attr(col, "caption")
        calc = col.find("calculation")
        if calc is not None:
            calcs.append({
                "host_column_name": name,
                "caption": caption,
                "tableau_expr": attr(calc, "formula"),
                "datatype": datatype,
                "role": role,
            })
```

Also update the module docstring comment on line 17 from:
```
  "calculations": [ {"host_column_name", "tableau_expr", "datatype", "role"} ],
```
to:
```
  "calculations": [ {"host_column_name", "caption", "tableau_expr", "datatype", "role"} ],
```

- [x] **Step 4: Fix `src/tableau2pbir/stages/_build_data_model.py`**

Change line 302 from:
```python
            name=raw_calc["host_column_name"],
```
to:
```python
            name=raw_calc.get("caption") or raw_calc["host_column_name"],
```

- [x] **Step 5: Run tests to verify they pass**

```
pytest tests/unit/stages/test_s02_datasources.py -v
```

Expected: all PASS.

- [x] **Step 6: Commit**

```
git add src/tableau2pbir/extract/datasources.py src/tableau2pbir/stages/_build_data_model.py tests/unit/stages/test_s02_datasources.py
git commit -m "fix(extract): use caption attribute as calculation name instead of internal ID"
```

---

## Task 10: Fix compound aggregate formula translation

**Files:**
- Modify: `src/tableau2pbir/translate/rules/aggregate.py`
- Test: `tests/unit/translate/rules/test_aggregate.py`

`_OUTER_RE` only matches single-aggregate calls (`SUM(x)`). Compound expressions like `COUNTD([order_id]) - COUNTD([order_id (returns)])` return `None`, falling through to the AI which produces broken DAX (`COUNTD` is not valid DAX). The fix: add a compound path that substitutes each aggregate term individually and verifies only arithmetic operators remain between them.

- [ ] **Step 1: Write failing tests**

Add to `tests/unit/translate/rules/test_aggregate.py`:

```python
def test_compound_subtraction_two_countd():
    out = translate_aggregate("COUNTD([order_id]) - COUNTD([order_id (returns)])")
    assert out == "DISTINCTCOUNT([order_id]) - DISTINCTCOUNT([order_id (returns)])", \
        f"COUNTD must become DISTINCTCOUNT in compound expr, got: {out}"


def test_compound_subtraction_two_sum():
    out = translate_aggregate("SUM([profit]) - sum([discount])")
    assert out == "SUM([profit]) - SUM([discount])", \
        f"lowercase sum must be normalised in compound expr, got: {out}"


def test_compound_addition():
    out = translate_aggregate("SUM([a]) + AVG([b])")
    assert out == "SUM([a]) + AVERAGE([b])"


def test_lowercase_single_sum():
    assert translate_aggregate("sum([Sales])") == "SUM([Sales])"


def test_compound_non_agg_returns_none():
    assert translate_aggregate("COUNTD([x]) - [plain_field]") is None
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/unit/translate/rules/test_aggregate.py -v
```

Expected: the four new tests FAIL; existing tests still PASS.

- [ ] **Step 3: Rewrite `src/tableau2pbir/translate/rules/aggregate.py`**

```python
"""Aggregate-calc rules. Returns DAX or None on no match."""
from __future__ import annotations

import re

_AGG_RENAMES = {
    "AVG": "AVERAGE",
    "COUNTD": "DISTINCTCOUNT",
}

_OUTER_RE = re.compile(
    r"^(?P<fn>SUM|AVG|COUNT|COUNTD|MIN|MAX)\s*\((?P<arg>.*)\)\s*$",
    re.DOTALL | re.IGNORECASE,
)
_COND_INNER_RE = re.compile(
    r"^IF\s+(?P<cond>.+?)\s+THEN\s+(?P<then>.+?)\s+END$",
    re.DOTALL,
)
# Matches one aggregate term with no nested parens — used for compound detection.
_TERM_RE = re.compile(
    r"(?P<fn>SUM|AVG|COUNT|COUNTD|MIN|MAX)\s*\((?P<arg>[^()]+)\)",
    re.IGNORECASE,
)


def _translate_single(fn: str, arg: str) -> str:
    dax_fn = _AGG_RENAMES.get(fn.upper(), fn.upper())
    arg = arg.strip()
    cond = _COND_INNER_RE.match(arg)
    if cond:
        inner = cond.group("then").strip()
        predicate = cond.group("cond").strip()
        return f"CALCULATE({dax_fn}({inner}), FILTER(ALLSELECTED(), {predicate}))"
    return f"{dax_fn}({arg})"


def translate_aggregate(tableau_expr: str) -> str | None:
    expr = tableau_expr.strip()

    # Fast path: single aggregate call.
    m = _OUTER_RE.match(expr)
    if m:
        return _translate_single(m.group("fn"), m.group("arg"))

    # Compound path: arithmetic of single aggregate calls, e.g. SUM(x) - SUM(y).
    # Replace each AGG(arg) term with a placeholder, verify only arithmetic operators
    # remain between placeholders, then substitute with translated DAX.
    check = _TERM_RE.sub("X", expr)
    if re.fullmatch(r"X(\s*[+\-*/]\s*X)+", check.strip()):
        return _TERM_RE.sub(
            lambda mo: _translate_single(mo.group("fn"), mo.group("arg")),
            expr,
        )

    return None
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/unit/translate/rules/test_aggregate.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```
git add src/tableau2pbir/translate/rules/aggregate.py tests/unit/translate/rules/test_aggregate.py
git commit -m "fix(translate): compound aggregate expressions translate correctly; COUNTD→DISTINCTCOUNT"
```

---

## Task 11: E2E verification — full pipeline run + output structure check

**Files:**
- No code changes — verification only.

Run the complete pipeline against `simple_join.twb` and verify the output matches the MVP file structure.

- [ ] **Step 1: Delete stale output to start clean**

```powershell
Remove-Item -Recurse -Force out\simple_join -ErrorAction SilentlyContinue
```

- [ ] **Step 2: Run the full pipeline**

```
python -m tableau2pbir.cli convert "tests/golden/real/simple_join.twb"
```

Expected: no Python exceptions, `out/simple_join/` created.

- [ ] **Step 3: Verify required PBIR files exist**

```powershell
$base = "out\simple_join"
$required = @(
    "Report\definition\report.json",
    "Report\definition\version.json",
    "Report\definition\pages\pages.json",
    "Report\definition.pbir",
    "SemanticModel\definition\database.tmdl",
    "SemanticModel\definition\model.tmdl",
    "SemanticModel\definition\relationships.tmdl"
)
foreach ($f in $required) {
    $p = Join-Path $base $f
    if (Test-Path $p) { Write-Host "OK  $f" } else { Write-Host "MISSING  $f" }
}
```

Expected: all lines show `OK`.

- [ ] **Step 4: Verify schema versions in output files**

```powershell
$base = "out\simple_join"
$reportJson = Get-Content "$base\Report\definition\report.json" | ConvertFrom-Json
Write-Host "report.json schema: $($reportJson.'$schema')"

$versionJson = Get-Content "$base\Report\definition\version.json" | ConvertFrom-Json
Write-Host "version.json version: $($versionJson.version)"

$pagesJson = Get-Content "$base\Report\definition\pages\pages.json" | ConvertFrom-Json
Write-Host "pages.json pageOrder count: $($pagesJson.pageOrder.Count)"

$defPbir = Get-Content "$base\Report\definition.pbir" | ConvertFrom-Json
Write-Host "definition.pbir keys: $(($defPbir | Get-Member -MemberType NoteProperty).Name -join ', ')"
```

Expected output:
```
report.json schema: https://...report/3.2.0/schema.json
version.json version: 2.0.0
pages.json pageOrder count: <N >= 1>
definition.pbir keys: datasetReference, version
```

- [ ] **Step 5: Verify at least one page folder and visual exist**

```powershell
$pagesDir = "out\simple_join\Report\definition\pages"
$pageFolders = Get-ChildItem $pagesDir -Directory
Write-Host "Page folders: $($pageFolders.Count)"
foreach ($p in $pageFolders) {
    $visuals = Get-ChildItem "$($p.FullName)\visuals" -Directory -ErrorAction SilentlyContinue
    Write-Host "  Page $($p.Name): $($visuals.Count) visual(s)"
    if ($visuals.Count -gt 0) {
        $vJson = Get-Content "$($visuals[0].FullName)\visual.json" | ConvertFrom-Json
        Write-Host "    visual schema: $($vJson.'$schema')"
    }
}
```

Expected: at least 1 page folder, at least 1 visual, schema contains `1.0.0`.

- [ ] **Step 6: Verify partition mode in TMDL tables**

```powershell
Get-ChildItem "out\simple_join\SemanticModel\definition\tables\*.tmdl" |
    ForEach-Object {
        $content = Get-Content $_.FullName -Raw
        $mode = if ($content -match "mode: (\w+)") { $matches[1] } else { "NOT FOUND" }
        Write-Host "$($_.Name): mode = $mode"
    }
```

Expected: postgres-backed tables show `directQuery`.

- [ ] **Step 7: Run the full unit + integration suite**

```
pytest tests/unit/ -v --tb=short 2>&1 | tail -20
pytest tests/integration/ -m integration -v --tb=short 2>&1 | tail -20
```

Expected: unit suite passes, integration E2E smoke test passes (or skips if no API key).

- [ ] **Step 8: Final commit**

```
git add -A
git commit -m "fix(e2e): verify PBIR output matches working format after all schema fixes"
```

---

## Self-Review Checklist

**Spec coverage:**
- ✅ report.json schema 3.2.0 — Task 1
- ✅ pages/pages.json manifest — Task 2
- ✅ version.json "2.0.0" — Task 2
- ✅ page.json schema 2.1.0 — Task 3
- ✅ visualContainer schema 1.0.0 — Task 4
- ✅ definition.pbir no $schema/byConnection — Task 5
- ✅ partition mode directQuery for DB — Task 6
- ✅ structural validator page-order bug — Task 7
- ✅ calculation names use caption not internal ID — Task 9
- ✅ compound aggregate formulas translate correctly — Task 10
- ✅ E2E verification — Task 11

**Placeholder scan:** No TBDs, no "similar to Task N" references. All code shown inline.

**Type consistency:**
- `render_report()` now takes 0 args (Tasks 1 + 2 are consistent)
- `render_pages_manifest(page_order: list[str])` used consistently in Tasks 1 and 2
- `_partition_mode(datasource: Datasource) -> str` used only in Task 6
- Structural validator changes in Tasks 7 use `pages_manifest.is_file()` guard consistently
