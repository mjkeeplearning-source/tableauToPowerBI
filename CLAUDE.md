# Tableau → PBIR Converter — Claude Workspace

## Project
Automated pipeline that converts local Tableau workbooks (`.twb`/`.twbx`) into Power BI projects in **PBIR format**. Publishing is out of scope.

## Implementation Tracking
Active implementation plan:
**`docs/superpowers/plans/2026-04-23-plan-1-scaffolding-infra.md`**

This plan covers Plan 1 of 5: Scaffolding & Infrastructure (23 tasks, TDD).
- Read the plan at the start of every implementation session.
- Execute one task at a time. Mark each task complete before moving to the next.
- Do not skip or batch tasks.
- Follow TDD order strictly: write failing test → run (confirm red) → implement → run (confirm green) → commit.

Plans 2–5 will be written after Plan 1 is fully executed and accepted.

## Design Spec
`docs/superpowers/specs/2026-04-23-tableau-to-pbir-design.md`
Refer to this for any architecture or schema decisions. The spec is the source of truth.

## Key Constraints
- Anthropic Claude (AI) is permitted **only** where Python is non-deterministic and AI provides a near-deterministic mapping (calc translation, visual mapping). All other logic must be deterministic Python.
- PBIR format only — strictly per Microsoft PBIR spec.
- No Parquet files — PBI connects directly to CSV, Excel, etc. via M expressions.
- No `tableauhyperapi` runtime dependency (extract reading uses file inspection, not the Hyper engine).
- PBI Desktop validation timeout: 300 seconds.

## Tech Stack
Python 3.11+, pydantic v2, anthropic SDK, lxml, tableaudocumentapi, PyYAML, pytest, multiprocessing (stdlib).

## Working Directory
`C:\Tableau_PBI` (Windows). Use Unix shell syntax in bash commands (forward slashes).
