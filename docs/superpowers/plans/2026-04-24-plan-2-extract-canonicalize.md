# Plan 2 — Stage 1 (extract) + Stage 2 (canonicalize → IR)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Plan-1 no-op stubs for stages 1 and 2 with real v1 implementations. End state: `tableau2pbir convert tests/golden/synthetic/<fixture>.twb --out ./out/` produces a real `01_extract.json` (raw structured dump of Tableau XML) and `02_ir.json` (validates against the committed IR JSON Schema, v1-scope objects populated), then the remaining stages 3–8 still run as no-op stubs. The full pytest suite stays green; `make schema` diff stays empty; Plan-1 golden paths still work.

**Architecture:** Stage 1 is a pure-Python walker over the Tableau `<workbook>` XML tree (lxml + `tableaudocumentapi` where in coverage). It emits a raw, JSON-serializable dict whose keys mirror the XML sections (datasources, parameters, worksheets, dashboards, actions, unsupported, plus `source_path` / `source_hash` / `tableau_version`). Stage 2 reads that raw dict, runs three deterministic classifiers — `connector_tier` (§5.8), `calc_kind` (§5.6), `parameter_intent` (§5.7) — maps everything to the pydantic IR from Plan 1, builds the calc `depends_on` graph, detects cycles, and routes any v1-deferred object (Tier 3 connector / non-row-aggregate-lod_fixed calc kinds / formatting_control parameters / quick-table-calc pill modifiers) to `Workbook.unsupported[]` with a stable `deferred_feature_*` code — per §16 "flags gate execution, not detection".

**Tech stack:** Python 3.11+, lxml, tableaudocumentapi (where in coverage), pydantic v2 (IR from Plan 1), stdlib `zipfile`, `hashlib`, `pathlib`, `re`. No new runtime dependencies.

**Spec reference:** `C:\Tableau_PBI\docs\superpowers\specs\2026-04-23-tableau-to-pbir-design.md`. Primary sections: §5 (IR), §5.6 (Calculation), §5.7 (Parameter), §5.8 (Connector matrix), §6 Stages 1–2, §16 (v1 scope + deferred-feature codes).

**Plan-1 outputs this plan builds on (do NOT re-create):**
- `src/tableau2pbir/ir/*.py` — pydantic IR models (Workbook, DataModel, Datasource, Table, Column, Relationship, Calculation + sub-records, Parameter + sub-records, Sheet, Dashboard + Action + Leaf + Container, UnsupportedItem).
- `src/tableau2pbir/ir/schema.py` + `schemas/ir-v1.0.0.schema.json` — JSON Schema autogen + committed artifact.
- `src/tableau2pbir/pipeline.py` — `StageResult`, `StageError`, `StageContext`, `run_pipeline`, `STAGE_SEQUENCE`.
- `src/tableau2pbir/stages/s01_extract.py` + `s02_canonicalize.py` — no-op stubs; this plan rewrites them.
- `tests/conftest.py`, `pytest.ini` with feature-flag markers.
- `tests/golden/synthetic/trivial.twb` — CSV + 1 sheet + 1 dashboard.

**Out of scope for Plan 2 (deferred to Plans 3–5):**
- Stage 3 (translate calcs), Stage 4 (map visuals), Stages 5–8 — remain no-op stubs.
- LLM calls — LLMClient methods still raise `NotImplementedError`.
- Writing per-sheet anonymous `Calculation` records for quick-table-calc expansion — quick-table-calc pill modifiers are *detected* in Stage 1 and *routed to unsupported[]* in Stage 2 with code `deferred_feature_table_calcs`; the per-sheet expansion itself ships with `--with-table-calcs` in Plan 3 / v1.1.
- Tier-3 connector strategies (cross-DB joins, blends, custom SQL, initial SQL) — classified as `deferred_feature_tier3` in Stage 2.
- `formatting_control` parameter switch-pattern detection — classified as `deferred_feature_format_switch` in Stage 2.
- Real-workbook rubric evaluation, Desktop-open gate, TMDL / PBIR emission, status rule — Plans 4–5.

**v1 scope per §16 — this plan's detection-vs-execution rule:** Stage 2 **classifies every object** regardless of flag state (§16 last paragraph). Objects whose *classification* falls outside v1 are still represented (kind/intent/tier filled in) but additionally get an `UnsupportedItem` appended to `Workbook.unsupported[]` with `code = "deferred_feature_<name>"`. §8.1 (Plan 4) reads those codes to compute workbook status. This plan does NOT implement the §8.1 rule yet; it just produces the inputs.

---

## File structure (Plan 2)

**Create (new files):**

```
C:\Tableau_PBI\
├── src/tableau2pbir/
│   ├── util/
│   │   ├── zip.py                        # .twb/.twbx reader + source_hash
│   │   ├── xml.py                        # lxml attr/text helpers
│   │   └── ids.py                        # deterministic id generation
│   ├── extract/
│   │   ├── __init__.py
│   │   ├── datasources.py                # raw datasource + connection + columns + calcs
│   │   ├── parameters.py                 # special <datasource name='Parameters'>
│   │   ├── worksheets.py                 # encodings, filters, sort, marks, table-calc metadata
│   │   ├── dashboards.py                 # zones tree, tiled vs floating
│   │   ├── actions.py                    # filter / highlight / url / parameter actions
│   │   └── tier_c_detect.py              # story points / R / Python / custom shapes / forecast / annotations / web-page
│   └── classify/
│       ├── __init__.py
│       ├── connector_tier.py             # §5.8 matrix
│       ├── calc_kind.py                  # §5.6 kind+phase discrimination
│       └── parameter_intent.py           # §5.7 intent table
├── tests/
│   ├── unit/
│   │   ├── util/
│   │   │   ├── __init__.py
│   │   │   ├── test_zip.py
│   │   │   ├── test_xml.py
│   │   │   └── test_ids.py
│   │   ├── extract/
│   │   │   ├── __init__.py
│   │   │   ├── test_datasources.py
│   │   │   ├── test_parameters.py
│   │   │   ├── test_worksheets.py
│   │   │   ├── test_dashboards.py
│   │   │   ├── test_actions.py
│   │   │   └── test_tier_c_detect.py
│   │   ├── classify/
│   │   │   ├── __init__.py
│   │   │   ├── test_connector_tier.py
│   │   │   ├── test_calc_kind.py
│   │   │   └── test_parameter_intent.py
│   │   └── stages/
│   │       ├── test_s01_extract.py       # replaces stub contract coverage
│   │       └── test_s02_canonicalize.py
│   ├── contract/
│   │   └── test_stage2_ir_contract.py    # 02_ir.json validates against ir-v1.0.0.schema.json
│   ├── integration/
│   │   └── test_stage1_stage2_integration.py
│   └── golden/synthetic/
│       ├── datasources_mixed.twb         # CSV + SQL Server + Snowflake + hyper(with upstream)
│       ├── datasource_hyper_orphan.twb   # hyper with null <connection> → Tier 4
│       ├── calc_row.twb                  # row calc
│       ├── calc_aggregate.twb            # aggregate calc
│       ├── calc_lod_fixed.twb            # FIXED LOD
│       ├── calc_lod_include.twb          # INCLUDE → deferred_feature_lod_relative
│       ├── calc_quick_table.twb          # pill-modifier table calc → deferred_feature_table_calcs
│       ├── params_all_intents.twb        # 4 parameters, one per intent
│       ├── dashboard_tiled_floating.twb  # both layout types in one dashboard
│       └── action_filter.twb             # filter + highlight actions
```

**Modify (Plan-1 files):**
- `src/tableau2pbir/stages/s01_extract.py` — replace stub with real implementation wiring the `extract/*` helpers.
- `src/tableau2pbir/stages/s02_canonicalize.py` — replace stub with real implementation wiring IR + classifiers.
- `tests/unit/stages/test_all_stages_stub.py` — no change needed; the parametrized contract still passes for stages 1 and 2 because they still return `StageResult`.

**Do NOT touch:**
- Anything under `src/tableau2pbir/ir/` (use as-is).
- `schemas/ir-v1.0.0.schema.json` (do not regenerate in Plan 2; fields on IR types don't change).
- `src/tableau2pbir/llm/`, `src/tableau2pbir/cli.py`, `src/tableau2pbir/pipeline.py`.
- Stages 3–8 stubs.

---

## Pre-Task: verify Plan-1 green baseline

Before starting, confirm nothing from Plan 1 is broken:

```bash
cd C:/Tableau_PBI
source .venv/Scripts/activate
pytest -q
make lint
make typecheck
make schema   # should produce no diff
git diff --stat schemas/
```

Expected: pytest green, lint clean, typecheck clean on `src/`, `schemas/` diff empty. If anything is red, fix before starting Plan 2.

---

## Task 1: `util/zip.py` — open `.twb` / `.twbx` and hash source

**Files:**
- Create: `src/tableau2pbir/util/__init__.py` (empty — Plan-1 file if present, otherwise create)
- Create: `src/tableau2pbir/util/zip.py`
- Create: `tests/unit/util/__init__.py` (empty)
- Create: `tests/unit/util/test_zip.py`

- [x] **Step 1.1: Write failing test**

`tests/unit/util/test_zip.py`:

```python
"""Unit tests for util/zip — workbook reader + source hash."""
from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from tableau2pbir.util.zip import WorkbookBytes, read_workbook


def _write_twb(path: Path, xml: str) -> Path:
    path.write_text(xml, encoding="utf-8")
    return path


def _write_twbx(path: Path, xml: str, extras: dict[str, bytes] | None = None) -> Path:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("workbook.twb", xml.encode("utf-8"))
        for name, data in (extras or {}).items():
            z.writestr(name, data)
    return path


_TWB_XML = "<?xml version='1.0'?>\n<workbook version='18.1'></workbook>\n"


def test_read_workbook_twb(tmp_path: Path):
    src = _write_twb(tmp_path / "simple.twb", _TWB_XML)
    result = read_workbook(src)
    assert isinstance(result, WorkbookBytes)
    assert result.xml_bytes.startswith(b"<?xml")
    assert result.source_path == str(src.resolve())
    assert len(result.source_hash) == 64   # sha256 hex


def test_read_workbook_twbx(tmp_path: Path):
    src = _write_twbx(tmp_path / "packaged.twbx", _TWB_XML,
                      extras={"Data/sample.csv": b"id,amount\n1,10\n"})
    result = read_workbook(src)
    assert b"<workbook" in result.xml_bytes


def test_read_workbook_twbx_missing_twb(tmp_path: Path):
    src = tmp_path / "empty.twbx"
    with zipfile.ZipFile(src, "w"):
        pass
    with pytest.raises(ValueError, match="no .twb entry"):
        read_workbook(src)


def test_source_hash_is_stable_across_reads(tmp_path: Path):
    src = _write_twb(tmp_path / "stable.twb", _TWB_XML)
    first = read_workbook(src).source_hash
    second = read_workbook(src).source_hash
    assert first == second


def test_source_hash_differs_across_files(tmp_path: Path):
    a = _write_twb(tmp_path / "a.twb", _TWB_XML)
    b = _write_twb(tmp_path / "b.twb", _TWB_XML + "<!-- differ -->\n")
    assert read_workbook(a).source_hash != read_workbook(b).source_hash


def test_read_workbook_unknown_extension(tmp_path: Path):
    src = tmp_path / "bogus.xlsx"
    src.write_bytes(b"not a workbook")
    with pytest.raises(ValueError, match="extension"):
        read_workbook(src)
```

- [x] **Step 1.2: Run test — verify failure**

```bash
pytest tests/unit/util/test_zip.py -v
```
Expected: `ModuleNotFoundError: No module named 'tableau2pbir.util.zip'` (or `no attribute 'read_workbook'` if the package already exists from Plan 1).

- [x] **Step 1.3: Write `src/tableau2pbir/util/__init__.py`** (if it doesn't already exist from Plan 1, make it empty; otherwise leave it alone).

- [x] **Step 1.4: Write `src/tableau2pbir/util/zip.py`**

```python
"""Workbook reader — loads XML bytes from .twb or .twbx, computes sha256
of the *raw file bytes on disk* so the hash is stable and cheap.

A `.twbx` is a zip archive containing exactly one `.twb` entry plus data
files (csv, hyper, images). The `.twb` entry path varies by Tableau
version; we pick the first entry ending in `.twb`."""
from __future__ import annotations

import hashlib
import zipfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WorkbookBytes:
    xml_bytes: bytes
    source_path: str     # absolute path string
    source_hash: str     # sha256 hex of the on-disk file (not of xml_bytes)


def _sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_workbook(path: Path) -> WorkbookBytes:
    """Open a .twb or .twbx and return its XML bytes + a content hash."""
    resolved = path.resolve()
    suffix = resolved.suffix.lower()
    source_hash = _sha256_of_file(resolved)

    if suffix == ".twb":
        xml_bytes = resolved.read_bytes()
    elif suffix == ".twbx":
        with zipfile.ZipFile(resolved) as z:
            twb_names = [n for n in z.namelist() if n.lower().endswith(".twb")]
            if not twb_names:
                raise ValueError(f"no .twb entry in {resolved}")
            xml_bytes = z.read(twb_names[0])
    else:
        raise ValueError(f"unsupported workbook extension: {suffix!r}")

    return WorkbookBytes(
        xml_bytes=xml_bytes,
        source_path=str(resolved),
        source_hash=source_hash,
    )
```

- [x] **Step 1.5: Run test — verify pass**

```bash
pytest tests/unit/util/test_zip.py -v
```
Expected: `6 passed`.

- [x] **Step 1.6: Commit**

```bash
git add src/tableau2pbir/util/__init__.py src/tableau2pbir/util/zip.py \
        tests/unit/util/__init__.py tests/unit/util/test_zip.py
git commit -m "feat(util): add workbook reader (.twb/.twbx) with source sha256"
```

---

## Task 2: `util/xml.py` — lxml attribute/text helpers

**Files:**
- Create: `src/tableau2pbir/util/xml.py`
- Create: `tests/unit/util/test_xml.py`

- [x] **Step 2.1: Write failing test**

`tests/unit/util/test_xml.py`:

```python
from __future__ import annotations

from lxml import etree

from tableau2pbir.util.xml import (
    attr,
    child_text,
    iter_children,
    optional_attr,
    parse_workbook_xml,
    require_attr,
)


_XML = b"""<?xml version='1.0'?>
<workbook version='18.1'>
  <datasources>
    <datasource name='Sales' caption='Sales DB'>
      <connection class='sqlserver' server='sql1'/>
    </datasource>
  </datasources>
</workbook>
"""


def test_parse_workbook_xml_returns_root():
    root = parse_workbook_xml(_XML)
    assert root.tag == "workbook"


def test_attr_returns_string_or_default():
    root = parse_workbook_xml(_XML)
    ds = root.find(".//datasource")
    assert attr(ds, "name") == "Sales"
    assert attr(ds, "missing", default="fallback") == "fallback"


def test_optional_attr_returns_none_when_missing():
    root = parse_workbook_xml(_XML)
    ds = root.find(".//datasource")
    assert optional_attr(ds, "caption") == "Sales DB"
    assert optional_attr(ds, "nope") is None


def test_require_attr_raises_when_missing():
    root = parse_workbook_xml(_XML)
    ds = root.find(".//datasource")
    import pytest
    with pytest.raises(ValueError, match="missing attribute"):
        require_attr(ds, "nope")


def test_child_text_handles_missing():
    root = parse_workbook_xml(b"<x><a>hi</a></x>")
    assert child_text(root, "a") == "hi"
    assert child_text(root, "b") is None


def test_iter_children_by_tag():
    root = parse_workbook_xml(b"<x><a/><b/><a/></x>")
    assert [c.tag for c in iter_children(root, "a")] == ["a", "a"]
```

- [x] **Step 2.2: Run test — verify failure**

```bash
pytest tests/unit/util/test_xml.py -v
```
Expected: `ModuleNotFoundError`.

- [x] **Step 2.3: Write `src/tableau2pbir/util/xml.py`**

```python
"""lxml helpers. All extract modules funnel through these so attribute-missing
errors raise uniformly and tests can monkey-patch parsing behavior once."""
from __future__ import annotations

from collections.abc import Iterator

from lxml import etree


def parse_workbook_xml(xml_bytes: bytes) -> etree._Element:
    """Parse workbook XML. Raises `etree.XMLSyntaxError` on malformed input."""
    parser = etree.XMLParser(remove_blank_text=False, recover=False)
    return etree.fromstring(xml_bytes, parser=parser)


def attr(elem: etree._Element, name: str, default: str = "") -> str:
    value = elem.get(name)
    return value if value is not None else default


def optional_attr(elem: etree._Element, name: str) -> str | None:
    return elem.get(name)


def require_attr(elem: etree._Element, name: str) -> str:
    value = elem.get(name)
    if value is None:
        raise ValueError(f"<{elem.tag}> missing attribute {name!r}")
    return value


def child_text(elem: etree._Element, tag: str) -> str | None:
    child = elem.find(tag)
    return child.text if child is not None else None


def iter_children(elem: etree._Element, tag: str) -> Iterator[etree._Element]:
    return iter(elem.findall(tag))
```

- [x] **Step 2.4: Run test — verify pass**

```bash
pytest tests/unit/util/test_xml.py -v
```
Expected: `6 passed`.

- [x] **Step 2.5: Commit**

```bash
git add src/tableau2pbir/util/xml.py tests/unit/util/test_xml.py
git commit -m "feat(util): add lxml attr/text helpers used by all extract modules"
```

---

## Task 3: `util/ids.py` — deterministic id generation

**Files:**
- Create: `src/tableau2pbir/util/ids.py`
- Create: `tests/unit/util/test_ids.py`

- [x] **Step 3.1: Write failing test**

`tests/unit/util/test_ids.py`:

```python
from __future__ import annotations

from tableau2pbir.util.ids import slug_id, stable_id


def test_slug_id_lowercases_and_replaces_unsafe_chars():
    assert slug_id("Sales By Region") == "sales_by_region"
    assert slug_id("[Profit Margin %]") == "profit_margin_pct"
    assert slug_id("Column 1") == "column_1"


def test_slug_id_collapses_runs_of_underscores():
    assert slug_id("a  b__c") == "a_b_c"


def test_slug_id_strips_leading_trailing_underscores():
    assert slug_id("__x__") == "x"


def test_slug_id_falls_back_to_hash_when_all_stripped():
    result = slug_id("$$$")
    assert result.startswith("id_")
    assert len(result) > 3


def test_stable_id_is_deterministic():
    assert stable_id("calc", "Profit") == stable_id("calc", "Profit")
    assert stable_id("calc", "Profit") != stable_id("calc", "Revenue")


def test_stable_id_prefixes_with_kind():
    result = stable_id("sheet", "Revenue Overview")
    assert result.startswith("sheet__")
```

- [x] **Step 3.2: Run test — verify failure**

```bash
pytest tests/unit/util/test_ids.py -v
```
Expected: `ModuleNotFoundError`.

- [x] **Step 3.3: Write `src/tableau2pbir/util/ids.py`**

```python
"""Deterministic id generation. Stage 1 uses Tableau internal names where
available; Stage 2 backfills with `stable_id(kind, name)` so ids remain
stable across re-runs of the same workbook."""
from __future__ import annotations

import hashlib
import re

_UNSAFE = re.compile(r"[^a-z0-9]+")
_UNDERSCORE_RUN = re.compile(r"_+")


def slug_id(raw: str) -> str:
    """Lowercase, non-alnum → underscore, collapse runs, strip ends.
    Falls back to `id_<hash8>` if nothing usable remains."""
    lowered = raw.lower().replace("%", "_pct_")
    sub = _UNSAFE.sub("_", lowered)
    sub = _UNDERSCORE_RUN.sub("_", sub).strip("_")
    if not sub:
        h = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:8]
        return f"id_{h}"
    return sub


def stable_id(kind: str, name: str) -> str:
    """Stable id for IR objects, prefixed with the kind for readability.
    `stable_id('calc', 'Profit Margin') -> 'calc__profit_margin'`."""
    return f"{kind}__{slug_id(name)}"
```

- [x] **Step 3.4: Run test — verify pass**

```bash
pytest tests/unit/util/test_ids.py -v
```
Expected: `6 passed`.

- [x] **Step 3.5: Commit**

```bash
git add src/tableau2pbir/util/ids.py tests/unit/util/test_ids.py
git commit -m "feat(util): add deterministic id generation (slug_id, stable_id)"
```

---

## Task 4: `extract/datasources.py` — raw datasource extraction

**Files:**
- Create: `src/tableau2pbir/extract/__init__.py` (empty)
- Create: `src/tableau2pbir/extract/datasources.py`
- Create: `tests/unit/extract/__init__.py` (empty)
- Create: `tests/unit/extract/test_datasources.py`

- [x] **Step 4.1: Write failing test**

`tests/unit/extract/test_datasources.py`:

```python
from __future__ import annotations

from tableau2pbir.extract.datasources import extract_datasources
from tableau2pbir.util.xml import parse_workbook_xml


_XML_CSV = b"""<?xml version='1.0'?>
<workbook>
  <datasources>
    <datasource caption='Sample' name='sample.csv' hasconnection='true'>
      <connection class='textscan' directory='.' filename='sample.csv' server=''/>
      <column datatype='integer' name='[id]' role='dimension' type='ordinal'/>
      <column datatype='integer' name='[amount]' role='measure' type='quantitative'/>
    </datasource>
  </datasources>
</workbook>
"""

_XML_WITH_CALC = b"""<?xml version='1.0'?>
<workbook>
  <datasources>
    <datasource caption='Orders' name='orders'>
      <connection class='sqlserver' server='sql1' dbname='Sales'/>
      <column datatype='real' name='[Revenue]' role='measure'/>
      <column datatype='real' name='[Profit Margin]' role='measure'>
        <calculation class='tableau' formula='SUM([Profit])/SUM([Revenue])'/>
      </column>
    </datasource>
  </datasources>
</workbook>
"""

_XML_HYPER_WITH_UPSTREAM = b"""<?xml version='1.0'?>
<workbook>
  <datasources>
    <datasource name='extract_ds'>
      <connection class='federated'>
        <named-connections>
          <named-connection name='upstream' caption='sql1'>
            <connection class='sqlserver' server='sql1' dbname='Sales'/>
          </named-connection>
        </named-connections>
        <extract enabled='true'>
          <connection class='hyper' dbname='Extract/extract.hyper'/>
        </extract>
      </connection>
    </datasource>
  </datasources>
</workbook>
"""


def test_single_csv_datasource():
    root = parse_workbook_xml(_XML_CSV)
    dss = extract_datasources(root)
    assert len(dss) == 1
    ds = dss[0]
    assert ds["name"] == "sample.csv"
    assert ds["caption"] == "Sample"
    assert ds["connection"]["class"] == "textscan"
    assert ds["extract"] is None
    assert len(ds["columns"]) == 2
    assert ds["columns"][0]["name"] == "id"       # [] stripped
    assert ds["columns"][0]["datatype"] == "integer"
    assert ds["columns"][0]["role"] == "dimension"
    assert ds["calculations"] == []


def test_calculated_column_promoted_to_calculations():
    root = parse_workbook_xml(_XML_WITH_CALC)
    ds = extract_datasources(root)[0]
    assert len(ds["columns"]) == 2           # raw column list still includes the calc's host column
    assert len(ds["calculations"]) == 1
    calc = ds["calculations"][0]
    assert calc["host_column_name"] == "Profit Margin"
    assert calc["tableau_expr"] == "SUM([Profit])/SUM([Revenue])"
    assert calc["datatype"] == "real"
    assert calc["role"] == "measure"


def test_hyper_extract_preserves_upstream_connection():
    root = parse_workbook_xml(_XML_HYPER_WITH_UPSTREAM)
    ds = extract_datasources(root)[0]
    assert ds["connection"]["class"] == "federated"
    assert ds["extract"] is not None
    assert ds["extract"]["connection"]["class"] == "hyper"
    # upstream named-connection must be preserved for connector_tier §5.8
    assert len(ds["named_connections"]) == 1
    upstream = ds["named_connections"][0]
    assert upstream["connection"]["class"] == "sqlserver"
    assert upstream["connection"]["server"] == "sql1"


def test_empty_workbook_returns_empty_list():
    root = parse_workbook_xml(b"<workbook><datasources/></workbook>")
    assert extract_datasources(root) == []


def test_parameters_datasource_skipped_here():
    # The special <datasource name='Parameters'> is handled by extract/parameters.py.
    xml = b"""<workbook><datasources>
      <datasource name='Parameters' hasconnection='false'><column name='[p1]'/></datasource>
      <datasource name='real_ds'><connection class='textscan'/></datasource>
    </datasources></workbook>"""
    root = parse_workbook_xml(xml)
    dss = extract_datasources(root)
    assert [d["name"] for d in dss] == ["real_ds"]
```

- [x] **Step 4.2: Run test — verify failure**

```bash
pytest tests/unit/extract/test_datasources.py -v
```
Expected: `ModuleNotFoundError: No module named 'tableau2pbir.extract.datasources'`.

- [x] **Step 4.3: Write `src/tableau2pbir/extract/__init__.py`** — empty file.

- [x] **Step 4.4: Write `src/tableau2pbir/extract/datasources.py`**

```python
"""Raw datasource extraction. Output is a list of JSON-serializable dicts
mirroring the XML structure; no classification or IR mapping here — that
lives in stage 2 (`classify/` + `s02_canonicalize.py`).

Structure per datasource:
{
  "name": str,
  "caption": str | None,
  "connection": {"class": str, **attrs},         # the outer <connection>
  "named_connections": [                         # preserves §5.8 upstream
      {"name": str, "caption": str | None,
       "connection": {"class": str, **attrs}},
      ...
  ],
  "extract": {"connection": {...}} | None,       # the <extract><connection/> if any
  "columns": [ {"name": str, "datatype": str, "role": str, "type": str | None} ],
  "calculations": [ {"host_column_name", "tableau_expr", "datatype", "role"} ],
}
"""
from __future__ import annotations

from typing import Any

from lxml import etree

from tableau2pbir.util.xml import attr, optional_attr


_RESERVED_DS_NAME = "Parameters"     # §5.7 — handled separately by extract/parameters.py


def _strip_brackets(s: str) -> str:
    if s.startswith("[") and s.endswith("]"):
        return s[1:-1]
    return s


def _connection_to_dict(conn: etree._Element) -> dict[str, Any]:
    out: dict[str, Any] = {"class": attr(conn, "class", default="unknown")}
    for k, v in conn.attrib.items():
        if k != "class":
            out[k] = v
    return out


def _extract_block(conn: etree._Element) -> dict[str, Any] | None:
    ex = conn.find("extract")
    if ex is None:
        return None
    inner = ex.find("connection")
    if inner is None:
        return {"connection": None}
    return {"connection": _connection_to_dict(inner)}


def _named_connections(conn: etree._Element) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for nc in conn.findall("named-connections/named-connection"):
        inner = nc.find("connection")
        out.append({
            "name": attr(nc, "name"),
            "caption": optional_attr(nc, "caption"),
            "connection": _connection_to_dict(inner) if inner is not None else None,
        })
    return out


def _columns_and_calculations(
    ds_elem: etree._Element,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cols: list[dict[str, Any]] = []
    calcs: list[dict[str, Any]] = []
    for col in ds_elem.findall("column"):
        name = _strip_brackets(attr(col, "name"))
        datatype = attr(col, "datatype", default="string")
        role = attr(col, "role", default="dimension")
        type_ = optional_attr(col, "type")
        cols.append({"name": name, "datatype": datatype, "role": role, "type": type_})
        calc = col.find("calculation")
        if calc is not None:
            calcs.append({
                "host_column_name": name,
                "tableau_expr": attr(calc, "formula"),
                "datatype": datatype,
                "role": role,
            })
    return cols, calcs


def extract_datasources(root: etree._Element) -> list[dict[str, Any]]:
    """Extract every `<datasource>` in the workbook except the reserved
    `Parameters` datasource (handled by extract/parameters.py)."""
    out: list[dict[str, Any]] = []
    for ds in root.findall("datasources/datasource"):
        name = attr(ds, "name")
        if name == _RESERVED_DS_NAME:
            continue
        conn = ds.find("connection")
        if conn is None:
            # Can happen for published datasources — preserve as-is with empty connection.
            conn_dict: dict[str, Any] = {"class": "unknown"}
            named: list[dict[str, Any]] = []
            extract: dict[str, Any] | None = None
        else:
            conn_dict = _connection_to_dict(conn)
            named = _named_connections(conn)
            extract = _extract_block(conn)
        cols, calcs = _columns_and_calculations(ds)
        out.append({
            "name": name,
            "caption": optional_attr(ds, "caption"),
            "connection": conn_dict,
            "named_connections": named,
            "extract": extract,
            "columns": cols,
            "calculations": calcs,
        })
    return out
```

- [x] **Step 4.5: Run test — verify pass**

```bash
pytest tests/unit/extract/test_datasources.py -v
```
Expected: `5 passed`.

- [x] **Step 4.6: Commit**

```bash
git add src/tableau2pbir/extract/__init__.py src/tableau2pbir/extract/datasources.py \
        tests/unit/extract/__init__.py tests/unit/extract/test_datasources.py
git commit -m "feat(extract): raw datasource/connection/extract/columns/calcs extraction"
```

---

## Task 5: `extract/parameters.py` — parameters datasource extraction

**Files:**
- Create: `src/tableau2pbir/extract/parameters.py`
- Create: `tests/unit/extract/test_parameters.py`

Tableau parameters live in a single `<datasource name='Parameters'>` with one `<column>` per parameter. Each parameter-column has:
- `param-domain-type='range' | 'list' | 'any'` (all values)
- `<calculation formula='...'>` holding the default value literal
- `<aliases>` / `<members>` containing allowable values for `list`
- `<range min='...' max='...' granularity='...'>` for `range`

Parameter "exposure" (card vs shelf vs calc-only) is NOT determined here — that requires cross-referencing worksheets + dashboards. Stage 2 fills `exposure` after sheets + dashboards are extracted.

- [x] **Step 5.1: Write failing test**

`tests/unit/extract/test_parameters.py`:

```python
from __future__ import annotations

from tableau2pbir.extract.parameters import extract_parameters
from tableau2pbir.util.xml import parse_workbook_xml


_XML_RANGE = b"""<?xml version='1.0'?>
<workbook><datasources>
  <datasource name='Parameters' hasconnection='false'>
    <column caption='Discount' datatype='real' name='[Parameter 1]'
            param-domain-type='range' role='measure' type='quantitative' value='0.1'>
      <calculation class='tableau' formula='0.1'/>
      <range granularity='0.05' max='0.5' min='0.0'/>
    </column>
  </datasource>
</datasources></workbook>
"""

_XML_LIST = b"""<?xml version='1.0'?>
<workbook><datasources>
  <datasource name='Parameters' hasconnection='false'>
    <column caption='Region' datatype='string' name='[Parameter 2]'
            param-domain-type='list' role='dimension' type='nominal' value='&quot;West&quot;'>
      <calculation class='tableau' formula='&quot;West&quot;'/>
      <members>
        <member value='&quot;West&quot;'/>
        <member value='&quot;East&quot;'/>
        <member value='&quot;North&quot;'/>
      </members>
    </column>
  </datasource>
</datasources></workbook>
"""

_XML_ANY = b"""<?xml version='1.0'?>
<workbook><datasources>
  <datasource name='Parameters'>
    <column caption='AxisMax' datatype='integer' name='[Parameter 3]'
            param-domain-type='any' role='measure' value='100'>
      <calculation class='tableau' formula='100'/>
    </column>
  </datasource>
</datasources></workbook>
"""


def test_range_parameter():
    root = parse_workbook_xml(_XML_RANGE)
    params = extract_parameters(root)
    assert len(params) == 1
    p = params[0]
    assert p["caption"] == "Discount"
    assert p["datatype"] == "real"
    assert p["domain_type"] == "range"
    assert p["default"] == "0.1"
    assert p["range"] == {"min": "0.0", "max": "0.5", "granularity": "0.05"}
    assert p["allowed_values"] == ()


def test_list_parameter():
    root = parse_workbook_xml(_XML_LIST)
    p = extract_parameters(root)[0]
    assert p["domain_type"] == "list"
    assert p["allowed_values"] == ('"West"', '"East"', '"North"')
    assert p["range"] is None


def test_any_parameter_has_no_allowed_values():
    root = parse_workbook_xml(_XML_ANY)
    p = extract_parameters(root)[0]
    assert p["domain_type"] == "any"
    assert p["allowed_values"] == ()
    assert p["range"] is None


def test_no_parameters_datasource_returns_empty():
    root = parse_workbook_xml(b"<workbook><datasources/></workbook>")
    assert extract_parameters(root) == []
```

- [x] **Step 5.2: Run test — verify failure**

```bash
pytest tests/unit/extract/test_parameters.py -v
```
Expected: `ModuleNotFoundError`.

- [x] **Step 5.3: Write `src/tableau2pbir/extract/parameters.py`**

```python
"""Extract the special `<datasource name='Parameters'>` into raw dicts.

Output per parameter:
{
  "name": str,                            # without brackets, e.g. 'Parameter 1'
  "caption": str | None,                  # user-visible label, e.g. 'Discount'
  "datatype": str,                        # 'real' | 'integer' | 'string' | 'date' | ...
  "domain_type": 'range' | 'list' | 'any',
  "default": str,                         # raw string literal from <calculation formula='...'> or value attr
  "allowed_values": tuple[str, ...],      # populated for list; empty otherwise
  "range": {"min", "max", "granularity"} | None,
}
"""
from __future__ import annotations

from typing import Any

from lxml import etree

from tableau2pbir.util.xml import attr, optional_attr


def _unbracket(s: str) -> str:
    return s[1:-1] if s.startswith("[") and s.endswith("]") else s


def _default_value(col: etree._Element) -> str:
    calc = col.find("calculation")
    if calc is not None and calc.get("formula") is not None:
        return attr(calc, "formula")
    return attr(col, "value", default="")


def _allowed_values(col: etree._Element) -> tuple[str, ...]:
    members = col.findall("members/member")
    return tuple(attr(m, "value") for m in members)


def _range(col: etree._Element) -> dict[str, str] | None:
    r = col.find("range")
    if r is None:
        return None
    return {
        "min": attr(r, "min"),
        "max": attr(r, "max"),
        "granularity": attr(r, "granularity"),
    }


def extract_parameters(root: etree._Element) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for ds in root.findall("datasources/datasource"):
        if attr(ds, "name") != "Parameters":
            continue
        for col in ds.findall("column"):
            out.append({
                "name": _unbracket(attr(col, "name")),
                "caption": optional_attr(col, "caption"),
                "datatype": attr(col, "datatype", default="string"),
                "domain_type": attr(col, "param-domain-type", default="any"),
                "default": _default_value(col),
                "allowed_values": _allowed_values(col),
                "range": _range(col),
            })
    return out
```

- [x] **Step 5.4: Run test — verify pass**

```bash
pytest tests/unit/extract/test_parameters.py -v
```
Expected: `4 passed`.

- [x] **Step 5.5: Commit**

```bash
git add src/tableau2pbir/extract/parameters.py tests/unit/extract/test_parameters.py
git commit -m "feat(extract): raw parameter extraction from Parameters datasource"
```

---

## Task 6: `extract/worksheets.py` — worksheet raw extraction

**Files:**
- Create: `src/tableau2pbir/extract/worksheets.py`
- Create: `tests/unit/extract/test_worksheets.py`

Spec §6 Stage 1 requires: mark type, encodings (rows/columns/color/size/label/detail/shape/tooltip/angle), filters, sort, dual-axis, reference lines, and **lift worksheet-level table-calc metadata** + **detect quick-table-calc pill modifiers**. For v1, quick-table-calc and table-calc metadata are recorded but downstream stage 2 will route them to `unsupported[]`.

- [x] **Step 6.1: Write failing test**

`tests/unit/extract/test_worksheets.py`:

```python
from __future__ import annotations

from tableau2pbir.extract.worksheets import extract_worksheets
from tableau2pbir.util.xml import parse_workbook_xml


_XML_BASIC = b"""<?xml version='1.0'?>
<workbook><worksheets>
  <worksheet name='Revenue'>
    <view>
      <datasources>
        <datasource name='sample.csv'/>
      </datasources>
      <rows>[amount]</rows>
      <columns>[month]</columns>
      <pane>
        <mark class='Bar'/>
        <encodings>
          <color column='[region]'/>
        </encodings>
      </pane>
    </view>
  </worksheet>
</worksheets></workbook>
"""

_XML_WITH_FILTER = b"""<?xml version='1.0'?>
<workbook><worksheets>
  <worksheet name='Filtered'>
    <view>
      <datasources><datasource name='ds1'/></datasources>
      <rows>[amount]</rows>
      <columns>[region]</columns>
      <filter class='categorical' column='[region]'>
        <groupfilter function='member' level='[region]' member='&quot;West&quot;'/>
        <groupfilter function='member' level='[region]' member='&quot;East&quot;'/>
      </filter>
      <pane><mark class='Bar'/></pane>
    </view>
  </worksheet>
</worksheets></workbook>
"""

_XML_QUICK_TABLE_CALC = b"""<?xml version='1.0'?>
<workbook><worksheets>
  <worksheet name='Running Sum'>
    <view>
      <datasources><datasource name='ds1'/></datasources>
      <rows>[amount]</rows>
      <columns>[month]</columns>
      <table>
        <rows>
          <datasource-dependencies datasource='ds1'>
            <column datatype='integer' name='[amount]' role='measure' type='quantitative'/>
          </datasource-dependencies>
        </rows>
      </table>
      <pane><mark class='Line'/></pane>
      <table-calculations>
        <table-calculation column='[amount]' type='running_sum'/>
      </table-calculations>
    </view>
  </worksheet>
</worksheets></workbook>
"""


def test_basic_worksheet_extract():
    root = parse_workbook_xml(_XML_BASIC)
    ws = extract_worksheets(root)
    assert len(ws) == 1
    w = ws[0]
    assert w["name"] == "Revenue"
    assert w["datasource_refs"] == ("sample.csv",)
    assert w["mark_type"] == "Bar"
    assert w["encodings"]["rows"] == ("amount",)
    assert w["encodings"]["columns"] == ("month",)
    assert w["encodings"]["color"] == "region"
    assert w["filters"] == []
    assert w["quick_table_calcs"] == []


def test_filter_categorical():
    root = parse_workbook_xml(_XML_WITH_FILTER)
    w = extract_worksheets(root)[0]
    assert len(w["filters"]) == 1
    f = w["filters"][0]
    assert f["kind"] == "categorical"
    assert f["column"] == "region"
    assert f["include"] == ('"West"', '"East"')


def test_quick_table_calc_detection():
    root = parse_workbook_xml(_XML_QUICK_TABLE_CALC)
    w = extract_worksheets(root)[0]
    assert len(w["quick_table_calcs"]) == 1
    qtc = w["quick_table_calcs"][0]
    assert qtc["column"] == "amount"
    assert qtc["type"] == "running_sum"


def test_no_worksheets_returns_empty():
    root = parse_workbook_xml(b"<workbook><worksheets/></workbook>")
    assert extract_worksheets(root) == []
```

- [x] **Step 6.2: Run test — verify failure**

```bash
pytest tests/unit/extract/test_worksheets.py -v
```
Expected: `ModuleNotFoundError`.

- [x] **Step 6.3: Write `src/tableau2pbir/extract/worksheets.py`**

```python
"""Raw worksheet extraction — mark type, encodings, filters, sort,
dual-axis, reference lines, quick-table-calc detection.

Output per worksheet:
{
  "name": str,
  "datasource_refs": tuple[str, ...],
  "mark_type": str,                       # Bar, Line, Circle, Square, ...
  "encodings": {
      "rows": tuple[str, ...],             # column names (no brackets)
      "columns": tuple[str, ...],
      "color": str | None,
      "size": str | None,
      "label": str | None,
      "tooltip": str | None,
      "detail": tuple[str, ...],
      "shape": str | None,
      "angle": str | None,
  },
  "filters": [
      {"kind": 'categorical'|'range'|'top_n'|'context'|'conditional',
       "column": str,
       "include": tuple[str, ...],
       "exclude": tuple[str, ...],
       "expr": str | None}
  ],
  "sort": [ {"column": str, "direction": 'asc'|'desc'} ],
  "dual_axis": bool,
  "reference_lines": [ {"kind": str, "scope_column": str, "value": str | None} ],
  "quick_table_calcs": [ {"column": str, "type": str, "compute_using": str | None} ],
}
"""
from __future__ import annotations

from typing import Any

from lxml import etree

from tableau2pbir.util.xml import attr, optional_attr


def _unbracket(s: str) -> str:
    return s[1:-1] if s.startswith("[") and s.endswith("]") else s


def _parse_shelf(text: str | None) -> tuple[str, ...]:
    if text is None:
        return ()
    # Shelves are `+` or whitespace separated bracketed names, e.g. "[a]+[b]".
    tokens = []
    buf = ""
    depth = 0
    for ch in text:
        if ch == "[":
            depth += 1
            buf += ch
        elif ch == "]":
            depth -= 1
            buf += ch
            if depth == 0:
                tokens.append(_unbracket(buf.strip()))
                buf = ""
        elif depth > 0:
            buf += ch
    return tuple(tokens)


def _datasource_refs(view: etree._Element) -> tuple[str, ...]:
    return tuple(
        attr(d, "name")
        for d in view.findall("datasources/datasource")
    )


def _encodings(view: etree._Element) -> dict[str, Any]:
    rows = view.findtext("rows")
    cols = view.findtext("columns")
    enc: dict[str, Any] = {
        "rows": _parse_shelf(rows),
        "columns": _parse_shelf(cols),
        "color": None, "size": None, "label": None, "tooltip": None,
        "detail": (), "shape": None, "angle": None,
    }
    for pane in view.findall("pane"):
        for ch in pane.findall("encodings/*"):
            col = optional_attr(ch, "column")
            if col is None:
                continue
            col = _unbracket(col)
            if ch.tag == "detail":
                enc["detail"] = (*enc["detail"], col)
            elif ch.tag in {"color", "size", "label", "tooltip", "shape", "angle"}:
                enc[ch.tag] = col
    return enc


def _filter_members(filter_elem: etree._Element) -> tuple[tuple[str, ...], tuple[str, ...]]:
    include: list[str] = []
    exclude: list[str] = []
    for gf in filter_elem.findall("groupfilter"):
        func = attr(gf, "function", default="member")
        member = optional_attr(gf, "member")
        if member is None:
            continue
        if func == "except":
            exclude.append(member)
        else:
            include.append(member)
    return tuple(include), tuple(exclude)


def _filters(view: etree._Element) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for f in view.findall("filter"):
        kind = attr(f, "class", default="categorical")
        column = _unbracket(attr(f, "column"))
        include, exclude = _filter_members(f)
        out.append({
            "kind": kind,
            "column": column,
            "include": include,
            "exclude": exclude,
            "expr": optional_attr(f, "formula"),
        })
    return out


def _sort(view: etree._Element) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for s in view.findall("sort"):
        col = optional_attr(s, "column")
        if col is None:
            continue
        out.append({
            "column": _unbracket(col),
            "direction": attr(s, "direction", default="asc"),
        })
    return out


def _reference_lines(view: etree._Element) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for rl in view.findall(".//formatted-text/reference-line"):
        out.append({
            "kind": attr(rl, "class", default="constant"),
            "scope_column": _unbracket(attr(rl, "column", default="")),
            "value": optional_attr(rl, "value"),
        })
    for rl in view.findall(".//reference-lines/reference-line"):
        out.append({
            "kind": attr(rl, "class", default="constant"),
            "scope_column": _unbracket(attr(rl, "column", default="")),
            "value": optional_attr(rl, "value"),
        })
    return out


def _dual_axis(view: etree._Element) -> bool:
    return view.find(".//pane[@dual-axis='true']") is not None \
        or view.find(".//dual-axis") is not None


def _quick_table_calcs(view: etree._Element) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for tc in view.findall(".//table-calculations/table-calculation"):
        out.append({
            "column": _unbracket(attr(tc, "column", default="")),
            "type": attr(tc, "type", default="unknown"),
            "compute_using": optional_attr(tc, "compute-using"),
        })
    return out


def extract_worksheets(root: etree._Element) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for ws in root.findall("worksheets/worksheet"):
        view = ws.find("view")
        if view is None:
            continue
        mark = view.find(".//pane/mark")
        mark_type = attr(mark, "class", default="Automatic") if mark is not None else "Automatic"
        out.append({
            "name": attr(ws, "name"),
            "datasource_refs": _datasource_refs(view),
            "mark_type": mark_type,
            "encodings": _encodings(view),
            "filters": _filters(view),
            "sort": _sort(view),
            "dual_axis": _dual_axis(view),
            "reference_lines": _reference_lines(view),
            "quick_table_calcs": _quick_table_calcs(view),
        })
    return out
```

- [x] **Step 6.4: Run test — verify pass**

```bash
pytest tests/unit/extract/test_worksheets.py -v
```
Expected: `4 passed`.

- [x] **Step 6.5: Commit**

```bash
git add src/tableau2pbir/extract/worksheets.py tests/unit/extract/test_worksheets.py
git commit -m "feat(extract): raw worksheet extraction (encodings, filters, quick-table-calc)"
```

---

## Task 7: `extract/dashboards.py` — dashboard zone tree extraction

**Files:**
- Create: `src/tableau2pbir/extract/dashboards.py`
- Create: `tests/unit/extract/test_dashboards.py`

Tableau `<dashboard>` contains a `<size>` element and a `<zones>` element with one `<zone>` per leaf (tiled) OR nested zones (containers). `type='worksheet'` | `'text'` | `'image'` | `'filter'` | `'parameter'` | `'legend'` | `'navigation'` | `'bitmap'` | `'webpage'` | `'blank'`. Floating zones have `floating='true'` and explicit `x/y/w/h`.

- [x] **Step 7.1: Write failing test**

`tests/unit/extract/test_dashboards.py`:

```python
from __future__ import annotations

from tableau2pbir.extract.dashboards import extract_dashboards
from tableau2pbir.util.xml import parse_workbook_xml


_XML_TILED = b"""<?xml version='1.0'?>
<workbook><dashboards>
  <dashboard name='Main'>
    <size maxheight='800' maxwidth='1200' minheight='800' minwidth='1200'/>
    <zones>
      <zone name='Revenue' type='worksheet' id='1' h='800' w='1200' x='0' y='0'/>
    </zones>
  </dashboard>
</dashboards></workbook>
"""

_XML_FLOATING = b"""<?xml version='1.0'?>
<workbook><dashboards>
  <dashboard name='Float'>
    <size maxheight='600' maxwidth='800' minheight='600' minwidth='800'/>
    <zones>
      <zone name='bg' type='worksheet' id='1' h='600' w='800' x='0' y='0'/>
      <zone name='Overlay' type='worksheet' id='2' h='200' w='300' x='100' y='100' floating='true'/>
    </zones>
  </dashboard>
</dashboards></workbook>
"""

_XML_LEAF_TYPES = b"""<?xml version='1.0'?>
<workbook><dashboards>
  <dashboard name='Kitchen Sink'>
    <size maxheight='768' maxwidth='1366' minheight='768' minwidth='1366'/>
    <zones>
      <zone type='text' id='1' h='50' w='1366' x='0' y='0' param='Header'/>
      <zone type='filter' id='2' h='50' w='300' x='0' y='50' param='[region]'/>
      <zone type='parameter' id='3' h='50' w='300' x='300' y='50' param='[Parameter 1]'/>
      <zone type='legend' id='4' h='50' w='300' x='600' y='50' param='Revenue'/>
      <zone type='bitmap' id='5' h='200' w='300' x='0' y='100'/>
      <zone type='blank' id='6' h='200' w='300' x='300' y='100'/>
      <zone type='webpage' id='7' h='200' w='300' x='600' y='100'/>
    </zones>
  </dashboard>
</dashboards></workbook>
"""


def test_tiled_dashboard_single_worksheet():
    root = parse_workbook_xml(_XML_TILED)
    dbs = extract_dashboards(root)
    assert len(dbs) == 1
    d = dbs[0]
    assert d["name"] == "Main"
    assert d["size"] == {"w": 1200, "h": 800, "kind": "exact"}
    assert len(d["leaves"]) == 1
    leaf = d["leaves"][0]
    assert leaf["leaf_kind"] == "sheet"
    assert leaf["payload"]["sheet_name"] == "Revenue"
    assert leaf["position"] == {"x": 0, "y": 0, "w": 1200, "h": 800}
    assert leaf["floating"] is False


def test_floating_zones_flagged():
    root = parse_workbook_xml(_XML_FLOATING)
    d = extract_dashboards(root)[0]
    assert len(d["leaves"]) == 2
    floating = [l for l in d["leaves"] if l["floating"]]
    assert len(floating) == 1
    assert floating[0]["payload"]["sheet_name"] == "Overlay"


def test_leaf_kind_mapping():
    root = parse_workbook_xml(_XML_LEAF_TYPES)
    d = extract_dashboards(root)[0]
    kinds = [l["leaf_kind"] for l in d["leaves"]]
    assert kinds == ["text", "filter_card", "parameter_card", "legend",
                     "image", "blank", "web_page"]


def test_no_dashboards_returns_empty():
    root = parse_workbook_xml(b"<workbook><dashboards/></workbook>")
    assert extract_dashboards(root) == []
```

- [x] **Step 7.2: Run test — verify failure**

```bash
pytest tests/unit/extract/test_dashboards.py -v
```
Expected: `ModuleNotFoundError`.

- [x] **Step 7.3: Write `src/tableau2pbir/extract/dashboards.py`**

```python
"""Raw dashboard extraction. Emits a flat list of leaves with position
info; stage 5 (Plan 4) walks and builds the container tree. Plan 2
stores leaves in document order; container inference is deferred.

Output per dashboard:
{
  "name": str,
  "size": {"w": int, "h": int, "kind": 'exact'|'automatic'|'range'},
  "leaves": [
      {"leaf_kind": 'sheet'|'text'|'image'|'filter_card'|'parameter_card'|
                    'legend'|'navigation'|'blank'|'web_page',
       "payload": dict,                       # see §5.2
       "position": {"x","y","w","h"},
       "floating": bool}
  ],
}
"""
from __future__ import annotations

from typing import Any

from lxml import etree

from tableau2pbir.util.xml import attr, optional_attr


_ZONE_KIND_MAP = {
    "worksheet":   "sheet",
    "text":        "text",
    "bitmap":      "image",
    "image":       "image",
    "filter":      "filter_card",
    "parameter":   "parameter_card",
    "legend":      "legend",
    "navigation":  "navigation",
    "blank":       "blank",
    "webpage":     "web_page",
    "web-page":    "web_page",
}


def _unbracket(s: str) -> str:
    return s[1:-1] if s.startswith("[") and s.endswith("]") else s


def _size(dashboard: etree._Element) -> dict[str, Any]:
    size = dashboard.find("size")
    if size is None:
        return {"w": 1200, "h": 800, "kind": "automatic"}
    minw = optional_attr(size, "minwidth")
    maxw = optional_attr(size, "maxwidth")
    minh = optional_attr(size, "minheight")
    maxh = optional_attr(size, "maxheight")
    if minw == maxw and minh == maxh and minw is not None:
        return {"w": int(minw), "h": int(minh), "kind": "exact"}
    if minw is not None and maxw is not None and minw != maxw:
        return {"w": int(maxw), "h": int(maxh or 768), "kind": "range"}
    return {"w": int(maxw or 1200), "h": int(maxh or 800), "kind": "automatic"}


def _payload_for_kind(kind: str, zone: etree._Element) -> dict[str, Any]:
    name = optional_attr(zone, "name")
    param = optional_attr(zone, "param")
    if kind == "sheet":
        return {"sheet_name": name or ""}
    if kind == "filter_card":
        return {"field": _unbracket(param) if param else ""}
    if kind == "parameter_card":
        return {"parameter_name": _unbracket(param) if param else ""}
    if kind == "legend":
        return {"host_sheet_name": param or name or ""}
    if kind == "text":
        return {"text": param or ""}
    if kind == "image":
        return {"path": optional_attr(zone, "param") or ""}
    if kind == "navigation":
        return {"target": param or ""}
    return {}   # blank, web_page — no structured payload


def _leaves(dashboard: etree._Element) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for zone in dashboard.findall(".//zones//zone"):
        # Only emit leaves that have a type (containers are untyped <zone> with children).
        z_type = optional_attr(zone, "type")
        if z_type is None:
            continue
        leaf_kind = _ZONE_KIND_MAP.get(z_type)
        if leaf_kind is None:
            leaf_kind = "blank"     # unknown leaf → placeholder; stage 2 logs to unsupported[]
        try:
            pos = {
                "x": int(attr(zone, "x", default="0")),
                "y": int(attr(zone, "y", default="0")),
                "w": int(attr(zone, "w", default="0")),
                "h": int(attr(zone, "h", default="0")),
            }
        except ValueError:
            pos = {"x": 0, "y": 0, "w": 0, "h": 0}
        out.append({
            "leaf_kind": leaf_kind,
            "payload": _payload_for_kind(leaf_kind, zone),
            "position": pos,
            "floating": attr(zone, "floating", default="false").lower() == "true",
        })
    return out


def extract_dashboards(root: etree._Element) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for db in root.findall("dashboards/dashboard"):
        out.append({
            "name": attr(db, "name"),
            "size": _size(db),
            "leaves": _leaves(db),
        })
    return out
```

- [x] **Step 7.4: Run test — verify pass**

```bash
pytest tests/unit/extract/test_dashboards.py -v
```
Expected: `4 passed`.

- [x] **Step 7.5: Commit**

```bash
git add src/tableau2pbir/extract/dashboards.py tests/unit/extract/test_dashboards.py
git commit -m "feat(extract): raw dashboard zone extraction (tiled + floating)"
```

---

## Task 8: `extract/actions.py` — actions extraction

**Files:**
- Create: `src/tableau2pbir/extract/actions.py`
- Create: `tests/unit/extract/test_actions.py`

Tableau actions sit at workbook level inside `<actions>` or under a dashboard's `<actions>` element. Action elements look like `<filter-action>`, `<highlight-action>`, `<url-action>`, `<parameter-action>`. Each has `source` and `target` children with `<datasource>` or `<worksheet>` / `<dashboard>` references.

- [x] **Step 8.1: Write failing test**

`tests/unit/extract/test_actions.py`:

```python
from __future__ import annotations

from tableau2pbir.extract.actions import extract_actions
from tableau2pbir.util.xml import parse_workbook_xml


_XML = b"""<?xml version='1.0'?>
<workbook>
  <dashboards>
    <dashboard name='Main'>
      <actions>
        <filter-action caption='By Region' name='a1' trigger='select' clearing-behavior='keep-filter'>
          <source><worksheet>Revenue</worksheet></source>
          <target><worksheet>Detail</worksheet></target>
        </filter-action>
        <highlight-action caption='Highlight' name='a2' trigger='hover'>
          <source><worksheet>Revenue</worksheet></source>
          <target><worksheet>Detail</worksheet></target>
        </highlight-action>
      </actions>
    </dashboard>
  </dashboards>
  <actions>
    <url-action caption='Open' name='a3' trigger='menu' url='https://x/?p=[Parameter 1]'>
      <source><worksheet>Revenue</worksheet></source>
      <target/>
    </url-action>
  </actions>
</workbook>
"""


def test_extract_actions_mixed_kinds():
    root = parse_workbook_xml(_XML)
    acts = extract_actions(root)
    assert len(acts) == 3
    by_name = {a["name"]: a for a in acts}
    assert by_name["a1"]["kind"] == "filter"
    assert by_name["a1"]["trigger"] == "select"
    assert by_name["a1"]["source_sheets"] == ("Revenue",)
    assert by_name["a1"]["target_sheets"] == ("Detail",)
    assert by_name["a1"]["clearing_behavior"] == "keep_filter"
    assert by_name["a2"]["kind"] == "highlight"
    assert by_name["a3"]["kind"] == "url"
    assert by_name["a3"]["url"] == "https://x/?p=[Parameter 1]"


def test_no_actions_returns_empty():
    root = parse_workbook_xml(b"<workbook/>")
    assert extract_actions(root) == []
```

- [x] **Step 8.2: Run test — verify failure**

```bash
pytest tests/unit/extract/test_actions.py -v
```
Expected: `ModuleNotFoundError`.

- [x] **Step 8.3: Write `src/tableau2pbir/extract/actions.py`**

```python
"""Raw actions extraction — workbook-level and dashboard-level.

Output per action:
{
  "name": str,
  "caption": str | None,
  "kind": 'filter'|'highlight'|'url'|'parameter',
  "trigger": 'select'|'hover'|'menu',
  "source_sheets": tuple[str, ...],
  "target_sheets": tuple[str, ...],
  "clearing_behavior": str,               # 'keep_filter'|'show_all'|'exclude'
  "url": str | None,                      # only for url actions
}
"""
from __future__ import annotations

from typing import Any

from lxml import etree

from tableau2pbir.util.xml import attr, optional_attr


_KIND_BY_TAG = {
    "filter-action":    "filter",
    "highlight-action": "highlight",
    "url-action":       "url",
    "parameter-action": "parameter",
}


def _sheets_under(elem: etree._Element | None) -> tuple[str, ...]:
    if elem is None:
        return ()
    return tuple(
        (w.text or "")
        for w in elem.findall("worksheet")
        if w.text
    )


def _normalize_clearing(raw: str | None) -> str:
    if raw is None:
        return "keep_filter"
    return raw.replace("-", "_")


def _one_action(elem: etree._Element) -> dict[str, Any]:
    return {
        "name": attr(elem, "name"),
        "caption": optional_attr(elem, "caption"),
        "kind": _KIND_BY_TAG[elem.tag],
        "trigger": attr(elem, "trigger", default="select"),
        "source_sheets": _sheets_under(elem.find("source")),
        "target_sheets": _sheets_under(elem.find("target")),
        "clearing_behavior": _normalize_clearing(optional_attr(elem, "clearing-behavior")),
        "url": optional_attr(elem, "url"),
    }


def extract_actions(root: etree._Element) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for tag in _KIND_BY_TAG:
        for elem in root.findall(f".//actions/{tag}"):
            out.append(_one_action(elem))
    return out
```

- [x] **Step 8.4: Run test — verify pass**

```bash
pytest tests/unit/extract/test_actions.py -v
```
Expected: `2 passed`.

- [x] **Step 8.5: Commit**

```bash
git add src/tableau2pbir/extract/actions.py tests/unit/extract/test_actions.py
git commit -m "feat(extract): raw action extraction (filter/highlight/url/parameter)"
```

---

## Task 9: `extract/tier_c_detect.py` — tier-C object detection

**Files:**
- Create: `src/tableau2pbir/extract/tier_c_detect.py`
- Create: `tests/unit/extract/test_tier_c_detect.py`

Tier-C objects per spec §2 + §14: story points, R / Python script calcs, custom shapes, forecast / trend lines, annotations, web-page objects, polygon marks, density marks, Gantt. Detection produces raw dicts that stage 2 maps to `UnsupportedItem` with code `unsupported_<subcategory>`.

- [x] **Step 9.1: Write failing test**

`tests/unit/extract/test_tier_c_detect.py`:

```python
from __future__ import annotations

from tableau2pbir.extract.tier_c_detect import detect_tier_c
from tableau2pbir.util.xml import parse_workbook_xml


def test_story_points_detected():
    xml = b"<workbook><stories><story name='Tour'/></stories></workbook>"
    items = detect_tier_c(parse_workbook_xml(xml))
    assert any(i["code"] == "unsupported_story_points" for i in items)


def test_r_script_calculation_detected():
    xml = b"""<workbook><datasources><datasource name='ds'>
      <column name='[r_calc]'>
        <calculation class='tableau' formula='SCRIPT_REAL(&quot;mean(.arg1)&quot;, SUM([Sales]))'/>
      </column>
    </datasource></datasources></workbook>"""
    items = detect_tier_c(parse_workbook_xml(xml))
    codes = [i["code"] for i in items]
    assert "unsupported_r_python_script" in codes


def test_polygon_mark_detected():
    xml = b"""<workbook><worksheets><worksheet name='w1'>
      <view><pane><mark class='Polygon'/></pane></view>
    </worksheet></worksheets></workbook>"""
    items = detect_tier_c(parse_workbook_xml(xml))
    assert any(i["code"] == "unsupported_mark_polygon" for i in items)


def test_annotation_detected():
    xml = b"""<workbook><worksheets><worksheet name='w1'>
      <view><pane><mark class='Bar'/></pane></view>
      <annotations>
        <annotation type='mark' text='Outlier'/>
      </annotations>
    </worksheet></worksheets></workbook>"""
    items = detect_tier_c(parse_workbook_xml(xml))
    assert any(i["code"] == "unsupported_annotation" for i in items)


def test_empty_workbook_produces_no_items():
    items = detect_tier_c(parse_workbook_xml(b"<workbook/>"))
    assert items == []
```

- [x] **Step 9.2: Run test — verify failure**

```bash
pytest tests/unit/extract/test_tier_c_detect.py -v
```
Expected: `ModuleNotFoundError`.

- [x] **Step 9.3: Write `src/tableau2pbir/extract/tier_c_detect.py`**

```python
"""Detect tier-C (hard-unsupported) objects during stage 1. Stage 2
lifts these into `Workbook.unsupported[]` as `UnsupportedItem`s.

Each detection emits a dict:
{
  "object_kind": 'story'|'calc'|'mark'|'annotation'|'forecast'|'webpage'|'shape',
  "object_id": str,                # stable per-object identifier
  "source_excerpt": str,           # XML snippet for debugging
  "reason": str,                   # human-readable one-liner
  "code": str,                     # §8.1-stable code (unsupported_<subcategory>)
}
"""
from __future__ import annotations

import re
from typing import Any

from lxml import etree

from tableau2pbir.util.xml import attr


_POLYGON_DENSITY_GANTT = {"Polygon", "Density", "Gantt"}

_R_PYTHON_PREFIX = re.compile(r"SCRIPT_(REAL|STR|INT|BOOL)\s*\(", re.IGNORECASE)


def _excerpt(elem: etree._Element) -> str:
    s = etree.tostring(elem, encoding="unicode")
    return s[:200].strip()


def _stories(root: etree._Element) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for story in root.findall("stories/story"):
        out.append({
            "object_kind": "story",
            "object_id": f"story__{attr(story, 'name', default='unnamed')}",
            "source_excerpt": _excerpt(story),
            "reason": "Tableau story points have no PBI equivalent (§14).",
            "code": "unsupported_story_points",
        })
    return out


def _r_python_calcs(root: etree._Element) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for col in root.findall(".//datasources/datasource/column"):
        calc = col.find("calculation")
        if calc is None:
            continue
        formula = attr(calc, "formula", default="")
        if _R_PYTHON_PREFIX.search(formula):
            name = attr(col, "name", default="unnamed")
            out.append({
                "object_kind": "calc",
                "object_id": f"calc__{name}",
                "source_excerpt": formula[:200],
                "reason": "R/Python script calculations are not mapped.",
                "code": "unsupported_r_python_script",
            })
    return out


def _polygon_density_gantt(root: etree._Element) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for ws in root.findall("worksheets/worksheet"):
        name = attr(ws, "name", default="unnamed")
        for mark in ws.findall(".//pane/mark"):
            kls = attr(mark, "class", default="")
            if kls in _POLYGON_DENSITY_GANTT:
                out.append({
                    "object_kind": "mark",
                    "object_id": f"mark__{name}__{kls.lower()}",
                    "source_excerpt": _excerpt(mark),
                    "reason": f"{kls} marks have no first-class PBIR equivalent.",
                    "code": f"unsupported_mark_{kls.lower()}",
                })
    return out


def _annotations(root: etree._Element) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for ws in root.findall("worksheets/worksheet"):
        name = attr(ws, "name", default="unnamed")
        for ann in ws.findall(".//annotations/annotation"):
            out.append({
                "object_kind": "annotation",
                "object_id": f"annotation__{name}__{attr(ann, 'type', default='')}",
                "source_excerpt": _excerpt(ann),
                "reason": "Annotations have no PBI equivalent (§14).",
                "code": "unsupported_annotation",
            })
    return out


def _forecast(root: etree._Element) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for fc in root.findall(".//worksheets/worksheet//forecast"):
        out.append({
            "object_kind": "forecast",
            "object_id": f"forecast__{id(fc)}",
            "source_excerpt": _excerpt(fc),
            "reason": "Forecast/trend lines have no PBI equivalent (§14).",
            "code": "unsupported_forecast",
        })
    return out


def detect_tier_c(root: etree._Element) -> list[dict[str, Any]]:
    return (
        _stories(root)
        + _r_python_calcs(root)
        + _polygon_density_gantt(root)
        + _annotations(root)
        + _forecast(root)
    )
```

- [x] **Step 9.4: Run test — verify pass**

```bash
pytest tests/unit/extract/test_tier_c_detect.py -v
```
Expected: `5 passed`.

- [x] **Step 9.5: Commit**

```bash
git add src/tableau2pbir/extract/tier_c_detect.py tests/unit/extract/test_tier_c_detect.py
git commit -m "feat(extract): tier-C object detection (story/R-Python/polygon/annotation/forecast)"
```

---

## Task 10: Stage 1 — wire `s01_extract.py` and replace the stub

**Files:**
- Modify: `src/tableau2pbir/stages/s01_extract.py`
- Create: `tests/unit/stages/test_s01_extract.py`

- [x] **Step 10.1: Write failing test**

`tests/unit/stages/test_s01_extract.py`:

```python
"""Stage 1 wiring test — exercises the real extract path against the
trivial Plan-1 fixture and asserts the shape of `01_extract.json`."""
from __future__ import annotations

from pathlib import Path

from tableau2pbir.pipeline import StageContext
from tableau2pbir.stages import s01_extract


def _ctx(tmp_path: Path) -> StageContext:
    return StageContext(workbook_id="trivial", output_dir=tmp_path,
                        config={}, stage_number=1)


def test_stage1_on_trivial_fixture(tmp_path: Path, synthetic_fixtures_dir: Path):
    fixture = synthetic_fixtures_dir / "trivial.twb"
    result = s01_extract.run({"source_path": str(fixture)}, _ctx(tmp_path))
    out = result.output

    assert out["source_path"].endswith("trivial.twb")
    assert len(out["source_hash"]) == 64
    assert out["tableau_version"] == "2024.1"       # parsed from source-build
    assert len(out["datasources"]) == 1
    assert out["datasources"][0]["name"] == "sample.csv"
    assert len(out["worksheets"]) == 1
    assert out["worksheets"][0]["name"] == "Revenue"
    assert len(out["dashboards"]) == 1
    assert out["parameters"] == []
    assert out["actions"] == []
    assert out["unsupported"] == []


def test_stage1_summary_contains_counts(tmp_path: Path, synthetic_fixtures_dir: Path):
    fixture = synthetic_fixtures_dir / "trivial.twb"
    result = s01_extract.run({"source_path": str(fixture)}, _ctx(tmp_path))
    assert "Stage 1 — extract" in result.summary_md
    assert "datasources: 1" in result.summary_md
    assert "worksheets: 1" in result.summary_md
    assert "dashboards: 1" in result.summary_md


def test_stage1_missing_source_path_raises(tmp_path: Path):
    import pytest
    with pytest.raises(KeyError):
        s01_extract.run({}, _ctx(tmp_path))
```

- [x] **Step 10.2: Run test — verify failure**

```bash
pytest tests/unit/stages/test_s01_extract.py -v
```
Expected: first test fails — the stub output has key `stub_stage` not `source_path`. Second fails on summary content. Third passes only accidentally.

- [x] **Step 10.3: Replace `src/tableau2pbir/stages/s01_extract.py`**

```python
"""Stage 1 — extract (pure python). See spec §6 Stage 1.

Loads the workbook XML (zip-aware for .twbx), walks the tree using the
`extract/` helpers, and returns a single JSON-serializable dict suitable
for persistence as `01_extract.json`."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from tableau2pbir.extract.actions import extract_actions
from tableau2pbir.extract.dashboards import extract_dashboards
from tableau2pbir.extract.datasources import extract_datasources
from tableau2pbir.extract.parameters import extract_parameters
from tableau2pbir.extract.tier_c_detect import detect_tier_c
from tableau2pbir.extract.worksheets import extract_worksheets
from tableau2pbir.pipeline import StageContext, StageResult
from tableau2pbir.util.xml import attr, parse_workbook_xml
from tableau2pbir.util.zip import read_workbook


def _tableau_version(root: Any) -> str:
    # Tableau writes source-build='2024.1' (major.minor) and version='18.1' (internal).
    # We prefer source-build when present since that tracks user-visible versions.
    build = attr(root, "source-build")
    if build:
        return build
    return attr(root, "version", default="unknown")


def _summary(counts: dict[str, int]) -> str:
    lines = ["# Stage 1 — extract", ""]
    for key in ("datasources", "parameters", "worksheets", "dashboards",
                "actions", "tier_c_objects"):
        lines.append(f"- {key}: {counts.get(key, 0)}")
    return "\n".join(lines) + "\n"


def run(input_json: dict[str, Any], ctx: StageContext) -> StageResult:
    source_path = Path(input_json["source_path"])
    wb = read_workbook(source_path)
    root = parse_workbook_xml(wb.xml_bytes)

    datasources = extract_datasources(root)
    parameters = extract_parameters(root)
    worksheets = extract_worksheets(root)
    dashboards = extract_dashboards(root)
    actions = extract_actions(root)
    unsupported = detect_tier_c(root)

    output: dict[str, Any] = {
        "source_path": wb.source_path,
        "source_hash": wb.source_hash,
        "tableau_version": _tableau_version(root),
        "datasources": datasources,
        "parameters": parameters,
        "worksheets": worksheets,
        "dashboards": dashboards,
        "actions": actions,
        "unsupported": unsupported,
    }
    counts = {
        "datasources": len(datasources),
        "parameters": len(parameters),
        "worksheets": len(worksheets),
        "dashboards": len(dashboards),
        "actions": len(actions),
        "tier_c_objects": len(unsupported),
    }
    return StageResult(output=output, summary_md=_summary(counts), errors=())
```

- [x] **Step 10.4: Run test — verify pass**

```bash
pytest tests/unit/stages/test_s01_extract.py -v
```
Expected: `3 passed`.

- [x] **Step 10.5: Verify existing stubs contract still satisfied**

```bash
pytest tests/unit/stages/test_all_stages_stub.py -v
```
Expected: `8 passed` — stage 1 still returns a `StageResult`; the parametrized test doesn't care about shape.

- [x] **Step 10.6: Run the Plan-1 end-to-end integration**

```bash
pytest tests/integration/test_empty_pipeline_end_to_end.py -v
```
Expected: `1 passed` — stage 1 output is richer now, but stages 2–8 still run as stubs and the artifact files exist.

- [x] **Step 10.7: Commit**

```bash
git add src/tableau2pbir/stages/s01_extract.py tests/unit/stages/test_s01_extract.py
git commit -m "feat(stage1): wire real extract pipeline — replaces Plan-1 stub"
```

---

## Task 11: `classify/connector_tier.py` — §5.8 matrix

**Files:**
- Create: `src/tableau2pbir/classify/__init__.py` (empty)
- Create: `src/tableau2pbir/classify/connector_tier.py`
- Create: `tests/unit/classify/__init__.py` (empty)
- Create: `tests/unit/classify/test_connector_tier.py`

Classifies a raw datasource dict (from `extract_datasources`) into one of the four tiers in §5.8. For `hyper` extracts, walks into `named_connections[0].connection` when the outer class is `federated` or `hyper` → picks upstream Tier-1/2 class. If no upstream → Tier 4.

- [x] **Step 11.1: Write failing test**

`tests/unit/classify/test_connector_tier.py`:

```python
from __future__ import annotations

import pytest

from tableau2pbir.classify.connector_tier import (
    ConnectorClassification,
    classify_connector,
)


def _raw(cls: str, **conn_extra: str) -> dict:
    return {
        "name": "ds",
        "connection": {"class": cls, **conn_extra},
        "named_connections": [],
        "extract": None,
    }


def test_tier_1_csv():
    r = classify_connector(_raw("textscan", filename="sample.csv"))
    assert isinstance(r, ConnectorClassification)
    assert r.tier == 1
    assert r.pbi_m_connector == "Csv.Document"
    assert r.user_action_required == ()


def test_tier_1_sqlserver():
    r = classify_connector(_raw("sqlserver", server="sql1", dbname="S"))
    assert r.tier == 1
    assert r.pbi_m_connector == "Sql.Database"


def test_tier_2_snowflake_needs_credentials():
    r = classify_connector(_raw("snowflake", server="acct.snowflakecomputing.com"))
    assert r.tier == 2
    assert r.pbi_m_connector == "Snowflake.Databases"
    assert "enter credentials" in r.user_action_required


def test_tier_2_oracle_needs_client_install():
    r = classify_connector(_raw("oracle", server="ora1"))
    assert r.tier == 2
    assert "install oracle client" in r.user_action_required


def test_tier_4_published_datasource():
    r = classify_connector(_raw("sqlproxy"))
    assert r.tier == 4
    assert r.pbi_m_connector is None


def test_hyper_with_upstream_reuses_upstream_class():
    raw = {
        "name": "e",
        "connection": {"class": "federated"},
        "named_connections": [
            {"name": "u", "caption": "x",
             "connection": {"class": "sqlserver", "server": "sql1"}},
        ],
        "extract": {"connection": {"class": "hyper"}},
    }
    r = classify_connector(raw)
    assert r.tier == 1
    assert r.pbi_m_connector == "Sql.Database"


def test_hyper_orphan_is_tier_4():
    raw = {
        "name": "e",
        "connection": {"class": "hyper"},
        "named_connections": [],
        "extract": None,
    }
    r = classify_connector(raw)
    assert r.tier == 4
    assert r.pbi_m_connector is None


def test_cross_db_joined_marked_tier_3():
    raw = {
        "name": "j",
        "connection": {"class": "federated"},
        "named_connections": [
            {"name": "a", "caption": None,
             "connection": {"class": "sqlserver", "server": "s"}},
            {"name": "b", "caption": None,
             "connection": {"class": "snowflake", "server": "acct"}},
        ],
        "extract": None,
    }
    r = classify_connector(raw)
    assert r.tier == 3
    assert r.pbi_m_connector is None


def test_unknown_class_falls_to_tier_4():
    r = classify_connector(_raw("mysteryproto"))
    assert r.tier == 4
```

- [x] **Step 11.2: Run test — verify failure**

```bash
pytest tests/unit/classify/test_connector_tier.py -v
```
Expected: `ModuleNotFoundError`.

- [x] **Step 11.3: Write `src/tableau2pbir/classify/connector_tier.py`**

```python
"""§5.8 connector matrix classifier.

Takes a raw datasource dict (from extract/datasources.py) and returns a
`ConnectorClassification` with tier, PBI M connector name, and per-source
user actions. Stage 2 converts this into `Datasource.connector_tier` and
`Datasource.pbi_m_connector`."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


_TIER_1 = {
    "textscan":       ("Csv.Document", ()),
    "csv":            ("Csv.Document", ()),
    "excel-direct":   ("Excel.Workbook", ()),
    "sqlserver":      ("Sql.Database", ()),
}

_TIER_2 = {
    "snowflake":      ("Snowflake.Databases", ("enter credentials",)),
    "databricks":     ("DatabricksMultiCloud.Catalogs", ("enter credentials",)),
    "bigquery":       ("GoogleBigQuery.Database", ("OAuth in Desktop",)),
    "google-bigquery":("GoogleBigQuery.Database", ("OAuth in Desktop",)),
    "postgres":       ("PostgreSQL.Database", ("enter credentials",)),
    "oracle":         ("Oracle.Database", ("enter credentials", "install oracle client")),
    "redshift":       ("AmazonRedshift.Database", ("enter credentials",)),
    "teradata":       ("Teradata.Database", ("enter credentials", "install teradata client")),
    "mysql":          ("MySql.Database", ("enter credentials",)),
}

_TIER_4_EXPLICIT = {
    "sqlproxy",       # Tableau Server / Online published datasource
    "wdc",            # Web Data Connector
    "tableau-r",
    "tableau-python",
    "odata",
    "sas",
    "spss",
}


@dataclass(frozen=True)
class ConnectorClassification:
    tier: int                                   # 1 | 2 | 3 | 4
    pbi_m_connector: str | None                 # None iff tier == 4
    user_action_required: tuple[str, ...] = ()
    reason: str = ""                            # filled in only when tier in {3, 4}


def _classify_class(cls: str) -> ConnectorClassification | None:
    if cls in _TIER_1:
        connector, actions = _TIER_1[cls]
        return ConnectorClassification(tier=1, pbi_m_connector=connector,
                                       user_action_required=actions)
    if cls in _TIER_2:
        connector, actions = _TIER_2[cls]
        return ConnectorClassification(tier=2, pbi_m_connector=connector,
                                       user_action_required=actions)
    if cls in _TIER_4_EXPLICIT:
        return ConnectorClassification(tier=4, pbi_m_connector=None,
                                       reason=f"connector class {cls!r} not in PBI matrix")
    return None


def classify_connector(raw_ds: dict[str, Any]) -> ConnectorClassification:
    outer_class = (raw_ds.get("connection") or {}).get("class", "unknown")

    # Tier 3 — cross-DB or blended federated datasource with 2+ distinct upstream classes.
    named = raw_ds.get("named_connections") or []
    upstream_classes = {
        (nc.get("connection") or {}).get("class")
        for nc in named
        if nc.get("connection") is not None
    }
    upstream_classes.discard(None)

    if outer_class == "federated" and len(upstream_classes) >= 2:
        return ConnectorClassification(
            tier=3, pbi_m_connector=None,
            reason="cross-database join / blend — deferred to v1.2",
        )

    # Hyper with upstream — use the single upstream class.
    if outer_class in {"federated", "hyper"} and len(upstream_classes) == 1:
        upstream = next(iter(upstream_classes))
        result = _classify_class(upstream)
        if result is not None:
            return result

    # Hyper with no upstream — Tier 4 per §5.8.
    if outer_class == "hyper" and not upstream_classes:
        return ConnectorClassification(
            tier=4, pbi_m_connector=None,
            reason="hyper extract with null/missing upstream <connection>",
        )

    result = _classify_class(outer_class)
    if result is not None:
        return result

    return ConnectorClassification(
        tier=4, pbi_m_connector=None,
        reason=f"connector class {outer_class!r} not in PBI matrix",
    )
```

- [x] **Step 11.4: Run test — verify pass**

```bash
pytest tests/unit/classify/test_connector_tier.py -v
```
Expected: `9 passed`.

- [x] **Step 11.5: Commit**

```bash
git add src/tableau2pbir/classify/__init__.py src/tableau2pbir/classify/connector_tier.py \
        tests/unit/classify/__init__.py tests/unit/classify/test_connector_tier.py
git commit -m "feat(classify): §5.8 connector-tier classification (1/2/3/4)"
```

---

## Task 12: `classify/calc_kind.py` — §5.6 kind/phase discrimination

**Files:**
- Create: `src/tableau2pbir/classify/calc_kind.py`
- Create: `tests/unit/classify/test_calc_kind.py`

Spec §5.6 kinds: `row | aggregate | table_calc | lod_fixed | lod_include | lod_exclude`. Phases: `row | aggregate | viz`. Discrimination rules (checked top-to-bottom):
1. LOD prefix `{FIXED` / `{INCLUDE` / `{EXCLUDE` → `lod_fixed` / `lod_include` / `lod_exclude`, phase `aggregate`.
2. Contains any top-level table-calc function (`RUNNING_*`, `WINDOW_*`, `LOOKUP`, `RANK`, `INDEX`, `FIRST`, `LAST`, `PREVIOUS_VALUE`, `SIZE`, `TOTAL`) → `table_calc`, phase `viz`.
3. Contains any top-level aggregation (`SUM`, `AVG`, `COUNT`, `COUNTD`, `MIN`, `MAX`, `MEDIAN`, `STDEV`, `STDEVP`, `VAR`, `VARP`, `ATTR`) → `aggregate`, phase `aggregate`.
4. Else → `row`, phase `row`.

"Top-level" means outside any string literal. The check uses token scanning with quote awareness.

- [x] **Step 12.1: Write failing test**

`tests/unit/classify/test_calc_kind.py`:

```python
from __future__ import annotations

from tableau2pbir.classify.calc_kind import CalcClassification, classify_calc_kind


def test_row_calc():
    r = classify_calc_kind("[Revenue] - [Cost]")
    assert isinstance(r, CalcClassification)
    assert r.kind == "row"
    assert r.phase == "row"


def test_aggregate_sum():
    r = classify_calc_kind("SUM([Sales])")
    assert r.kind == "aggregate"
    assert r.phase == "aggregate"


def test_aggregate_with_if():
    r = classify_calc_kind("IF SUM([Sales]) > 0 THEN AVG([Profit]) END")
    assert r.kind == "aggregate"


def test_lod_fixed():
    r = classify_calc_kind("{FIXED [Region]: SUM([Sales])}")
    assert r.kind == "lod_fixed"
    assert r.phase == "aggregate"


def test_lod_include():
    r = classify_calc_kind("{INCLUDE [Customer]: SUM([Sales])}")
    assert r.kind == "lod_include"


def test_lod_exclude():
    r = classify_calc_kind("{EXCLUDE [Region]: SUM([Sales])}")
    assert r.kind == "lod_exclude"


def test_table_calc_running_sum():
    r = classify_calc_kind("RUNNING_SUM(SUM([Sales]))")
    assert r.kind == "table_calc"
    assert r.phase == "viz"


def test_table_calc_window():
    r = classify_calc_kind("WINDOW_AVG(SUM([Sales]), -2, 0)")
    assert r.kind == "table_calc"


def test_table_calc_rank():
    r = classify_calc_kind("RANK(SUM([Sales]))")
    assert r.kind == "table_calc"


def test_aggregate_string_literal_with_sum_not_misclassified():
    r = classify_calc_kind('"SUM of everything"')
    assert r.kind == "row"


def test_whitespace_insensitive_lod_prefix():
    r = classify_calc_kind("  {  FIXED [x]: SUM([y]) }")
    assert r.kind == "lod_fixed"
```

- [x] **Step 12.2: Run test — verify failure**

```bash
pytest tests/unit/classify/test_calc_kind.py -v
```
Expected: `ModuleNotFoundError`.

- [x] **Step 12.3: Write `src/tableau2pbir/classify/calc_kind.py`**

```python
"""§5.6 calc-kind/phase discrimination. Pure-Python token scan over the
Tableau expression. Rule order is stable; tests pin specific cases."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal


Kind = Literal["row", "aggregate", "table_calc", "lod_fixed", "lod_include", "lod_exclude"]
Phase = Literal["row", "aggregate", "viz"]


_AGG_FUNCS = {
    "SUM", "AVG", "COUNT", "COUNTD", "MIN", "MAX",
    "MEDIAN", "STDEV", "STDEVP", "VAR", "VARP", "ATTR",
}

_TABLE_CALC_FUNCS = {
    "RUNNING_SUM", "RUNNING_AVG", "RUNNING_COUNT", "RUNNING_MIN", "RUNNING_MAX",
    "WINDOW_SUM", "WINDOW_AVG", "WINDOW_COUNT", "WINDOW_MIN", "WINDOW_MAX",
    "WINDOW_MEDIAN", "WINDOW_VAR", "WINDOW_STDEV",
    "LOOKUP", "RANK", "RANK_DENSE", "RANK_UNIQUE", "RANK_MODIFIED", "RANK_PERCENTILE",
    "INDEX", "FIRST", "LAST", "PREVIOUS_VALUE", "SIZE", "TOTAL",
}

_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


@dataclass(frozen=True)
class CalcClassification:
    kind: Kind
    phase: Phase


def _strip_string_literals(expr: str) -> str:
    """Replace everything inside "..." or '...' with equivalent-length spaces
    so downstream substring checks are literal-free. Tableau uses both
    single- and double-quoted strings."""
    out = []
    in_str: str | None = None
    for ch in expr:
        if in_str:
            out.append(" ")
            if ch == in_str:
                in_str = None
        else:
            if ch in ('"', "'"):
                in_str = ch
                out.append(" ")
            else:
                out.append(ch)
    return "".join(out)


def _starts_with_lod(stripped: str) -> str | None:
    text = stripped.lstrip()
    if not text.startswith("{"):
        return None
    inner = text[1:].lstrip().upper()
    if inner.startswith("FIXED"):
        return "lod_fixed"
    if inner.startswith("INCLUDE"):
        return "lod_include"
    if inner.startswith("EXCLUDE"):
        return "lod_exclude"
    return None


def _has_identifier(stripped: str, names: set[str]) -> bool:
    for tok in _IDENT.findall(stripped):
        if tok.upper() in names:
            return True
    return False


def classify_calc_kind(tableau_expr: str) -> CalcClassification:
    stripped = _strip_string_literals(tableau_expr)

    lod = _starts_with_lod(stripped)
    if lod == "lod_fixed":
        return CalcClassification(kind="lod_fixed", phase="aggregate")
    if lod == "lod_include":
        return CalcClassification(kind="lod_include", phase="aggregate")
    if lod == "lod_exclude":
        return CalcClassification(kind="lod_exclude", phase="aggregate")

    if _has_identifier(stripped, _TABLE_CALC_FUNCS):
        return CalcClassification(kind="table_calc", phase="viz")

    if _has_identifier(stripped, _AGG_FUNCS):
        return CalcClassification(kind="aggregate", phase="aggregate")

    return CalcClassification(kind="row", phase="row")
```

- [x] **Step 12.4: Run test — verify pass**

```bash
pytest tests/unit/classify/test_calc_kind.py -v
```
Expected: `11 passed`.

- [x] **Step 12.5: Commit**

```bash
git add src/tableau2pbir/classify/calc_kind.py tests/unit/classify/test_calc_kind.py
git commit -m "feat(classify): §5.6 calc-kind/phase discrimination (row/agg/tc/lod)"
```

---

## Task 13: `classify/parameter_intent.py` — §5.7 intent table

**Files:**
- Create: `src/tableau2pbir/classify/parameter_intent.py`
- Create: `tests/unit/classify/test_parameter_intent.py`

§5.7 maps `(domain_type, exposure)` → intent. Exposure is derived by stage 2 from worksheet + dashboard references; this classifier accepts it as an argument.

| Domain / Exposure | intent |
|---|---|
| `range` + `card` | `numeric_what_if` |
| `list` + `card` | `categorical_selector` |
| `*` + `calc_only` (no card, no shelf) | `internal_constant` |
| (switch-pattern detected by stage 2 helper) | `formatting_control` |
| else | `unsupported` |

Formatting-control detection (switch pattern: parameter drives a `CASE` whose branches differ only in format string) is complex enough that Plan 2 defers it behind a simple signature check: when the caller passes `drives_format_switch=True`, return `formatting_control`.

- [x] **Step 13.1: Write failing test**

`tests/unit/classify/test_parameter_intent.py`:

```python
from __future__ import annotations

from tableau2pbir.classify.parameter_intent import classify_parameter_intent


def test_range_with_card_is_numeric_what_if():
    assert classify_parameter_intent(domain_type="range", exposure="card") \
        == "numeric_what_if"


def test_list_with_card_is_categorical_selector():
    assert classify_parameter_intent(domain_type="list", exposure="card") \
        == "categorical_selector"


def test_calc_only_is_internal_constant_regardless_of_domain():
    for dt in ("range", "list", "any"):
        assert classify_parameter_intent(domain_type=dt, exposure="calc_only") \
            == "internal_constant"


def test_drives_format_switch_returns_formatting_control():
    assert classify_parameter_intent(domain_type="list", exposure="card",
                                     drives_format_switch=True) \
        == "formatting_control"


def test_range_on_shelf_is_unsupported_heuristic():
    # range parameter used on a shelf (not a card) — no clean PBI mapping.
    assert classify_parameter_intent(domain_type="range", exposure="shelf") \
        == "unsupported"


def test_any_with_card_is_unsupported():
    # 'any' (open-ended) parameter with a card — user can type arbitrary values,
    # no PBI equivalent.
    assert classify_parameter_intent(domain_type="any", exposure="card") \
        == "unsupported"
```

- [x] **Step 13.2: Run test — verify failure**

```bash
pytest tests/unit/classify/test_parameter_intent.py -v
```
Expected: `ModuleNotFoundError`.

- [x] **Step 13.3: Write `src/tableau2pbir/classify/parameter_intent.py`**

```python
"""§5.7 parameter-intent classification."""
from __future__ import annotations

from typing import Literal


Intent = Literal[
    "numeric_what_if", "categorical_selector",
    "internal_constant", "formatting_control", "unsupported",
]
DomainType = Literal["range", "list", "any"]
Exposure = Literal["card", "shelf", "calc_only"]


def classify_parameter_intent(
    *,
    domain_type: str,
    exposure: str,
    drives_format_switch: bool = False,
) -> Intent:
    # Explicit format-switch detection wins over everything else.
    if drives_format_switch:
        return "formatting_control"
    if exposure == "calc_only":
        return "internal_constant"
    if domain_type == "range" and exposure == "card":
        return "numeric_what_if"
    if domain_type == "list" and exposure == "card":
        return "categorical_selector"
    return "unsupported"
```

- [x] **Step 13.4: Run test — verify pass**

```bash
pytest tests/unit/classify/test_parameter_intent.py -v
```
Expected: `6 passed`.

- [x] **Step 13.5: Commit**

```bash
git add src/tableau2pbir/classify/parameter_intent.py \
        tests/unit/classify/test_parameter_intent.py
git commit -m "feat(classify): §5.7 parameter-intent (numeric/categorical/constant/format/unsupported)"
```

---

## Task 14: Stage 2 skeleton — Workbook stamp + schema contract

**Files:**
- Modify: `src/tableau2pbir/stages/s02_canonicalize.py`
- Create: `tests/unit/stages/test_s02_canonicalize.py`
- Create: `tests/contract/test_stage2_ir_contract.py`

Stage 2 will be built in layers: skeleton + schema contract now; data_model piece by piece in tasks 15–21; cross-cutting routing in 22; summary in 23. This task wires the skeleton that assembles a minimal empty `Workbook` and proves the output validates against `schemas/ir-v1.0.0.schema.json`.

- [x] **Step 14.1: Write failing test for stage 2 skeleton**

`tests/unit/stages/test_s02_canonicalize.py`:

```python
"""Stage 2 wiring test. Built incrementally: this task covers only the
skeleton (version stamp + top-level Workbook assembly). Subsequent tasks
add datasource/table/calc/parameter/sheet/dashboard coverage."""
from __future__ import annotations

from pathlib import Path

from tableau2pbir.ir.version import IR_SCHEMA_VERSION
from tableau2pbir.pipeline import StageContext
from tableau2pbir.stages import s02_canonicalize


def _ctx(tmp_path: Path) -> StageContext:
    return StageContext(workbook_id="wb", output_dir=tmp_path, config={}, stage_number=2)


_MIN_EXTRACT: dict = {
    "source_path": "/fake/trivial.twb",
    "source_hash": "0" * 64,
    "tableau_version": "2024.1",
    "datasources": [],
    "parameters": [],
    "worksheets": [],
    "dashboards": [],
    "actions": [],
    "unsupported": [],
}


def test_stage2_stamps_schema_version(tmp_path: Path):
    result = s02_canonicalize.run(_MIN_EXTRACT, _ctx(tmp_path))
    assert result.output["ir_schema_version"] == IR_SCHEMA_VERSION


def test_stage2_preserves_source_metadata(tmp_path: Path):
    result = s02_canonicalize.run(_MIN_EXTRACT, _ctx(tmp_path))
    out = result.output
    assert out["source_path"] == "/fake/trivial.twb"
    assert out["source_hash"] == "0" * 64
    assert out["tableau_version"] == "2024.1"


def test_stage2_empty_workbook_has_empty_data_model(tmp_path: Path):
    result = s02_canonicalize.run(_MIN_EXTRACT, _ctx(tmp_path))
    dm = result.output["data_model"]
    for key in ("datasources", "tables", "relationships",
                "calculations", "parameters", "hierarchies", "sets"):
        assert dm[key] == []
    assert result.output["sheets"] == []
    assert result.output["dashboards"] == []
    assert result.output["unsupported"] == []
```

- [x] **Step 14.2: Write failing contract test**

`tests/contract/test_stage2_ir_contract.py`:

```python
"""Stage 2 output must validate against the committed IR JSON Schema."""
from __future__ import annotations

import json
from pathlib import Path

from tableau2pbir.ir.version import IR_SCHEMA_VERSION
from tableau2pbir.ir.workbook import Workbook
from tableau2pbir.pipeline import StageContext
from tableau2pbir.stages import s02_canonicalize


def _ctx(tmp_path: Path) -> StageContext:
    return StageContext(workbook_id="wb", output_dir=tmp_path, config={}, stage_number=2)


_MIN_EXTRACT: dict = {
    "source_path": "/fake/trivial.twb",
    "source_hash": "0" * 64,
    "tableau_version": "2024.1",
    "datasources": [], "parameters": [], "worksheets": [],
    "dashboards": [], "actions": [], "unsupported": [],
}


def test_stage2_empty_output_validates_against_ir_schema(tmp_path: Path, repo_root: Path):
    result = s02_canonicalize.run(_MIN_EXTRACT, _ctx(tmp_path))
    # Schema exists (Plan-1 committed artifact).
    schema_path = repo_root / "schemas" / f"ir-v{IR_SCHEMA_VERSION}.schema.json"
    assert schema_path.exists()
    # Round-trip via pydantic: if Workbook.model_validate accepts it, it matches
    # the schema (pydantic is the schema's source of truth per §5.4).
    Workbook.model_validate(result.output)
```

- [x] **Step 14.3: Run both tests — verify failure**

```bash
pytest tests/unit/stages/test_s02_canonicalize.py tests/contract/test_stage2_ir_contract.py -v
```
Expected: stub returns `stub_stage` key, not `ir_schema_version` — multiple failures.

- [x] **Step 14.4: Replace `src/tableau2pbir/stages/s02_canonicalize.py`** (skeleton only; tasks 15–23 will flesh out sub-functions)

```python
"""Stage 2 — canonicalize → IR (pure python). See spec §6 Stage 2.

This module is built in layers (one task per IR sub-tree). The top-level
orchestrator `run(input_json, ctx)` delegates to small pure builders
that take raw extract dicts and return pydantic IR fragments."""
from __future__ import annotations

from typing import Any

from tableau2pbir.ir.version import IR_SCHEMA_VERSION
from tableau2pbir.ir.workbook import DataModel, Workbook
from tableau2pbir.pipeline import StageContext, StageResult


def run(input_json: dict[str, Any], ctx: StageContext) -> StageResult:
    """Orchestrator. Each sub-builder is pure and side-effect-free."""
    # Plan 2 task 14: skeleton only — empty data model, preserves metadata.
    # Subsequent tasks replace each `()` below with a real sub-builder call.
    wb = Workbook(
        ir_schema_version=IR_SCHEMA_VERSION,
        source_path=input_json["source_path"],
        source_hash=input_json["source_hash"],
        tableau_version=input_json["tableau_version"],
        config={},
        data_model=DataModel(),
        sheets=(),
        dashboards=(),
        unsupported=(),
    )
    return StageResult(
        output=wb.model_dump(mode="json"),
        summary_md="# Stage 2 — canonicalize\n\n(skeleton)\n",
        errors=(),
    )
```

- [x] **Step 14.5: Run tests — verify pass**

```bash
pytest tests/unit/stages/test_s02_canonicalize.py tests/contract/test_stage2_ir_contract.py -v
```
Expected: `4 passed` (3 in unit + 1 in contract).

- [x] **Step 14.6: Commit**

```bash
git add src/tableau2pbir/stages/s02_canonicalize.py \
        tests/unit/stages/test_s02_canonicalize.py \
        tests/contract/test_stage2_ir_contract.py
git commit -m "feat(stage2): wire skeleton with schema-version stamp + IR contract test"
```

---

## Task 15: Stage 2 — canonicalize datasources (with tier classification)

**Files:**
- Create: `src/tableau2pbir/stages/_build_data_model.py` (new private module for stage 2 builders)
- Modify: `src/tableau2pbir/stages/s02_canonicalize.py`
- Create: `tests/unit/stages/test_s02_datasources.py`

Builder function takes `raw_datasources: list[dict]` and returns `(tuple[Datasource, ...], tuple[UnsupportedItem, ...])`. Tier 3 / Tier 4 datasources get both an IR `Datasource` record AND an `UnsupportedItem` appended (tier 4 `unsupported_datasource_tier_4`; tier 3 `deferred_feature_tier3`).

- [x] **Step 15.1: Write failing test**

`tests/unit/stages/test_s02_datasources.py`:

```python
from __future__ import annotations

from tableau2pbir.ir.datasource import ConnectorTier
from tableau2pbir.stages._build_data_model import build_datasources


def test_tier_1_csv():
    raw = [{
        "name": "sample.csv", "caption": "Sample",
        "connection": {"class": "textscan", "filename": "sample.csv", "directory": "."},
        "named_connections": [], "extract": None,
        "columns": [], "calculations": [],
    }]
    datasources, unsupported = build_datasources(raw)
    assert len(datasources) == 1
    ds = datasources[0]
    assert ds.name == "sample.csv"
    assert ds.connector_tier == ConnectorTier.TIER_1
    assert ds.pbi_m_connector == "Csv.Document"
    assert ds.connection_params["filename"] == "sample.csv"
    assert unsupported == ()


def test_tier_2_snowflake_user_action():
    raw = [{
        "name": "sales", "caption": None,
        "connection": {"class": "snowflake", "server": "acct.snowflakecomputing.com",
                       "warehouse": "WH1"},
        "named_connections": [], "extract": None,
        "columns": [], "calculations": [],
    }]
    datasources, unsupported = build_datasources(raw)
    assert datasources[0].connector_tier == ConnectorTier.TIER_2
    assert "enter credentials" in datasources[0].user_action_required
    assert unsupported == ()


def test_tier_3_cross_db_emits_deferred_feature():
    raw = [{
        "name": "joined",
        "connection": {"class": "federated"},
        "named_connections": [
            {"name": "a", "caption": None, "connection": {"class": "sqlserver"}},
            {"name": "b", "caption": None, "connection": {"class": "snowflake"}},
        ],
        "extract": None, "columns": [], "calculations": [],
    }]
    datasources, unsupported = build_datasources(raw)
    assert datasources[0].connector_tier == ConnectorTier.TIER_3
    assert datasources[0].pbi_m_connector is None
    assert len(unsupported) == 1
    assert unsupported[0].code == "deferred_feature_tier3"
    assert unsupported[0].object_kind == "datasource"


def test_tier_4_published_emits_unsupported():
    raw = [{
        "name": "pub",
        "connection": {"class": "sqlproxy"},
        "named_connections": [], "extract": None,
        "columns": [], "calculations": [],
    }]
    datasources, unsupported = build_datasources(raw)
    assert datasources[0].connector_tier == ConnectorTier.TIER_4
    assert len(unsupported) == 1
    assert unsupported[0].code == "unsupported_datasource_tier_4"


def test_extract_ignored_flag_when_hyper_with_upstream():
    raw = [{
        "name": "extract_ds",
        "connection": {"class": "federated"},
        "named_connections": [
            {"name": "u", "caption": None, "connection": {"class": "sqlserver"}},
        ],
        "extract": {"connection": {"class": "hyper"}},
        "columns": [], "calculations": [],
    }]
    datasources, _ = build_datasources(raw)
    assert datasources[0].extract_ignored is True
```

- [x] **Step 15.2: Run test — verify failure**

```bash
pytest tests/unit/stages/test_s02_datasources.py -v
```
Expected: `ModuleNotFoundError`.

- [x] **Step 15.3: Write `src/tableau2pbir/stages/_build_data_model.py` with `build_datasources`**

```python
"""Private builders for Stage 2. One function per IR sub-tree. These are
pure: no I/O, no module-level state, fully unit-testable."""
from __future__ import annotations

from typing import Any

from tableau2pbir.classify.connector_tier import classify_connector
from tableau2pbir.ir.common import UnsupportedItem
from tableau2pbir.ir.datasource import ConnectorTier, Datasource
from tableau2pbir.util.ids import stable_id


def _connection_params(raw_ds: dict[str, Any]) -> dict[str, str]:
    conn = raw_ds.get("connection") or {}
    params: dict[str, str] = {}
    for key in ("server", "dbname", "database", "warehouse", "filename",
                "directory", "host", "port", "schema", "http_path",
                "billing_project", "catalog"):
        if key in conn and conn[key]:
            params[key] = conn[key]
    return params


def _source_excerpt(raw_ds: dict[str, Any]) -> str:
    conn = raw_ds.get("connection") or {}
    return f"<datasource name={raw_ds.get('name')!r} connection.class={conn.get('class')!r}/>"


def build_datasources(
    raw_datasources: list[dict[str, Any]],
) -> tuple[tuple[Datasource, ...], tuple[UnsupportedItem, ...]]:
    """Map raw extract datasources to IR Datasources with §5.8 classification.
    Returns (datasources, unsupported_items). Tier 3/4 datasources get both
    an IR record AND an UnsupportedItem appended."""
    datasources: list[Datasource] = []
    unsupported: list[UnsupportedItem] = []

    for raw in raw_datasources:
        classification = classify_connector(raw)
        ds_id = stable_id("ds", raw["name"])
        extract_ignored = raw.get("extract") is not None and classification.tier in (1, 2)

        ds = Datasource(
            id=ds_id,
            name=raw["name"],
            tableau_kind=(raw.get("connection") or {}).get("class", "unknown"),
            connector_tier=ConnectorTier(classification.tier),
            pbi_m_connector=classification.pbi_m_connector,
            connection_params=_connection_params(raw),
            user_action_required=classification.user_action_required,
            table_ids=(),                # populated in task 16 (build_tables)
            extract_ignored=extract_ignored,
        )
        datasources.append(ds)

        if classification.tier == 4:
            unsupported.append(UnsupportedItem(
                object_kind="datasource",
                object_id=ds_id,
                source_excerpt=_source_excerpt(raw),
                reason=classification.reason or "Tier 4 datasource — no PBI mapping.",
                code="unsupported_datasource_tier_4",
            ))
        elif classification.tier == 3:
            unsupported.append(UnsupportedItem(
                object_kind="datasource",
                object_id=ds_id,
                source_excerpt=_source_excerpt(raw),
                reason=classification.reason or "Tier 3 datasource — deferred to v1.2.",
                code="deferred_feature_tier3",
            ))

    return tuple(datasources), tuple(unsupported)
```

- [x] **Step 15.4: Wire `build_datasources` into `s02_canonicalize.py`**

Replace the `run` function body so it calls `build_datasources`:

```python
from tableau2pbir.stages._build_data_model import build_datasources


def run(input_json: dict[str, Any], ctx: StageContext) -> StageResult:
    datasources, ds_unsupported = build_datasources(input_json.get("datasources", []))

    wb = Workbook(
        ir_schema_version=IR_SCHEMA_VERSION,
        source_path=input_json["source_path"],
        source_hash=input_json["source_hash"],
        tableau_version=input_json["tableau_version"],
        config={},
        data_model=DataModel(datasources=datasources),
        sheets=(),
        dashboards=(),
        unsupported=ds_unsupported,
    )
    return StageResult(
        output=wb.model_dump(mode="json"),
        summary_md="# Stage 2 — canonicalize\n\n(datasources wired)\n",
        errors=(),
    )
```

- [x] **Step 15.5: Run test — verify pass**

```bash
pytest tests/unit/stages/test_s02_datasources.py \
       tests/unit/stages/test_s02_canonicalize.py \
       tests/contract/test_stage2_ir_contract.py -v
```
Expected: all pass (skeleton tests + new datasource tests + schema contract).

- [x] **Step 15.6: Commit**

```bash
git add src/tableau2pbir/stages/_build_data_model.py \
        src/tableau2pbir/stages/s02_canonicalize.py \
        tests/unit/stages/test_s02_datasources.py
git commit -m "feat(stage2): canonicalize datasources with §5.8 tier classification"
```

---

## Task 16: Stage 2 — canonicalize tables + columns

**Files:**
- Modify: `src/tableau2pbir/stages/_build_data_model.py`
- Create: `tests/unit/stages/test_s02_tables.py`

Tableau has no explicit `<table>` element in a CSV/single-connection datasource — it implicitly has one "table" per datasource. For our IR we emit one `Table` per datasource whose `column_ids` are all `Column` ids from that datasource. Relationships are out of scope for Plan 2 (only show up with multi-table federated/joined datasources; those go through Plan 3+ / Plan 4).

- [x] **Step 16.1: Write failing test**

`tests/unit/stages/test_s02_tables.py`:

```python
from __future__ import annotations

from tableau2pbir.ir.model import ColumnKind, ColumnRole
from tableau2pbir.stages._build_data_model import build_tables


def test_one_table_per_datasource():
    raw = [{
        "name": "sample.csv", "caption": "Sample",
        "connection": {"class": "textscan"}, "named_connections": [], "extract": None,
        "columns": [
            {"name": "id", "datatype": "integer", "role": "dimension", "type": "ordinal"},
            {"name": "amount", "datatype": "integer", "role": "measure", "type": "quantitative"},
        ],
        "calculations": [],
    }]
    tables, columns = build_tables(raw)
    assert len(tables) == 1
    assert tables[0].name == "sample.csv"
    assert tables[0].datasource_id == "ds__sample_csv"
    assert len(columns) == 2
    amount = next(c for c in columns if c.name == "amount")
    assert amount.role == ColumnRole.MEASURE
    assert amount.kind == ColumnKind.RAW
    assert amount.datatype == "integer"


def test_calculated_column_has_tableau_expr_and_kind_calculated():
    raw = [{
        "name": "orders", "caption": None,
        "connection": {"class": "sqlserver"}, "named_connections": [], "extract": None,
        "columns": [
            {"name": "Revenue", "datatype": "real", "role": "measure", "type": None},
            {"name": "Profit Margin", "datatype": "real", "role": "measure", "type": None},
        ],
        "calculations": [
            {"host_column_name": "Profit Margin", "tableau_expr": "SUM([Profit])/SUM([Revenue])",
             "datatype": "real", "role": "measure"},
        ],
    }]
    _, columns = build_tables(raw)
    margin = next(c for c in columns if c.name == "Profit Margin")
    assert margin.kind == ColumnKind.CALCULATED
    assert margin.tableau_expr == "SUM([Profit])/SUM([Revenue])"
    assert margin.dax_expr is None          # Populated in Plan 3 (stage 3).


def test_table_column_ids_reference_columns():
    raw = [{
        "name": "sample.csv", "caption": None,
        "connection": {"class": "textscan"}, "named_connections": [], "extract": None,
        "columns": [
            {"name": "id", "datatype": "integer", "role": "dimension", "type": None},
            {"name": "amount", "datatype": "integer", "role": "measure", "type": None},
        ],
        "calculations": [],
    }]
    tables, columns = build_tables(raw)
    column_ids = {c.id for c in columns}
    assert set(tables[0].column_ids) == column_ids


def test_empty_datasources_returns_empty():
    tables, columns = build_tables([])
    assert tables == ()
    assert columns == ()
```

- [x] **Step 16.2: Run test — verify failure**

```bash
pytest tests/unit/stages/test_s02_tables.py -v
```
Expected: `ImportError: cannot import name 'build_tables'`.

- [x] **Step 16.3: Add `build_tables` to `_build_data_model.py`**

Append to `src/tableau2pbir/stages/_build_data_model.py`:

```python
from tableau2pbir.ir.model import Column, ColumnKind, ColumnRole, Table


def _column_role(raw_role: str) -> ColumnRole:
    return ColumnRole.MEASURE if raw_role == "measure" else ColumnRole.DIMENSION


def build_tables(
    raw_datasources: list[dict[str, Any]],
) -> tuple[tuple[Table, ...], tuple[Column, ...]]:
    """Emit one IR Table per datasource with all its columns.

    Calculated columns are recognized here: when a raw column's name matches
    a calculation's `host_column_name`, its kind becomes CALCULATED and the
    `tableau_expr` is carried through. DAX translation happens in Plan 3."""
    tables: list[Table] = []
    columns: list[Column] = []

    for raw in raw_datasources:
        ds_id = stable_id("ds", raw["name"])
        table_id = stable_id("tbl", raw["name"])
        calc_by_host = {c["host_column_name"]: c for c in raw.get("calculations", [])}
        col_ids: list[str] = []

        for col in raw.get("columns", []):
            col_id = f"{table_id}__{stable_id('col', col['name'])}"
            calc = calc_by_host.get(col["name"])
            if calc is not None:
                column = Column(
                    id=col_id, name=col["name"],
                    datatype=col["datatype"], role=_column_role(col["role"]),
                    kind=ColumnKind.CALCULATED,
                    tableau_expr=calc["tableau_expr"],
                    dax_expr=None,
                )
            else:
                column = Column(
                    id=col_id, name=col["name"],
                    datatype=col["datatype"], role=_column_role(col["role"]),
                    kind=ColumnKind.RAW,
                )
            columns.append(column)
            col_ids.append(col_id)

        tables.append(Table(
            id=table_id,
            name=raw["name"],
            datasource_id=ds_id,
            column_ids=tuple(col_ids),
            primary_key=None,
        ))

    return tuple(tables), tuple(columns)
```

- [x] **Step 16.4: Wire `build_tables` into `s02_canonicalize.run`**

Replace `data_model=DataModel(datasources=datasources)` with:

```python
tables, _columns = build_tables(input_json.get("datasources", []))
# Columns live *inside* tables via column_ids; IR DataModel tracks tables only.
# Keep the columns list locally for cross-lookups in later tasks (calcs).
data_model = DataModel(datasources=datasources, tables=tables)
```

and update the `from tableau2pbir.stages._build_data_model` import line:

```python
from tableau2pbir.stages._build_data_model import build_datasources, build_tables
```

- [x] **Step 16.5: Run test — verify pass**

```bash
pytest tests/unit/stages/test_s02_tables.py \
       tests/unit/stages/test_s02_canonicalize.py \
       tests/contract/test_stage2_ir_contract.py -v
```
Expected: all pass.

- [x] **Step 16.6: Commit**

```bash
git add src/tableau2pbir/stages/_build_data_model.py \
        src/tableau2pbir/stages/s02_canonicalize.py \
        tests/unit/stages/test_s02_tables.py
git commit -m "feat(stage2): canonicalize tables and columns (raw + calculated)"
```

---

## Task 17: Stage 2 — canonicalize calculations (with kind/phase)

**Files:**
- Modify: `src/tableau2pbir/stages/_build_data_model.py`
- Create: `tests/unit/stages/test_s02_calculations.py`

Each raw calculation becomes an IR `Calculation`. Kind and phase come from `classify_calc_kind`; kind-discriminated payloads (`lod_fixed`, `lod_relative`, `table_calc`) are populated for `lod_fixed` only in Plan 2 — the other kinds go through the v1-deferred routing in Task 22. Parsing the LOD dimensions / table-calc metadata in detail is out of scope (stage 3 consumes what we give it; for v1 we only *need* the dimensions for lod_fixed since that's the only kind that ships).

**LOD FIXED dimension parsing** — for `{FIXED [a], [b]: SUM(...)}` the dimensions between `{FIXED` and `:` are a comma-separated list of bracketed column references. The list can be empty (`{FIXED : SUM(...)}` — grand-total LOD). Each `[Name]` maps to a `FieldRef(table_id=<ds default>, column_id=<column name>)` — we don't have per-field table resolution in Plan 2, so we use the *first datasource's table id* as a placeholder. Plan 3 / Plan 4 refine when calc translation needs real refs.

**`depends_on` at this stage** is populated by finding bracketed identifiers in the expression that match another calc's name. Computed in `build_calculations` after all calcs are collected.

- [x] **Step 17.1: Write failing test**

`tests/unit/stages/test_s02_calculations.py`:

```python
from __future__ import annotations

from tableau2pbir.ir.calculation import CalculationKind, CalculationPhase, CalculationScope
from tableau2pbir.stages._build_data_model import build_calculations


def _raw_ds_with_calcs(ds_name: str, calcs: list[dict]) -> dict:
    return {
        "name": ds_name, "caption": None,
        "connection": {"class": "textscan"}, "named_connections": [],
        "extract": None,
        "columns": [{"name": c["host_column_name"], "datatype": c["datatype"],
                     "role": c["role"], "type": None} for c in calcs],
        "calculations": calcs,
    }


def test_row_calc_gets_kind_row():
    raw = [_raw_ds_with_calcs("ds", [
        {"host_column_name": "Profit", "tableau_expr": "[Revenue] - [Cost]",
         "datatype": "real", "role": "measure"},
    ])]
    calcs = build_calculations(raw)
    assert len(calcs) == 1
    c = calcs[0]
    assert c.kind == CalculationKind.ROW
    assert c.phase == CalculationPhase.ROW
    assert c.scope == CalculationScope.MEASURE
    assert c.lod_fixed is None
    assert c.table_calc is None


def test_aggregate_calc():
    raw = [_raw_ds_with_calcs("ds", [
        {"host_column_name": "Total Sales", "tableau_expr": "SUM([Sales])",
         "datatype": "real", "role": "measure"},
    ])]
    c = build_calculations(raw)[0]
    assert c.kind == CalculationKind.AGGREGATE
    assert c.phase == CalculationPhase.AGGREGATE


def test_lod_fixed_carries_dimensions():
    raw = [_raw_ds_with_calcs("ds", [
        {"host_column_name": "Sales By Region",
         "tableau_expr": "{FIXED [Region], [Year]: SUM([Sales])}",
         "datatype": "real", "role": "measure"},
    ])]
    c = build_calculations(raw)[0]
    assert c.kind == CalculationKind.LOD_FIXED
    assert c.lod_fixed is not None
    dim_columns = [d.column_id for d in c.lod_fixed.dimensions]
    assert dim_columns == ["region", "year"]


def test_lod_fixed_grand_total_has_empty_dimensions():
    raw = [_raw_ds_with_calcs("ds", [
        {"host_column_name": "Grand Total", "tableau_expr": "{FIXED : SUM([Sales])}",
         "datatype": "real", "role": "measure"},
    ])]
    c = build_calculations(raw)[0]
    assert c.kind == CalculationKind.LOD_FIXED
    assert c.lod_fixed is not None
    assert c.lod_fixed.dimensions == ()


def test_lod_include_sets_relative_and_kind():
    raw = [_raw_ds_with_calcs("ds", [
        {"host_column_name": "Sales By Customer",
         "tableau_expr": "{INCLUDE [Customer]: SUM([Sales])}",
         "datatype": "real", "role": "measure"},
    ])]
    c = build_calculations(raw)[0]
    assert c.kind == CalculationKind.LOD_INCLUDE
    assert c.lod_relative is not None
    assert c.lod_relative.extra_dims is not None
    assert [d.column_id for d in c.lod_relative.extra_dims] == ["customer"]


def test_depends_on_detects_sibling_calcs():
    raw = [_raw_ds_with_calcs("ds", [
        {"host_column_name": "Revenue", "tableau_expr": "SUM([Sales])",
         "datatype": "real", "role": "measure"},
        {"host_column_name": "Margin", "tableau_expr": "[Revenue] - SUM([Cost])",
         "datatype": "real", "role": "measure"},
    ])]
    calcs = build_calculations(raw)
    margin = next(c for c in calcs if c.name == "Margin")
    revenue = next(c for c in calcs if c.name == "Revenue")
    assert revenue.id in margin.depends_on
```

- [x] **Step 17.2: Run test — verify failure**

```bash
pytest tests/unit/stages/test_s02_calculations.py -v
```
Expected: `ImportError: cannot import name 'build_calculations'`.

- [x] **Step 17.3: Add `build_calculations` to `_build_data_model.py`**

Append:

```python
import re

from tableau2pbir.classify.calc_kind import classify_calc_kind
from tableau2pbir.ir.calculation import (
    Calculation, CalculationKind, CalculationPhase, CalculationScope,
    LodFixed, LodRelative,
)
from tableau2pbir.ir.common import FieldRef


_LOD_HEADER = re.compile(
    r"^\s*\{\s*(FIXED|INCLUDE|EXCLUDE)\s*(?P<dims>.*?)\s*:\s*.*\}\s*$",
    re.IGNORECASE | re.DOTALL,
)
_BRACKETED = re.compile(r"\[([^\[\]]+)\]")


def _parse_lod_dimensions(tableau_expr: str, table_id: str) -> tuple[FieldRef, ...]:
    m = _LOD_HEADER.match(tableau_expr)
    if not m:
        return ()
    dims_text = m.group("dims").strip()
    if not dims_text:
        return ()
    refs: list[FieldRef] = []
    for name in _BRACKETED.findall(dims_text):
        refs.append(FieldRef(table_id=table_id, column_id=stable_id("", name).lstrip("_")))
    return tuple(refs)


def _scope(raw_role: str) -> CalculationScope:
    return CalculationScope.MEASURE if raw_role == "measure" else CalculationScope.COLUMN


def _dependency_ids(expr: str, calc_name_to_id: dict[str, str]) -> tuple[str, ...]:
    deps: list[str] = []
    for name in _BRACKETED.findall(expr):
        if name in calc_name_to_id and calc_name_to_id[name] not in deps:
            deps.append(calc_name_to_id[name])
    return tuple(deps)


def build_calculations(
    raw_datasources: list[dict[str, Any]],
) -> tuple[Calculation, ...]:
    """Map raw calculations (from extract) to IR Calculations with
    classified kind/phase. Kind-specific payloads (lod_fixed, lod_relative)
    are filled in here; table_calc specifics and anonymous quick-table-calc
    records are handled in task 22 (deferred-feature routing) for v1."""
    # First pass — build name → id map for dependency resolution.
    name_to_id: dict[str, str] = {}
    per_calc: list[tuple[dict[str, Any], str, str]] = []   # (raw_calc, calc_id, table_id)
    for raw_ds in raw_datasources:
        table_id = stable_id("tbl", raw_ds["name"])
        for calc in raw_ds.get("calculations", []):
            calc_id = stable_id("calc", calc["host_column_name"])
            name_to_id[calc["host_column_name"]] = calc_id
            per_calc.append((calc, calc_id, table_id))

    out: list[Calculation] = []
    for raw_calc, calc_id, table_id in per_calc:
        expr = raw_calc["tableau_expr"]
        classification = classify_calc_kind(expr)
        kind = CalculationKind(classification.kind)
        phase = CalculationPhase(classification.phase)

        lod_fixed = None
        lod_relative = None
        if kind == CalculationKind.LOD_FIXED:
            lod_fixed = LodFixed(dimensions=_parse_lod_dimensions(expr, table_id))
        elif kind == CalculationKind.LOD_INCLUDE:
            dims = _parse_lod_dimensions(expr, table_id)
            lod_relative = LodRelative(extra_dims=dims if dims else None)
        elif kind == CalculationKind.LOD_EXCLUDE:
            dims = _parse_lod_dimensions(expr, table_id)
            lod_relative = LodRelative(excluded_dims=dims if dims else None)

        out.append(Calculation(
            id=calc_id,
            name=raw_calc["host_column_name"],
            scope=_scope(raw_calc["role"]),
            tableau_expr=expr,
            dax_expr=None,
            depends_on=_dependency_ids(expr, name_to_id),
            kind=kind,
            phase=phase,
            lod_fixed=lod_fixed,
            lod_relative=lod_relative,
            table_calc=None,                # Plan 3 populates table_calc details.
            owner_sheet_id=None,
        ))
    return tuple(out)
```

- [x] **Step 17.4: Wire `build_calculations` into `s02_canonicalize.run`**

Update imports:

```python
from tableau2pbir.stages._build_data_model import (
    build_calculations, build_datasources, build_tables,
)
```

And in `run`:

```python
calculations = build_calculations(input_json.get("datasources", []))
data_model = DataModel(
    datasources=datasources,
    tables=tables,
    calculations=calculations,
)
```

- [x] **Step 17.5: Run test — verify pass**

```bash
pytest tests/unit/stages/test_s02_calculations.py \
       tests/unit/stages/test_s02_canonicalize.py \
       tests/contract/test_stage2_ir_contract.py -v
```
Expected: all pass.

- [x] **Step 17.6: Commit**

```bash
git add src/tableau2pbir/stages/_build_data_model.py \
        src/tableau2pbir/stages/s02_canonicalize.py \
        tests/unit/stages/test_s02_calculations.py
git commit -m "feat(stage2): canonicalize calculations with kind/phase + LOD dims"
```

---

## Task 18: Stage 2 — canonicalize parameters (with intent)

**Files:**
- Modify: `src/tableau2pbir/stages/_build_data_model.py`
- Create: `tests/unit/stages/test_s02_parameters.py`

`build_parameters` takes `raw_params: list[dict]` and `usage: dict[str, str]` where `usage[param_name] ∈ {"card", "shelf", "calc_only"}`. Usage is derived by the orchestrator from the dashboard's `parameter_card` leaves (card) and sheet encodings (shelf). For Plan 2, parameters used in neither get `calc_only`.

- [x] **Step 18.1: Write failing test**

`tests/unit/stages/test_s02_parameters.py`:

```python
from __future__ import annotations

from tableau2pbir.ir.parameter import ParameterExposure, ParameterIntent
from tableau2pbir.stages._build_data_model import build_parameters


def test_range_with_card_becomes_numeric_what_if():
    raw = [{
        "name": "Parameter 1", "caption": "Discount",
        "datatype": "real", "domain_type": "range", "default": "0.1",
        "allowed_values": (), "range": {"min": "0.0", "max": "0.5", "granularity": "0.05"},
    }]
    usage = {"Parameter 1": "card"}
    params = build_parameters(raw, usage)
    assert len(params) == 1
    p = params[0]
    assert p.intent == ParameterIntent.NUMERIC_WHAT_IF
    assert p.exposure == ParameterExposure.CARD
    assert p.default == "0.1"
    # For range parameters, allowed_values are synthesized from min/max/granularity
    # (used by Plan 4 to generate the GENERATESERIES table).
    assert len(p.allowed_values) >= 2


def test_list_with_card_becomes_categorical_selector():
    raw = [{
        "name": "Parameter 2", "caption": "Region",
        "datatype": "string", "domain_type": "list", "default": '"West"',
        "allowed_values": ('"West"', '"East"'),
        "range": None,
    }]
    params = build_parameters(raw, {"Parameter 2": "card"})
    assert params[0].intent == ParameterIntent.CATEGORICAL_SELECTOR
    assert params[0].allowed_values == ('"West"', '"East"')


def test_calc_only_becomes_internal_constant():
    raw = [{
        "name": "AxisMax", "caption": "AxisMax",
        "datatype": "integer", "domain_type": "any", "default": "100",
        "allowed_values": (), "range": None,
    }]
    params = build_parameters(raw, {})
    assert params[0].intent == ParameterIntent.INTERNAL_CONSTANT
    assert params[0].exposure == ParameterExposure.CALC_ONLY


def test_range_on_shelf_is_unsupported():
    raw = [{
        "name": "Threshold", "caption": None,
        "datatype": "real", "domain_type": "range", "default": "0",
        "allowed_values": (), "range": {"min": "0", "max": "1", "granularity": "0.1"},
    }]
    params = build_parameters(raw, {"Threshold": "shelf"})
    assert params[0].intent == ParameterIntent.UNSUPPORTED


def test_parameter_id_is_stable():
    raw = [{
        "name": "Discount", "caption": None,
        "datatype": "real", "domain_type": "range", "default": "0",
        "allowed_values": (), "range": {"min": "0", "max": "1", "granularity": "0.1"},
    }]
    first = build_parameters(raw, {"Discount": "card"})[0].id
    second = build_parameters(raw, {"Discount": "card"})[0].id
    assert first == second
    assert first.startswith("param__")
```

- [x] **Step 18.2: Run test — verify failure**

```bash
pytest tests/unit/stages/test_s02_parameters.py -v
```
Expected: `ImportError: cannot import name 'build_parameters'`.

- [x] **Step 18.3: Add `build_parameters` to `_build_data_model.py`**

Append:

```python
from tableau2pbir.classify.parameter_intent import classify_parameter_intent
from tableau2pbir.ir.parameter import Parameter, ParameterExposure, ParameterIntent


def _synthesize_range_values(range_dict: dict[str, str]) -> tuple[str, ...]:
    """For numeric-what-if, produce the discrete sample list for the
    disconnected table (Plan 4 will GENERATESERIES this in M; Plan 2 stores
    endpoints for round-tripping)."""
    return (range_dict["min"], range_dict["max"], range_dict["granularity"])


def _exposure(raw_usage: str | None) -> ParameterExposure:
    if raw_usage == "card":
        return ParameterExposure.CARD
    if raw_usage == "shelf":
        return ParameterExposure.SHELF
    return ParameterExposure.CALC_ONLY


def build_parameters(
    raw_parameters: list[dict[str, Any]],
    usage: dict[str, str],
) -> tuple[Parameter, ...]:
    """`usage[param_name]` ∈ {'card','shelf','calc_only'} derived by the
    orchestrator from dashboards + worksheets. Defaults to 'calc_only'."""
    out: list[Parameter] = []
    for raw in raw_parameters:
        exposure_raw = usage.get(raw["name"], "calc_only")
        intent_str = classify_parameter_intent(
            domain_type=raw["domain_type"],
            exposure=exposure_raw,
        )
        exposure = _exposure(exposure_raw)
        allowed = raw["allowed_values"]
        if not allowed and raw["domain_type"] == "range" and raw["range"]:
            allowed = _synthesize_range_values(raw["range"])
        out.append(Parameter(
            id=stable_id("param", raw["name"]),
            name=raw["name"],
            datatype=raw["datatype"],
            default=raw["default"],
            allowed_values=tuple(allowed),
            intent=ParameterIntent(intent_str),
            exposure=exposure,
            binding_target=None,        # formatting_control target is Plan 3+.
        ))
    return tuple(out)
```

- [x] **Step 18.4: Compute `usage` in `s02_canonicalize.run` and wire parameters**

Add a helper to `s02_canonicalize.py`:

```python
def _parameter_usage(input_json: dict[str, Any]) -> dict[str, str]:
    """Derive card vs shelf vs calc_only exposure for each parameter by
    scanning raw dashboards + worksheets. Card takes precedence over shelf."""
    usage: dict[str, str] = {}
    # Cards: dashboard parameter_card leaves.
    for db in input_json.get("dashboards", []):
        for leaf in db.get("leaves", []):
            if leaf["leaf_kind"] == "parameter_card":
                name = leaf["payload"].get("parameter_name")
                if name:
                    usage[name] = "card"
    # Shelves: worksheet rows/columns shelf references (rare but possible).
    for ws in input_json.get("worksheets", []):
        for channel in ("rows", "columns"):
            for ref in ws["encodings"].get(channel, ()):
                # Parameter shelf refs surface as the parameter's user-facing name.
                usage.setdefault(ref, "shelf")
    return usage
```

Update `run`:

```python
usage = _parameter_usage(input_json)
parameters = build_parameters(input_json.get("parameters", []), usage)
data_model = DataModel(
    datasources=datasources,
    tables=tables,
    calculations=calculations,
    parameters=parameters,
)
```

Update import:

```python
from tableau2pbir.stages._build_data_model import (
    build_calculations, build_datasources, build_parameters, build_tables,
)
```

- [x] **Step 18.5: Run tests — verify pass**

```bash
pytest tests/unit/stages/test_s02_parameters.py \
       tests/unit/stages/test_s02_canonicalize.py \
       tests/contract/test_stage2_ir_contract.py -v
```
Expected: all pass.

- [x] **Step 18.6: Commit**

```bash
git add src/tableau2pbir/stages/_build_data_model.py \
        src/tableau2pbir/stages/s02_canonicalize.py \
        tests/unit/stages/test_s02_parameters.py
git commit -m "feat(stage2): canonicalize parameters with §5.7 intent classification"
```

---

## Task 19: Stage 2 — canonicalize sheets (with `uses_calculations` back-ref)

**Files:**
- Create: `src/tableau2pbir/stages/_build_sheets.py`
- Modify: `src/tableau2pbir/stages/s02_canonicalize.py`
- Create: `tests/unit/stages/test_s02_sheets.py`

Each raw worksheet becomes a `Sheet`. `uses_calculations` is populated by scanning the sheet's encoded column names against the set of calculation names.

- [x] **Step 19.1: Write failing test**

`tests/unit/stages/test_s02_sheets.py`:

```python
from __future__ import annotations

from tableau2pbir.stages._build_sheets import build_sheets


def test_basic_sheet():
    raw = [{
        "name": "Revenue",
        "datasource_refs": ("sample.csv",),
        "mark_type": "Bar",
        "encodings": {"rows": ("amount",), "columns": ("month",),
                      "color": None, "size": None, "label": None, "tooltip": None,
                      "detail": (), "shape": None, "angle": None},
        "filters": [], "sort": [], "dual_axis": False, "reference_lines": [],
        "quick_table_calcs": [],
    }]
    sheets, qtc_items = build_sheets(raw, calc_names=set(), table_id_for_ref={"sample.csv": "tbl__sample_csv"})
    assert len(sheets) == 1
    s = sheets[0]
    assert s.name == "Revenue"
    assert s.mark_type == "Bar"
    assert len(s.encoding.rows) == 1
    assert s.encoding.rows[0].column_id == "amount"
    assert s.uses_calculations == ()
    assert qtc_items == ()


def test_sheet_uses_calculations_back_ref():
    raw = [{
        "name": "Profit",
        "datasource_refs": ("ds",), "mark_type": "Bar",
        "encodings": {"rows": ("Profit Margin",), "columns": ("month",),
                      "color": None, "size": None, "label": None, "tooltip": None,
                      "detail": (), "shape": None, "angle": None},
        "filters": [], "sort": [], "dual_axis": False, "reference_lines": [],
        "quick_table_calcs": [],
    }]
    sheets, _ = build_sheets(raw, calc_names={"Profit Margin"},
                             table_id_for_ref={"ds": "tbl__ds"})
    assert sheets[0].uses_calculations == ("calc__profit_margin",)


def test_categorical_filter():
    raw = [{
        "name": "f", "datasource_refs": ("ds",), "mark_type": "Bar",
        "encodings": {"rows": (), "columns": (), "color": None, "size": None,
                      "label": None, "tooltip": None, "detail": (),
                      "shape": None, "angle": None},
        "filters": [{"kind": "categorical", "column": "region",
                     "include": ('"West"',), "exclude": (), "expr": None}],
        "sort": [], "dual_axis": False, "reference_lines": [],
        "quick_table_calcs": [],
    }]
    sheets, _ = build_sheets(raw, calc_names=set(), table_id_for_ref={"ds": "tbl__ds"})
    f = sheets[0].filters[0]
    assert f.kind == "categorical"
    assert f.include == ('"West"',)


def test_quick_table_calc_surfaces_deferred_item():
    raw = [{
        "name": "Running", "datasource_refs": ("ds",), "mark_type": "Line",
        "encodings": {"rows": ("amount",), "columns": ("month",),
                      "color": None, "size": None, "label": None, "tooltip": None,
                      "detail": (), "shape": None, "angle": None},
        "filters": [], "sort": [], "dual_axis": False, "reference_lines": [],
        "quick_table_calcs": [{"column": "amount", "type": "running_sum", "compute_using": None}],
    }]
    _, qtc_items = build_sheets(raw, calc_names=set(), table_id_for_ref={"ds": "tbl__ds"})
    assert len(qtc_items) == 1
    assert qtc_items[0].code == "deferred_feature_table_calcs"
    assert "running_sum" in qtc_items[0].source_excerpt
```

- [x] **Step 19.2: Run test — verify failure**

```bash
pytest tests/unit/stages/test_s02_sheets.py -v
```
Expected: `ModuleNotFoundError`.

- [x] **Step 19.3: Write `src/tableau2pbir/stages/_build_sheets.py`**

```python
"""Stage 2 sheet builder. Produces IR Sheets from raw extract worksheets
and surfaces quick-table-calc pill modifiers as deferred-feature
UnsupportedItems (v1 defers table_calc kinds per §16)."""
from __future__ import annotations

from typing import Any

from tableau2pbir.ir.common import FieldRef, UnsupportedItem
from tableau2pbir.ir.sheet import Encoding, Filter, ReferenceLine, Sheet, SortSpec
from tableau2pbir.util.ids import stable_id


def _ref(column_name: str, table_id: str) -> FieldRef:
    return FieldRef(table_id=table_id, column_id=stable_id("", column_name).lstrip("_"))


def _build_encoding(raw_enc: dict[str, Any], table_id: str) -> Encoding:
    def r(name: str | None) -> FieldRef | None:
        return _ref(name, table_id) if name else None
    return Encoding(
        rows=tuple(_ref(n, table_id) for n in raw_enc.get("rows", ())),
        columns=tuple(_ref(n, table_id) for n in raw_enc.get("columns", ())),
        color=r(raw_enc.get("color")),
        size=r(raw_enc.get("size")),
        label=r(raw_enc.get("label")),
        tooltip=r(raw_enc.get("tooltip")),
        detail=tuple(_ref(n, table_id) for n in raw_enc.get("detail", ())),
        shape=r(raw_enc.get("shape")),
        angle=r(raw_enc.get("angle")),
    )


def _build_filter(raw_f: dict[str, Any], sheet_idx: int, filter_idx: int, table_id: str) -> Filter:
    return Filter(
        id=f"filter__s{sheet_idx}_{filter_idx}",
        kind=raw_f["kind"],
        field=_ref(raw_f["column"], table_id),
        include=tuple(raw_f.get("include", ())),
        exclude=tuple(raw_f.get("exclude", ())),
        expr=raw_f.get("expr"),
    )


def _build_sort(raw_sorts: list[dict[str, Any]], table_id: str) -> tuple[SortSpec, ...]:
    return tuple(
        SortSpec(field=_ref(s["column"], table_id), direction=s["direction"])
        for s in raw_sorts
    )


def _build_reference_lines(
    raw_rls: list[dict[str, Any]], sheet_idx: int, table_id: str,
) -> tuple[ReferenceLine, ...]:
    out: list[ReferenceLine] = []
    for idx, rl in enumerate(raw_rls):
        scope = rl.get("scope_column") or ""
        if not scope:
            continue
        value_str = rl.get("value")
        try:
            value_num: float | None = float(value_str) if value_str is not None else None
        except ValueError:
            value_num = None
        out.append(ReferenceLine(
            id=f"refline__s{sheet_idx}_{idx}",
            scope_field=_ref(scope, table_id),
            kind=rl["kind"],
            value=value_num,
            lod_expr=None,
        ))
    return tuple(out)


def build_sheets(
    raw_worksheets: list[dict[str, Any]],
    calc_names: set[str],
    table_id_for_ref: dict[str, str],
) -> tuple[tuple[Sheet, ...], tuple[UnsupportedItem, ...]]:
    sheets: list[Sheet] = []
    qtc_unsupported: list[UnsupportedItem] = []

    for idx, raw in enumerate(raw_worksheets):
        # Resolve the table id — pick the first datasource ref's table as primary.
        ds_refs = raw["datasource_refs"]
        table_id = table_id_for_ref.get(ds_refs[0]) if ds_refs else "tbl__unknown"
        if table_id is None:
            table_id = "tbl__unknown"

        # Back-refs: which calculations this sheet uses (by name match on shelf strings).
        used_names: list[str] = []
        for channel in ("rows", "columns", "detail"):
            for name in raw["encodings"].get(channel, ()):
                if name in calc_names and name not in used_names:
                    used_names.append(name)
        for channel in ("color", "size", "label", "tooltip", "shape", "angle"):
            name = raw["encodings"].get(channel)
            if name and name in calc_names and name not in used_names:
                used_names.append(name)
        uses_calculations = tuple(stable_id("calc", n) for n in used_names)

        filters = tuple(
            _build_filter(f, idx, fi, table_id)
            for fi, f in enumerate(raw["filters"])
        )
        sheet_id = stable_id("sheet", raw["name"])
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
            format=None,
            uses_calculations=uses_calculations,
        ))

        for qtc in raw.get("quick_table_calcs", []):
            qtc_unsupported.append(UnsupportedItem(
                object_kind="calc",
                object_id=f"{sheet_id}__qtc__{qtc['type']}__{stable_id('', qtc['column'])}",
                source_excerpt=f"sheet={raw['name']!r} column={qtc['column']!r} type={qtc['type']!r}",
                reason="Quick table calculation — deferred to v1.1 behind --with-table-calcs.",
                code="deferred_feature_table_calcs",
            ))

    return tuple(sheets), tuple(qtc_unsupported)
```

- [x] **Step 19.4: Wire `build_sheets` into `s02_canonicalize.run`**

Add imports:

```python
from tableau2pbir.stages._build_sheets import build_sheets
```

Extend `run`:

```python
calc_names = {c.name for c in calculations}
table_id_for_ref = {ds.name: tbl.id for ds, tbl in zip(datasources, tables, strict=False)}
sheets, qtc_unsupported = build_sheets(
    input_json.get("worksheets", []),
    calc_names=calc_names,
    table_id_for_ref=table_id_for_ref,
)
```

And use `sheets=sheets` in the `Workbook(...)` call; append `qtc_unsupported` to `unsupported`:

```python
unsupported = ds_unsupported + qtc_unsupported
```

- [x] **Step 19.5: Run tests — verify pass**

```bash
pytest tests/unit/stages/test_s02_sheets.py \
       tests/unit/stages/test_s02_canonicalize.py \
       tests/contract/test_stage2_ir_contract.py -v
```
Expected: all pass.

- [x] **Step 19.6: Commit**

```bash
git add src/tableau2pbir/stages/_build_sheets.py \
        src/tableau2pbir/stages/s02_canonicalize.py \
        tests/unit/stages/test_s02_sheets.py
git commit -m "feat(stage2): canonicalize sheets + quick-table-calc deferred routing"
```

---

## Task 20: Stage 2 — canonicalize dashboards + actions

**Files:**
- Create: `src/tableau2pbir/stages/_build_dashboards.py`
- Modify: `src/tableau2pbir/stages/s02_canonicalize.py`
- Create: `tests/unit/stages/test_s02_dashboards.py`

For Plan 2 we model every dashboard as a single top-level `Container(kind='floating', children=...)` with each raw leaf attached as a `Leaf`. Position preserved from extract. `Leaf.payload` uses the schema dictated by `LeafKind` in spec §5.2: `sheet → {sheet_id}`, `text → {text}`, `filter_card → {field_id}`, etc. Stage 5 (Plan 4) rebuilds the real container tree.

Actions map to `Action` records, resolving `source_sheets` names to sheet ids.

- [ ] **Step 20.1: Write failing test**

`tests/unit/stages/test_s02_dashboards.py`:

```python
from __future__ import annotations

from tableau2pbir.ir.dashboard import (
    ActionKind, ActionTrigger, ContainerKind, Leaf, LeafKind, Position,
)
from tableau2pbir.stages._build_dashboards import build_actions, build_dashboards


def test_single_sheet_dashboard():
    raw = [{
        "name": "Main",
        "size": {"w": 1200, "h": 800, "kind": "exact"},
        "leaves": [{
            "leaf_kind": "sheet",
            "payload": {"sheet_name": "Revenue"},
            "position": {"x": 0, "y": 0, "w": 1200, "h": 800},
            "floating": False,
        }],
    }]
    sheet_id_for_name = {"Revenue": "sheet__revenue"}
    param_id_for_name: dict[str, str] = {}
    field_id_for_name: dict[str, str] = {}
    dashboards = build_dashboards(raw, sheet_id_for_name, param_id_for_name, field_id_for_name)
    assert len(dashboards) == 1
    d = dashboards[0]
    assert d.size.w == 1200
    assert d.size.kind == "exact"
    # Root is a floating container with one sheet leaf.
    assert d.layout_tree.kind == ContainerKind.FLOATING
    assert len(d.layout_tree.children) == 1
    leaf = d.layout_tree.children[0]
    assert isinstance(leaf, Leaf)
    assert leaf.kind == LeafKind.SHEET
    assert leaf.payload["sheet_id"] == "sheet__revenue"
    assert leaf.position == Position(x=0, y=0, w=1200, h=800)


def test_filter_card_resolves_field():
    raw = [{
        "name": "D",
        "size": {"w": 800, "h": 600, "kind": "exact"},
        "leaves": [{
            "leaf_kind": "filter_card",
            "payload": {"field": "region"},
            "position": {"x": 0, "y": 0, "w": 200, "h": 100},
            "floating": False,
        }],
    }]
    dashboards = build_dashboards(
        raw, sheet_id_for_name={}, param_id_for_name={},
        field_id_for_name={"region": "tbl__ds__col__region"},
    )
    leaf = dashboards[0].layout_tree.children[0]
    assert leaf.kind == LeafKind.FILTER_CARD
    assert leaf.payload["field_id"] == "tbl__ds__col__region"


def test_action_resolves_sheet_ids():
    raw = [{
        "name": "a1", "caption": "Filter",
        "kind": "filter", "trigger": "select",
        "source_sheets": ("Revenue",),
        "target_sheets": ("Detail",),
        "clearing_behavior": "keep_filter", "url": None,
    }]
    actions = build_actions(raw, sheet_id_for_name={
        "Revenue": "sheet__revenue", "Detail": "sheet__detail",
    })
    assert len(actions) == 1
    a = actions[0]
    assert a.kind == ActionKind.FILTER
    assert a.trigger == ActionTrigger.SELECT
    assert a.source_sheet_ids == ("sheet__revenue",)
    assert a.target_sheet_ids == ("sheet__detail",)


def test_action_ignores_unknown_sheet_names():
    raw = [{
        "name": "a1", "caption": None, "kind": "highlight", "trigger": "hover",
        "source_sheets": ("Ghost",), "target_sheets": ("Detail",),
        "clearing_behavior": "keep_filter", "url": None,
    }]
    actions = build_actions(raw, sheet_id_for_name={"Detail": "sheet__detail"})
    assert actions[0].source_sheet_ids == ()
    assert actions[0].target_sheet_ids == ("sheet__detail",)
```

- [ ] **Step 20.2: Run test — verify failure**

```bash
pytest tests/unit/stages/test_s02_dashboards.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 20.3: Write `src/tableau2pbir/stages/_build_dashboards.py`**

```python
"""Stage 2 dashboard + action builders."""
from __future__ import annotations

from typing import Any

from tableau2pbir.ir.dashboard import (
    Action, ActionKind, ActionTrigger,
    Container, ContainerKind, Dashboard, DashboardSize,
    Leaf, LeafKind, Position,
)
from tableau2pbir.util.ids import stable_id


def _payload_for_leaf(
    leaf_kind: str,
    raw_payload: dict[str, Any],
    sheet_id_for_name: dict[str, str],
    param_id_for_name: dict[str, str],
    field_id_for_name: dict[str, str],
) -> dict[str, Any]:
    if leaf_kind == "sheet":
        name = raw_payload.get("sheet_name", "")
        return {"sheet_id": sheet_id_for_name.get(name, stable_id("sheet", name))}
    if leaf_kind == "text":
        return {"text": raw_payload.get("text", ""), "format": {}}
    if leaf_kind == "image":
        return {"path": raw_payload.get("path", "")}
    if leaf_kind == "filter_card":
        name = raw_payload.get("field", "")
        return {"field_id": field_id_for_name.get(name, "")}
    if leaf_kind == "parameter_card":
        name = raw_payload.get("parameter_name", "")
        return {"parameter_id": param_id_for_name.get(name, stable_id("param", name))}
    if leaf_kind == "legend":
        name = raw_payload.get("host_sheet_name", "")
        return {"host_sheet_id": sheet_id_for_name.get(name, stable_id("sheet", name))}
    if leaf_kind == "navigation":
        return {"target": raw_payload.get("target", "")}
    return {}


def _leaf_from_raw(
    raw_leaf: dict[str, Any],
    sheet_id_for_name: dict[str, str],
    param_id_for_name: dict[str, str],
    field_id_for_name: dict[str, str],
) -> Leaf:
    pos = raw_leaf["position"]
    return Leaf(
        kind=LeafKind(raw_leaf["leaf_kind"]),
        payload=_payload_for_leaf(
            raw_leaf["leaf_kind"], raw_leaf["payload"],
            sheet_id_for_name, param_id_for_name, field_id_for_name,
        ),
        position=Position(x=pos["x"], y=pos["y"], w=pos["w"], h=pos["h"]),
    )


def build_dashboards(
    raw_dashboards: list[dict[str, Any]],
    sheet_id_for_name: dict[str, str],
    param_id_for_name: dict[str, str],
    field_id_for_name: dict[str, str],
) -> tuple[Dashboard, ...]:
    out: list[Dashboard] = []
    for raw in raw_dashboards:
        leaves = tuple(
            _leaf_from_raw(rl, sheet_id_for_name, param_id_for_name, field_id_for_name)
            for rl in raw["leaves"]
        )
        root = Container(kind=ContainerKind.FLOATING, children=leaves, padding=0, background=None)
        size = raw["size"]
        out.append(Dashboard(
            id=stable_id("dashboard", raw["name"]),
            name=raw["name"],
            size=DashboardSize(w=size["w"], h=size["h"], kind=size["kind"]),
            layout_tree=root,
            actions=(),
        ))
    return tuple(out)


_ACTION_KIND_MAP = {
    "filter":    ActionKind.FILTER,
    "highlight": ActionKind.HIGHLIGHT,
    "url":       ActionKind.URL,
    "parameter": ActionKind.PARAMETER,
}


def _trigger(raw: str) -> ActionTrigger:
    if raw == "hover":
        return ActionTrigger.HOVER
    if raw == "menu":
        return ActionTrigger.MENU
    return ActionTrigger.SELECT


def build_actions(
    raw_actions: list[dict[str, Any]],
    sheet_id_for_name: dict[str, str],
) -> tuple[Action, ...]:
    def resolve(names: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(
            sheet_id_for_name[n]
            for n in names
            if n in sheet_id_for_name
        )

    out: list[Action] = []
    for raw in raw_actions:
        out.append(Action(
            id=stable_id("action", raw["name"]),
            name=raw.get("caption") or raw["name"],
            kind=_ACTION_KIND_MAP[raw["kind"]],
            trigger=_trigger(raw["trigger"]),
            source_sheet_ids=resolve(raw["source_sheets"]),
            target_sheet_ids=resolve(raw["target_sheets"]),
            source_fields=(),           # Plan 3/4 resolves field-level actions.
            target_fields=(),
            clearing_behavior=raw["clearing_behavior"],
        ))
    return tuple(out)
```

- [ ] **Step 20.4: Wire dashboards + actions into `s02_canonicalize.run`**

Add imports:

```python
from tableau2pbir.stages._build_dashboards import build_actions, build_dashboards
```

Extend `run`:

```python
sheet_id_for_name = {raw_ws["name"]: stable_id_sheet(raw_ws["name"])
                     for raw_ws in input_json.get("worksheets", [])}
param_id_for_name = {p.name: p.id for p in parameters}
# Column id lookup by bare name (best-effort — first table wins).
field_id_for_name: dict[str, str] = {}
for tbl in tables:
    for col_id in tbl.column_ids:
        # Extract the slug portion after the last '__col__'
        bare = col_id.split("__col__", 1)[-1] if "__col__" in col_id else col_id
        field_id_for_name.setdefault(bare, col_id)

dashboards = build_dashboards(
    input_json.get("dashboards", []),
    sheet_id_for_name=sheet_id_for_name,
    param_id_for_name=param_id_for_name,
    field_id_for_name=field_id_for_name,
)
actions = build_actions(input_json.get("actions", []), sheet_id_for_name)

# Attach actions to the first dashboard (Plan 2 proxy — Plan 4 routes per-dashboard).
if actions and dashboards:
    dashboards = (dashboards[0].model_copy(update={"actions": actions}), *dashboards[1:])
```

Add helper at top of `s02_canonicalize.py`:

```python
from tableau2pbir.util.ids import stable_id as _sid

def stable_id_sheet(name: str) -> str:
    return _sid("sheet", name)
```

And replace `dashboards=()` → `dashboards=dashboards` in the `Workbook(...)` call.

- [ ] **Step 20.5: Run tests — verify pass**

```bash
pytest tests/unit/stages/test_s02_dashboards.py \
       tests/unit/stages/test_s02_canonicalize.py \
       tests/contract/test_stage2_ir_contract.py -v
```
Expected: all pass.

- [ ] **Step 20.6: Commit**

```bash
git add src/tableau2pbir/stages/_build_dashboards.py \
        src/tableau2pbir/stages/s02_canonicalize.py \
        tests/unit/stages/test_s02_dashboards.py
git commit -m "feat(stage2): canonicalize dashboards (floating root) + actions"
```

---

## Task 21: Stage 2 — calc dependency graph + cycle detection

**Files:**
- Create: `src/tableau2pbir/stages/_calc_graph.py`
- Modify: `src/tableau2pbir/stages/s02_canonicalize.py`
- Create: `tests/unit/stages/test_s02_calc_graph.py`

Cycle detection uses Kahn's algorithm over the `depends_on` edges from task 17. A cycle doesn't halt stage 2 — it appends an `UnsupportedItem` with code `calc_cycle` for each calc in the cycle, and stage 3 (Plan 3) will refuse to translate cyclic calcs.

- [ ] **Step 21.1: Write failing test**

`tests/unit/stages/test_s02_calc_graph.py`:

```python
from __future__ import annotations

from tableau2pbir.ir.calculation import (
    Calculation, CalculationKind, CalculationPhase, CalculationScope,
)
from tableau2pbir.stages._calc_graph import detect_cycles


def _calc(id_: str, name: str, depends_on: tuple[str, ...] = ()) -> Calculation:
    return Calculation(
        id=id_, name=name, scope=CalculationScope.MEASURE,
        tableau_expr="dummy", kind=CalculationKind.ROW,
        phase=CalculationPhase.ROW, depends_on=depends_on,
    )


def test_no_cycle_returns_empty():
    calcs = (
        _calc("c1", "A"),
        _calc("c2", "B", ("c1",)),
        _calc("c3", "C", ("c2",)),
    )
    assert detect_cycles(calcs) == ()


def test_self_loop_detected():
    calcs = (_calc("c1", "A", ("c1",)),)
    items = detect_cycles(calcs)
    assert len(items) == 1
    assert items[0].code == "calc_cycle"
    assert items[0].object_id == "c1"


def test_two_cycle_detected():
    calcs = (
        _calc("c1", "A", ("c2",)),
        _calc("c2", "B", ("c1",)),
    )
    ids = {i.object_id for i in detect_cycles(calcs)}
    assert ids == {"c1", "c2"}


def test_cycle_with_leaves_only_reports_cycle_members():
    calcs = (
        _calc("c1", "A"),
        _calc("c2", "B", ("c3",)),
        _calc("c3", "C", ("c2",)),
        _calc("c4", "D", ("c1",)),
    )
    ids = {i.object_id for i in detect_cycles(calcs)}
    assert ids == {"c2", "c3"}
```

- [ ] **Step 21.2: Run test — verify failure**

```bash
pytest tests/unit/stages/test_s02_calc_graph.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 21.3: Write `src/tableau2pbir/stages/_calc_graph.py`**

```python
"""Calc dependency graph utilities. Kahn-style topo-walk to isolate cycle
members; everything not removed is a cycle member."""
from __future__ import annotations

from collections import defaultdict, deque

from tableau2pbir.ir.calculation import Calculation
from tableau2pbir.ir.common import UnsupportedItem


def detect_cycles(calcs: tuple[Calculation, ...]) -> tuple[UnsupportedItem, ...]:
    """Return an UnsupportedItem for every calc that participates in a cycle."""
    ids = {c.id for c in calcs}
    # Edges are depends_on-restricted to known ids (ignore dangling refs).
    incoming: dict[str, set[str]] = defaultdict(set)
    outgoing: dict[str, set[str]] = defaultdict(set)
    for c in calcs:
        for dep in c.depends_on:
            if dep in ids:
                incoming[c.id].add(dep)
                outgoing[dep].add(c.id)

    queue: deque[str] = deque(cid for cid in ids if not incoming[cid])
    resolved: set[str] = set()
    while queue:
        n = queue.popleft()
        resolved.add(n)
        for m in list(outgoing[n]):
            outgoing[n].discard(m)
            incoming[m].discard(n)
            if not incoming[m]:
                queue.append(m)

    cycle_members = ids - resolved
    out: list[UnsupportedItem] = []
    calc_by_id = {c.id: c for c in calcs}
    for cid in sorted(cycle_members):
        calc = calc_by_id[cid]
        out.append(UnsupportedItem(
            object_kind="calc",
            object_id=cid,
            source_excerpt=calc.tableau_expr[:200],
            reason=f"Calculation {calc.name!r} participates in a dependency cycle.",
            code="calc_cycle",
        ))
    return tuple(out)
```

- [ ] **Step 21.4: Wire `detect_cycles` into `s02_canonicalize.run`**

Add import:

```python
from tableau2pbir.stages._calc_graph import detect_cycles
```

Extend the `unsupported` aggregation:

```python
cycle_items = detect_cycles(calculations)
unsupported = ds_unsupported + qtc_unsupported + cycle_items
```

- [ ] **Step 21.5: Run tests — verify pass**

```bash
pytest tests/unit/stages/test_s02_calc_graph.py \
       tests/unit/stages/test_s02_canonicalize.py \
       tests/contract/test_stage2_ir_contract.py -v
```
Expected: all pass.

- [ ] **Step 21.6: Commit**

```bash
git add src/tableau2pbir/stages/_calc_graph.py \
        src/tableau2pbir/stages/s02_canonicalize.py \
        tests/unit/stages/test_s02_calc_graph.py
git commit -m "feat(stage2): detect calc dependency cycles and emit UnsupportedItems"
```

---

## Task 22: Stage 2 — v1 deferred-feature routing

**Files:**
- Create: `src/tableau2pbir/stages/_deferred_routing.py`
- Modify: `src/tableau2pbir/stages/s02_canonicalize.py`
- Create: `tests/unit/stages/test_s02_deferred_routing.py`

Per §16 "flags gate execution, not detection": for every IR calc whose `kind` is v1-deferred (`table_calc`, `lod_include`, `lod_exclude`), append an `UnsupportedItem` with the appropriate `deferred_feature_*` code. Same for every parameter whose `intent == UNSUPPORTED` — classify root cause (`formatting_control` → `deferred_feature_format_switch`; else `deferred_feature_unsupported_parameter`). Tier-3 datasources are already routed in task 15; tier-4 already in task 15. Stage-1 tier-C detections (passed through in `input_json["unsupported"]`) are lifted as-is.

- [ ] **Step 22.1: Write failing test**

`tests/unit/stages/test_s02_deferred_routing.py`:

```python
from __future__ import annotations

from tableau2pbir.ir.calculation import (
    Calculation, CalculationKind, CalculationPhase, CalculationScope,
    LodRelative, TableCalc, TableCalcFrame, TableCalcFrameType,
)
from tableau2pbir.ir.common import FieldRef, UnsupportedItem
from tableau2pbir.ir.parameter import (
    Parameter, ParameterExposure, ParameterIntent,
)
from tableau2pbir.stages._deferred_routing import (
    lift_tier_c_detections, route_deferred_calcs, route_deferred_parameters,
)


def _tc_calc() -> Calculation:
    return Calculation(
        id="c_tc", name="Running", scope=CalculationScope.MEASURE,
        tableau_expr="RUNNING_SUM(SUM([Sales]))",
        kind=CalculationKind.TABLE_CALC, phase=CalculationPhase.VIZ,
        depends_on=(),
        table_calc=TableCalc(
            partitioning=(), addressing=(), sort=(),
            frame=TableCalcFrame(type=TableCalcFrameType.CUMULATIVE),
            restart_every=None,
        ),
    )


def _lod_include_calc() -> Calculation:
    return Calculation(
        id="c_li", name="Per Customer", scope=CalculationScope.MEASURE,
        tableau_expr="{INCLUDE [Customer]: SUM([Sales])}",
        kind=CalculationKind.LOD_INCLUDE, phase=CalculationPhase.AGGREGATE,
        depends_on=(),
        lod_relative=LodRelative(extra_dims=(FieldRef(table_id="t", column_id="customer"),)),
    )


def test_table_calc_routed_to_deferred():
    items = route_deferred_calcs((_tc_calc(),))
    assert len(items) == 1
    assert items[0].code == "deferred_feature_table_calcs"
    assert items[0].object_id == "c_tc"


def test_lod_include_routed_to_deferred():
    items = route_deferred_calcs((_lod_include_calc(),))
    assert items[0].code == "deferred_feature_lod_relative"


def test_v1_kinds_not_routed():
    ok = Calculation(
        id="c_ok", name="Sum", scope=CalculationScope.MEASURE,
        tableau_expr="SUM([Sales])", kind=CalculationKind.AGGREGATE,
        phase=CalculationPhase.AGGREGATE, depends_on=(),
    )
    assert route_deferred_calcs((ok,)) == ()


def _param(name: str, intent: ParameterIntent) -> Parameter:
    return Parameter(
        id=f"param__{name}", name=name, datatype="string", default="",
        allowed_values=(), intent=intent, exposure=ParameterExposure.CARD,
    )


def test_formatting_control_param_routes_to_format_switch_flag():
    p = _param("fmt", ParameterIntent.FORMATTING_CONTROL)
    items = route_deferred_parameters((p,))
    assert items[0].code == "deferred_feature_format_switch"


def test_unsupported_intent_routes_to_unsupported_parameter():
    p = _param("ghost", ParameterIntent.UNSUPPORTED)
    items = route_deferred_parameters((p,))
    assert items[0].code == "unsupported_parameter"


def test_v1_intents_not_routed():
    params = (
        _param("p1", ParameterIntent.NUMERIC_WHAT_IF),
        _param("p2", ParameterIntent.CATEGORICAL_SELECTOR),
        _param("p3", ParameterIntent.INTERNAL_CONSTANT),
    )
    assert route_deferred_parameters(params) == ()


def test_lift_tier_c_preserves_stage1_detections():
    raw_unsupported = [
        {"object_kind": "story", "object_id": "story__tour",
         "source_excerpt": "<story/>", "reason": "Story points have no PBI equivalent.",
         "code": "unsupported_story_points"},
    ]
    lifted = lift_tier_c_detections(raw_unsupported)
    assert len(lifted) == 1
    assert isinstance(lifted[0], UnsupportedItem)
    assert lifted[0].code == "unsupported_story_points"
```

- [ ] **Step 22.2: Run test — verify failure**

```bash
pytest tests/unit/stages/test_s02_deferred_routing.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 22.3: Write `src/tableau2pbir/stages/_deferred_routing.py`**

```python
"""v1 deferred-feature routing. Stage 2 classifies every object per §5.6 /
§5.7 / §5.8; this module emits the corresponding UnsupportedItem records
with stable `deferred_feature_*` codes so §8.1 (Plan 4) can key off them."""
from __future__ import annotations

from typing import Any

from tableau2pbir.ir.calculation import Calculation, CalculationKind
from tableau2pbir.ir.common import UnsupportedItem
from tableau2pbir.ir.parameter import Parameter, ParameterIntent


_DEFERRED_CALC_KINDS: dict[CalculationKind, str] = {
    CalculationKind.TABLE_CALC:   "deferred_feature_table_calcs",
    CalculationKind.LOD_INCLUDE:  "deferred_feature_lod_relative",
    CalculationKind.LOD_EXCLUDE:  "deferred_feature_lod_relative",
}


def route_deferred_calcs(calcs: tuple[Calculation, ...]) -> tuple[UnsupportedItem, ...]:
    out: list[UnsupportedItem] = []
    for c in calcs:
        code = _DEFERRED_CALC_KINDS.get(c.kind)
        if code is None:
            continue
        out.append(UnsupportedItem(
            object_kind="calc",
            object_id=c.id,
            source_excerpt=c.tableau_expr[:200],
            reason=f"Calculation {c.name!r} uses v1-deferred kind {c.kind.value!r}.",
            code=code,
        ))
    return tuple(out)


def route_deferred_parameters(params: tuple[Parameter, ...]) -> tuple[UnsupportedItem, ...]:
    out: list[UnsupportedItem] = []
    for p in params:
        if p.intent == ParameterIntent.FORMATTING_CONTROL:
            out.append(UnsupportedItem(
                object_kind="parameter",
                object_id=p.id,
                source_excerpt=f"parameter={p.name!r} intent=formatting_control",
                reason="Formatting-control parameters are deferred behind --with-format-switch.",
                code="deferred_feature_format_switch",
            ))
        elif p.intent == ParameterIntent.UNSUPPORTED:
            out.append(UnsupportedItem(
                object_kind="parameter",
                object_id=p.id,
                source_excerpt=f"parameter={p.name!r} default={p.default!r}",
                reason="Parameter shape has no PBI equivalent (§5.7 fallthrough).",
                code="unsupported_parameter",
            ))
    return tuple(out)


def lift_tier_c_detections(
    raw_unsupported: list[dict[str, Any]],
) -> tuple[UnsupportedItem, ...]:
    """Convert stage-1 tier-C raw dicts into IR UnsupportedItems."""
    out: list[UnsupportedItem] = []
    for raw in raw_unsupported:
        out.append(UnsupportedItem(
            object_kind=raw["object_kind"],
            object_id=raw["object_id"],
            source_excerpt=raw["source_excerpt"],
            reason=raw["reason"],
            code=raw["code"],
        ))
    return tuple(out)
```

- [ ] **Step 22.4: Wire deferred routing into `s02_canonicalize.run`**

Add imports:

```python
from tableau2pbir.stages._deferred_routing import (
    lift_tier_c_detections, route_deferred_calcs, route_deferred_parameters,
)
```

Extend the `unsupported` aggregation:

```python
tier_c_items = lift_tier_c_detections(input_json.get("unsupported", []))
deferred_calc_items = route_deferred_calcs(calculations)
deferred_param_items = route_deferred_parameters(parameters)

unsupported = (
    ds_unsupported
    + qtc_unsupported
    + cycle_items
    + tier_c_items
    + deferred_calc_items
    + deferred_param_items
)
```

- [ ] **Step 22.5: Run tests — verify pass**

```bash
pytest tests/unit/stages/test_s02_deferred_routing.py \
       tests/unit/stages/test_s02_canonicalize.py \
       tests/contract/test_stage2_ir_contract.py -v
```
Expected: all pass.

- [ ] **Step 22.6: Commit**

```bash
git add src/tableau2pbir/stages/_deferred_routing.py \
        src/tableau2pbir/stages/s02_canonicalize.py \
        tests/unit/stages/test_s02_deferred_routing.py
git commit -m "feat(stage2): v1 deferred-feature routing to unsupported[] per §16"
```

---

## Task 23: Stage 2 — summary.md generation

**Files:**
- Create: `src/tableau2pbir/stages/_summary.py`
- Modify: `src/tableau2pbir/stages/s02_canonicalize.py`
- Create: `tests/unit/stages/test_s02_summary.py`

Per spec §6 Stage 2 summary requirements: IR object counts by kind; calc kind histogram (row/aggregate/table_calc/lod_*); parameter intent histogram; datasource tier histogram; dependency graph stats; unsupported breakdown.

- [ ] **Step 23.1: Write failing test**

`tests/unit/stages/test_s02_summary.py`:

```python
from __future__ import annotations

from tableau2pbir.ir.calculation import (
    Calculation, CalculationKind, CalculationPhase, CalculationScope,
)
from tableau2pbir.ir.common import UnsupportedItem
from tableau2pbir.ir.datasource import ConnectorTier, Datasource
from tableau2pbir.ir.parameter import Parameter, ParameterExposure, ParameterIntent
from tableau2pbir.stages._summary import render_stage2_summary


def _ds(name: str, tier: ConnectorTier) -> Datasource:
    return Datasource(
        id=f"ds__{name}", name=name, tableau_kind="csv",
        connector_tier=tier, pbi_m_connector="Csv.Document" if tier != ConnectorTier.TIER_4 else None,
        connection_params={}, user_action_required=(), table_ids=(),
        extract_ignored=False,
    )


def _calc(kind: CalculationKind) -> Calculation:
    return Calculation(
        id=f"calc__{kind.value}", name=kind.value, scope=CalculationScope.MEASURE,
        tableau_expr="x", kind=kind, phase=CalculationPhase.AGGREGATE, depends_on=(),
    )


def _param(intent: ParameterIntent) -> Parameter:
    return Parameter(
        id=f"param__{intent.value}", name=intent.value, datatype="string",
        default="", allowed_values=(), intent=intent, exposure=ParameterExposure.CARD,
    )


def test_summary_includes_tier_histogram():
    md = render_stage2_summary(
        datasources=(_ds("a", ConnectorTier.TIER_1), _ds("b", ConnectorTier.TIER_2)),
        calculations=(),
        parameters=(),
        sheets_count=0, dashboards_count=0,
        unsupported=(),
    )
    assert "datasource tier histogram" in md.lower()
    assert "tier 1: 1" in md.lower()
    assert "tier 2: 1" in md.lower()


def test_summary_includes_calc_histogram():
    md = render_stage2_summary(
        datasources=(),
        calculations=(_calc(CalculationKind.ROW), _calc(CalculationKind.AGGREGATE),
                      _calc(CalculationKind.LOD_FIXED)),
        parameters=(), sheets_count=0, dashboards_count=0, unsupported=(),
    )
    assert "row: 1" in md.lower()
    assert "aggregate: 1" in md.lower()
    assert "lod_fixed: 1" in md.lower()


def test_summary_includes_parameter_intent_histogram():
    md = render_stage2_summary(
        datasources=(), calculations=(),
        parameters=(_param(ParameterIntent.NUMERIC_WHAT_IF),
                    _param(ParameterIntent.CATEGORICAL_SELECTOR)),
        sheets_count=0, dashboards_count=0, unsupported=(),
    )
    assert "numeric_what_if: 1" in md.lower()
    assert "categorical_selector: 1" in md.lower()


def test_summary_includes_unsupported_breakdown():
    md = render_stage2_summary(
        datasources=(), calculations=(), parameters=(),
        sheets_count=0, dashboards_count=0,
        unsupported=(UnsupportedItem(
            object_kind="calc", object_id="x",
            source_excerpt="", reason="", code="deferred_feature_table_calcs",
        ),),
    )
    assert "deferred_feature_table_calcs: 1" in md.lower()
```

- [ ] **Step 23.2: Run test — verify failure**

```bash
pytest tests/unit/stages/test_s02_summary.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 23.3: Write `src/tableau2pbir/stages/_summary.py`**

```python
"""Stage 2 summary.md renderer. Stable ordering so golden tests don't flap."""
from __future__ import annotations

from collections import Counter

from tableau2pbir.ir.calculation import Calculation
from tableau2pbir.ir.common import UnsupportedItem
from tableau2pbir.ir.datasource import Datasource
from tableau2pbir.ir.parameter import Parameter


def _histogram(lines: list[str], title: str, counter: Counter) -> None:
    lines.append(f"## {title}")
    lines.append("")
    if not counter:
        lines.append("- (none)")
    else:
        for key in sorted(counter):
            lines.append(f"- {key}: {counter[key]}")
    lines.append("")


def render_stage2_summary(
    *,
    datasources: tuple[Datasource, ...],
    calculations: tuple[Calculation, ...],
    parameters: tuple[Parameter, ...],
    sheets_count: int,
    dashboards_count: int,
    unsupported: tuple[UnsupportedItem, ...],
) -> str:
    lines: list[str] = ["# Stage 2 — canonicalize → IR", ""]

    lines.append("## IR object counts")
    lines.append("")
    lines.append(f"- datasources: {len(datasources)}")
    lines.append(f"- calculations: {len(calculations)}")
    lines.append(f"- parameters: {len(parameters)}")
    lines.append(f"- sheets: {sheets_count}")
    lines.append(f"- dashboards: {dashboards_count}")
    lines.append(f"- unsupported entries: {len(unsupported)}")
    lines.append("")

    tier_counter = Counter(f"Tier {ds.connector_tier.value}" for ds in datasources)
    _histogram(lines, "Datasource tier histogram", tier_counter)

    kind_counter = Counter(c.kind.value for c in calculations)
    _histogram(lines, "Calc kind histogram", kind_counter)

    intent_counter = Counter(p.intent.value for p in parameters)
    _histogram(lines, "Parameter intent histogram", intent_counter)

    code_counter = Counter(item.code for item in unsupported)
    _histogram(lines, "Unsupported breakdown (by code)", code_counter)

    return "\n".join(lines) + "\n"
```

- [ ] **Step 23.4: Wire `render_stage2_summary` into `s02_canonicalize.run`**

Add import:

```python
from tableau2pbir.stages._summary import render_stage2_summary
```

Replace the `summary_md=...` argument with:

```python
summary_md = render_stage2_summary(
    datasources=datasources,
    calculations=calculations,
    parameters=parameters,
    sheets_count=len(sheets),
    dashboards_count=len(dashboards),
    unsupported=unsupported,
)
return StageResult(
    output=wb.model_dump(mode="json"),
    summary_md=summary_md,
    errors=(),
)
```

- [ ] **Step 23.5: Run tests — verify pass**

```bash
pytest tests/unit/stages/test_s02_summary.py \
       tests/unit/stages/test_s02_canonicalize.py \
       tests/contract/test_stage2_ir_contract.py -v
```
Expected: all pass.

- [ ] **Step 23.6: Commit**

```bash
git add src/tableau2pbir/stages/_summary.py \
        src/tableau2pbir/stages/s02_canonicalize.py \
        tests/unit/stages/test_s02_summary.py
git commit -m "feat(stage2): render summary.md with tier/kind/intent/unsupported histograms"
```

---

## Task 24: Synthetic fixtures + end-to-end integration test

**Files:**
- Create: 9 new `.twb` fixtures under `tests/golden/synthetic/`
- Create: `tests/integration/test_stage1_stage2_integration.py`

All fixtures are hand-authored, minimal-XML Tableau workbooks. Each exercises exactly one v1 feature. Downstream plans add the `real/*.twbx` subset.

- [ ] **Step 24.1: Create `tests/golden/synthetic/datasources_mixed.twb`**

```xml
<?xml version='1.0' encoding='utf-8' ?>
<workbook xmlns:user='http://www.tableausoftware.com/xml/user' source-build='2024.1' source-platform='win' version='18.1'>
  <datasources>
    <datasource caption='CSV' name='sample.csv'>
      <connection class='textscan' directory='.' filename='sample.csv' server=''/>
      <column datatype='integer' name='[id]' role='dimension' type='ordinal'/>
    </datasource>
    <datasource caption='SQL' name='orders'>
      <connection class='sqlserver' server='sql1' dbname='Sales'/>
      <column datatype='real' name='[revenue]' role='measure' type='quantitative'/>
    </datasource>
    <datasource caption='Snowflake' name='sf'>
      <connection class='snowflake' server='acct.snowflakecomputing.com' warehouse='WH1'/>
      <column datatype='real' name='[amount]' role='measure' type='quantitative'/>
    </datasource>
  </datasources>
  <worksheets/><dashboards/>
</workbook>
```

- [ ] **Step 24.2: Create `tests/golden/synthetic/datasource_hyper_orphan.twb`**

```xml
<?xml version='1.0' encoding='utf-8' ?>
<workbook source-build='2024.1' version='18.1'>
  <datasources>
    <datasource name='orphan_extract'>
      <connection class='hyper' dbname='Extract/orphan.hyper'/>
      <column datatype='integer' name='[x]' role='dimension'/>
    </datasource>
  </datasources>
  <worksheets/><dashboards/>
</workbook>
```

- [ ] **Step 24.3: Create `tests/golden/synthetic/calc_row.twb`**

```xml
<?xml version='1.0' encoding='utf-8' ?>
<workbook source-build='2024.1' version='18.1'>
  <datasources>
    <datasource name='ds'>
      <connection class='textscan' filename='x.csv'/>
      <column datatype='real' name='[Revenue]' role='measure'/>
      <column datatype='real' name='[Cost]' role='measure'/>
      <column datatype='real' name='[Profit]' role='measure'>
        <calculation class='tableau' formula='[Revenue] - [Cost]'/>
      </column>
    </datasource>
  </datasources>
  <worksheets/><dashboards/>
</workbook>
```

- [ ] **Step 24.4: Create `tests/golden/synthetic/calc_aggregate.twb`**

```xml
<?xml version='1.0' encoding='utf-8' ?>
<workbook source-build='2024.1' version='18.1'>
  <datasources>
    <datasource name='ds'>
      <connection class='textscan' filename='x.csv'/>
      <column datatype='real' name='[Sales]' role='measure'/>
      <column datatype='real' name='[Total Sales]' role='measure'>
        <calculation class='tableau' formula='SUM([Sales])'/>
      </column>
    </datasource>
  </datasources>
  <worksheets/><dashboards/>
</workbook>
```

- [ ] **Step 24.5: Create `tests/golden/synthetic/calc_lod_fixed.twb`**

```xml
<?xml version='1.0' encoding='utf-8' ?>
<workbook source-build='2024.1' version='18.1'>
  <datasources>
    <datasource name='ds'>
      <connection class='textscan' filename='x.csv'/>
      <column datatype='string' name='[Region]' role='dimension'/>
      <column datatype='real' name='[Sales]' role='measure'/>
      <column datatype='real' name='[Sales By Region]' role='measure'>
        <calculation class='tableau' formula='{FIXED [Region]: SUM([Sales])}'/>
      </column>
    </datasource>
  </datasources>
  <worksheets/><dashboards/>
</workbook>
```

- [ ] **Step 24.6: Create `tests/golden/synthetic/calc_lod_include.twb`**

```xml
<?xml version='1.0' encoding='utf-8' ?>
<workbook source-build='2024.1' version='18.1'>
  <datasources>
    <datasource name='ds'>
      <connection class='textscan' filename='x.csv'/>
      <column datatype='string' name='[Customer]' role='dimension'/>
      <column datatype='real' name='[Sales]' role='measure'/>
      <column datatype='real' name='[Sales With Customer]' role='measure'>
        <calculation class='tableau' formula='{INCLUDE [Customer]: SUM([Sales])}'/>
      </column>
    </datasource>
  </datasources>
  <worksheets/><dashboards/>
</workbook>
```

- [ ] **Step 24.7: Create `tests/golden/synthetic/calc_quick_table.twb`**

```xml
<?xml version='1.0' encoding='utf-8' ?>
<workbook source-build='2024.1' version='18.1'>
  <datasources>
    <datasource name='ds'>
      <connection class='textscan' filename='x.csv'/>
      <column datatype='integer' name='[month]' role='dimension' type='ordinal'/>
      <column datatype='real' name='[amount]' role='measure' type='quantitative'/>
    </datasource>
  </datasources>
  <worksheets>
    <worksheet name='Running'>
      <view>
        <datasources><datasource name='ds'/></datasources>
        <rows>[amount]</rows>
        <columns>[month]</columns>
        <pane><mark class='Line'/></pane>
        <table-calculations>
          <table-calculation column='[amount]' type='running_sum'/>
        </table-calculations>
      </view>
    </worksheet>
  </worksheets>
  <dashboards/>
</workbook>
```

- [ ] **Step 24.8: Create `tests/golden/synthetic/params_all_intents.twb`**

```xml
<?xml version='1.0' encoding='utf-8' ?>
<workbook source-build='2024.1' version='18.1'>
  <datasources>
    <datasource name='Parameters' hasconnection='false'>
      <column caption='Discount' datatype='real' name='[Parameter 1]'
              param-domain-type='range' role='measure' value='0.1'>
        <calculation class='tableau' formula='0.1'/>
        <range granularity='0.05' max='0.5' min='0.0'/>
      </column>
      <column caption='Region' datatype='string' name='[Parameter 2]'
              param-domain-type='list' role='dimension' value='&quot;West&quot;'>
        <calculation class='tableau' formula='&quot;West&quot;'/>
        <members>
          <member value='&quot;West&quot;'/>
          <member value='&quot;East&quot;'/>
        </members>
      </column>
      <column caption='AxisMax' datatype='integer' name='[Parameter 3]'
              param-domain-type='any' role='measure' value='100'>
        <calculation class='tableau' formula='100'/>
      </column>
    </datasource>
    <datasource name='ds'>
      <connection class='textscan' filename='x.csv'/>
      <column datatype='real' name='[Sales]' role='measure'/>
    </datasource>
  </datasources>
  <worksheets/>
  <dashboards>
    <dashboard name='Main'>
      <size maxheight='800' maxwidth='1200' minheight='800' minwidth='1200'/>
      <zones>
        <zone type='parameter' id='1' h='50' w='300' x='0' y='0' param='[Parameter 1]'/>
        <zone type='parameter' id='2' h='50' w='300' x='300' y='0' param='[Parameter 2]'/>
      </zones>
    </dashboard>
  </dashboards>
</workbook>
```

Note: `Parameter 3` has no parameter-card zone → Stage 2 classifies it as `internal_constant`.

- [ ] **Step 24.9: Create `tests/golden/synthetic/dashboard_tiled_floating.twb`**

```xml
<?xml version='1.0' encoding='utf-8' ?>
<workbook source-build='2024.1' version='18.1'>
  <datasources>
    <datasource name='ds'>
      <connection class='textscan' filename='x.csv'/>
      <column datatype='integer' name='[id]' role='dimension'/>
    </datasource>
  </datasources>
  <worksheets>
    <worksheet name='Revenue'>
      <view><datasources><datasource name='ds'/></datasources>
        <pane><mark class='Bar'/></pane></view>
    </worksheet>
    <worksheet name='Detail'>
      <view><datasources><datasource name='ds'/></datasources>
        <pane><mark class='Bar'/></pane></view>
    </worksheet>
  </worksheets>
  <dashboards>
    <dashboard name='Mixed'>
      <size maxheight='768' maxwidth='1366' minheight='768' minwidth='1366'/>
      <zones>
        <zone name='Revenue' type='worksheet' id='1' h='500' w='1366' x='0' y='0'/>
        <zone name='Detail' type='worksheet' id='2' h='200' w='500' x='100' y='200' floating='true'/>
      </zones>
    </dashboard>
  </dashboards>
</workbook>
```

- [ ] **Step 24.10: Create `tests/golden/synthetic/action_filter.twb`**

```xml
<?xml version='1.0' encoding='utf-8' ?>
<workbook source-build='2024.1' version='18.1'>
  <datasources>
    <datasource name='ds'>
      <connection class='textscan' filename='x.csv'/>
      <column datatype='integer' name='[id]' role='dimension'/>
    </datasource>
  </datasources>
  <worksheets>
    <worksheet name='Revenue'><view><datasources><datasource name='ds'/></datasources><pane><mark class='Bar'/></pane></view></worksheet>
    <worksheet name='Detail'><view><datasources><datasource name='ds'/></datasources><pane><mark class='Bar'/></pane></view></worksheet>
  </worksheets>
  <dashboards>
    <dashboard name='Main'>
      <size maxheight='768' maxwidth='1366' minheight='768' minwidth='1366'/>
      <zones>
        <zone name='Revenue' type='worksheet' id='1' h='400' w='1366' x='0' y='0'/>
        <zone name='Detail' type='worksheet' id='2' h='368' w='1366' x='0' y='400'/>
      </zones>
      <actions>
        <filter-action caption='By Region' name='a1' trigger='select' clearing-behavior='keep-filter'>
          <source><worksheet>Revenue</worksheet></source>
          <target><worksheet>Detail</worksheet></target>
        </filter-action>
        <highlight-action caption='Hover' name='a2' trigger='hover'>
          <source><worksheet>Revenue</worksheet></source>
          <target><worksheet>Detail</worksheet></target>
        </highlight-action>
      </actions>
    </dashboard>
  </dashboards>
</workbook>
```

- [ ] **Step 24.11: Write the end-to-end integration test**

`tests/integration/test_stage1_stage2_integration.py`:

```python
"""Runs the Stage 1 + Stage 2 pipeline against each Plan-2 synthetic fixture
and asserts v1-scope IR shape. Stages 3–8 run as no-op stubs."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tableau2pbir.ir.version import IR_SCHEMA_VERSION


def _run_convert(fixture: Path, out: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "tableau2pbir.cli", "convert",
         str(fixture), "--out", str(out)],
        capture_output=True, text=True,
    )


def _load_ir(out: Path, wb_name: str) -> dict:
    path = out / wb_name / "stages" / "02_canonicalize.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.integration
def test_trivial_fixture_still_works(tmp_path: Path, synthetic_fixtures_dir: Path):
    out = tmp_path / "out"
    result = _run_convert(synthetic_fixtures_dir / "trivial.twb", out)
    assert result.returncode == 0, result.stderr
    ir = _load_ir(out, "trivial")
    assert ir["ir_schema_version"] == IR_SCHEMA_VERSION
    assert len(ir["data_model"]["datasources"]) == 1
    assert len(ir["sheets"]) == 1
    assert len(ir["dashboards"]) == 1


@pytest.mark.integration
def test_datasources_mixed_tiers(tmp_path: Path, synthetic_fixtures_dir: Path):
    out = tmp_path / "out"
    result = _run_convert(synthetic_fixtures_dir / "datasources_mixed.twb", out)
    assert result.returncode == 0, result.stderr
    ir = _load_ir(out, "datasources_mixed")
    tiers = sorted(ds["connector_tier"] for ds in ir["data_model"]["datasources"])
    # Tier 1 (csv + sqlserver) + Tier 2 (snowflake)
    assert tiers == [1, 1, 2]


@pytest.mark.integration
def test_hyper_orphan_forces_tier_4(tmp_path: Path, synthetic_fixtures_dir: Path):
    out = tmp_path / "out"
    result = _run_convert(synthetic_fixtures_dir / "datasource_hyper_orphan.twb", out)
    assert result.returncode == 0, result.stderr
    ir = _load_ir(out, "datasource_hyper_orphan")
    ds = ir["data_model"]["datasources"][0]
    assert ds["connector_tier"] == 4
    assert ds["pbi_m_connector"] is None
    codes = [u["code"] for u in ir["unsupported"]]
    assert "unsupported_datasource_tier_4" in codes


@pytest.mark.integration
@pytest.mark.parametrize("fixture,expected_kind", [
    ("calc_row.twb", "row"),
    ("calc_aggregate.twb", "aggregate"),
    ("calc_lod_fixed.twb", "lod_fixed"),
    ("calc_lod_include.twb", "lod_include"),
])
def test_calc_kind_classification(
    tmp_path: Path, synthetic_fixtures_dir: Path,
    fixture: str, expected_kind: str,
):
    out = tmp_path / "out"
    result = _run_convert(synthetic_fixtures_dir / fixture, out)
    assert result.returncode == 0, result.stderr
    wb_name = Path(fixture).stem
    ir = _load_ir(out, wb_name)
    calcs = ir["data_model"]["calculations"]
    assert len(calcs) >= 1
    kinds = {c["kind"] for c in calcs}
    assert expected_kind in kinds


@pytest.mark.integration
def test_lod_include_routed_to_deferred(tmp_path: Path, synthetic_fixtures_dir: Path):
    out = tmp_path / "out"
    _run_convert(synthetic_fixtures_dir / "calc_lod_include.twb", out)
    ir = _load_ir(out, "calc_lod_include")
    codes = [u["code"] for u in ir["unsupported"]]
    assert "deferred_feature_lod_relative" in codes


@pytest.mark.integration
def test_quick_table_calc_routed_to_deferred(tmp_path: Path, synthetic_fixtures_dir: Path):
    out = tmp_path / "out"
    _run_convert(synthetic_fixtures_dir / "calc_quick_table.twb", out)
    ir = _load_ir(out, "calc_quick_table")
    codes = [u["code"] for u in ir["unsupported"]]
    assert "deferred_feature_table_calcs" in codes


@pytest.mark.integration
def test_all_parameter_intents(tmp_path: Path, synthetic_fixtures_dir: Path):
    out = tmp_path / "out"
    _run_convert(synthetic_fixtures_dir / "params_all_intents.twb", out)
    ir = _load_ir(out, "params_all_intents")
    intents = {p["intent"] for p in ir["data_model"]["parameters"]}
    assert "numeric_what_if" in intents
    assert "categorical_selector" in intents
    assert "internal_constant" in intents


@pytest.mark.integration
def test_dashboard_leaves_include_floating(tmp_path: Path, synthetic_fixtures_dir: Path):
    out = tmp_path / "out"
    _run_convert(synthetic_fixtures_dir / "dashboard_tiled_floating.twb", out)
    ir = _load_ir(out, "dashboard_tiled_floating")
    d = ir["dashboards"][0]
    assert d["size"]["kind"] == "exact"
    # Root container's children — one tiled + one floating leaf; both carry positions.
    children = d["layout_tree"]["children"]
    assert len(children) == 2
    positions = [c["position"] for c in children]
    assert {"x": 100, "y": 200, "w": 500, "h": 200} in positions


@pytest.mark.integration
def test_actions_resolved_to_sheet_ids(tmp_path: Path, synthetic_fixtures_dir: Path):
    out = tmp_path / "out"
    _run_convert(synthetic_fixtures_dir / "action_filter.twb", out)
    ir = _load_ir(out, "action_filter")
    actions = ir["dashboards"][0]["actions"]
    assert len(actions) == 2
    kinds = {a["kind"] for a in actions}
    assert kinds == {"filter", "highlight"}
    filter_action = next(a for a in actions if a["kind"] == "filter")
    assert filter_action["source_sheet_ids"] == ["sheet__revenue"]
    assert filter_action["target_sheet_ids"] == ["sheet__detail"]
```

- [ ] **Step 24.12: Run the integration test**

```bash
pytest tests/integration/test_stage1_stage2_integration.py -v
```
Expected: all parametrized + individual cases pass (roughly 13 integration tests).

- [ ] **Step 24.13: Run the full suite**

```bash
pytest -q
```
Expected: the full suite is green — Plan-1 tests + Plan-2 unit + contract + integration.

- [ ] **Step 24.14: Verify make targets**

```bash
make lint
make typecheck
make schema
git diff --stat schemas/
```
Expected: lint clean, typecheck clean on `src/`, `schemas/ir-v1.0.0.schema.json` diff empty (IR types unchanged).

- [ ] **Step 24.15: Commit fixtures + integration tests**

```bash
git add tests/golden/synthetic/datasources_mixed.twb \
        tests/golden/synthetic/datasource_hyper_orphan.twb \
        tests/golden/synthetic/calc_row.twb \
        tests/golden/synthetic/calc_aggregate.twb \
        tests/golden/synthetic/calc_lod_fixed.twb \
        tests/golden/synthetic/calc_lod_include.twb \
        tests/golden/synthetic/calc_quick_table.twb \
        tests/golden/synthetic/params_all_intents.twb \
        tests/golden/synthetic/dashboard_tiled_floating.twb \
        tests/golden/synthetic/action_filter.twb \
        tests/integration/test_stage1_stage2_integration.py
git commit -m "test(golden): v1-scope synthetic fixtures + stage1+2 integration tests"
```

---

## Plan 2 acceptance — done when all true

- [ ] `pytest -q` green across Plan-1 and Plan-2 tests.
- [ ] `make lint` clean.
- [ ] `make typecheck` clean on `src/`.
- [ ] `make schema` yields an unchanged `schemas/ir-v1.0.0.schema.json` (no IR field changes in Plan 2).
- [ ] `tableau2pbir convert tests/golden/synthetic/trivial.twb --out ./out/` exits 0; `out/trivial/stages/01_extract.json` and `02_canonicalize.json` are populated (not the Plan-1 stub shape).
- [ ] `02_canonicalize.json` validates against `schemas/ir-v1.0.0.schema.json` for every Plan-2 synthetic fixture.
- [ ] Every Plan-2 synthetic fixture converts end-to-end without crashing; stages 3–8 remain no-op stubs; the pipeline still writes all 8 stage JSONs plus the placeholder `.pbip` and `unsupported.json`.
- [ ] Connector tier classification correct for CSV (Tier 1), SQL Server (Tier 1), Snowflake (Tier 2), orphan hyper (Tier 4).
- [ ] Calc kind classification correct for row / aggregate / lod_fixed / lod_include.
- [ ] Parameter intent classification correct for numeric_what_if / categorical_selector / internal_constant.
- [ ] Deferred features (LOD INCLUDE/EXCLUDE, table calcs, Tier 3 connectors, formatting_control parameters) populate `Workbook.unsupported[]` with stable `deferred_feature_*` codes — detection ships, execution defers.
- [ ] `git log --oneline` shows roughly one commit per task, no batched commits.
- [ ] Plan table in `CLAUDE.md` updated: Plan 2 → ✅ DONE, Plan 3 → 🔲 NEXT.

## Next plan

Plan 3 — Stage 3 (translate calcs) + Stage 4 (map visuals). Starts against the IR produced here: calc rule library for `row` / `aggregate` / `lod_fixed`, DAX syntax gate, LLMClient wired with prompt folders from Plan 1, AI snapshot harness on `tests/llm_snapshots/translate_calc/` + `map_visual/`, §9 layer iv-c probes wired to `tests/validity/dax_semantic/`.

