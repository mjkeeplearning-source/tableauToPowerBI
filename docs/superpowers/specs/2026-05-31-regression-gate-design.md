# Regression Gate — Semantic Snapshot Validation

**Date:** 2026-05-31  
**Author:** Manish Jain  
**Status:** Approved

## Goal

Add a regression gate that ensures changes to the pipeline never silently break already-verified workbook conversions. When a workbook is manually verified in PBI Desktop and registered, its PBIR/TMDL output is snapshotted. Any future pipeline change that alters the semantic content of that output is caught before it can be committed.

## Scope

- Semantic match only — not byte-for-byte. Whitespace, JSON key ordering, and blank lines are ignored. Actual content (DAX expressions, column data types, visual field bindings, filter conditions, relationship definitions) must be identical.
- Final pipeline output only (Stages 6 + 7 artifacts): `.tmdl` files and PBIR `.json` files under `SemanticModel/` and `Report/definition/`.
- Corpus is append-only. Snapshots are immutable once registered. There is no update path — a changed output means a pipeline bug, not an intentional change.

## Corpus & Snapshot Storage

**Corpus manifest** — `tests/regression/corpus.yaml`:

```yaml
workbooks:
  - name: simple_join
    path: tests/golden/real/simple_join.twb
    added_by: Manish Jain
    added_on: 2026-05-31
    notes: "baseline join + calculated line chart"
```

**Snapshot tree** — `tests/regression/snapshots/<name>/`:

```
tests/regression/snapshots/simple_join/
  SemanticModel/definition/tables/orders.tmdl
  SemanticModel/definition/model.tmdl
  Report/definition/report.json
  Report/definition/pages/ReportSection1/page.json
  Report/definition/pages/ReportSection1/visuals/visual_1/visual.json
  ...
```

Only `.tmdl` and `.json` files are snapshotted. Stage JSON artifacts, `.pbip` root files, and summary `.md` files are excluded.

## Registration Flow — `regression-add`

```
tableau2pbir regression-add tests/golden/real/simple_join.twb --notes "baseline join"
```

1. Run full 8-stage pipeline into a temp directory. Abort on non-zero exit.
2. Copy all `.tmdl` and `.json` files from `SemanticModel/` and `Report/definition/` into `tests/regression/snapshots/<name>/`, preserving the relative directory tree.
3. Append an entry to `tests/regression/corpus.yaml` (name derived from workbook stem, path as given, `added_by` from `git config user.name`, `added_on` = today, notes from `--notes`).
4. Print: `Registered <name> — N TMDL files, M PBIR JSON files snapshotted`.

**Guard:** If the workbook name is already in `corpus.yaml`, abort with an error. No silent overwrites.

## Regression Check Flow — `regression-check`

```
tableau2pbir regression-check              # all corpus workbooks
tableau2pbir regression-check simple_join  # single workbook by name
```

Per workbook:
1. Run full 8-stage pipeline into a temp directory.
2. For each file in `tests/regression/snapshots/<name>/`, locate the corresponding file in the temp output.
3. Compare semantically:
   - **PBIR JSON**: load both as dicts, recursively sort all object keys, sort arrays of objects by `name` key then `id` key (if neither exists, preserve original order), deep-compare.
   - **TMDL**: parse both into a structured dict (`table → {columns[], measures[], partitions[], relationships[]}`) using a lightweight line-by-line regex parser; compare the structured dicts.
4. Collect all differences into a `RegressionResult`.

**Report format:**

```
FAIL  simple_join
  orders.tmdl
    measure [Profit Ratio]  DAX changed
      - = SUM([Profit]) / SUM([Sales])
      + = DIVIDE(SUM([Profit]), SUM([Sales]))
    column order_id  dataType changed:  int64 → string
  visual_1/visual.json
    encoding Y  field changed:  Sales → Profit

PASS  Superstore
```

Exit code 0 if all pass, exit code 1 if any fail.

## Pre-commit Hook Wiring — `regression-install-hook`

```
tableau2pbir regression-install-hook
```

Writes `.git/hooks/pre-commit`:

```sh
#!/bin/sh
python -m tableau2pbir.cli regression-check
```

Sets the file executable. If `.git/hooks/pre-commit` already exists, appends the call and warns the developer to review manually. Does not overwrite existing content silently.

Developers can bypass with `git commit --no-verify` (standard git escape hatch).

## Package Layout

```
src/tableau2pbir/regression/
  __init__.py
  corpus.py          # CorpusEntry Pydantic model; load/save corpus.yaml
  snapshot.py        # regression-add: run pipeline, copy snapshot files
  compare/
    __init__.py
    json_diff.py     # PBIR JSON semantic normalise + deep-compare
    tmdl_diff.py     # TMDL line-by-line parser → structured dict + compare
    result.py        # RegressionResult, FileDiff, EntityDiff dataclasses
  check.py           # regression-check orchestrator
  report.py          # format and print semantic diff to stdout
  hook.py            # regression-install-hook writer

tests/regression/
  corpus.yaml                # grows as workbooks are registered
  snapshots/                 # snapshotted TMDL + PBIR JSON files (git-committed)
  __init__.py
  test_corpus.py             # unit: load/save corpus.yaml
  test_json_diff.py          # unit: JSON normalisation + diff
  test_tmdl_diff.py          # unit: TMDL parser + structured diff
  test_check.py              # integration: mock pipeline run vs fixture snapshots
```

## CLI Subcommands

Three new subcommands added to `cli.py`:

| Command | Description |
|---|---|
| `regression-add <path> [--notes]` | Register a workbook; snapshot its output |
| `regression-check [<name>]` | Run semantic check against all (or one) corpus workbook |
| `regression-install-hook` | Install pre-commit hook into `.git/hooks/` |

## Testing Strategy

- **Unit tests** for `json_diff.py` and `tmdl_diff.py` — cover normalisation edge cases (key ordering, array ordering, whitespace, multiline DAX).
- **Unit tests** for `corpus.py` — load/save round-trip, duplicate guard.
- **Integration test** for `check.py` — mock pipeline run that produces known output; assert correct `RegressionResult` for both pass and fail cases.
- All new tests run under `pytest -m regression` marker; none require a real workbook conversion or API key.

## Out of Scope

- Updating snapshots — there is no update command. Re-register by manually removing the corpus entry and snapshot directory.
- Byte-for-byte file comparison.
- Comparison of stage JSON artifacts (01–08), `.pbip` root files, or `.md` summary files.
- CI integration (pre-commit hook is the CI gate; no separate CI job defined here).
- Visual regression / pixel diff.
