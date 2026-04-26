# Tableau → PBIR Converter — Claude Workspace

## Project

Automated pipeline that converts local Tableau workbooks (`.twb`/`.twbx`) into Power BI projects in **PBIR format**. Publishing is out of scope.

## Implementation Tracking

| Plan | Title | Status | File |
|------|-------|--------|------|
| 1 | Scaffolding & Infrastructure | ✅ DONE | `docs/superpowers/plans/2026-04-23-plan-1-scaffolding-infra.md` |
| 2 | Stage 1 & 2 — Extract + Canonicalize → IR | ✅ DONE | `docs/superpowers/plans/2026-04-24-plan-2-extract-canonicalize.md` |
| 3 | Stage 3 & 4 — Calc Translation + Visual Mapping | 🔲 NEXT | TBD |
| 4 | Stage 5, 6 & 7 — Layout, TMDL + PBIR Emission | 🔲 TODO | TBD |
| 5 | Stage 8 — Package, Validate & Desktop-Open Gate | 🔲 TODO | TBD |

**Session rules:**
- Read the active plan file at the start of every session.
- Execute one task at a time. Mark complete before moving to the next.
- Do not skip or batch tasks.
- Follow TDD strictly: failing test → red → implement → green → commit.
- After each plan completes, update the table above and write the next plan.

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