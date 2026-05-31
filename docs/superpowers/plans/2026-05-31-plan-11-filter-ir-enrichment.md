# Filter IR Enrichment & Schema-Compliant Emission — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use **superpowers:subagent-driven-development** to implement this plan. A fresh subagent is dispatched per task with review between tasks. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix three schema violations in PBIR filter emission, enrich the IR `Filter` model into a Pydantic v2 discriminated union, bundle 5 missing Microsoft semantic-query schemas, and wire `RefResolver` so the JSON schema validator can fully validate `filterConfig` bodies.

**Architecture:** Each layer is touched once in dependency order — schemas first, then validator, then IR, then extract, then canonicalize, then emit. Each task is self-contained: failing test → implementation → green → commit → E2E gate.

**Tech Stack:** Python 3.11, Pydantic v2, `jsonschema` (Draft7Validator + RefResolver), lxml, pytest.

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Create | `src/tableau2pbir/validate/_schemas/semanticQuery-1.0.0.json` | Semantic query expressions (visualContainer 1.0.0) |
| Create | `src/tableau2pbir/validate/_schemas/semanticQuery-1.2.0.json` | Semantic query expressions (filterConfig 1.1.0) |
| Create | `src/tableau2pbir/validate/_schemas/semanticQuery-1.4.0.json` | Semantic query expressions (filterConfig 1.3.0) |
| Create | `src/tableau2pbir/validate/_schemas/filterConfiguration-1.1.0.json` | Filter body schema (visualContainer 2.0.0) |
| Create | `src/tableau2pbir/validate/_schemas/filterConfiguration-1.3.0.json` | Filter body schema (page 2.1.0) |
| Modify | `src/tableau2pbir/validate/_schemas/manifest.json` | Add 5 new URL→filename entries |
| Modify | `src/tableau2pbir/validate/refresh_schemas.py` | No code change — manifest drives it |
| Modify | `src/tableau2pbir/validate/json_schema.py` | Build RefResolver store from manifest |
| Modify | `src/tableau2pbir/ir/sheet.py` | Replace `Filter` class with discriminated union |
| Modify | `src/tableau2pbir/extract/worksheets.py` | Class-to-kind mapping; range/topN XML fields |
| Modify | `src/tableau2pbir/stages/_build_sheets.py` | Filter factory; TopN/Conditional UnsupportedItems |
| Modify | `src/tableau2pbir/emit/pbir/filters.py` | Full rewrite; `_format_literal`; per-kind emit |
| Modify | `tests/unit/ir/test_sheet.py` | `Filter(kind=…)` → typed subclass constructors |
| Modify | `tests/unit/emit/pbir/test_filters.py` | `Filter(kind=…)` → typed subclass constructors |
| Create | `tests/unit/validate/test_refresolver.py` | RefResolver resolves nested $ref |
| Create | `tests/unit/extract/test_extract_filters.py` | Class-to-kind mapping; XML field capture |
| Create | `tests/unit/stages/test_build_sheets_filters.py` | Factory dispatch; UnsupportedItem recording |
| Create | `tests/unit/emit/pbir/test_filter_literal.py` | `_format_literal` conversion cases |
| Create | `tests/unit/emit/pbir/test_filters_emit.py` | Per-kind emit; None returns; field/Where structure |

---

## Task 1 — Bundle 5 missing schemas + update manifest

**Files:**
- Create: `src/tableau2pbir/validate/_schemas/semanticQuery-1.0.0.json`
- Create: `src/tableau2pbir/validate/_schemas/semanticQuery-1.2.0.json`
- Create: `src/tableau2pbir/validate/_schemas/semanticQuery-1.4.0.json`
- Create: `src/tableau2pbir/validate/_schemas/filterConfiguration-1.1.0.json`
- Create: `src/tableau2pbir/validate/_schemas/filterConfiguration-1.3.0.json`
- Modify: `src/tableau2pbir/validate/_schemas/manifest.json`

- [x] **Step 1: Fetch and save the 5 schemas from Microsoft CDN**

Run this Python script from the repo root (requires internet access):

```python
# run as: python scripts/fetch_bundled_schemas.py
import json, urllib.request
from pathlib import Path

BASE = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition"
DEST = Path("src/tableau2pbir/validate/_schemas")

SCHEMAS = [
    ("semanticQuery/1.0.0/schema.json",                   "semanticQuery-1.0.0.json"),
    ("semanticQuery/1.2.0/schema.json",                   "semanticQuery-1.2.0.json"),
    ("semanticQuery/1.4.0/schema.json",                   "semanticQuery-1.4.0.json"),
    ("filterConfiguration/1.1.0/schema-embedded.json",    "filterConfiguration-1.1.0.json"),
    ("filterConfiguration/1.3.0/schema-embedded.json",    "filterConfiguration-1.3.0.json"),
]

for rel, filename in SCHEMAS:
    url = f"{BASE}/{rel}"
    print(f"Fetching {filename}...", end=" ")
    with urllib.request.urlopen(url) as r:
        content = r.read()
    # Pretty-print for readability and consistent diffs
    parsed = json.loads(content)
    (DEST / filename).write_text(json.dumps(parsed, indent=2), encoding="utf-8")
    print("ok")
```

Save this as `scripts/fetch_bundled_schemas.py`, then run:
```
python scripts/fetch_bundled_schemas.py
```

Expected output: 5 lines each ending `ok`.

- [x] **Step 2: Verify all 5 files exist and are valid JSON**

```
python -c "
import json
from pathlib import Path
d = Path('src/tableau2pbir/validate/_schemas')
for f in ['semanticQuery-1.0.0.json','semanticQuery-1.2.0.json',
          'semanticQuery-1.4.0.json','filterConfiguration-1.1.0.json',
          'filterConfiguration-1.3.0.json']:
    schema = json.loads((d/f).read_text())
    print(f, 'keys:', list(schema.keys())[:3])
"
```

Expected: each file prints its top-level keys (should include `$id`, `$schema`, `definitions` or similar).

- [x] **Step 3: Update manifest.json — add 5 new entries**

Open `src/tableau2pbir/validate/_schemas/manifest.json`. The file currently has a `"schemas"` array with 7 entries. Append these 5 entries to the array:

```json
{
  "url": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/semanticQuery/1.0.0/schema.json",
  "file": "semanticQuery-1.0.0.json",
  "description": "Semantic query expressions — referenced by visualContainer 1.0.0 filterConfig"
},
{
  "url": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/semanticQuery/1.2.0/schema.json",
  "file": "semanticQuery-1.2.0.json",
  "description": "Semantic query expressions — referenced by filterConfiguration 1.1.0"
},
{
  "url": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/semanticQuery/1.4.0/schema.json",
  "file": "semanticQuery-1.4.0.json",
  "description": "Semantic query expressions — referenced by filterConfiguration 1.3.0"
},
{
  "url": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/filterConfiguration/1.1.0/schema-embedded.json",
  "file": "filterConfiguration-1.1.0.json",
  "description": "Filter configuration — referenced by visualContainer 2.0.0"
},
{
  "url": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/filterConfiguration/1.3.0/schema-embedded.json",
  "file": "filterConfiguration-1.3.0.json",
  "description": "Filter configuration — referenced by page 2.1.0"
}
```

The manifest now has 12 entries total.

- [x] **Step 4: Verify manifest has 12 entries**

```
python -c "
import json
from pathlib import Path
m = json.loads(Path('src/tableau2pbir/validate/_schemas/manifest.json').read_text())
print(len(m['schemas']), 'entries')
for e in m['schemas']: print(' ', e['file'])
"
```

Expected: `12 entries` followed by 12 filenames.

- [x] **Step 5: Run existing schema cache tests — they must still pass**

```
pytest tests/unit/validate/test_schema_cache.py tests/unit/validate/test_refresh_schemas.py -v
```

Expected: all pass. No changes to those files were needed — `refresh_schemas.py` already reads from the manifest, so it will pick up the 5 new URLs automatically on next run.

- [x] **Step 6: Run E2E gate**

```
pytest tests/integration/test_real_workbooks_e2e.py -v
```

Expected: all pass (no production code changed yet).

- [x] **Step 7: Commit**

```
git add src/tableau2pbir/validate/_schemas/ scripts/fetch_bundled_schemas.py
git commit -m "feat(schemas): bundle semanticQuery 1.0/1.2/1.4 and filterConfiguration 1.1/1.3"
```

---

## Task 2 — Wire RefResolver in json_schema.py

**Files:**
- Modify: `src/tableau2pbir/validate/json_schema.py`
- Create: `tests/unit/validate/test_refresolver.py`

Background: `json_schema.py` currently calls `Draft7Validator(schema).validate(instance)` without a resolver, so `$ref` links inside schemas (e.g. `filterConfig → semanticQuery`) silently resolve to nothing. We need to pre-populate a `RefResolver` store keyed on the manifest URL (which matches what `$ref` resolves to) so cross-schema references validate correctly.

- [x] **Step 1: Write the failing test**

Create `tests/unit/validate/test_refresolver.py`:

```python
"""Tests that run_json_schema resolves nested $ref links via RefResolver."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tableau2pbir.validate.json_schema import run_json_schema
from tableau2pbir.validate.results import ValidatorOutcome

# Minimal schema that references a sibling definition via $ref
_OUTER_URL = "https://example.com/outer/1.0.0/schema.json"
_INNER_URL = "https://example.com/inner/1.0.0/schema.json"

_INNER_SCHEMA = {
    "$id": _INNER_URL,
    "$schema": "http://json-schema.org/draft-07/schema#",
    "definitions": {
        "Name": {
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
            "additionalProperties": False,
        }
    },
}

_OUTER_SCHEMA = {
    "$id": _OUTER_URL,
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "$schema": {"type": "string"},
        "name": {"$ref": f"{_INNER_URL}#/definitions/Name"},
    },
    "required": ["$schema", "name"],
    "additionalProperties": False,
}


def _setup(tmp_path: Path) -> tuple[Path, Path, Path]:
    out_dir = tmp_path / "output"
    out_dir.mkdir()
    bundled = tmp_path / "bundled"
    bundled.mkdir()
    manifest = {
        "schemas": [
            {"url": _OUTER_URL, "file": "outer-1.0.0.json", "description": "outer"},
            {"url": _INNER_URL, "file": "inner-1.0.0.json", "description": "inner"},
        ]
    }
    (bundled / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (bundled / "outer-1.0.0.json").write_text(json.dumps(_OUTER_SCHEMA), encoding="utf-8")
    (bundled / "inner-1.0.0.json").write_text(json.dumps(_INNER_SCHEMA), encoding="utf-8")
    user_cache = tmp_path / "cache"
    user_cache.mkdir()
    return out_dir, bundled, user_cache


def test_ref_resolved_valid_passes(tmp_path: Path) -> None:
    out_dir, bundled, user_cache = _setup(tmp_path)
    (out_dir / "good.json").write_text(
        json.dumps({"$schema": _OUTER_URL, "name": {"value": "hello"}}),
        encoding="utf-8",
    )
    result = run_json_schema(out_dir, cache_dir=user_cache, _bundled_dir=bundled)
    assert result.outcome == ValidatorOutcome.PASSED


def test_ref_resolved_invalid_fails(tmp_path: Path) -> None:
    out_dir, bundled, user_cache = _setup(tmp_path)
    # name.value must be a string but we pass an int — caught only if $ref resolves
    (out_dir / "bad.json").write_text(
        json.dumps({"$schema": _OUTER_URL, "name": {"value": 42}}),
        encoding="utf-8",
    )
    result = run_json_schema(out_dir, cache_dir=user_cache, _bundled_dir=bundled)
    assert result.outcome == ValidatorOutcome.FAILED
    assert any("value" in f.message for f in result.findings)
```

- [x] **Step 2: Run the test — verify it fails**

```
pytest tests/unit/validate/test_refresolver.py -v
```

Expected: `test_ref_resolved_invalid_fails` FAILS (the invalid value passes because $ref is not resolved).

- [x] **Step 3: Update json_schema.py to build and use RefResolver**

In `src/tableau2pbir/validate/json_schema.py`, replace the `run_json_schema` function body. The only change is how the validator is constructed — add a `_build_resolver` helper and use it:

```python
"""JSON schema validation against official Microsoft PBIR schemas. See spec §5."""
from __future__ import annotations

import json
import os
from pathlib import Path

import jsonschema

from tableau2pbir.validate.results import (
    SchemaFinding,
    SchemaValidationResult,
    ValidatorOutcome,
)

_BUNDLED_DIR = Path(__file__).parent / "_schemas"
_SKIP_DIRS = frozenset({"validation", "stages"})


def _load_manifest(bundled_dir: Path) -> dict[str, str]:
    """Return {url: filename} from manifest.json in bundled_dir."""
    data = json.loads((bundled_dir / "manifest.json").read_text(encoding="utf-8"))
    return {entry["url"]: entry["file"] for entry in data["schemas"]}


def _resolve_schema(url: str, cache_dir: Path, bundled_dir: Path) -> dict[str, object] | None:
    """Return schema dict from user cache or bundled fallback. None if unavailable."""
    manifest = _load_manifest(bundled_dir)
    filename = manifest.get(url)
    if filename is None:
        return None
    for search_dir in (cache_dir, bundled_dir):
        candidate = search_dir / filename
        if candidate.is_file():
            return json.loads(candidate.read_text(encoding="utf-8"))  # type: ignore[return-value]
    return None


def _build_resolver(
    manifest: dict[str, str], cache_dir: Path, bundled_dir: Path
) -> jsonschema.RefResolver:
    """Build a RefResolver whose store is keyed on manifest URLs.

    Manifest URLs match what $ref links resolve to (the hyphenated form for
    filterConfiguration schemas). The $id inside those files uses a dot form —
    these are different strings, so we key on the manifest URL, not $id.
    """
    store: dict[str, object] = {}
    for url, filename in manifest.items():
        for search_dir in (cache_dir, bundled_dir):
            candidate = search_dir / filename
            if candidate.is_file():
                store[url] = json.loads(candidate.read_text(encoding="utf-8"))
                break
    return jsonschema.RefResolver(base_uri="", referrer={}, store=store)


def _default_cache_dir() -> Path:
    env = os.environ.get("T2P_SCHEMA_CACHE")
    return Path(env) if env else Path.home() / ".cache" / "tableau2pbir" / "schemas"


def run_json_schema(
    out_dir: Path,
    cache_dir: Path | None = None,
    _bundled_dir: Path = _BUNDLED_DIR,
) -> SchemaValidationResult:
    """Walk all *.json under out_dir and validate files that declare $schema."""
    if cache_dir is None:
        cache_dir = _default_cache_dir()
    manifest = _load_manifest(_bundled_dir)
    resolver = _build_resolver(manifest, cache_dir, _bundled_dir)
    findings: list[SchemaFinding] = []

    for json_file in sorted(out_dir.rglob("*.json")):
        rel_parts = json_file.relative_to(out_dir).parts
        if rel_parts[0] in _SKIP_DIRS:
            continue
        try:
            data: dict[str, object] = json.loads(json_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(data, dict):
            continue
        url = data.get("$schema")
        if not isinstance(url, str):
            continue
        if url not in manifest:
            findings.append(SchemaFinding(
                code="schema.not_cached",
                severity="warn",
                message=f"$schema URL not in bundled manifest: {url!r}",
                location=str(json_file.relative_to(out_dir)),
            ))
            continue
        schema = _resolve_schema(url, cache_dir, _bundled_dir)
        if schema is None:
            continue
        validator = jsonschema.Draft7Validator(schema, resolver=resolver)
        for error in validator.iter_errors(data):
            path_str = " > ".join(str(p) for p in error.absolute_path) or "(root)"
            findings.append(SchemaFinding(
                code="schema.violation",
                severity="warn",
                message=f"{error.message} (at {path_str})",
                location=str(json_file.relative_to(out_dir)),
            ))

    outcome = ValidatorOutcome.FAILED if findings else ValidatorOutcome.PASSED
    return SchemaValidationResult(
        outcome=outcome,
        findings=tuple(findings),
        log_path="validation/json_schema.json",
    )
```

- [x] **Step 4: Run all json_schema tests — verify they all pass**

```
pytest tests/unit/validate/test_json_schema.py tests/unit/validate/test_refresolver.py -v
```

Expected: all pass, including the previously failing `test_ref_resolved_invalid_fails`.

- [x] **Step 5: Run E2E gate**

```
pytest tests/integration/test_real_workbooks_e2e.py -v
```

Expected: all pass.

- [x] **Step 6: Commit**

```
git add src/tableau2pbir/validate/json_schema.py tests/unit/validate/test_refresolver.py
git commit -m "feat(validate): wire RefResolver so nested schema $ref links resolve during validation"
```

---

## Task 3 — IR discriminated union in ir/sheet.py

**Files:**
- Modify: `src/tableau2pbir/ir/sheet.py`
- Modify: `tests/unit/ir/test_sheet.py` (fix callers)
- Modify: `tests/unit/emit/pbir/test_filters.py` (fix callers)

The single `Filter` class becomes a type alias for a Pydantic v2 discriminated union of 5 concrete subtypes. Existing code that calls `Filter(id=…, kind="categorical", …)` must be updated to use the concrete subtype directly.

- [x] **Step 1: Write new IR tests**

Add these to `tests/unit/ir/test_sheet.py` (append after existing tests):

```python
from tableau2pbir.ir.sheet import (
    CategoricalFilter, RangeFilter, TopNFilter, ContextFilter, ConditionalFilter, Filter,
)


def test_categorical_filter_roundtrip():
    f = CategoricalFilter(
        id="f1", field=FieldRef(table_id="Sales", column_id="Region"),
        include=("East", "West"), exclude=(),
    )
    assert f.kind == "categorical"
    assert f.include == ("East", "West")
    # Pydantic round-trip: serialize → deserialize via the union
    import json
    from pydantic import TypeAdapter
    ta = TypeAdapter(Filter)
    restored = ta.validate_python(json.loads(f.model_dump_json()))
    assert isinstance(restored, CategoricalFilter)
    assert restored.include == ("East", "West")


def test_range_filter_roundtrip():
    f = RangeFilter(
        id="f2", field=FieldRef(table_id="Sales", column_id="Amount"),
        min_val="100", max_val="9999",
    )
    assert f.kind == "range"
    from pydantic import TypeAdapter
    ta = TypeAdapter(Filter)
    restored = ta.validate_python(f.model_dump())
    assert isinstance(restored, RangeFilter)
    assert restored.min_val == "100"


def test_topn_filter_fields():
    f = TopNFilter(
        id="f3", field=FieldRef(table_id="Sales", column_id="Customer"),
        n=10, direction="Top",
        by_field=FieldRef(table_id="Sales", column_id="Revenue"),
        by_agg="SUM",
    )
    assert f.kind == "top_n"
    assert f.n == 10
    assert f.by_agg == "SUM"


def test_context_filter_is_categorical_shaped():
    f = ContextFilter(
        id="f4", field=FieldRef(table_id="Sales", column_id="Year"),
        include=("2023",), exclude=(),
    )
    assert f.kind == "context"


def test_conditional_filter_fields():
    f = ConditionalFilter(
        id="f5", field=FieldRef(table_id="Sales", column_id="Profit"),
        expr="[Profit] > 0",
    )
    assert f.kind == "conditional"
    assert f.expr == "[Profit] > 0"


def test_sheet_accepts_new_filter_subtypes():
    from tableau2pbir.ir.sheet import Sheet, Encoding
    f = RangeFilter(
        id="f6", field=FieldRef(table_id="t1", column_id="price"),
        min_val="10",
    )
    s = Sheet(
        id="sheet3", name="Priced",
        datasource_refs=("ds1",),
        mark_type="bar",
        encoding=Encoding(rows=(), columns=()),
        filters=(f,),
        sort=(), dual_axis=False, reference_lines=(),
        format=None, uses_calculations=(),
    )
    assert isinstance(s.filters[0], RangeFilter)
```

- [x] **Step 2: Run the new tests — verify they fail**

```
pytest tests/unit/ir/test_sheet.py::test_categorical_filter_roundtrip -v
```

Expected: `ImportError` — `CategoricalFilter` does not exist yet.

- [x] **Step 3: Rewrite ir/sheet.py**

Replace the entire file content:

```python
"""Sheet IR — §5.1."""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from tableau2pbir.ir.common import FieldRef, IRBase


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


class FilterBase(IRBase):
    id: str
    field: FieldRef


class CategoricalFilter(FilterBase):
    kind: Literal["categorical"] = "categorical"
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()


class RangeFilter(FilterBase):
    kind: Literal["range"] = "range"
    min_val: str | None = None
    max_val: str | None = None
    agg_prefix: str | None = None  # reserved for v1.1; always None from extraction


class TopNFilter(FilterBase):
    kind: Literal["top_n"] = "top_n"
    n: int = 10
    direction: str = "Top"          # "Top" | "Bottom"
    by_field: FieldRef | None = None
    by_agg: str | None = None


class ContextFilter(FilterBase):
    kind: Literal["context"] = "context"
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()


class ConditionalFilter(FilterBase):
    kind: Literal["conditional"] = "conditional"
    expr: str | None = None


Filter = Annotated[
    CategoricalFilter | RangeFilter | TopNFilter | ContextFilter | ConditionalFilter,
    Field(discriminator="kind"),
]


class SortSpec(IRBase):
    field: FieldRef
    direction: str                          # "asc" | "desc"


class ReferenceLine(IRBase):
    id: str
    scope_field: FieldRef
    kind: str                               # "constant" | "average" | "median" | "lod"
    value: float | None = None
    lod_expr: str | None = None


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
    format: dict[str, str] = {}


Sheet.model_rebuild()
```

- [x] **Step 4: Fix existing callers in test_sheet.py**

In `tests/unit/ir/test_sheet.py`, the two existing tests construct `Filter(id=…, kind="categorical", …)`. Update them to use `CategoricalFilter`:

```python
# test_sheet_with_categorical_filter — change:
# OLD: f = Filter(id="f1", kind="categorical", field=..., include=(...), exclude=(), expr=None)
# NEW:
f = CategoricalFilter(
    id="f1", field=FieldRef(table_id="t1", column_id="region"),
    include=("West", "East"),
)
```

Also update the import at the top of the file from:
```python
from tableau2pbir.ir.sheet import Encoding, Filter, Sheet
```
to:
```python
from tableau2pbir.ir.sheet import (
    CategoricalFilter, Encoding, Filter, RangeFilter, Sheet,
    TopNFilter, ContextFilter, ConditionalFilter,
)
```

- [x] **Step 5: Fix existing callers in test_filters.py**

In `tests/unit/emit/pbir/test_filters.py`, update all `Filter(…)` constructors and the import:

```python
# OLD import:
from tableau2pbir.ir.sheet import Filter
# NEW import:
from tableau2pbir.ir.sheet import CategoricalFilter, RangeFilter

# test_dedupes_filters_across_sheets_of_same_page:
# OLD: f1 = Filter(id="f1", kind="categorical", field=..., include=("West","East"))
# NEW:
f1 = CategoricalFilter(id="f1", field=FieldRef(table_id="Sales", column_id="Region"), include=("West", "East"))
f2 = CategoricalFilter(id="f2", field=FieldRef(table_id="Sales", column_id="Region"), include=("West", "East"))

# test_unique_filters_kept:
# OLD: f1 = Filter(id="f1", kind="categorical", ...) / f2 = Filter(id="f2", kind="range", ...)
# NEW:
f1 = CategoricalFilter(id="f1", field=FieldRef(table_id="Sales", column_id="Region"), include=("West",))
f2 = RangeFilter(id="f2", field=FieldRef(table_id="Sales", column_id="Year"))
```

- [x] **Step 6: Run all IR and filter tests**

```
pytest tests/unit/ir/test_sheet.py tests/unit/emit/pbir/test_filters.py -v
```

Expected: all pass.

- [x] **Step 7: Run full unit suite to catch any other callers**

```
pytest tests/unit/ -v --tb=short 2>&1 | grep -E "FAILED|ERROR"
```

Expected: no FAILEDs or ERRORs. If any other test imports `Filter` with old-style kwargs, fix them the same way.

- [x] **Step 8: Run E2E gate**

```
pytest tests/integration/test_real_workbooks_e2e.py -v
```

Expected: all pass.

- [x] **Step 9: Commit**

```
git add src/tableau2pbir/ir/sheet.py tests/unit/ir/test_sheet.py tests/unit/emit/pbir/test_filters.py
git commit -m "feat(ir): replace Filter class with Pydantic v2 discriminated union of 5 subtypes"
```

---

## Task 4 — Extract layer: class mapping + range/topN XML fields

**Files:**
- Modify: `src/tableau2pbir/extract/worksheets.py`
- Create: `tests/unit/extract/test_extract_filters.py`

- [x] **Step 1: Write the failing tests**

Create `tests/unit/extract/test_extract_filters.py`:

```python
"""Tests for _filters() class normalisation and child-element capture."""
from __future__ import annotations

from lxml import etree

from tableau2pbir.extract.worksheets import _filters


def _view(xml_body: str) -> etree._Element:
    return etree.fromstring(f"<view>{xml_body}</view>")


def test_quantitative_mapped_to_range():
    v = _view("""
        <filter class='quantitative' column='[Amount]'>
          <min>100</min>
          <max>500</max>
        </filter>
    """)
    result = _filters(v)
    assert len(result) == 1
    f = result[0]
    assert f["kind"] == "range"
    assert f["column"] == "Amount"
    assert f["min_val"] == "100"
    assert f["max_val"] == "500"
    assert f["agg_prefix"] is None


def test_quantitative_min_only():
    v = _view("<filter class='quantitative' column='[Sales]'><min>0</min></filter>")
    f = _filters(v)[0]
    assert f["kind"] == "range"
    assert f["min_val"] == "0"
    assert f["max_val"] is None


def test_top_mapped_to_top_n():
    v = _view("""
        <filter class='top' column='[Customer]'>
          <top-spec-count>10</top-spec-count>
          <top-spec-direction>Top</top-spec-direction>
          <top-spec-field column='[Revenue]' aggregation='SUM'/>
        </filter>
    """)
    result = _filters(v)
    assert len(result) == 1
    f = result[0]
    assert f["kind"] == "top_n"
    assert f["column"] == "Customer"
    assert f["n"] == 10
    assert f["direction"] == "Top"
    assert f["by_column"] == "Revenue"
    assert f["by_agg"] == "SUM"


def test_top_without_spec_field():
    v = _view("""
        <filter class='top' column='[Product]'>
          <top-spec-count>5</top-spec-count>
          <top-spec-direction>Bottom</top-spec-direction>
        </filter>
    """)
    f = _filters(v)[0]
    assert f["kind"] == "top_n"
    assert f["n"] == 5
    assert f["direction"] == "Bottom"
    assert f["by_column"] is None
    assert f["by_agg"] is None


def test_condition_mapped_to_conditional():
    v = _view("<filter class='condition' column='[Profit]' formula='[Profit] &gt; 0'/>")
    f = _filters(v)[0]
    assert f["kind"] == "conditional"
    assert f["expr"] == "[Profit] > 0"


def test_context_kind_preserved():
    v = _view("""
        <filter class='context' column='[Region]'>
          <groupfilter function='member' member='West'/>
        </filter>
    """)
    f = _filters(v)[0]
    assert f["kind"] == "context"
    assert "West" in f["include"]


def test_unknown_class_defaults_to_categorical():
    v = _view("<filter class='unknown_future_type' column='[X]'/>")
    f = _filters(v)[0]
    assert f["kind"] == "categorical"


def test_categorical_members_captured():
    v = _view("""
        <filter class='categorical' column='[Region]'>
          <groupfilter function='member' member='East'/>
          <groupfilter function='member' member='West'/>
          <groupfilter function='except' member='North'/>
        </filter>
    """)
    f = _filters(v)[0]
    assert f["kind"] == "categorical"
    assert "East" in f["include"]
    assert "West" in f["include"]
    assert "North" in f["exclude"]
```

- [x] **Step 2: Run the tests — verify they fail**

```
pytest tests/unit/extract/test_extract_filters.py -v
```

Expected: multiple FAILEDs — `kind` values not yet normalised.

- [x] **Step 3: Update `_filters()` in extract/worksheets.py**

Replace the existing `_filters` function (lines 126-139) with:

```python
_TABLEAU_CLASS_TO_KIND: dict[str, str] = {
    "categorical": "categorical",
    "quantitative": "range",
    "top": "top_n",
    "context": "context",
    "condition": "conditional",
}


def _filters(view: etree._Element) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for f in view.findall("filter"):
        tableau_class = attr(f, "class", default="categorical")
        kind = _TABLEAU_CLASS_TO_KIND.get(tableau_class, "categorical")
        column = _unbracket(attr(f, "column"))

        if kind == "range":
            out.append({
                "kind": "range",
                "column": column,
                "min_val": f.findtext("min"),
                "max_val": f.findtext("max"),
                "agg_prefix": None,
            })
        elif kind == "top_n":
            spec = f.find("top-spec-field")
            out.append({
                "kind": "top_n",
                "column": column,
                "n": int(f.findtext("top-spec-count") or 10),
                "direction": f.findtext("top-spec-direction") or "Top",
                "by_column": _unbracket(attr(spec, "column", default="")) if spec is not None else None,
                "by_agg": attr(spec, "aggregation", default=None) if spec is not None else None,
            })
        else:
            include, exclude = _filter_members(f)
            out.append({
                "kind": kind,
                "column": column,
                "include": include,
                "exclude": exclude,
                "expr": optional_attr(f, "formula"),
            })
    return out
```

- [x] **Step 4: Run extract filter tests**

```
pytest tests/unit/extract/test_extract_filters.py tests/unit/stages/test_s01_extract.py -v
```

Expected: all pass.

- [x] **Step 5: Run E2E gate**

```
pytest tests/integration/test_real_workbooks_e2e.py -v
```

Expected: all pass.

- [x] **Step 6: Commit**

```
git add src/tableau2pbir/extract/worksheets.py tests/unit/extract/test_extract_filters.py
git commit -m "feat(extract): normalise Tableau filter class values to IR kinds; capture range/topN XML fields"
```

---

## Task 5 — Canonicalize factory in _build_sheets.py

**Files:**
- Modify: `src/tableau2pbir/stages/_build_sheets.py`
- Create: `tests/unit/stages/test_build_sheets_filters.py`

- [x] **Step 1: Write the failing tests**

Create `tests/unit/stages/test_build_sheets_filters.py`:

```python
"""Tests for _build_filter factory dispatch and UnsupportedItem recording."""
from __future__ import annotations

from tableau2pbir.ir.common import FieldRef
from tableau2pbir.ir.sheet import (
    CategoricalFilter, ConditionalFilter, ContextFilter, RangeFilter, TopNFilter,
)
from tableau2pbir.stages._build_sheets import _build_filter, build_sheets


def _field(col: str) -> FieldRef:
    return FieldRef(table_id="tbl__sales", column_id=col)


def test_categorical_dispatch():
    f = _build_filter({"kind": "categorical", "column": "Region",
                       "include": ("East",), "exclude": (), "expr": None},
                      sheet_idx=0, filter_idx=0, table_id="tbl__sales")
    assert isinstance(f, CategoricalFilter)
    assert f.include == ("East",)
    assert f.field == _field("region")


def test_range_dispatch():
    f = _build_filter({"kind": "range", "column": "Amount",
                       "min_val": "10", "max_val": "500", "agg_prefix": None},
                      sheet_idx=0, filter_idx=1, table_id="tbl__sales")
    assert isinstance(f, RangeFilter)
    assert f.min_val == "10"
    assert f.max_val == "500"
    assert f.agg_prefix is None


def test_top_n_dispatch():
    f = _build_filter({"kind": "top_n", "column": "Customer",
                       "n": 10, "direction": "Top",
                       "by_column": "Revenue", "by_agg": "SUM"},
                      sheet_idx=0, filter_idx=2, table_id="tbl__sales")
    assert isinstance(f, TopNFilter)
    assert f.n == 10
    assert f.by_agg == "SUM"
    assert f.by_field == _field("revenue")


def test_context_dispatch():
    f = _build_filter({"kind": "context", "column": "Year",
                       "include": ("2023",), "exclude": (), "expr": None},
                      sheet_idx=0, filter_idx=3, table_id="tbl__sales")
    assert isinstance(f, ContextFilter)
    assert f.include == ("2023",)


def test_conditional_dispatch():
    f = _build_filter({"kind": "conditional", "column": "Profit",
                       "include": (), "exclude": (), "expr": "[Profit] > 0"},
                      sheet_idx=0, filter_idx=4, table_id="tbl__sales")
    assert isinstance(f, ConditionalFilter)
    assert f.expr == "[Profit] > 0"


def test_topn_filter_adds_unsupported_item():
    raw_worksheets = [{
        "name": "Top Customers",
        "datasource_refs": ("ds1",),
        "mark_type": "bar",
        "encodings": {"rows": (), "columns": (), "color": None, "size": None,
                      "label": None, "tooltip": None, "detail": (), "shape": None, "angle": None},
        "filters": [{"kind": "top_n", "column": "Customer",
                     "n": 5, "direction": "Top", "by_column": None, "by_agg": None}],
        "sort": [], "dual_axis": False, "reference_lines": [], "quick_table_calcs": [],
    }]
    sheets, unsupported = build_sheets(raw_worksheets, set(), {"ds1": "tbl__sales"})
    assert len(sheets) == 1
    assert isinstance(sheets[0].filters[0], TopNFilter)
    assert any(u.code == "deferred_feature_topn_filter" for u in unsupported)


def test_conditional_filter_adds_unsupported_item():
    raw_worksheets = [{
        "name": "Conditions",
        "datasource_refs": ("ds1",),
        "mark_type": "bar",
        "encodings": {"rows": (), "columns": (), "color": None, "size": None,
                      "label": None, "tooltip": None, "detail": (), "shape": None, "angle": None},
        "filters": [{"kind": "conditional", "column": "Profit",
                     "include": (), "exclude": (), "expr": "[Profit] > 0"}],
        "sort": [], "dual_axis": False, "reference_lines": [], "quick_table_calcs": [],
    }]
    sheets, unsupported = build_sheets(raw_worksheets, set(), {"ds1": "tbl__sales"})
    assert any(u.code == "deferred_feature_conditional_filter" for u in unsupported)
```

- [x] **Step 2: Run tests — verify they fail**

```
pytest tests/unit/stages/test_build_sheets_filters.py -v
```

Expected: `ImportError` for `_build_filter` (it's currently a module-private function but exists; the failure will be on `isinstance` checks since the factory doesn't dispatch yet).

- [x] **Step 3: Update _build_sheets.py**

At the top of `src/tableau2pbir/stages/_build_sheets.py`, update the imports:

```python
from tableau2pbir.ir.common import FieldRef, UnsupportedItem
from tableau2pbir.ir.sheet import (
    CategoricalFilter, ConditionalFilter, ContextFilter,
    Encoding, Filter, RangeFilter, ReferenceLine, Sheet, SortSpec, TopNFilter,
)
```

Replace the `_build_filter` function:

```python
def _build_filter(raw_f: dict[str, Any], sheet_idx: int, filter_idx: int, table_id: str) -> Filter:
    fid = f"filter__s{sheet_idx}_{filter_idx}"
    field = _ref(raw_f["column"], table_id)
    kind = raw_f["kind"]

    if kind == "range":
        return RangeFilter(id=fid, field=field,
                           min_val=raw_f.get("min_val"),
                           max_val=raw_f.get("max_val"),
                           agg_prefix=raw_f.get("agg_prefix"))
    if kind == "top_n":
        by_col = raw_f.get("by_column")
        return TopNFilter(id=fid, field=field,
                          n=raw_f.get("n", 10),
                          direction=raw_f.get("direction", "Top"),
                          by_field=_ref(by_col, table_id) if by_col else None,
                          by_agg=raw_f.get("by_agg"))
    if kind == "conditional":
        return ConditionalFilter(id=fid, field=field, expr=raw_f.get("expr"))
    if kind == "context":
        return ContextFilter(id=fid, field=field,
                             include=tuple(raw_f.get("include", ())),
                             exclude=tuple(raw_f.get("exclude", ())))
    # categorical + any unrecognised kind → CategoricalFilter
    return CategoricalFilter(id=fid, field=field,
                             include=tuple(raw_f.get("include", ())),
                             exclude=tuple(raw_f.get("exclude", ())))
```

In the `build_sheets` function, after building `filters`, collect UnsupportedItems for deferred filter kinds. Find the line `filters = tuple(...)` and add:

```python
        filters = tuple(
            _build_filter(f, idx, fi, table_id)
            for fi, f in enumerate(raw["filters"])
        )
        # Record deferred filter kinds as unsupported items
        for fi, fobj in enumerate(filters):
            if isinstance(fobj, TopNFilter):
                qtc_unsupported.append(UnsupportedItem(
                    object_kind="filter",
                    object_id=fobj.id,
                    source_excerpt=f"sheet={raw['name']!r} column={raw['filters'][fi]['column']!r} kind=top_n",
                    reason="TopN filter emission deferred to v1.1.",
                    code="deferred_feature_topn_filter",
                ))
            elif isinstance(fobj, ConditionalFilter):
                qtc_unsupported.append(UnsupportedItem(
                    object_kind="filter",
                    object_id=fobj.id,
                    source_excerpt=f"sheet={raw['name']!r} column={raw['filters'][fi]['column']!r} kind=conditional",
                    reason="Conditional filter emission deferred to v1.1.",
                    code="deferred_feature_conditional_filter",
                ))
```

- [x] **Step 4: Run tests**

```
pytest tests/unit/stages/test_build_sheets_filters.py tests/unit/stages/test_s02_calculations.py -v
```

Expected: all pass.

- [x] **Step 5: Run E2E gate**

```
pytest tests/integration/test_real_workbooks_e2e.py -v
```

Expected: all pass.

- [x] **Step 6: Commit**

```
git add src/tableau2pbir/stages/_build_sheets.py tests/unit/stages/test_build_sheets_filters.py
git commit -m "feat(canonicalize): replace Filter factory with typed dispatch; record TopN/Conditional as unsupported"
```

---

## Task 6 — Emit helpers: _format_literal, _entity_field, _alias_col_expr

**Files:**
- Modify: `src/tableau2pbir/emit/pbir/filters.py` (add helpers only; keep existing collect_page_filters)
- Create: `tests/unit/emit/pbir/test_filter_literal.py`

- [x] **Step 1: Write failing tests**

Create `tests/unit/emit/pbir/test_filter_literal.py`:

```python
"""Tests for _format_literal and field-building helpers."""
from __future__ import annotations

import pytest

from tableau2pbir.emit.pbir.filters import _alias_col_expr, _entity_field, _format_literal


class TestFormatLiteral:
    def test_none_returns_null(self):
        assert _format_literal(None) == "null"

    def test_empty_string_returns_null(self):
        assert _format_literal("") == "null"

    def test_date_only(self):
        assert _format_literal("#2023-01-03#") == "datetime'2023-01-03T00:00:00'"

    def test_datetime_with_time(self):
        assert _format_literal("#2023-01-03 12:30:00#") == "datetime'2023-01-03T12:30:00'"

    def test_integer_string(self):
        assert _format_literal("42") == "42L"

    def test_negative_integer(self):
        assert _format_literal("-7") == "-7L"

    def test_float_string(self):
        assert _format_literal("3.14") == "3.14D"

    def test_plain_string(self):
        assert _format_literal("East") == "'East'"

    def test_string_with_apostrophe_escaped(self):
        # Single quotes inside strings are doubled per DAX convention
        result = _format_literal("O'Brien")
        assert result == "'O''Brien'"

    def test_zero_integer(self):
        assert _format_literal("0") == "0L"


class TestEntityField:
    def test_column_entity_field(self):
        result = _entity_field("Sales", "Region", "Column")
        assert result == {
            "Column": {
                "Expression": {"SourceRef": {"Entity": "Sales"}},
                "Property": "Region",
            }
        }

    def test_measure_entity_field(self):
        result = _entity_field("Sales", "Total", "Measure")
        assert "Measure" in result
        assert result["Measure"]["Expression"]["SourceRef"]["Entity"] == "Sales"


class TestAliasColExpr:
    def test_alias_col_expression(self):
        result = _alias_col_expr("f", "Region")
        assert result == {
            "Column": {
                "Expression": {"SourceRef": {"Source": "f"}},
                "Property": "Region",
            }
        }
```

- [x] **Step 2: Run tests — verify they fail**

```
pytest tests/unit/emit/pbir/test_filter_literal.py -v
```

Expected: `ImportError` — helpers don't exist yet.

- [x] **Step 3: Add helpers to filters.py**

Replace the contents of `src/tableau2pbir/emit/pbir/filters.py` with the following. Keep `collect_page_filters` working (it still imports `Filter` but now via the union) — we'll update the None-guard in Task 8.

```python
"""PBIR filter emission — builds schema-valid FilterDefinition bodies."""
from __future__ import annotations

from tableau2pbir.ir.sheet import (
    CategoricalFilter, ConditionalFilter, ContextFilter, Filter,
    RangeFilter, TopNFilter,
)


# ---------------------------------------------------------------------------
# Literal formatting
# ---------------------------------------------------------------------------

def _format_literal(value: str | None) -> str:
    """Convert a raw Tableau filter value to a PBI QueryLiteralExpression.Value string.

    Official formats per semanticQuery schema:
      Integer → "24L"   Double → "2.4D"   String → "'value'"
      DateTime → "datetime'YYYY-MM-DDThh:mm:ss'"   Null → "null"
    """
    if not value:
        return "null"
    v = value.strip()
    # Tableau date literal: #2023-01-03# or #2023-01-03 12:30:00#
    if v.startswith("#") and v.endswith("#"):
        inner = v[1:-1].strip()
        if " " in inner:
            date_part, time_part = inner.split(" ", 1)
            return f"datetime'{date_part}T{time_part}'"
        return f"datetime'{inner}T00:00:00'"
    # Numeric
    try:
        int_val = int(v)
        return f"{int_val}L"
    except ValueError:
        pass
    try:
        float(v)
        return f"{v}D"
    except ValueError:
        pass
    # String — escape single quotes by doubling them (DAX convention)
    escaped = v.replace("'", "''")
    return f"'{escaped}'"


# ---------------------------------------------------------------------------
# Expression builders
# ---------------------------------------------------------------------------

def _entity_field(table_name: str, col_name: str, field_type: str = "Column") -> dict:
    """Top-level FilterContainer.field using StandaloneSourceRefExpression (Entity key)."""
    return {
        field_type: {
            "Expression": {"SourceRef": {"Entity": table_name}},
            "Property": col_name,
        }
    }


def _alias_col_expr(alias: str, col_name: str) -> dict:
    """Column expression inside From/Where using QuerySourceRefExpression (Source key)."""
    return {
        "Column": {
            "Expression": {"SourceRef": {"Source": alias}},
            "Property": col_name,
        }
    }


def _literal(value: str | None) -> dict:
    return {"Literal": {"Value": _format_literal(value)}}


# ---------------------------------------------------------------------------
# Per-kind emit (stubbed — completed in subsequent tasks)
# ---------------------------------------------------------------------------

def _filter_to_pbir(f: Filter) -> dict | None:
    """Return a FilterContainer dict, or None if this filter kind is deferred."""
    return None  # placeholder — implemented in Tasks 7–9


# ---------------------------------------------------------------------------
# Page filter collection
# ---------------------------------------------------------------------------

def collect_page_filters(per_sheet: list[tuple[tuple[str, ...], list]]) -> list[dict]:
    seen_keys: set[tuple] = set()
    out: list[dict] = []
    for _sheet_ids, filters in per_sheet:
        for f in filters:
            if isinstance(f, CategoricalFilter):
                key = (f.field.table_id, f.field.column_id, f.kind, tuple(f.include), tuple(f.exclude))
            elif isinstance(f, RangeFilter):
                key = (f.field.table_id, f.field.column_id, f.kind, f.min_val, f.max_val)
            else:
                key = (f.field.table_id, f.field.column_id, f.kind)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            result = _filter_to_pbir(f)
            if result is not None:
                out.append(result)
    return out
```

Note: `collect_page_filters` now has the None-guard built in from the start. The old per-field dedup key is replaced by kind-aware keys.

- [x] **Step 4: Run helper tests**

```
pytest tests/unit/emit/pbir/test_filter_literal.py tests/unit/emit/pbir/test_filters.py -v
```

Expected: all helper tests pass. The two existing `test_filters.py` tests (`test_dedupes_filters_across_sheets_of_same_page`, `test_unique_filters_kept`) will show `len(out) == 0` because `_filter_to_pbir` returns `None` for all — that's expected at this stage. Update them to assert `len(out) == 0` temporarily if they fail, or mark them as xfail.

Actually: the dedupe test checks `len(out) == 1` which will now fail because `_filter_to_pbir` returns `None`. Update those two tests to assert `len(out) == 0` as a temporary placeholder — they'll be restored to their real assertions once the emit is complete in Task 7.

```python
# Temporarily in test_filters.py while _filter_to_pbir returns None:
def test_dedupes_filters_across_sheets_of_same_page():
    ...
    out = collect_page_filters(...)
    assert len(out) == 0  # placeholder: _filter_to_pbir returns None until Task 7


def test_unique_filters_kept():
    ...
    out = collect_page_filters(...)
    assert len(out) == 0  # placeholder
```

- [x] **Step 5: Run E2E gate**

```
pytest tests/integration/test_real_workbooks_e2e.py -v
```

Expected: all pass (filter output is now empty lists, not invalid JSON).

- [x] **Step 6: Commit**

```
git add src/tableau2pbir/emit/pbir/filters.py tests/unit/emit/pbir/test_filter_literal.py tests/unit/emit/pbir/test_filters.py
git commit -m "feat(emit): add _format_literal, _entity_field, _alias_col_expr helpers; stub _filter_to_pbir"
```

---

## Task 7 — Emit: Categorical and Context filters

**Files:**
- Modify: `src/tableau2pbir/emit/pbir/filters.py`
- Create: `tests/unit/emit/pbir/test_filters_emit.py`
- Modify: `tests/unit/emit/pbir/test_filters.py` (restore assertions)

- [x] **Step 1: Write failing tests**

Create `tests/unit/emit/pbir/test_filters_emit.py`:

```python
"""Tests for _filter_to_pbir per-kind emit."""
from __future__ import annotations

import pytest

from tableau2pbir.emit.pbir.filters import _filter_to_pbir
from tableau2pbir.ir.common import FieldRef
from tableau2pbir.ir.sheet import (
    CategoricalFilter, ConditionalFilter, ContextFilter,
    RangeFilter, TopNFilter,
)

_FIELD = FieldRef(table_id="Sales", column_id="Region")


def _cat(include=(), exclude=()):
    return CategoricalFilter(id="f1", field=_FIELD, include=include, exclude=exclude)


class TestCategoricalEmit:
    def test_include_only(self):
        result = _filter_to_pbir(_cat(include=("East", "West")))
        assert result is not None
        assert result["type"] == "Categorical"
        assert result["name"] == "f1"
        # top-level field uses Entity (StandaloneSourceRef)
        assert result["field"]["Column"]["Expression"]["SourceRef"]["Entity"] == "Sales"
        assert result["field"]["Column"]["Property"] == "Region"
        # filter body
        fd = result["filter"]
        assert fd["Version"] == 2
        assert fd["From"][0] == {"Name": "f", "Entity": "Sales", "Type": 0}
        condition = fd["Where"][0]["Condition"]
        assert "In" in condition
        in_expr = condition["In"]
        # alias-ref inside Where uses Source key
        assert in_expr["Expressions"][0]["Column"]["Expression"]["SourceRef"]["Source"] == "f"
        values = [v[0]["Literal"]["Value"] for v in in_expr["Values"]]
        assert "'East'" in values
        assert "'West'" in values
        assert result["howCreated"] == "User"
        assert result["isHiddenInViewMode"] is False

    def test_exclude_only(self):
        result = _filter_to_pbir(_cat(exclude=("North",)))
        assert result is not None
        condition = result["filter"]["Where"][0]["Condition"]
        assert "Not" in condition
        assert "In" in condition["Not"]["Expression"]

    def test_include_and_exclude(self):
        result = _filter_to_pbir(_cat(include=("East",), exclude=("North",)))
        assert result is not None
        condition = result["filter"]["Where"][0]["Condition"]
        assert "And" in condition
        assert "In" in condition["And"]["Left"]
        assert "Not" in condition["And"]["Right"]

    def test_empty_returns_none(self):
        assert _filter_to_pbir(_cat()) is None

    def test_howcreated_and_hidden(self):
        result = _filter_to_pbir(_cat(include=("East",)))
        assert result["howCreated"] == "User"
        assert result["isHiddenInViewMode"] is False


class TestContextEmit:
    def test_context_same_structure_as_categorical(self):
        f = ContextFilter(id="f2", field=_FIELD, include=("West",))
        result = _filter_to_pbir(f)
        assert result is not None
        assert result["type"] == "Categorical"
        condition = result["filter"]["Where"][0]["Condition"]
        assert "In" in condition

    def test_context_empty_returns_none(self):
        f = ContextFilter(id="f3", field=_FIELD)
        assert _filter_to_pbir(f) is None
```

- [x] **Step 2: Run tests — verify they fail**

```
pytest tests/unit/emit/pbir/test_filters_emit.py::TestCategoricalEmit -v
```

Expected: FAILEDs — `_filter_to_pbir` returns `None` for everything.

- [x] **Step 3: Implement categorical/context emit in filters.py**

Replace the `_filter_to_pbir` stub with the categorical/context implementation:

```python
def _filter_to_pbir(f: Filter) -> dict | None:
    """Return a FilterContainer dict, or None if this filter kind is deferred."""
    if isinstance(f, (CategoricalFilter, ContextFilter)):
        return _emit_categorical(f)
    if isinstance(f, RangeFilter):
        return None  # implemented in Task 8
    # TopNFilter, ConditionalFilter — deferred
    return None


def _emit_categorical(f: CategoricalFilter | ContextFilter) -> dict | None:
    table = f.field.table_id
    col = f.field.column_id
    alias = "f"

    include_vals = list(f.include)
    exclude_vals = list(f.exclude)

    if not include_vals and not exclude_vals:
        return None

    alias_col = _alias_col_expr(alias, col)

    def _in_expr(values: list[str]) -> dict:
        return {
            "In": {
                "Expressions": [alias_col],
                "Values": [[_literal(v)] for v in values],
            }
        }

    if include_vals and not exclude_vals:
        condition = _in_expr(include_vals)
    elif exclude_vals and not include_vals:
        condition = {"Not": {"Expression": _in_expr(exclude_vals)}}
    else:
        condition = {
            "And": {
                "Left": _in_expr(include_vals),
                "Right": {"Not": {"Expression": _in_expr(exclude_vals)}},
            }
        }

    return {
        "name": f.id,
        "field": _entity_field(table, col, "Column"),
        "type": "Categorical",
        "filter": {
            "Version": 2,
            "From": [{"Name": alias, "Entity": table, "Type": 0}],
            "Where": [{"Condition": condition}],
        },
        "howCreated": "User",
        "isHiddenInViewMode": False,
    }
```

- [x] **Step 4: Restore collect_page_filters assertions in test_filters.py**

Update `tests/unit/emit/pbir/test_filters.py` — restore the two tests back to their correct assertions:

```python
def test_dedupes_filters_across_sheets_of_same_page():
    f1 = CategoricalFilter(id="f1", field=FieldRef(table_id="Sales", column_id="Region"), include=("West", "East"))
    f2 = CategoricalFilter(id="f2", field=FieldRef(table_id="Sales", column_id="Region"), include=("West", "East"))
    out = collect_page_filters([(("s1",), [f1]), (("s2",), [f2])])
    assert len(out) == 1  # deduplicated


def test_unique_filters_kept():
    f1 = CategoricalFilter(id="f1", field=FieldRef(table_id="Sales", column_id="Region"), include=("West",))
    f2 = RangeFilter(id="f2", field=FieldRef(table_id="Sales", column_id="Year"), min_val="2020")
    out = collect_page_filters([(("s1",), [f1]), (("s2",), [f2])])
    # f1 emits (categorical with include), f2 will emit once Task 8 is done
    # for now: f1 emits (1 result), f2 returns None (0 result) → total 1
    assert len(out) == 1
```

- [x] **Step 5: Run all emit tests**

```
pytest tests/unit/emit/pbir/test_filters_emit.py tests/unit/emit/pbir/test_filter_literal.py tests/unit/emit/pbir/test_filters.py -v
```

Expected: all pass.

- [x] **Step 6: Run E2E gate**

```
pytest tests/integration/test_real_workbooks_e2e.py -v
```

Expected: all pass.

- [x] **Step 7: Commit**

```
git add src/tableau2pbir/emit/pbir/filters.py tests/unit/emit/pbir/test_filters_emit.py tests/unit/emit/pbir/test_filters.py
git commit -m "feat(emit): implement Categorical and Context filter emission with schema-valid FilterDefinition"
```

---

## Task 8 — Emit: Range filters (row-level and post-aggregation)

**Files:**
- Modify: `src/tableau2pbir/emit/pbir/filters.py`
- Modify: `tests/unit/emit/pbir/test_filters_emit.py` (add range tests)
- Modify: `tests/unit/emit/pbir/test_filters.py` (restore range assertion)

- [x] **Step 1: Write failing range tests**

Append to `tests/unit/emit/pbir/test_filters_emit.py`:

```python
_AMOUNT_FIELD = FieldRef(table_id="Sales", column_id="Amount")


class TestRangeEmit:
    def test_both_bounds_uses_between(self):
        f = RangeFilter(id="r1", field=_AMOUNT_FIELD, min_val="100", max_val="500")
        result = _filter_to_pbir(f)
        assert result is not None
        assert result["type"] == "Range"
        assert result["field"]["Column"]["Expression"]["SourceRef"]["Entity"] == "Sales"
        condition = result["filter"]["Where"][0]["Condition"]
        assert "Between" in condition
        between = condition["Between"]
        assert between["Expression"]["Column"]["Expression"]["SourceRef"]["Source"] == "f"
        assert between["LowerBound"]["Literal"]["Value"] == "100L"
        assert between["UpperBound"]["Literal"]["Value"] == "500L"

    def test_min_only_uses_gte_comparison(self):
        f = RangeFilter(id="r2", field=_AMOUNT_FIELD, min_val="0")
        result = _filter_to_pbir(f)
        assert result is not None
        assert result["type"] == "Range"
        condition = result["filter"]["Where"][0]["Condition"]
        assert "Comparison" in condition
        comp = condition["Comparison"]
        assert comp["ComparisonKind"] == 2  # GreaterThanOrEqual

    def test_max_only_uses_lte_comparison(self):
        f = RangeFilter(id="r3", field=_AMOUNT_FIELD, max_val="999")
        result = _filter_to_pbir(f)
        assert result is not None
        condition = result["filter"]["Where"][0]["Condition"]
        comp = condition["Comparison"]
        assert comp["ComparisonKind"] == 4  # LessThanOrEqual

    def test_no_bounds_returns_none(self):
        f = RangeFilter(id="r4", field=_AMOUNT_FIELD)
        assert _filter_to_pbir(f) is None

    def test_advanced_post_agg_type(self):
        f = RangeFilter(id="r5", field=_AMOUNT_FIELD, min_val="1000", agg_prefix="SUM")
        result = _filter_to_pbir(f)
        assert result is not None
        assert result["type"] == "Advanced"
        # top-level field is Aggregation wrapping Entity ref
        assert "Aggregation" in result["field"]
        agg_field = result["field"]["Aggregation"]
        assert agg_field["Function"] == 0  # Sum
        assert agg_field["Expression"]["Column"]["Expression"]["SourceRef"]["Entity"] == "Sales"
        # Where condition is Comparison with Aggregation on left
        condition = result["filter"]["Where"][0]["Condition"]
        assert "Comparison" in condition
        left = condition["Comparison"]["Left"]
        assert "Aggregation" in left
        assert left["Aggregation"]["Expression"]["Column"]["Expression"]["SourceRef"]["Source"] == "f"

    def test_advanced_unknown_agg_prefix_returns_none(self):
        f = RangeFilter(id="r6", field=_AMOUNT_FIELD, min_val="1", agg_prefix="UNKNOWN_AGG")
        assert _filter_to_pbir(f) is None


class TestDeferredEmit:
    def test_topn_returns_none(self):
        f = TopNFilter(id="t1", field=_FIELD, n=10)
        assert _filter_to_pbir(f) is None

    def test_conditional_returns_none(self):
        f = ConditionalFilter(id="c1", field=_FIELD, expr="[x] > 0")
        assert _filter_to_pbir(f) is None
```

- [x] **Step 2: Run new tests — verify they fail**

```
pytest tests/unit/emit/pbir/test_filters_emit.py::TestRangeEmit tests/unit/emit/pbir/test_filters_emit.py::TestDeferredEmit -v
```

Expected: range tests fail (returns `None`); deferred tests pass.

- [x] **Step 3: Implement range emit in filters.py**

Add the aggregation prefix map and `_emit_range` function. Update `_filter_to_pbir` to call it:

```python
_AGG_PREFIX_TO_FUNC: dict[str, int] = {
    "sum": 0, "avg": 1, "average": 1, "cntd": 2, "ctd": 2,
    "min": 3, "max": 4, "cnt": 5, "median": 6,
}


def _emit_range(f: RangeFilter) -> dict | None:
    table = f.field.table_id
    col = f.field.column_id
    alias = "f"

    has_min = f.min_val is not None
    has_max = f.max_val is not None
    if not has_min and not has_max:
        return None

    alias_col = _alias_col_expr(alias, col)

    if f.agg_prefix is not None:
        func_code = _AGG_PREFIX_TO_FUNC.get(f.agg_prefix.lower())
        if func_code is None:
            return None  # unknown prefix — skip with silent degradation

        agg_alias_expr = {"Aggregation": {"Function": func_code, "Expression": alias_col}}
        agg_entity_expr = {
            "Aggregation": {
                "Function": func_code,
                "Expression": {
                    "Column": {
                        "Expression": {"SourceRef": {"Entity": table}},
                        "Property": col,
                    }
                },
            }
        }
        # Build comparison(s)
        where_conditions = []
        if has_min:
            where_conditions.append({"Condition": {"Comparison": {
                "ComparisonKind": 2,
                "Left": agg_alias_expr,
                "Right": _literal(f.min_val),
            }}})
        if has_max:
            where_conditions.append({"Condition": {"Comparison": {
                "ComparisonKind": 4,
                "Left": agg_alias_expr,
                "Right": _literal(f.max_val),
            }}})
        return {
            "name": f.id,
            "field": agg_entity_expr,
            "type": "Advanced",
            "filter": {
                "Version": 2,
                "From": [{"Name": alias, "Entity": table, "Type": 0}],
                "Where": where_conditions,
            },
            "howCreated": "User",
            "isHiddenInViewMode": False,
        }

    # Row-level range filter
    if has_min and has_max:
        condition = {
            "Between": {
                "Expression": alias_col,
                "LowerBound": _literal(f.min_val),
                "UpperBound": _literal(f.max_val),
            }
        }
    elif has_min:
        condition = {"Comparison": {"ComparisonKind": 2, "Left": alias_col, "Right": _literal(f.min_val)}}
    else:
        condition = {"Comparison": {"ComparisonKind": 4, "Left": alias_col, "Right": _literal(f.max_val)}}

    return {
        "name": f.id,
        "field": _entity_field(table, col, "Column"),
        "type": "Range",
        "filter": {
            "Version": 2,
            "From": [{"Name": alias, "Entity": table, "Type": 0}],
            "Where": [{"Condition": condition}],
        },
        "howCreated": "User",
        "isHiddenInViewMode": False,
    }
```

Update `_filter_to_pbir` to call `_emit_range`:

```python
def _filter_to_pbir(f: Filter) -> dict | None:
    if isinstance(f, (CategoricalFilter, ContextFilter)):
        return _emit_categorical(f)
    if isinstance(f, RangeFilter):
        return _emit_range(f)
    # TopNFilter, ConditionalFilter — deferred
    return None
```

Also update `test_unique_filters_kept` in `test_filters.py` — now that RangeFilter emits, the total is 2:

```python
def test_unique_filters_kept():
    f1 = CategoricalFilter(id="f1", field=FieldRef(table_id="Sales", column_id="Region"), include=("West",))
    f2 = RangeFilter(id="f2", field=FieldRef(table_id="Sales", column_id="Year"), min_val="2020")
    out = collect_page_filters([(("s1",), [f1]), (("s2",), [f2])])
    assert len(out) == 2
```

- [x] **Step 4: Run all emit tests**

```
pytest tests/unit/emit/pbir/test_filters_emit.py tests/unit/emit/pbir/test_filter_literal.py tests/unit/emit/pbir/test_filters.py -v
```

Expected: all pass.

- [x] **Step 5: Run E2E gate**

```
pytest tests/integration/test_real_workbooks_e2e.py -v
```

Expected: all pass.

- [x] **Step 6: Commit**

```
git add src/tableau2pbir/emit/pbir/filters.py tests/unit/emit/pbir/test_filters_emit.py tests/unit/emit/pbir/test_filters.py
git commit -m "feat(emit): implement Range (row-level) and Advanced (post-agg) filter emission"
```

---

## Task 9 — Final wiring: full test suite + CLAUDE.md update

**Files:**
- Modify: `CLAUDE.md`

- [x] **Step 1: Run the full unit test suite**

```
pytest tests/unit/ -v --tb=short
```

Expected: all pass. If any test references the old `Filter(kind=…, …)` constructor pattern and was missed, fix it now using the same approach as Task 3.

- [x] **Step 2: Run the full integration + E2E suite**

```
pytest tests/ -v --tb=short -x
```

Expected: all pass.

- [x] **Step 3: Update CLAUDE.md implementation tracking table**

In `CLAUDE.md`, mark Plan 5 as still halted and add Plan 11 row:

```markdown
| 11 | Filter IR Enrichment & Schema-Compliant Emission | ✅ DONE | `docs/superpowers/plans/2026-05-31-plan-11-filter-ir-enrichment.md` |
```

Add a completion note after the Plan 10 note:

```
**Plan 11 complete (2026-05-31):** Filter IR enriched to Pydantic v2 discriminated union
(CategoricalFilter, RangeFilter, TopNFilter, ContextFilter, ConditionalFilter). Fixed all
three PBIR filter emission bugs: (1) type capitalisation now "Categorical"/"Range"/"Advanced";
(2) filter body emits valid FilterDefinition with Version/From/Where semantic query expressions;
(3) top-level field uses Entity (StandaloneSourceRef), Where body uses Source alias
(QuerySourceRefExpression). Bundled 5 missing schemas (semanticQuery 1.0/1.2/1.4,
filterConfiguration 1.1/1.3). Wired RefResolver so nested $ref chains validate. Extract layer
maps Tableau XML class values to IR kinds; captures <min>/<max> and top-spec child elements.
TopN and Conditional filters recorded as UnsupportedItems, deferred to v1.1.
```

- [x] **Step 4: Commit CLAUDE.md**

```
git add CLAUDE.md
git commit -m "docs: mark Plan 11 complete — filter IR enrichment and schema-compliant emission"
```

---

## Self-Review Checklist

**Spec coverage:**

| Spec requirement | Covered in task |
|---|---|
| Bundle semanticQuery-1.0.0/1.2.0/1.4.0 | Task 1 |
| Bundle filterConfiguration-1.1.0/1.3.0 | Task 1 |
| Manifest 5 new entries | Task 1 |
| refresh_schemas picks up new URLs automatically | Task 1 (no code change needed) |
| RefResolver store keyed on manifest URL | Task 2 |
| Dot vs hyphen discrepancy handled | Task 2 (manifest URL = hyphenated form) |
| IR: FilterBase + 5 subtypes + discriminated union | Task 3 |
| IR: Sheet.filters accepts new union | Task 3 |
| Extract: Tableau class → IR kind mapping | Task 4 |
| Extract: range XML `<min>`/`<max>` | Task 4 |
| Extract: topN XML child elements | Task 4 |
| Extract: agg_prefix always None in v1 | Task 4 |
| Canonicalize: factory dispatch on kind | Task 5 |
| Canonicalize: TopN/Conditional → UnsupportedItem | Task 5 |
| Emit: `_format_literal` all formats | Task 6 |
| Emit: `_entity_field` (Entity/StandaloneRef) | Task 6 |
| Emit: `_alias_col_expr` (Source/QueryRef) | Task 6 |
| Emit: Categorical include-only/exclude-only/both/empty | Task 7 |
| Emit: Context same as Categorical | Task 7 |
| Emit: collect_page_filters None-guard | Task 6 (built in from start) |
| Emit: Range both-bounds/min-only/max-only/neither | Task 8 |
| Emit: Advanced (post-agg) | Task 8 |
| Emit: TopN → None | Task 8 |
| Emit: Conditional → None | Task 8 |
| E2E gate after every task | Every task |

**Type consistency check:** All tasks use `CategoricalFilter`, `RangeFilter`, `TopNFilter`, `ContextFilter`, `ConditionalFilter` — consistent across IR definition (Task 3), factory (Task 5), and emit (Tasks 7–8). `_filter_to_pbir` signature is `(f: Filter) -> dict | None` throughout.

**No placeholders found.**
