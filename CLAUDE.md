# Tableau → PBIR Converter — Claude Workspace

## Project

Automated pipeline that converts local Tableau workbooks (`.twb`/`.twbx`) into Power BI projects in **PBIR format**. Publishing is out of scope.

## Implementation Tracking

| Plan | Title | Status | File |
|------|-------|--------|------|
| 1 | Scaffolding & Infrastructure | ✅ DONE | `docs/superpowers/plans/2026-04-23-plan-1-scaffolding-infra.md` |
| 2 | Stage 1 & 2 — Extract + Canonicalize → IR | ✅ DONE | `docs/superpowers/plans/2026-04-24-plan-2-extract-canonicalize.md` |
| 3 | Stage 3 & 4 — Calc Translation + Visual Mapping | ✅ DONE | `docs/superpowers/plans/2026-04-26-plan-3-calc-translation-visual-mapping.md` |
| 4 | Stage 5, 6 & 7 — Layout, TMDL + PBIR Emission | ✅ DONE | `docs/superpowers/plans/2026-04-29-plan-4-layout-tmdl-pbir-emission.md` |
| 5 | Stage 8 — Package, Validate & Desktop-Open Gate | ⏸ HALTED | `docs/superpowers/plans/2026-05-01-plan-5-package-validate-desktop-gate.md` |
| 6 | PBIR Schema Fixes — Desktop-Open Unblocking | ✅ DONE | `docs/superpowers/plans/2026-05-02-plan-6-pbir-schema-fixes.md` |
| 7 | TMDL Column Emission Fix | ✅ DONE | `docs/superpowers/plans/2026-05-02-plan-7-tmdl-column-emission.md` |
| 8 | Visual Emission Fix — Markers, Channels, Field Resolution, Naming | ✅ DONE | `docs/superpowers/plans/2026-05-02-plan-8-visual-emission-fix.md` |
| 9 | TMDL Syntax Fixes — PBI Desktop Openability | ✅ DONE | `docs/superpowers/plans/2026-05-30-plan-9-tmdl-syntax-fixes.md` |
| 10 | JSON Schema Validation Against Official Microsoft PBI Schemas | ✅ DONE | `docs/superpowers/plans/2026-05-30-plan-10-json-schema-validation.md` |
| 11 | Filter IR Enrichment & Schema-Compliant Emission | ✅ DONE | `docs/superpowers/plans/2026-05-31-plan-11-filter-ir-enrichment.md` |
| 12 | Mark Style Emission — Data Labels & Static Color | ✅ DONE | `docs/superpowers/plans/2026-05-31-plan-12-mark-style-emission.md` |

**Session rules:**
- Read the active plan file at the start of every session.
- Execute one task at a time. Mark complete before moving to the next.
- Do not skip or batch tasks.
- Follow TDD strictly: failing test → red → implement → green → commit.
- After each plan completes, update the table above and write the next plan.

**Plan 8 complete (2026-05-02):** Fixed all 7 visual emission bugs: (1) datasource marker pills
filtered from Stage 2 encoding; (2) catalog channel names capitalized to PBI-required form;
(3) dispatch fixed — bar chart COLUMNS→Category, ROWS→Y; (4) new `field_lookup.py` bridges
pill slugs to semantic model names using `slug_id(col.name)` matching; (5) `render_visual`
uses `Entity` key, resolved names, `queryRef`, `active`, correct `Column`/`Measure` type;
(6) page/visual naming changed to `ReportSection{N}`/`visual_{N}`; (7) stale integration
test assertion fixed. All 439 unit tests + 18 real-workbook E2E tests pass.

**Plan 9 complete (2026-05-30):** Fixed all four TMDL/PBIR emission bugs: (1) `measure.py`
now emits `= DAX` inline syntax; (2) `column.py` now emits `= DAX` inline for calculated
columns with multiline DAX support; (3) `page.py` omits `filterConfig` when no filters;
(4) `model.py` stripped to minimal properties only. PBI Desktop can now open converted
output. Plan 5 resumes next.

**Plan 10 complete (2026-05-31):** Added JSON schema validation against official Microsoft PBI
schemas. New `validate/json_schema.py` auto-discovers all `*.json` output files, resolves each
file's `$schema` URL via two-tier cache (user cache → bundled fallback in `_schemas/`), and
validates with `jsonschema.Draft7Validator`. Schema violations reported as soft warnings in
Stage 8. New `tableau2pbir refresh-schemas` CLI command updates user cache from Microsoft CDN.
16 new unit tests across `test_schema_cache.py`, `test_json_schema.py`, `test_refresh_schemas.py`.
Key finding: all 7 Microsoft PBI schemas declare `$schema` as a required property — instance
data must be passed to the validator as-is (not stripped).

**Plan 11 complete (2026-05-31):** Filter IR enriched to Pydantic v2 discriminated union
(CategoricalFilter, RangeFilter, TopNFilter, ContextFilter, ConditionalFilter). Fixed all
three PBIR filter emission bugs: (1) type capitalisation now "Categorical"/"Range"/"Advanced";
(2) filter body emits valid FilterDefinition with Version/From/Where semantic query expressions;
(3) top-level field uses Entity (StandaloneSourceRef), Where body uses Source alias
(QuerySourceRefExpression). Bundled 5 missing schemas (semanticQuery 1.0/1.2/1.4,
filterConfiguration 1.1/1.3). Wired referencing.Registry so nested $ref chains validate. Extract
layer maps Tableau XML class values to IR kinds; captures <min>/<max> and top-spec child elements.
TopN and Conditional filters recorded as UnsupportedItems, deferred to v1.1.

## Design Spec

`docs/superpowers/specs/2026-04-23-tableau-to-pbir-design.md` — source of truth for all architecture and schema decisions.

## Key Constraints

- PBIR format only — strictly per Microsoft PBIR spec.
- No `tableauhyperapi` runtime dependency.
- No Parquet files — PBI connects via M expressions directly.
- PBI Desktop validation timeout: 300 seconds.

## Tech Stack

Python 3.11+, pydantic v2, anthropic SDK, lxml, tableaudocumentapi, PyYAML, pytest, multiprocessing (stdlib).

## Working Directory

`C:\Tableau_PBI` (Windows). Use Unix shell syntax in bash commands (forward slashes).