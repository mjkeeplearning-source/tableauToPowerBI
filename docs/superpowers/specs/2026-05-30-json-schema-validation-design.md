# JSON Schema Validation Against Official Microsoft PBI Schemas

**Date:** 2026-05-30
**Status:** Approved
**Plan:** Plan 10 (to be written)

---

## 1. Problem

The current project emits PBIR JSON files with `$schema` fields pointing to the official Microsoft CDN schemas, but never validates them. The MVP project validated every generated JSON file against its declared schema using `jsonschema.Draft7Validator`. This gap means schema-level bugs in `visual.json`, `page.json`, `report.json`, etc. — wrong property names, missing required fields, wrong value types — pass through all 457 tests undetected and are only caught when PBI Desktop fails to open the output.

---

## 2. Goals

- Validate every PBIR JSON output file against its official Microsoft schema
- Work fully offline (no network dependency at conversion time)
- Allow users to refresh schemas from the Microsoft CDN via a single CLI command
- Report violations as soft warnings (findings in the validation log) without blocking the pipeline status
- Fit cleanly into the existing `validate/` module pattern

---

## 3. Non-Goals

- TMDL file validation (plain text, not JSON — handled by `tmdl_schema.py` via TabularEditor 2)
- Hard-blocking the pipeline on schema violations (deferred until validator is validated against real workbooks)
- Validating files outside the converter's output directory

---

## 4. Architecture

Three new pieces, all contained within the existing `validate/` structure:

```
src/tableau2pbir/
  validate/
    json_schema.py          ← new validator module
    _schemas/               ← bundled fallback schemas (package data)
      manifest.json         ← maps schema URL → filename + description
      *.json                ← one file per known schema URL
  cli.py                    ← adds `refresh-schemas` subcommand
pyproject.toml              ← adds jsonschema>=4.0,<5.0 dependency
```

### Schema Resolution — Two-Tier Lookup

```
1. User cache:   ~/.cache/tableau2pbir/schemas/   (or $T2P_SCHEMA_CACHE env var)
                 ↑ populated by `tableau2pbir refresh-schemas`
2. Bundled:      src/tableau2pbir/validate/_schemas/
                 ↑ shipped with the package, always present, works on fresh install
```

The validator checks the user cache first (freshest), falls back to bundled (offline safety). The bundled schemas are updated manually by developers before a release; `refresh-schemas` only writes to the user cache.

### Manifest Format

`validate/_schemas/manifest.json`:

```json
{
  "schemas": [
    {
      "url": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/1.0.0/schema.json",
      "file": "report-visualContainer-1.0.0.json",
      "description": "visual.json — visual container definition"
    },
    {
      "url": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json",
      "file": "report-page-2.1.0.json",
      "description": "page.json — report page definition"
    },
    {
      "url": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/1.0.0/schema.json",
      "file": "report-report-1.0.0.json",
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
      "url": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
      "file": "report-definitionProperties-2.0.0.json",
      "description": "definition.pbir — report definition and dataset reference"
    },
    {
      "url": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
      "file": "semanticModel-definitionProperties-1.0.0.json",
      "description": "definition.pbism — semantic model definition"
    }
  ]
}
```

The filename slug (`report-visualContainer-1.0.0.json`) is human-readable and stable. Both cache tiers use the same filename.

---

## 5. Validator Module — `validate/json_schema.py`

### Public API

```python
def run_json_schema(out_dir: Path) -> SchemaValidationResult
```

### Algorithm

1. Walk all `*.json` files under `out_dir` recursively
2. Skip files under `out_dir/validation/` and `out_dir/stages/` — those are internal pipeline artifacts, not PBIR output
3. For each file:
   a. Parse JSON — if invalid JSON, skip (structural.py already catches malformed JSON)
   b. Check for top-level `$schema` key — if absent, skip (not a file we validate)
   c. Call `_resolve_schema(url)` → returns schema dict or `None`
      - If URL is not in manifest: append `SchemaFinding(code="schema.not_cached", severity="warn")` and continue
      - Check user cache: `<cache_dir>/<filename>` where filename is looked up from manifest by URL
      - Fall back to bundled: `validate/_schemas/<filename>`
      - If URL is in manifest but file is absent from both caches (packaging error): return `None`, skip validation for this file
   d. Validate with `jsonschema.Draft7Validator(schema).iter_errors(data)`
   e. Each error → `SchemaFinding(code="schema.violation", severity="warn", message=<error + path>, location=<rel path to file>)`
4. Return `SchemaValidationResult(outcome=PASSED if no findings else FAILED, findings=tuple(findings))`

### Schema Lookup Detail

`_resolve_schema(url: str) -> dict | None`:
- Builds a URL→filename map by loading `manifest.json` once (module-level cache)
- Looks up the filename for the given URL
- Checks user cache path, then bundled path
- Returns parsed JSON dict or None

### Excluded Directories

Files under these paths relative to `out_dir` are skipped:
- `validation/` — validator log files
- `stages/` — pipeline stage intermediate JSON

---

## 6. New Result Types — `results.py`

```python
@dataclass(frozen=True)
class SchemaFinding:
    code: str        # "schema.violation" | "schema.not_cached"
    severity: str    # "warn" (always, until promoted to hard-blocker)
    message: str     # jsonschema error message + property path
    location: str    # path relative to out_dir

@dataclass(frozen=True)
class SchemaValidationResult:
    outcome: ValidatorOutcome   # PASSED | FAILED
    findings: tuple[SchemaFinding, ...]
    log_path: str | None = None
```

---

## 7. Integration into Stage 8 — `s08_package_validate.py`

After the existing structural check:

```python
schema_res = _schema.run_json_schema(out_dir)

(out_dir / "validation" / "json_schema.json").write_text(
    json.dumps({
        "outcome": schema_res.outcome.value,
        "findings": [{"code": f.code, "severity": f.severity,
                      "message": f.message, "location": f.location}
                     for f in schema_res.findings],
    }, indent=2), encoding="utf-8")
```

Added to the `validators` dict as `"json_schema"` for inclusion in the workbook report.

**`status.py` and `compute_status()` are not changed.** The `json_schema` outcome does not feed into pipeline status. Schema findings are visible in the report but do not cause a `failed` or `needs_review` status. This will be promoted to a hard-blocker in a later plan after validating against real workbooks.

---

## 8. CLI — `refresh-schemas` Subcommand

```
tableau2pbir refresh-schemas [--cache-dir PATH]
```

**Behaviour:**
1. Load `manifest.json` to get the list of known schema URLs and filenames
2. For each schema:
   - Download from the manifest URL using `urllib.request`
   - Compare to existing cached file (if any) — skip if identical
   - Write to `cache_dir/<filename>`
   - Print: `updated  report-visualContainer-1.0.0.json` / `unchanged ...` / `FAILED   ... (<reason>)`
3. Exit code 0 if all schemas downloaded successfully, 1 if any failed

**Default cache dir:** `~/.cache/tableau2pbir/schemas/` (created if absent)
**Override:** `--cache-dir PATH` flag or `T2P_SCHEMA_CACHE` env var

The bundled `_schemas/` directory is **never written to** by this command. Updating bundled schemas is a developer task done manually before a package release (download fresh copies, replace files, update manifest if version URLs changed).

---

## 9. Dependency Change

`pyproject.toml`:

```toml
dependencies = [
  ...
  "jsonschema>=4.0,<5.0",
]
```

No other new runtime dependencies. `urllib.request` is stdlib.

---

## 10. Tests

All new tests in `tests/unit/validate/`:

### `test_json_schema.py`

| Test | What it verifies |
|------|-----------------|
| `test_valid_file_passes` | A JSON file whose `$schema` matches the bundled schema produces zero findings |
| `test_invalid_file_produces_finding` | A JSON file with a missing required property produces a `schema.violation` finding |
| `test_file_without_schema_key_skipped` | A JSON file without `$schema` is skipped entirely |
| `test_unknown_schema_url_produces_warning` | A `$schema` URL not in the manifest produces `schema.not_cached` finding |
| `test_stages_dir_excluded` | Files under `out_dir/stages/` are not validated |
| `test_validation_dir_excluded` | Files under `out_dir/validation/` are not validated |
| `test_user_cache_takes_precedence` | When both user cache and bundled have a schema, user cache is used |
| `test_bundled_fallback_used` | When user cache is absent, bundled schema is used |

### `test_refresh_schemas.py`

| Test | What it verifies |
|------|-----------------|
| `test_refresh_downloads_all_schemas` | All URLs in manifest are downloaded (mocked `urllib.request`) |
| `test_refresh_skips_unchanged` | Files identical to existing cache are reported as `unchanged` |
| `test_refresh_exit_1_on_failure` | A network error for any schema sets exit code 1 |
| `test_refresh_custom_cache_dir` | `--cache-dir` flag writes to the specified path |
| `test_refresh_env_var_cache_dir` | `T2P_SCHEMA_CACHE` env var overrides default cache dir |

### `test_schema_cache.py`

| Test | What it verifies |
|------|-----------------|
| `test_resolve_user_cache_hit` | Returns schema from user cache when file exists |
| `test_resolve_bundled_fallback` | Returns bundled schema when user cache is absent |
| `test_resolve_returns_none_when_missing` | Returns None when neither cache has the URL |

### E2E coverage

`tests/integration/test_real_workbooks_e2e.py` already runs the full pipeline including `s08`. After this change those tests will also exercise `run_json_schema` against real generated output — all expected to pass since Plan 9 fixed the blocking TMDL bugs.

---

## 11. Promotion Path to Hard-Blocker

After this plan ships:
1. Run against all golden real workbooks — confirm zero schema findings
2. Run against a few new real workbooks
3. If consistently zero findings: update `status.py` to treat `json_schema` outcome as a blocker
4. Document in CLAUDE.md under a new Plan 11 entry

---

## 12. File Change Summary

| File | Change |
|------|--------|
| `src/tableau2pbir/validate/json_schema.py` | New — validator module |
| `src/tableau2pbir/validate/_schemas/manifest.json` | New — schema URL manifest |
| `src/tableau2pbir/validate/_schemas/*.json` | New — 7 bundled schema files |
| `src/tableau2pbir/validate/results.py` | Add `SchemaFinding`, `SchemaValidationResult` |
| `src/tableau2pbir/stages/s08_package_validate.py` | Call `run_json_schema`, add to validators dict |
| `src/tableau2pbir/cli.py` | Add `refresh-schemas` subcommand |
| `pyproject.toml` | Add `jsonschema>=4.0,<5.0` |
| `tests/unit/validate/test_json_schema.py` | New — 8 unit tests |
| `tests/unit/validate/test_refresh_schemas.py` | New — 5 unit tests |
| `tests/unit/validate/test_schema_cache.py` | New — 3 unit tests |
