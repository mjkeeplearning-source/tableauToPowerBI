# Plan 10 — JSON Schema Validation Against Official Microsoft PBI Schemas

> **Execution method:** superpowers:subagent-driven-development — fresh subagent per task, two-stage review (spec compliance then code quality) after each task.

**Goal:** Add a new `run_json_schema` validator to Stage 8 that auto-discovers every PBIR JSON output file, validates it against its declared Microsoft `$schema` URL using bundled schemas, and reports violations as soft warnings without blocking pipeline status.

**Architecture:** A new `validate/json_schema.py` module walks `*.json` output files, reads each file's own `$schema` field, resolves the schema via a two-tier lookup (user cache → bundled fallback in `validate/_schemas/`), and validates with `jsonschema.Draft7Validator`. A new `validate/refresh_schemas.py` module powers the `tableau2pbir refresh-schemas` CLI command that updates the user cache from the Microsoft CDN.

**Tech Stack:** `jsonschema>=4.0,<5.0` (new runtime dep), `urllib.request` (stdlib), pytest + `unittest.mock` for tests.

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `src/tableau2pbir/validate/_schemas/manifest.json` | URL→filename map for all 7 known schemas |
| Create | `src/tableau2pbir/validate/_schemas/*.json` | 7 bundled schema files from Microsoft CDN |
| Create | `src/tableau2pbir/validate/json_schema.py` | `run_json_schema`, `_resolve_schema`, `_load_manifest` |
| Create | `src/tableau2pbir/validate/refresh_schemas.py` | `refresh_schemas`, `_get_cache_dir` |
| Create | `tests/unit/validate/test_schema_cache.py` | 3 tests for `_resolve_schema` two-tier lookup |
| Create | `tests/unit/validate/test_json_schema.py` | 8 tests for `run_json_schema` |
| Create | `tests/unit/validate/test_refresh_schemas.py` | 5 tests for `refresh_schemas` + CLI |
| Modify | `src/tableau2pbir/validate/results.py` | Add `SchemaFinding`, `SchemaValidationResult` |
| Modify | `src/tableau2pbir/stages/s08_package_validate.py` | Call `run_json_schema`, add to validators dict |
| Modify | `src/tableau2pbir/cli.py` | Add `refresh-schemas` subcommand |
| Modify | `pyproject.toml` | Add `jsonschema>=4.0,<5.0`; hatchling includes `_schemas/` automatically |
| Modify | `CLAUDE.md` | Add Plan 10 entry to implementation tracking table |

---

## Task 1: Add `jsonschema` dependency

**Files:**
- Modify: `pyproject.toml`

- [x] **Step 1: Add `jsonschema` to dependencies**

Edit `pyproject.toml`. The `dependencies` list becomes:

```toml
dependencies = [
  "anthropic>=0.34,<1.0",
  "pydantic>=2.5,<3.0",
  "lxml>=5.0",
  "tableaudocumentapi>=0.11",
  "PyYAML>=6.0",
  "sqlglot>=23,<27",
  "python-dotenv>=1.0",
  "jsonschema>=4.0,<5.0",
]
```

Note: hatchling includes all files under `src/tableau2pbir/` by default (not just `.py`), so the `_schemas/*.json` files will be bundled automatically without additional config.

- [x] **Step 2: Install the new dependency**

```bash
pip install -e ".[dev]"
```

Expected: installs `jsonschema` and its dependencies (`attrs`, `jsonschema-specifications`, `referencing`, etc.) with no errors.

- [x] **Step 3: Verify import works**

```bash
python -c "import jsonschema; print(jsonschema.__version__)"
```

Expected: prints a version starting with `4.`.

- [x] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "feat(deps): add jsonschema>=4.0,<5.0 for PBI schema validation"
```

---

## Task 2: Bootstrap `_schemas/` — manifest + bundled schema files

**Files:**
- Create: `src/tableau2pbir/validate/_schemas/manifest.json`
- Create: `src/tableau2pbir/validate/_schemas/*.json` (7 files)

This is a data bootstrap task — no TDD. The result is 8 files committed to the repo.

- [x] **Step 1: Create the `_schemas/` directory**

```bash
mkdir src/tableau2pbir/validate/_schemas
```

- [x] **Step 2: Write `manifest.json`**

Create `src/tableau2pbir/validate/_schemas/manifest.json` with this exact content:

```json
{
  "schemas": [
    {
      "url": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/1.0.0/schema.json",
      "file": "report-visualContainer-1.0.0.json",
      "description": "visual.json — visual container definition (charts, maps)"
    },
    {
      "url": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.0.0/schema.json",
      "file": "report-visualContainer-2.0.0.json",
      "description": "visual.json — visual container definition (slicers)"
    },
    {
      "url": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json",
      "file": "report-page-2.1.0.json",
      "description": "page.json — report page definition"
    },
    {
      "url": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.2.0/schema.json",
      "file": "report-report-3.2.0.json",
      "description": "report.json — report-level metadata"
    },
    {
      "url": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.0.0/schema.json",
      "file": "report-pagesMetadata-1.0.0.json",
      "description": "pages.json — page order and active page"
    },
    {
      "url": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
      "file": "report-versionMetadata-1.0.0.json",
      "description": "version.json — PBIR format version"
    },
    {
      "url": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
      "file": "semanticModel-definitionProperties-1.0.0.json",
      "description": "definition.pbism — semantic model definition"
    }
  ]
}
```

- [x] **Step 3: Download the 7 schema files from Microsoft CDN**

Run this Python script from the repo root (requires internet access):

```bash
python - <<'EOF'
import json, urllib.request
from pathlib import Path

SCHEMAS_DIR = Path("src/tableau2pbir/validate/_schemas")
manifest = json.loads((SCHEMAS_DIR / "manifest.json").read_text(encoding="utf-8"))
for entry in manifest["schemas"]:
    url, filename = entry["url"], entry["file"]
    dest = SCHEMAS_DIR / filename
    print(f"Downloading {filename}...", end=" ", flush=True)
    try:
        with urllib.request.urlopen(url) as resp:
            dest.write_bytes(resp.read())
        print("ok")
    except Exception as e:
        print(f"FAILED: {e}")
EOF
```

Expected output (7 lines, all `ok`):
```
Downloading report-visualContainer-1.0.0.json... ok
Downloading report-visualContainer-2.0.0.json... ok
Downloading report-page-2.1.0.json... ok
Downloading report-report-3.2.0.json... ok
Downloading report-pagesMetadata-1.0.0.json... ok
Downloading report-versionMetadata-1.0.0.json... ok
Downloading semanticModel-definitionProperties-1.0.0.json... ok
```

- [x] **Step 4: Verify all 8 files exist**

```bash
python -c "
from pathlib import Path
d = Path('src/tableau2pbir/validate/_schemas')
files = sorted(d.iterdir())
for f in files:
    print(f.name, f.stat().st_size, 'bytes')
assert len(files) == 8, f'Expected 8 files, got {len(files)}'
print('OK — 8 files present')
"
```

Expected: 8 lines (manifest.json + 7 schema files), all > 0 bytes, final line `OK — 8 files present`.

- [x] **Step 5: Commit**

```bash
git add src/tableau2pbir/validate/_schemas/
git commit -m "feat(validate): add bundled Microsoft PBI schema files and manifest"
```

---

## Task 3: Add result types to `results.py`

**Files:**
- Modify: `src/tableau2pbir/validate/results.py`
- Test: `tests/unit/validate/test_results.py` (new or existing — check if file exists first)

- [x] **Step 1: Write the failing test**

Check if `tests/unit/validate/test_results.py` already exists. If not, create it. Append these tests:

```python
# tests/unit/validate/test_results.py  (append or create)
from tableau2pbir.validate.results import (
    SchemaFinding, SchemaValidationResult, ValidatorOutcome,
)


def test_schema_finding_is_frozen():
    f = SchemaFinding(
        code="schema.violation",
        severity="warn",
        message="'name' is a required property (at (root))",
        location="Report/definition/pages/ReportSection1/visuals/visual_1/visual.json",
    )
    assert f.code == "schema.violation"
    assert f.severity == "warn"
    import pytest
    with pytest.raises(Exception):
        object.__setattr__(f, "code", "other")  # frozen dataclass raises


def test_schema_validation_result_passed():
    r = SchemaValidationResult(outcome=ValidatorOutcome.PASSED, findings=())
    assert r.outcome == ValidatorOutcome.PASSED
    assert r.findings == ()
    assert r.log_path is None


def test_schema_validation_result_failed_with_findings():
    f = SchemaFinding(code="schema.violation", severity="warn",
                      message="msg", location="loc")
    r = SchemaValidationResult(
        outcome=ValidatorOutcome.FAILED,
        findings=(f,),
        log_path="validation/json_schema.json",
    )
    assert r.outcome == ValidatorOutcome.FAILED
    assert len(r.findings) == 1
    assert r.log_path == "validation/json_schema.json"
```

- [x] **Step 2: Run to confirm failure**

```bash
pytest tests/unit/validate/test_results.py -v -k "schema"
```

Expected: `ImportError: cannot import name 'SchemaFinding'`

- [x] **Step 3: Add the new types to `results.py`**

Append to the end of `src/tableau2pbir/validate/results.py`:

```python


@dataclass(frozen=True)
class SchemaFinding:
    code: str        # "schema.violation" | "schema.not_cached"
    severity: str    # "warn" (always, until promoted to hard-blocker)
    message: str
    location: str    # path relative to out_dir


@dataclass(frozen=True)
class SchemaValidationResult:
    outcome: ValidatorOutcome
    findings: tuple[SchemaFinding, ...]
    log_path: str | None = None
```

- [x] **Step 4: Run tests to confirm pass**

```bash
pytest tests/unit/validate/test_results.py -v -k "schema"
```

Expected: 3 tests PASSED.

- [x] **Step 5: Commit**

```bash
git add src/tableau2pbir/validate/results.py tests/unit/validate/test_results.py
git commit -m "feat(validate): add SchemaFinding and SchemaValidationResult types"
```

---

## Task 4: Implement `json_schema.py` — cache lookup + auto-discovery

**Files:**
- Create: `src/tableau2pbir/validate/json_schema.py`
- Create: `tests/unit/validate/test_schema_cache.py`
- Create: `tests/unit/validate/test_json_schema.py`

### Part A — `_resolve_schema` cache lookup (3 tests)

- [x] **Step 1: Write failing tests for `_resolve_schema`**

Create `tests/unit/validate/test_schema_cache.py`:

```python
"""Tests for _resolve_schema two-tier cache lookup."""
import json
import pytest
from pathlib import Path

FAKE_URL = "https://example.com/fake/1.0.0/schema.json"
FAKE_SCHEMA = {"$schema": "http://json-schema.org/draft-07/schema#", "type": "object"}
ALT_SCHEMA = {"$schema": "http://json-schema.org/draft-07/schema#", "type": "string"}


def _make_bundled(tmp_path: Path, include_schema: bool = True) -> Path:
    bundled = tmp_path / "bundled"
    bundled.mkdir()
    manifest = {"schemas": [{"url": FAKE_URL, "file": "fake-1.0.0.json", "description": "test"}]}
    (bundled / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    if include_schema:
        (bundled / "fake-1.0.0.json").write_text(json.dumps(FAKE_SCHEMA), encoding="utf-8")
    return bundled


def test_resolve_user_cache_hit(tmp_path):
    bundled = _make_bundled(tmp_path, include_schema=True)
    user_cache = tmp_path / "user_cache"
    user_cache.mkdir()
    # Put a different schema in user cache to prove it wins over bundled
    (user_cache / "fake-1.0.0.json").write_text(json.dumps(ALT_SCHEMA), encoding="utf-8")

    from tableau2pbir.validate.json_schema import _resolve_schema
    result = _resolve_schema(FAKE_URL, user_cache, bundled)
    assert result == ALT_SCHEMA


def test_resolve_bundled_fallback(tmp_path):
    bundled = _make_bundled(tmp_path, include_schema=True)
    user_cache = tmp_path / "empty_cache"
    user_cache.mkdir()  # empty — no files

    from tableau2pbir.validate.json_schema import _resolve_schema
    result = _resolve_schema(FAKE_URL, user_cache, bundled)
    assert result == FAKE_SCHEMA


def test_resolve_returns_none_when_files_missing(tmp_path):
    bundled = _make_bundled(tmp_path, include_schema=False)  # manifest exists, schema file does not
    user_cache = tmp_path / "empty_cache"
    user_cache.mkdir()

    from tableau2pbir.validate.json_schema import _resolve_schema
    result = _resolve_schema(FAKE_URL, user_cache, bundled)
    assert result is None
```

- [x] **Step 2: Run to confirm failure**

```bash
pytest tests/unit/validate/test_schema_cache.py -v
```

Expected: `ModuleNotFoundError: No module named 'tableau2pbir.validate.json_schema'`

- [x] **Step 3: Create `json_schema.py` with `_load_manifest` and `_resolve_schema`**

Create `src/tableau2pbir/validate/json_schema.py`:

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
    findings: list[SchemaFinding] = []

    for json_file in sorted(out_dir.rglob("*.json")):
        rel_parts = json_file.relative_to(out_dir).parts
        if rel_parts[0] in _SKIP_DIRS:
            continue
        try:
            data: dict[str, object] = json.loads(json_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
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
            continue  # in manifest but files missing — packaging error, skip silently
        validator = jsonschema.Draft7Validator(schema)
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

- [x] **Step 4: Run cache tests to confirm pass**

```bash
pytest tests/unit/validate/test_schema_cache.py -v
```

Expected: 3 tests PASSED.

### Part B — `run_json_schema` auto-discovery (8 tests)

- [x] **Step 5: Write failing tests for `run_json_schema`**

Create `tests/unit/validate/test_json_schema.py`:

```python
"""Tests for run_json_schema auto-discovery validator."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tableau2pbir.validate.json_schema import run_json_schema
from tableau2pbir.validate.results import ValidatorOutcome

FAKE_URL = "https://example.com/fake/1.0.0/schema.json"

FAKE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["name"],
    "properties": {"name": {"type": "string"}},
    "additionalProperties": False,
}

STRICT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["name", "extra"],
    "properties": {
        "name": {"type": "string"},
        "extra": {"type": "string"},
    },
}


def _setup(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Returns (out_dir, bundled_dir, user_cache)."""
    out_dir = tmp_path / "output"
    out_dir.mkdir()
    bundled = tmp_path / "bundled"
    bundled.mkdir()
    manifest = {
        "schemas": [{"url": FAKE_URL, "file": "fake-1.0.0.json", "description": "test"}]
    }
    (bundled / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (bundled / "fake-1.0.0.json").write_text(json.dumps(FAKE_SCHEMA), encoding="utf-8")
    user_cache = tmp_path / "user_cache"
    user_cache.mkdir()
    return out_dir, bundled, user_cache


def test_valid_file_passes(tmp_path: Path) -> None:
    out_dir, bundled, user_cache = _setup(tmp_path)
    (out_dir / "test.json").write_text(
        json.dumps({"$schema": FAKE_URL, "name": "foo"}), encoding="utf-8"
    )
    result = run_json_schema(out_dir, cache_dir=user_cache, _bundled_dir=bundled)
    assert result.outcome == ValidatorOutcome.PASSED
    assert result.findings == ()


def test_invalid_file_produces_finding(tmp_path: Path) -> None:
    out_dir, bundled, user_cache = _setup(tmp_path)
    (out_dir / "bad.json").write_text(
        json.dumps({"$schema": FAKE_URL}),  # missing required "name"
        encoding="utf-8",
    )
    result = run_json_schema(out_dir, cache_dir=user_cache, _bundled_dir=bundled)
    assert result.outcome == ValidatorOutcome.FAILED
    assert len(result.findings) == 1
    assert result.findings[0].code == "schema.violation"
    assert "name" in result.findings[0].message


def test_file_without_schema_key_skipped(tmp_path: Path) -> None:
    out_dir, bundled, user_cache = _setup(tmp_path)
    (out_dir / "no_schema.json").write_text(
        json.dumps({"version": "4.0", "x": 1}), encoding="utf-8"
    )
    result = run_json_schema(out_dir, cache_dir=user_cache, _bundled_dir=bundled)
    assert result.outcome == ValidatorOutcome.PASSED
    assert result.findings == ()


def test_unknown_schema_url_produces_not_cached_finding(tmp_path: Path) -> None:
    out_dir, bundled, user_cache = _setup(tmp_path)
    (out_dir / "unknown.json").write_text(
        json.dumps({"$schema": "https://unknown.example.com/schema.json", "x": 1}),
        encoding="utf-8",
    )
    result = run_json_schema(out_dir, cache_dir=user_cache, _bundled_dir=bundled)
    assert result.outcome == ValidatorOutcome.FAILED
    assert result.findings[0].code == "schema.not_cached"
    assert "unknown.example.com" in result.findings[0].message


def test_stages_dir_excluded(tmp_path: Path) -> None:
    out_dir, bundled, user_cache = _setup(tmp_path)
    stages = out_dir / "stages"
    stages.mkdir()
    (stages / "01_extract.json").write_text(
        json.dumps({"$schema": "https://unknown.example.com/bad.json"}), encoding="utf-8"
    )
    result = run_json_schema(out_dir, cache_dir=user_cache, _bundled_dir=bundled)
    assert result.outcome == ValidatorOutcome.PASSED
    assert result.findings == ()


def test_validation_dir_excluded(tmp_path: Path) -> None:
    out_dir, bundled, user_cache = _setup(tmp_path)
    validation = out_dir / "validation"
    validation.mkdir()
    (validation / "structural.json").write_text(
        json.dumps({"$schema": "https://unknown.example.com/bad.json"}), encoding="utf-8"
    )
    result = run_json_schema(out_dir, cache_dir=user_cache, _bundled_dir=bundled)
    assert result.outcome == ValidatorOutcome.PASSED
    assert result.findings == ()


def test_user_cache_takes_precedence_over_bundled(tmp_path: Path) -> None:
    out_dir, bundled, user_cache = _setup(tmp_path)
    # Place a stricter schema in user cache (requires both "name" AND "extra")
    (user_cache / "fake-1.0.0.json").write_text(json.dumps(STRICT_SCHEMA), encoding="utf-8")
    # File that satisfies bundled (just "name") but fails strict (missing "extra")
    (out_dir / "test.json").write_text(
        json.dumps({"$schema": FAKE_URL, "name": "foo"}), encoding="utf-8"
    )
    result = run_json_schema(out_dir, cache_dir=user_cache, _bundled_dir=bundled)
    # If user cache is used → FAILED (missing "extra"); if bundled used → PASSED
    assert result.outcome == ValidatorOutcome.FAILED


def test_bundled_fallback_used_when_user_cache_empty(tmp_path: Path) -> None:
    out_dir, bundled, user_cache = _setup(tmp_path)
    # user_cache is empty — bundled has the schema
    (out_dir / "test.json").write_text(
        json.dumps({"$schema": FAKE_URL, "name": "foo"}), encoding="utf-8"
    )
    result = run_json_schema(out_dir, cache_dir=user_cache, _bundled_dir=bundled)
    assert result.outcome == ValidatorOutcome.PASSED
```

- [x] **Step 6: Run to confirm failure**

```bash
pytest tests/unit/validate/test_json_schema.py -v
```

Expected: all 8 tests FAILED with import errors or assertion errors (module exists now but tests exercise real logic).

- [x] **Step 7: Run tests to confirm all pass (implementation already done in Step 3)**

```bash
pytest tests/unit/validate/test_json_schema.py -v
```

Expected: 8 tests PASSED.

- [x] **Step 8: Run the full unit suite to check for regressions**

```bash
pytest tests/unit/ -x -q
```

Expected: all existing tests still pass + 11 new tests pass.

- [x] **Step 9: Commit**

```bash
git add src/tableau2pbir/validate/json_schema.py \
        tests/unit/validate/test_schema_cache.py \
        tests/unit/validate/test_json_schema.py
git commit -m "feat(validate): add json_schema validator with two-tier schema cache"
```

---

## Task 5: Implement `refresh_schemas.py` with TDD

**Files:**
- Create: `src/tableau2pbir/validate/refresh_schemas.py`
- Create: `tests/unit/validate/test_refresh_schemas.py`

- [x] **Step 1: Write failing tests**

Create `tests/unit/validate/test_refresh_schemas.py`:

```python
"""Tests for refresh_schemas command logic."""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

FAKE_CONTENT_A = b'{"$schema":"http://json-schema.org/draft-07/schema#","type":"object"}'
FAKE_CONTENT_B = b'{"$schema":"http://json-schema.org/draft-07/schema#","type":"string"}'


def _make_bundled(tmp_path: Path) -> Path:
    bundled = tmp_path / "bundled"
    bundled.mkdir()
    manifest = {
        "schemas": [
            {
                "url": "https://example.com/schema-a/1.0.0/schema.json",
                "file": "schema-a-1.0.0.json",
                "description": "A",
            },
            {
                "url": "https://example.com/schema-b/1.0.0/schema.json",
                "file": "schema-b-1.0.0.json",
                "description": "B",
            },
        ]
    }
    (bundled / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return bundled


def _mock_urlopen(responses: dict[str, bytes] | None = None) -> MagicMock:
    """Returns a mock for urllib.request.urlopen that serves bytes by URL."""
    default_content = FAKE_CONTENT_A
    if responses is None:
        responses = {}

    def fake_open(url: str) -> MagicMock:
        content = responses.get(url, default_content)
        cm = MagicMock()
        cm.__enter__ = lambda s: s
        cm.__exit__ = MagicMock(return_value=False)
        cm.read.return_value = content
        return cm

    return MagicMock(side_effect=fake_open)


def test_refresh_downloads_all_schemas(tmp_path: Path) -> None:
    bundled = _make_bundled(tmp_path)
    cache = tmp_path / "cache"
    with patch("urllib.request.urlopen", _mock_urlopen()):
        from tableau2pbir.validate.refresh_schemas import refresh_schemas
        ok = refresh_schemas(cache_dir=cache, bundled_dir=bundled)
    assert ok is True
    assert (cache / "schema-a-1.0.0.json").read_bytes() == FAKE_CONTENT_A
    assert (cache / "schema-b-1.0.0.json").read_bytes() == FAKE_CONTENT_A


def test_refresh_skips_unchanged(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bundled = _make_bundled(tmp_path)
    cache = tmp_path / "cache"
    cache.mkdir()
    # Pre-populate cache with same content the mock will return
    (cache / "schema-a-1.0.0.json").write_bytes(FAKE_CONTENT_A)
    (cache / "schema-b-1.0.0.json").write_bytes(FAKE_CONTENT_A)
    with patch("urllib.request.urlopen", _mock_urlopen()):
        from tableau2pbir.validate.refresh_schemas import refresh_schemas
        refresh_schemas(cache_dir=cache, bundled_dir=bundled)
    captured = capsys.readouterr()
    assert "unchanged" in captured.out
    assert "updated" not in captured.out


def test_refresh_returns_false_on_network_failure(tmp_path: Path) -> None:
    bundled = _make_bundled(tmp_path)
    cache = tmp_path / "cache"
    with patch("urllib.request.urlopen", side_effect=OSError("network error")):
        from tableau2pbir.validate.refresh_schemas import refresh_schemas
        ok = refresh_schemas(cache_dir=cache, bundled_dir=bundled)
    assert ok is False


def test_refresh_custom_cache_dir_creates_dir(tmp_path: Path) -> None:
    bundled = _make_bundled(tmp_path)
    custom_cache = tmp_path / "deeply" / "nested" / "cache"
    assert not custom_cache.exists()
    with patch("urllib.request.urlopen", _mock_urlopen()):
        from tableau2pbir.validate.refresh_schemas import refresh_schemas
        refresh_schemas(cache_dir=custom_cache, bundled_dir=bundled)
    assert (custom_cache / "schema-a-1.0.0.json").exists()


def test_get_cache_dir_uses_env_var(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_path = tmp_path / "env_cache"
    monkeypatch.setenv("T2P_SCHEMA_CACHE", str(env_path))
    from tableau2pbir.validate.refresh_schemas import _get_cache_dir
    assert _get_cache_dir() == env_path
```

- [x] **Step 2: Run to confirm failure**

```bash
pytest tests/unit/validate/test_refresh_schemas.py -v
```

Expected: `ModuleNotFoundError: No module named 'tableau2pbir.validate.refresh_schemas'`

- [x] **Step 3: Implement `refresh_schemas.py`**

Create `src/tableau2pbir/validate/refresh_schemas.py`:

```python
"""refresh-schemas command logic — downloads schemas to user cache. See spec §8."""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

_BUNDLED_DIR = Path(__file__).parent / "_schemas"


def _get_cache_dir(cli_override: str | None = None) -> Path:
    """Resolve cache dir: CLI flag → T2P_SCHEMA_CACHE env var → default."""
    val = cli_override or os.environ.get("T2P_SCHEMA_CACHE")
    return Path(val) if val else Path.home() / ".cache" / "tableau2pbir" / "schemas"


def refresh_schemas(cache_dir: Path, bundled_dir: Path = _BUNDLED_DIR) -> bool:
    """Download all schemas from manifest into cache_dir. Returns True if all succeeded."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    data = json.loads((bundled_dir / "manifest.json").read_text(encoding="utf-8"))
    all_ok = True
    for entry in data["schemas"]:
        url: str = entry["url"]
        filename: str = entry["file"]
        dest = cache_dir / filename
        try:
            with urllib.request.urlopen(url) as resp:
                content: bytes = resp.read()
        except Exception as exc:
            print(f"FAILED   {filename} ({exc})")
            all_ok = False
            continue
        existing = dest.read_bytes() if dest.is_file() else None
        if existing == content:
            print(f"unchanged  {filename}")
        else:
            dest.write_bytes(content)
            print(f"updated  {filename}")
    return all_ok
```

- [x] **Step 4: Run tests to confirm pass**

```bash
pytest tests/unit/validate/test_refresh_schemas.py -v
```

Expected: 5 tests PASSED.

- [x] **Step 5: Commit**

```bash
git add src/tableau2pbir/validate/refresh_schemas.py \
        tests/unit/validate/test_refresh_schemas.py
git commit -m "feat(validate): add refresh_schemas module for user cache update"
```

---

## Task 6: Add `refresh-schemas` subcommand to `cli.py`

**Files:**
- Modify: `src/tableau2pbir/cli.py`

No new test file needed — the `test_get_cache_dir_uses_env_var` test in Task 5 already covers the core logic. The CLI wiring is thin glue code.

- [x] **Step 1: Add `_cmd_refresh_schemas` and register the subcommand**

Edit `src/tableau2pbir/cli.py`. Add the import and handler after the `_cmd_resume` function (before `build_parser`):

```python
def _cmd_refresh_schemas(args: argparse.Namespace) -> int:
    from tableau2pbir.validate.refresh_schemas import _get_cache_dir, refresh_schemas
    cache_dir = _get_cache_dir(cli_override=getattr(args, "cache_dir", None))
    ok = refresh_schemas(cache_dir=cache_dir)
    return 0 if ok else 1
```

Then in `build_parser()`, add the subparser after the `p_res` block (before `return parser`):

```python
    p_refresh = sub.add_parser(
        "refresh-schemas",
        help="Download latest Microsoft PBI schemas to local cache.",
    )
    p_refresh.add_argument(
        "--cache-dir",
        default=None,
        help="Override schema cache directory (default: ~/.cache/tableau2pbir/schemas/)",
    )
    p_refresh.set_defaults(func=_cmd_refresh_schemas)
```

- [x] **Step 2: Verify the CLI shows the new subcommand**

```bash
python -m tableau2pbir.cli --help
```

Expected output includes:
```
  refresh-schemas  Download latest Microsoft PBI schemas to local cache.
```

- [x] **Step 3: Dry-run the command with `--cache-dir` pointing to a temp location**

```bash
python -m tableau2pbir.cli refresh-schemas --cache-dir /tmp/schema_test_cache
```

Expected: 7 lines of output (`updated` or `unchanged` for each schema file), exit code 0.

Verify the files were written:
```bash
ls /tmp/schema_test_cache/
```

Expected: 7 `.json` files.

- [x] **Step 4: Commit**

```bash
git add src/tableau2pbir/cli.py
git commit -m "feat(cli): add refresh-schemas subcommand"
```

---

## Task 7: Wire `run_json_schema` into `s08_package_validate.py`

**Files:**
- Modify: `src/tableau2pbir/stages/s08_package_validate.py`

- [x] **Step 1: Add the import**

In `s08_package_validate.py`, change the validate import block from:

```python
from tableau2pbir.validate import (
    desktop_open as _do, pbir_compile as _pbir, pbip as _pbip,
    report as _report, rubric as _rubric, status as _status,
    structural as _struct, tmdl_schema as _tmdl,
)
```

to:

```python
from tableau2pbir.validate import (
    desktop_open as _do, json_schema as _schema, pbir_compile as _pbir, pbip as _pbip,
    report as _report, rubric as _rubric, status as _status,
    structural as _struct, tmdl_schema as _tmdl,
)
```

- [x] **Step 2: Add the validator call and log write**

In the `run()` function, after the structural block (after the `(out_dir / "validation" / "structural.json").write_text(...)` call), add:

```python
    # 4.5. JSON schema validation (soft warning — does not affect pipeline status).
    schema_res = _schema.run_json_schema(out_dir)
    (out_dir / "validation" / "json_schema.json").write_text(
        json.dumps({
            "outcome": schema_res.outcome.value,
            "findings": [
                {"code": f.code, "severity": f.severity,
                 "message": f.message, "location": f.location}
                for f in schema_res.findings
            ],
        }, indent=2), encoding="utf-8")
```

- [x] **Step 3: Add `json_schema` to the validators dict**

In the `validators` dict (around line 137), add the `json_schema` entry after the `structural` entry:

```python
        "json_schema":  {"result": schema_res.outcome.value,
                         "reason": None,
                         "findings": [
                             {"code": f.code, "severity": f.severity,
                              "message": f.message, "location": f.location}
                             for f in schema_res.findings
                         ],
                         "log_path": schema_res.log_path},
```

- [x] **Step 4: Run the full unit suite**

```bash
pytest tests/unit/ -x -q
```

Expected: all tests pass (no regressions from the import change).

- [x] **Step 5: Run the full E2E suite**

```bash
pytest tests/integration/test_real_workbooks_e2e.py -v
```

Expected: all real-workbook E2E tests pass. Each workbook report now has a `json_schema` section in the validator output. If any test produces `schema.violation` findings, investigate before committing — those indicate genuine output bugs.

- [x] **Step 6: Spot-check one workbook's validation log**

Run a single conversion and inspect the json_schema log:

```bash
python -m tableau2pbir.cli convert tests/golden/real/simple_join_calculated_line.twb --out /tmp/plan10_check
cat "/tmp/plan10_check/simple_join_calculated_line/validation/json_schema.json"
```

Expected: `"outcome": "passed"` with an empty `"findings": []`. If findings appear, read each one carefully — the `location` and `message` fields identify exactly which file and property failed.

- [x] **Step 7: Commit**

```bash
git add src/tableau2pbir/stages/s08_package_validate.py
git commit -m "feat(s08): wire run_json_schema into Stage 8 as soft-warning validator"
```

---

## Task 8: Update CLAUDE.md + final verification

**Files:**
- Modify: `CLAUDE.md`

- [x] **Step 1: Add Plan 10 to the implementation tracking table in `CLAUDE.md`**

In the `## Implementation Tracking` table, add a new row:

```markdown
| 10 | JSON Schema Validation Against Official Microsoft PBI Schemas | ✅ DONE | `docs/superpowers/plans/2026-05-30-plan-10-json-schema-validation.md` |
```

Also update the summary paragraph below the table to include:

```
**Plan 10 complete (2026-05-30):** Added JSON schema validation against official Microsoft PBI
schemas. New `validate/json_schema.py` auto-discovers all `*.json` output files, resolves each
file's `$schema` URL via two-tier cache (user cache → bundled fallback in `_schemas/`), and
validates with `jsonschema.Draft7Validator`. Schema violations reported as soft warnings.
New `tableau2pbir refresh-schemas` CLI command updates user cache from Microsoft CDN.
16 new unit tests across `test_schema_cache.py`, `test_json_schema.py`, `test_refresh_schemas.py`.
```

- [x] **Step 2: Run the complete test suite one final time**

```bash
pytest tests/ -x -q
```

Expected: all tests pass. Count should be previous count + 16 new unit tests.

- [x] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: mark Plan 10 complete — JSON schema validation against Microsoft PBI schemas"
```
