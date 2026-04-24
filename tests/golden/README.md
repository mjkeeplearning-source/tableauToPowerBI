# Golden fixtures

Full-roadmap corpus per spec §9. Plan 1 ships only `synthetic/trivial.twb`;
subsequent plans add fixtures per §9's tables (~25 calc kind×frame,
~5 parameter intent, ~12 connector Tier-1/Tier-2, edge cases).

- `synthetic/` — hand-authored single-feature `.twb` workbooks.
- `real/` — 3–5 production workbooks with paired `<wb>.rubric.yaml` (§15).
- `expected/` — expected `.pbip` trees for the diff-based layer iii tests.
