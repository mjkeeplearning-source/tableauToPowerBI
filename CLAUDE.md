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
| 5 | Stage 8 — Package, Validate & Desktop-Open Gate | 📝 PLANNED | `docs/superpowers/plans/2026-05-01-plan-5-package-validate-desktop-gate.md` |

**Session rules:**
- Read the active plan file at the start of every session.
- Execute one task at a time. Mark complete before moving to the next.
- Do not skip or batch tasks.
- Follow TDD strictly: failing test → red → implement → green → commit.
- After each plan completes, update the table above and write the next plan.

**Plan 5 is next to execute:** the plan is authored at
`docs/superpowers/plans/2026-05-01-plan-5-package-validate-desktop-gate.md` (16
TDD tasks: `.pbip` writer, structural checker, TE2/pbi-tools wrappers,
trace-event mapper, Desktop-open gate, rubric + `acceptance.json`, §8.1 status
rule, reporters, orchestrator, contract + integration tests, CLI run-manifest).
Execute inline with `superpowers:executing-plans` one task at a time.

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