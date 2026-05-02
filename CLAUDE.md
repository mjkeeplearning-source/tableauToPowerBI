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
| 5 | Stage 8 — Package, Validate & Desktop-Open Gate | 🔄 ACTIVE | `docs/superpowers/plans/2026-05-01-plan-5-package-validate-desktop-gate.md` |
| 6 | PBIR Schema Fixes — Desktop-Open Unblocking | ✅ DONE | `docs/superpowers/plans/2026-05-02-plan-6-pbir-schema-fixes.md` |
| 7 | TMDL Column Emission Fix | ✅ DONE | `docs/superpowers/plans/2026-05-02-plan-7-tmdl-column-emission.md` |
| 8 | Visual Emission Fix — Markers, Channels, Field Resolution, Naming | ✅ DONE | `docs/superpowers/plans/2026-05-02-plan-8-visual-emission-fix.md` |

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

**Plan 5 now active (Plans 6, 7, 8 complete):** Resume Plan 5 from where it left off.
Plan 5 covers Stage 8 — Package, Validate & Desktop-Open Gate.

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