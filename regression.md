# Regression Gate

The regression gate detects unintended semantic changes to the converter's PBIR/TMDL output. It works by storing a snapshot of a known-good conversion for each registered workbook, then re-running the pipeline on every future change and comparing the output semantically. A diff in any measure DAX, column type, or PBIR JSON value fails the gate.

---

## How It Works

```
regression-add my.twb
    |
    v
Run pipeline --> snapshot SemanticModel/**/*.tmdl
                           Report/definition/**/*.json
    |
    v
Append entry to corpus.yaml
    |
    v
Commit snapshots + corpus.yaml to git

... later, on every commit ...

regression-check (or pre-commit hook)
    |
    v
For each workbook in corpus.yaml:
    Re-run pipeline in temp dir
    Compare output to snapshot (semantic diff, not byte diff)
    |
    v
PASS  --> continue
FAIL  --> print diff, exit 1
SKIP  --> no API key in env, treated as PASS
```

The comparison is **semantic**, not textual. Key-order differences in JSON, array reordering by `name`/`id`, and whitespace in string values are all ignored. For TMDL files the parser extracts columns, calculated columns, and measures by name and compares DAX expressions and data types — partition blocks are skipped entirely.

---

## CLI Commands

All three commands are subcommands of the main `tableau2pbir` CLI.

### `regression-add` — Register a workbook

```
python -m tableau2pbir.cli regression-add <source> [options]
```

Runs the full pipeline against `<source>`, copies TMDL and PBIR JSON output to the snapshot store, and appends an entry to `corpus.yaml`.

| Argument | Default | Description |
|---|---|---|
| `source` | (required) | Path to `.twb` or `.twbx` to register |
| `--notes` | `""` | Free-text description stored in corpus |
| `--corpus` | `tests/regression/corpus.yaml` | Path to corpus manifest |
| `--snapshots-root` | `tests/regression/snapshots` | Root directory for snapshot storage |

**Example:**

```
python -m tableau2pbir.cli regression-add tests/golden/real/simple_join.twb --notes "baseline — two-table join"
```

**Output on success:**

```
Registered simple_join -- 3 TMDL files, 4 PBIR JSON files snapshotted
```

**Errors:**
- If the workbook name is already registered: prints an error and exits 1 (re-registration is blocked)
- If the pipeline fails: prints the pipeline stderr and exits 1, no snapshot is written

`added_by` is read from `git config user.name` automatically (falls back to `"unknown"`). `added_on` is today's date.

After running, commit the new snapshot files and the updated `corpus.yaml` to version control.

---

### `regression-check` — Run the gate

```
python -m tableau2pbir.cli regression-check [name] [options]
```

Re-runs the pipeline for every workbook in the corpus (or just `[name]` if specified) and compares output to the stored snapshot.

| Argument | Default | Description |
|---|---|---|
| `name` | (optional) | Check only this workbook name |
| `--corpus` | `tests/regression/corpus.yaml` | Path to corpus manifest |
| `--snapshots-root` | `tests/regression/snapshots` | Root directory for snapshots |

**Exit codes:**
- `0` — all workbooks PASS or SKIP
- `1` — at least one workbook FAIL

**Example output:**

```
PASS  simple_join
FAIL  superstore
  SemanticModel/definition/tables/Orders.tmdl
    measure [Profit Ratio]  DAX changed
      - SUM([Profit]) / SUM([Sales])
      + DIVIDE(SUM([Profit]), SUM([Sales]))
  Report/definition/pages/ReportSection1/visuals/visual_1/visual.json
    $.config.singleVisual.prototypeQuery.Select[0].Measure.Property  value changed
      - Profit Ratio
      + ProfitRatio
```

**SKIP behaviour:** If the pipeline exits with an error that includes any of `ANTHROPIC_API_KEY not set`, `authentication_error`, or `invalid x-api-key`, the workbook is marked SKIP and treated as passing. This lets the gate run in environments without an LLM API key (e.g. CI without secrets).

---

### `regression-install-hook` — Wire into git pre-commit

```
python -m tableau2pbir.cli regression-install-hook [--hook-path <path>]
```

Appends `regression-check` to `.git/hooks/pre-commit`, making the gate run automatically before every commit. Safe to run multiple times (idempotent).

| Argument | Default | Description |
|---|---|---|
| `--hook-path` | `.git/hooks/pre-commit` | Path to the pre-commit hook file |

If the hook file already exists, the line is appended rather than overwriting. The file is made executable (`chmod +x`).

To bypass the hook for a single commit (e.g. when updating snapshots):

```
git commit --no-verify
```

---

## Corpus Manifest (`corpus.yaml`)

Located at `tests/regression/corpus.yaml`. Tracks which workbooks are registered. Managed automatically by `regression-add` — do not edit by hand unless removing an entry.

**Schema:**

```yaml
workbooks:
  - name: simple_join          # stem of the .twb/.twbx file; used as snapshot directory name
    path: tests/golden/real/simple_join.twb   # path to source workbook (relative or absolute)
    added_by: Manish Jain      # from git config user.name at registration time
    added_on: '2026-06-01'     # ISO date
    notes: baseline -- two-table join   # optional free text
```

**Duplicate guard:** `regression-add` refuses to register a workbook whose `name` (file stem) is already in the corpus. To re-baseline a workbook:

1. Delete its entry from `corpus.yaml`
2. Delete its snapshot directory from `tests/regression/snapshots/<name>/`
3. Run `regression-add` again
4. Commit the updated corpus and new snapshots

---

## Snapshot Layout

Snapshots live under `tests/regression/snapshots/<name>/` and mirror the pipeline output tree, but only for semantic content:

```
tests/regression/snapshots/
  simple_join/
    SemanticModel/
      definition/
        model.tmdl              # culture, defaultPowerBIDataSourceVersion
        tables/
          orders.tmdl           # columns, measures, calculated columns
          returns.tmdl
    Report/
      definition/
        report.json
        pages/
          ReportSection1/
            page.json
            visuals/
              visual_1/
                visual.json
```

**What is snapshotted:**
- All `.tmdl` files under `SemanticModel/`
- All `.json` files under `Report/definition/`

**What is NOT snapshotted:**
- `stages/` directory (intermediate pipeline artefacts)
- Any other file types

---

## Semantic Diff Rules

### PBIR JSON (`.json` files)

Before comparing, both snapshot and new output are normalised:
- Dict keys are sorted alphabetically
- Arrays of dicts are sorted by `name` then `id`
- String values are trimmed of leading/trailing whitespace

This means cosmetic reformatting, property reordering, and visual re-sequencing never produce a false FAIL.

### TMDL table files (`.tmdl` files, not `model.tmdl`)

The parser extracts:
- **Columns**: name, `dataType`, `sourceColumn`, and DAX expression (for calculated columns)
- **Measures**: name and DAX expression (single-line or multiline)

Partition blocks are ignored entirely. Comparison is snapshot-anchored: columns/measures present in the snapshot but absent from new output are flagged as FAIL; extra columns/measures in new output that were not in the snapshot are silently ignored (additive changes are not regressions).

DAX expressions are whitespace-normalised before comparison (collapsed to single spaces).

### `model.tmdl`

Only `culture` and `defaultPowerBIDataSourceVersion` are compared.

---

## Running with pytest

All regression tests are marked with `@pytest.mark.regression`. To run only the regression test suite:

```
pytest -m regression tests/regression/ -v
```

Note: this suite tests the regression framework itself (corpus load/save, diff logic, check orchestration, hook installation). It does not re-run the regression gate against real workbooks — that is done via `regression-check` directly.

The full suite including unit and golden E2E tests:

```
pytest tests/unit/ tests/regression/ tests/golden/ -v --tb=short
```

---

## Package Layout

```
src/tableau2pbir/regression/
  __init__.py
  corpus.py          # CorpusEntry dataclass, load_corpus, save_corpus
  snapshot.py        # register_workbook, RegistrationError
  check.py           # run_regression_check orchestrator
  report.py          # format_report -- renders diffs to stdout
  hook.py            # install_hook, HookInstallError
  compare/
    __init__.py
    result.py        # EntityDiff, FileDiff, WorkbookResult, RegressionResult dataclasses
    json_diff.py     # diff_json -- PBIR JSON normalise + deep diff
    tmdl_diff.py     # parse_table_tmdl, parse_model_tmdl, diff_tmdl_table, diff_model_tmdl
```

---

## Typical Workflow for a New Developer

```bash
# 1. Register a workbook after verifying its output looks correct
python -m tableau2pbir.cli regression-add tests/golden/real/simple_join.twb --notes "two-table join baseline"

# 2. Commit snapshots and corpus update
git add tests/regression/
git commit -m "regression: add simple_join to corpus"

# 3. Install the pre-commit hook (once per clone)
python -m tableau2pbir.cli regression-install-hook

# 4. Work normally -- the hook checks for regressions before every commit
git commit -m "feat: my change"
# => runs regression-check automatically

# 5. If a regression is detected and the change is intentional, re-baseline:
#    a. Remove old entry and snapshots
#    b. Run regression-add again
#    c. Commit the new baseline
```
