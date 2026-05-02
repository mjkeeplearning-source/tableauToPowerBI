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

**Session rules:**
- Read the active plan file at the start of every session.
- Execute one task at a time. Mark complete before moving to the next.
- Do not skip or batch tasks.
- Follow TDD strictly: failing test → red → implement → green → commit.
- After each plan completes, update the table above and write the next plan.

**Plan 5 now active (Plan 7 complete):** Plan 7 fixed all four TMDL column emission bugs
(DataModel.columns field, sourceColumn emission, Tableau→TMDL datatype map, internal column
filter) and bumped compatibilityLevel to 1600. Resume Plan 5 from where it left off.

**Pre-Plan-5 bug fixes (2026-05-01):** Before Plan 5 tasks begin, five bugs were
found opening `simple_join` in PBI Desktop and fixed: (1) TMDL measure `expression:`
indentation (1 tab → 2 tabs); (2) Stage 1 now extracts `<relation>` elements and
`<cols><map>` from federated datasources; (3) `connection_params` for federated
resolves from `named_connections[0]` not the stub outer connection; (4) `build_tables`
emits one `Table` per physical relation (not per datasource) with `physical_schema` /
`physical_table` fields on the IR; (5) M expression uses schema-qualified navigation
`Source{[Schema=..., Item=...]}[Data]` for those tables. Full details in plan-5 preamble.

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