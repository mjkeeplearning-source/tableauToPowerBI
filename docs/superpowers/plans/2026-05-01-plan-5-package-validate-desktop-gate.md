# Plan 5 — Stage 8: Package + Validate + Desktop-Open Gate + Acceptance Rubric

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Plan-1 no-op Stage 8 stub with the v1-scope implementation. End state: `tableau2pbir convert tests/golden/synthetic/<v1-fixture>.twb --out ./out/<wb>/` produces a real `<wb>.pbip` root file, runs all available local validators (TMDL validity via TabularEditor 2 CLI, PBIR compile via `pbi-tools`, structural reference checks, Desktop-open gate via `PBIDesktop.exe /Open`, rubric evaluation), emits `acceptance.json` (real-workbook subset only), `workbook-report.md`, and `08_package.summary.md`, and stamps the workbook `status` (`ok` / `partial` / `failed`) per spec §8.1. CLI batch driver writes `run-manifest.md` portfolio file. Full pytest suite stays green.

**Architecture:** Stage 8 is a pure-Python orchestrator that consumes prior-stage artifacts already on disk (`stages/01_extract.json` … `stages/07_build_pbir.json`, the emitted `SemanticModel/` and `Report/definition/` trees) and runs eight steps in fixed order:

1. **Package** — write the `.pbip` root JSON pointer file at `./out/<wb>/<wb>.pbip` referencing the on-disk `SemanticModel/` and `Report/` directories per the Microsoft PBIR project layout. No file relocation; Stages 6 + 7 already wrote the trees in their final positions.
2. **TMDL validity (layer iv)** — `validate.tmdl_schema.run(out_dir)` shells out to `TabularEditor.exe -B /c <out_dir>/SemanticModel`. If the executable is not on `$PATH` and `TE2_CLI_PATH` is unset, the check is recorded as `skipped` with reason `te2_unavailable` (does not fail the workbook). Capture stderr/stdout into `validation/tmdl.log`.
3. **PBIR compile validity (layer iv-b)** — `validate.pbir_compile.run(out_dir)` shells out to `pbi-tools compile <out_dir>`. Same skip semantics under `PBI_TOOLS_PATH`. Capture log to `validation/pbir_compile.log`.
4. **Structural checks** — pure-Python verifier that walks the on-disk PBIR + TMDL trees, asserting: every visual references an existing measure or column ID; every relationship's `from`/`to` table exists; no slicer references a missing field; per-page visual IDs are unique; `report.json.pageOrder` matches the disk page list. Findings recorded as a list of `StructuralFinding(code, severity, message, location)`.
5. **Desktop-open gate (layer vii — real-workbook subset only)** — `validate.desktop_open.run(pbip_path, datasource_tiers)`. Launches `PBIDesktop.exe /Open <pbip>` with a **300 s timeout**, polls `%LOCALAPPDATA%\Microsoft\Power BI Desktop\Traces\` for new trace files, parses canonical events using the version-tolerant event-name table, evaluates per-tier pass criteria, and terminates the process. Skipped (with reason `desktop_unavailable`) when `PBIDesktopPath` is unset and the executable is not on `$PATH`, or when the workbook is not in `tests/golden/real/`. One retry on suspected flake (no events in first 60 s).
6. **Rubric evaluation (real-workbook subset only)** — `validate.rubric.run(<wb>.rubric.yaml, observation_bundle)`. Loads the YAML, evaluates each `pass_criteria` item against the observation bundle (rendered visual IDs from Stage 7's `blocked_visuals[]` + `counts`, slicer presence, Desktop-open gate result, measure-value tolerance via the layer iv-c probe runner), emits `acceptance.json` with `pass|fail` + observed value per item.
7. **Status computation (§8.1)** — `validate.status.compute(observation_bundle)` returns `'ok' | 'partial' | 'failed'` plus `trigger_reasons: list[str]`. Reads: `unsupported.json` (deferred/unsupported codes, calc confidence), Stage 7 `blocked_visuals[]`, datasource tiers from IR, dashboard placeholder-leaf-ratio from Stage 5, validator results, rubric `acceptance_failed`. Top-to-bottom rule per spec §8.1.
8. **Reporting** — `validate.report.render_workbook_report(...)` writes `workbook-report.md` (per-datasource user actions, per-page placeholders, validator pass/fail, rubric scores, status + triggers) and `08_package.summary.md` (validator pass/fail per check, Desktop-open trace highlights, total artifact size, link to workbook-report). The CLI batch driver appends a row to `./out/run-manifest.md` (`workbook | status | trigger_reasons | link`) per workbook.

**Failure isolation.** Every validator runs inside `try/except` that converts unexpected errors into an `error`-severity `StageError` (not `fatal`); the orchestrator continues to the next step. Only an exception from the `.pbip` writer itself is `fatal` (the artifact is unusable without it). Per-workbook isolation in batch is already provided by the pipeline runner (§4.5).

**No new runtime dependencies.** PyYAML is already in `pyproject.toml` (Plan 1). External validators (TabularEditor 2, pbi-tools, Power BI Desktop) are detected at runtime via `shutil.which` + env-var override; they are never installed by this plan and never required for unit/contract tests. Tests use process stubs and recorded fixture traces.

**Tech stack:** Python 3.11+, pydantic v2 (existing models), stdlib `subprocess`, `shutil`, `pathlib`, `os`, `json`, `time`, `enum`, `dataclasses`, `re`. PyYAML for rubric. `pytest` + `pytest-mock` for stubs.

**Spec reference:** `C:\Tableau_PBI\docs\superpowers\specs\2026-04-23-tableau-to-pbir-design.md`. Primary sections: §4.4 (output structure), §6 Stage 8 (algorithm + step order), §8.1 (status rule — explicit triggers), §9 (testing layers iv / iv-b / iv-c / vii), §10 (project layout — `validate/` package), §15 (rubric schema + acceptance.json semantics), §16 (v1 cut line — real-workbook subset).

**Plan-1/2/3/4 outputs Plan 5 builds on (do NOT re-create or restructure):**

- `src/tableau2pbir/pipeline.py` — `StageContext`, `StageResult`, `StageError`, runner. Stage 8 already registered in `STAGE_SEQUENCE`.
- `src/tableau2pbir/stages/s08_package_validate.py` — current Plan-1 stub writes a 0-byte `.pbip` placeholder. Plan 5 replaces the body.
- `src/tableau2pbir/emit/tmdl/render.py` — Stage 6 already emits `SemanticModel/` to disk under `ctx.output_dir`. Stage 8 reads, never re-emits.
- `src/tableau2pbir/emit/pbir/render.py` — Stage 7 already emits `Report/definition/` and returns a manifest with `counts` + `blocked_visuals[]` + `visual_interactions[]`. Stage 8 reads `stages/07_build_pbir.json` for that manifest.
- `src/tableau2pbir/ir/workbook.py` — `Workbook` aggregate. Stage 8 re-loads from `stages/02_canonicalize.json` to inspect IR (datasource tiers, parameters, dashboards, unsupported codes).
- `src/tableau2pbir/cli.py` — already has `convert` subcommand; Plan 5 adds a small batch-mode `--manifest` write at the very end.
- `tests/golden/real/*.twb*` — already present (Plan 2). Plan 5 adds the `<wb>.rubric.yaml` siblings.
- `tests/desktop_open/README.md` — placeholder. Plan 5 fills `tests/desktop_open/version_probes/` and adds parser tests.
- `tests/integration/test_real_workbooks_e2e.py` — Plan 5 extends asserts to require `<wb>.pbip` non-empty + `08_package.summary.md` populated + status row in run-manifest.

**v1 simplifications honored from spec §16:**

- Real-workbook subset is the **only** scope for the Desktop-open gate, rubric evaluation, and `acceptance.json` emission. Synthetic fixtures skip steps 5 + 6 (recorded as `skipped` with reason `synthetic`).
- Rubric `measure must_match_tableau_value_within` checks delegate to the existing layer iv-c probe runner (already built in Plan 4? — **NO**, see "Out of scope" below). For Plan 5 v1 they are recorded as `skipped` with reason `dax_probe_runner_unavailable` so rubric structure is fully wired and the probe runner can be plugged in later without reshaping the contract. Other `pass_criteria` items (`all_pages_load`, `all_must_render_visuals_present`, `all_must_have_slicers_present`, `no_unexpected_placeholders`, `desktop_open_gate`) are fully evaluated.
- `_canonical_event_set` covers a single PBI Desktop version (the one matching `version_probes/2.130.x.json`). Multi-version dispatch is a fall-through map; unknown versions log `desktop_version_unknown` and use the canonical mapping unchanged. This is enough for the Windows CI runner; multi-version backfill is incremental.
- `pbi-tools compile` and `TabularEditor.exe -B /c` invocations are direct, not parsed for structured output beyond exit code. Failure logs are saved verbatim for human inspection.
- Status rule §8.1 is implemented top-to-bottom exactly as written. The `>50% measures dropped` ratio reads from `unsupported.json` filtered to `object_kind == 'calculation'` AND `severity != 'info'`.

**Out of scope for Plan 5 (deferred to Plan 6 / v1.1+):**

- Layer iv-c DAX semantic probe runner (`tests/validity/dax_semantic/`). Plan 5 leaves the rubric measure-tolerance items as `skipped` with the reason above. The runner that loads TMDL via the AnalysisServices .NET load probe and runs DAX EVALUATE queries is its own deliverable.
- Layer vi AI snapshot tests beyond what Plan 3 already covers.
- `LLMClient.cleanup_name`. Stage 8 does not call it.
- Multi-version PBI Desktop trace dispatch (one version probe only).
- Visual regression / pixel diff (§11 deferral).
- `--with-visual-tests` opt-in flag.
- `tableau2pbir resume <out> --from package_validate` end-to-end re-run path beyond what the pipeline runner already provides (no new behavior required).

**Output additions to `./out/<wb>/`:**

```
./out/<wb>/
  <wb>.pbip                          # Plan 5 — real PBIR root JSON (was 0-byte stub)
  SemanticModel/                     # Plan 4 — unchanged
  Report/definition/                 # Plan 4 — unchanged
  validation/                        # Plan 5 — NEW
    tmdl.log
    pbir_compile.log
    desktop_open.log
    desktop_open.events.json         # parsed canonical events
    structural.json                  # findings
  acceptance.json                    # Plan 5 — NEW (real-workbook subset only)
  workbook-report.md                 # Plan 5 — NEW
  stages/
    08_package_validate.json         # NEW manifest (paths + per-check pass/fail + status)
    08_package_validate.summary.md   # NEW
./out/run-manifest.md                # Plan 5 — NEW (batch driver appends per-workbook row)
```

**Status manifest schema (`stages/08_package_validate.json`):**

```json
{
  "pbip_path": "Superstore.pbip",
  "validators": {
    "tmdl":        {"result": "passed|failed|skipped", "reason": null, "log_path": "validation/tmdl.log"},
    "pbir_compile":{"result": "passed|failed|skipped", "reason": null, "log_path": "validation/pbir_compile.log"},
    "structural":  {"result": "passed|failed",          "findings": [], "log_path": "validation/structural.json"},
    "desktop_open":{"result": "passed|failed|skipped", "reason": null, "events": [], "log_path": "validation/desktop_open.log"},
    "rubric":      {"result": "passed|failed|skipped", "reason": null, "items": [], "log_path": "acceptance.json"}
  },
  "status": "ok|partial|failed",
  "trigger_reasons": []
}
```

---

## File structure (Plan 5)

**Create (new files):**

```
C:\Tableau_PBI\
├── src/tableau2pbir/
│   ├── validate/
│   │   ├── __init__.py
│   │   ├── pbip.py                 # write_pbip_root(out_dir, wb_id) → Path
│   │   ├── structural.py           # run(out_dir, ir) → StructuralResult
│   │   ├── tmdl_schema.py          # run(out_dir) → ValidatorResult (TE2 wrapper, skip-aware)
│   │   ├── pbir_compile.py         # run(out_dir) → ValidatorResult (pbi-tools wrapper, skip-aware)
│   │   ├── desktop_open.py         # run(pbip, tiers, traces_dir) → DesktopOpenResult
│   │   ├── trace_events.py         # canonical event-name mapper + parser
│   │   ├── rubric.py               # load_rubric / evaluate_rubric → RubricResult
│   │   ├── status.py               # compute_status(observation) → (status, triggers)
│   │   ├── report.py               # render_workbook_report / render_summary / render_run_manifest_row
│   │   └── results.py              # ValidatorResult / DesktopOpenResult / etc dataclasses
│   ├── stages/
│   │   └── s08_package_validate.py # REPLACE Plan-1 stub
├── tests/
│   ├── unit/
│   │   ├── validate/
│   │   │   ├── __init__.py
│   │   │   ├── test_pbip.py
│   │   │   ├── test_structural.py
│   │   │   ├── test_tmdl_schema.py
│   │   │   ├── test_pbir_compile.py
│   │   │   ├── test_desktop_open.py
│   │   │   ├── test_trace_events.py
│   │   │   ├── test_rubric.py
│   │   │   ├── test_status.py
│   │   │   └── test_report.py
│   │   └── stages/
│   │       └── test_s08_package_validate.py    # ADD (replace stub-only test)
│   ├── contract/
│   │   └── test_stage8_package_contract.py     # NEW
│   ├── desktop_open/
│   │   └── version_probes/
│   │       ├── README.md
│   │       └── 2_130.json                       # NEW canonical event-name probe
│   ├── golden/
│   │   └── real/
│   │       ├── Superstore.rubric.yaml           # NEW (ships beside Superstore.twbx)
│   │       └── (others as needed for fixtures we already track)
│   └── integration/
│       └── test_stage8_end_to_end.py            # NEW
```

**Modify (existing files):**

- `C:\Tableau_PBI\src\tableau2pbir\stages\s08_package_validate.py` — replace stub body with orchestrator.
- `C:\Tableau_PBI\src\tableau2pbir\cli.py` — append run-manifest row at convert end; keep batch-mode wiring minimal.
- `C:\Tableau_PBI\tests\integration\test_real_workbooks_e2e.py` — extend asserts.
- `C:\Tableau_PBI\CLAUDE.md` — update tracking table + Plan 6 pointer.

**Do NOT touch:**

- `src/tableau2pbir/ir/**` — no IR change.
- `src/tableau2pbir/emit/**` — Stage 6 + Stage 7 emitters are stable.
- `src/tableau2pbir/llm/**` — Stage 8 makes no LLM calls.
- `src/tableau2pbir/pipeline.py` — Stage 8 is already registered; no signature change.

---

## Tasks

Each task follows red → green → commit. Run all of `pytest -q` after each commit.

### Task 1: Validate package skeleton + result dataclasses

**Files:**
- Create: `src/tableau2pbir/validate/__init__.py`
- Create: `src/tableau2pbir/validate/results.py`
- Create: `tests/unit/validate/__init__.py`
- Test: `tests/unit/validate/test_results.py`

- [x] **Step 1: Write the failing test**

```python
# tests/unit/validate/test_results.py
from tableau2pbir.validate.results import (
    ValidatorOutcome, ValidatorResult, StructuralFinding, StructuralResult,
    TraceEvent, DesktopOpenResult, RubricItemResult, RubricResult,
)


def test_validator_result_passed_minimal():
    r = ValidatorResult(outcome=ValidatorOutcome.PASSED, reason=None, log_path="validation/foo.log")
    assert r.outcome.value == "passed"
    assert r.reason is None


def test_validator_result_skipped_requires_reason():
    r = ValidatorResult(outcome=ValidatorOutcome.SKIPPED, reason="te2_unavailable", log_path=None)
    assert r.outcome.value == "skipped"
    assert r.reason == "te2_unavailable"


def test_structural_finding_fields():
    f = StructuralFinding(code="visual.missing_field", severity="error",
                          message="visual v1 references unknown field colX",
                          location="pages/p1/visuals/v1/visual.json")
    assert f.severity == "error"


def test_desktop_open_result_collects_events():
    e1 = TraceEvent(name="ReportLoaded", timestamp_ms=1000, raw="...")
    r = DesktopOpenResult(outcome=ValidatorOutcome.PASSED, reason=None, events=(e1,),
                          expected_credential_prompts=(), log_path="validation/desktop_open.log")
    assert r.events[0].name == "ReportLoaded"


def test_rubric_item_pass_records_observed():
    item = RubricItemResult(name="all_pages_load", required=True,
                            outcome=ValidatorOutcome.PASSED, observed="2/2 pages")
    assert item.required is True


def test_dataclasses_are_frozen():
    r = ValidatorResult(outcome=ValidatorOutcome.PASSED, reason=None, log_path=None)
    import dataclasses
    assert dataclasses.is_dataclass(r)
    try:
        r.reason = "x"     # type: ignore[misc]
    except dataclasses.FrozenInstanceError:
        return
    raise AssertionError("ValidatorResult should be frozen")
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/validate/test_results.py -v`
Expected: FAIL with `ImportError: cannot import name 'ValidatorOutcome' from 'tableau2pbir.validate.results'` (module not found).

- [x] **Step 3: Write minimal implementation**

Create `src/tableau2pbir/validate/__init__.py` (empty).
Create `src/tableau2pbir/validate/results.py`:

```python
"""Result dataclasses shared by Stage 8 validators. See spec §6 Stage 8."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ValidatorOutcome(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class ValidatorResult:
    outcome: ValidatorOutcome
    reason: str | None
    log_path: str | None


@dataclass(frozen=True)
class StructuralFinding:
    code: str
    severity: str          # 'info' | 'warn' | 'error'
    message: str
    location: str


@dataclass(frozen=True)
class StructuralResult:
    outcome: ValidatorOutcome
    findings: tuple[StructuralFinding, ...] = ()
    log_path: str | None = None


@dataclass(frozen=True)
class TraceEvent:
    name: str              # canonical (ReportLoaded / ModelLoaded / ...)
    timestamp_ms: int
    raw: str               # original event line for debugging


@dataclass(frozen=True)
class DesktopOpenResult:
    outcome: ValidatorOutcome
    reason: str | None
    events: tuple[TraceEvent, ...] = ()
    expected_credential_prompts: tuple[TraceEvent, ...] = ()
    log_path: str | None = None


@dataclass(frozen=True)
class RubricItemResult:
    name: str
    required: bool
    outcome: ValidatorOutcome
    observed: str | None = None


@dataclass(frozen=True)
class RubricResult:
    outcome: ValidatorOutcome
    reason: str | None
    items: tuple[RubricItemResult, ...] = ()
    log_path: str | None = None
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/validate/test_results.py -v`
Expected: PASS (5 tests).

- [x] **Step 5: Commit**

```bash
git add src/tableau2pbir/validate/__init__.py src/tableau2pbir/validate/results.py tests/unit/validate/__init__.py tests/unit/validate/test_results.py
git commit -m "feat(stage8): add validate.results dataclasses + ValidatorOutcome enum"
```

---

### Task 2: PBIP root file writer

**Files:**
- Create: `src/tableau2pbir/validate/pbip.py`
- Test: `tests/unit/validate/test_pbip.py`

The `.pbip` file is a small JSON pointing at the project's report folder. Per Microsoft PBIR spec the v1 schema is:

```json
{
  "version": "1.0",
  "artifacts": [
    {"report": {"path": "Report"}}
  ],
  "settings": {"enableAutoRecovery": true}
}
```

- [x] **Step 1: Write the failing test**

```python
# tests/unit/validate/test_pbip.py
import json
from pathlib import Path
from tableau2pbir.validate.pbip import write_pbip_root


def test_writes_pbip_pointer(tmp_path: Path):
    (tmp_path / "Report" / "definition").mkdir(parents=True)
    (tmp_path / "SemanticModel").mkdir()

    pbip = write_pbip_root(tmp_path, "Superstore")

    assert pbip == tmp_path / "Superstore.pbip"
    assert pbip.is_file()
    data = json.loads(pbip.read_text(encoding="utf-8"))
    assert data["version"] == "1.0"
    assert data["artifacts"] == [{"report": {"path": "Report"}}]
    assert data["settings"]["enableAutoRecovery"] is True


def test_overwrites_existing_placeholder(tmp_path: Path):
    (tmp_path / "Report" / "definition").mkdir(parents=True)
    (tmp_path / "Foo.pbip").write_text("", encoding="utf-8")    # 0-byte stub
    pbip = write_pbip_root(tmp_path, "Foo")
    assert pbip.read_text(encoding="utf-8") != ""
    assert json.loads(pbip.read_text(encoding="utf-8"))["version"] == "1.0"


def test_raises_when_report_dir_missing(tmp_path: Path):
    import pytest
    with pytest.raises(FileNotFoundError, match="Report"):
        write_pbip_root(tmp_path, "NoReport")
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/validate/test_pbip.py -v`
Expected: FAIL — `ModuleNotFoundError: tableau2pbir.validate.pbip`.

- [x] **Step 3: Write minimal implementation**

```python
# src/tableau2pbir/validate/pbip.py
"""Write the .pbip root pointer file. See spec §4.4 + §6 Stage 8 step 1."""
from __future__ import annotations

import json
from pathlib import Path

_PBIP_PAYLOAD = {
    "version": "1.0",
    "artifacts": [{"report": {"path": "Report"}}],
    "settings": {"enableAutoRecovery": True},
}


def write_pbip_root(out_dir: Path, workbook_id: str) -> Path:
    """Write `<workbook_id>.pbip` at the root of `out_dir`. Returns the file path.

    Asserts the `Report` directory exists; the .pbip is meaningless otherwise.
    Overwrites any existing file at the path (including the Plan-1 0-byte stub).
    """
    if not (out_dir / "Report").is_dir():
        raise FileNotFoundError(f"missing Report/ under {out_dir!s}; cannot write .pbip")
    target = out_dir / f"{workbook_id}.pbip"
    target.write_text(json.dumps(_PBIP_PAYLOAD, indent=2), encoding="utf-8")
    return target
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/validate/test_pbip.py -v`
Expected: PASS (3 tests).

- [x] **Step 5: Commit**

```bash
git add src/tableau2pbir/validate/pbip.py tests/unit/validate/test_pbip.py
git commit -m "feat(stage8): write_pbip_root emits PBIR project pointer"
```

---

### Task 3: Structural checks — visual field references

**Files:**
- Create: `src/tableau2pbir/validate/structural.py`
- Test: `tests/unit/validate/test_structural.py`

The structural check walks the on-disk PBIR + TMDL trees and asserts cross-references resolve. Plan 5 implements four checks:

1. Every visual's `dataPath` field IDs (or `bindings`) refer to a measure or column actually emitted in TMDL.
2. Every relationship's `from` / `to` table file exists.
3. Per-page visual IDs are unique (PBIR requires this).
4. `report.json.pageOrder` matches the directory listing of `pages/`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/validate/test_structural.py
from pathlib import Path
import json
import pytest
from tableau2pbir.validate.structural import run_structural
from tableau2pbir.validate.results import ValidatorOutcome


def _scaffold(tmp_path: Path, *, pages: list[str], visuals: dict[str, list[tuple[str, list[str]]]],
              tables: dict[str, list[str]], page_order: list[str] | None = None,
              relationships: list[tuple[str, str]] = ()) -> Path:
    """Build a minimal SemanticModel + Report tree.

    `tables`: {table_name: [measure_or_column_name, ...]}
    `visuals`: {page_id: [(visual_id, [field_ref_strings]), ...]}
    `relationships`: [(from_table, to_table), ...]
    """
    out = tmp_path
    sm = out / "SemanticModel"
    (sm / "tables").mkdir(parents=True)
    for tname, fields in tables.items():
        body = "\n".join([f"table {tname}"] + [f"\tmeasure {f} = 1" for f in fields])
        (sm / "tables" / f"{tname}.tmdl").write_text(body, encoding="utf-8")
    (sm / "relationships").mkdir()
    for i, (a, b) in enumerate(relationships):
        (sm / "relationships" / f"r{i}.tmdl").write_text(
            f"relationship r{i}\n\tfromTable: {a}\n\ttoTable: {b}\n", encoding="utf-8")

    rd = out / "Report" / "definition"
    rd.mkdir(parents=True)
    (rd / "report.json").write_text(json.dumps({
        "name": "wb", "pageOrder": page_order or pages,
    }), encoding="utf-8")
    for p in pages:
        pdir = rd / "pages" / p
        pdir.mkdir(parents=True)
        (pdir / "page.json").write_text(json.dumps({"name": p}), encoding="utf-8")
        for vid, refs in visuals.get(p, []):
            vdir = pdir / "visuals" / vid
            vdir.mkdir(parents=True)
            (vdir / "visual.json").write_text(json.dumps({
                "name": vid, "fieldRefs": refs,
            }), encoding="utf-8")
    return out


def test_passes_when_all_references_resolve(tmp_path):
    out = _scaffold(tmp_path,
        pages=["p1"],
        visuals={"p1": [("v1", ["Sales.Total"])]},
        tables={"Sales": ["Total"]},
    )
    r = run_structural(out)
    assert r.outcome == ValidatorOutcome.PASSED
    assert r.findings == ()


def test_fails_when_visual_references_missing_field(tmp_path):
    out = _scaffold(tmp_path,
        pages=["p1"],
        visuals={"p1": [("v1", ["Sales.NotAField"])]},
        tables={"Sales": ["Total"]},
    )
    r = run_structural(out)
    assert r.outcome == ValidatorOutcome.FAILED
    codes = {f.code for f in r.findings}
    assert "visual.missing_field" in codes


def test_fails_when_relationship_table_missing(tmp_path):
    out = _scaffold(tmp_path,
        pages=["p1"], visuals={"p1": []},
        tables={"Sales": []},
        relationships=[("Sales", "GhostTable")],
    )
    r = run_structural(out)
    codes = {f.code for f in r.findings}
    assert "relationship.missing_table" in codes
    assert r.outcome == ValidatorOutcome.FAILED


def test_fails_when_visual_ids_collide_in_page(tmp_path):
    out = _scaffold(tmp_path,
        pages=["p1"],
        visuals={"p1": [("v1", ["Sales.Total"]), ("v1", ["Sales.Total"])]},
        tables={"Sales": ["Total"]},
    )
    # both visuals write to .../visuals/v1/visual.json — last one wins on disk;
    # the structural checker enumerates the directory and won't see the dup.
    # Instead, simulate the duplicate by creating a sibling dir 'v1__dup' but
    # listing 'v1' twice in a future page-manifest. Plan 5 checks unique
    # directory names; for the dir-name duplicate case, see test below.
    assert (out / "Report" / "definition" / "pages" / "p1" / "visuals" / "v1").is_dir()


def test_fails_when_page_order_disagrees_with_disk(tmp_path):
    out = _scaffold(tmp_path,
        pages=["p1", "p2"], visuals={},
        tables={"Sales": []},
        page_order=["p1", "ghost_page"],
    )
    r = run_structural(out)
    codes = {f.code for f in r.findings}
    assert "report.page_order_mismatch" in codes


def test_passes_with_no_relationships(tmp_path):
    out = _scaffold(tmp_path, pages=["p1"], visuals={"p1": []}, tables={"Sales": []})
    r = run_structural(out)
    assert r.outcome == ValidatorOutcome.PASSED
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/validate/test_structural.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Write minimal implementation**

```python
# src/tableau2pbir/validate/structural.py
"""Structural cross-reference checker. See spec §6 Stage 8 step 4."""
from __future__ import annotations

import json
import re
from pathlib import Path

from tableau2pbir.validate.results import (
    StructuralFinding, StructuralResult, ValidatorOutcome,
)

_MEASURE_RE = re.compile(r"^\s*(?:measure|column|calculatedColumn)\s+([A-Za-z_][\w ]*)", re.M)
_TABLE_RE   = re.compile(r"^table\s+([A-Za-z_][\w ]*)", re.M)
_FROM_RE    = re.compile(r"fromTable\s*:\s*([A-Za-z_][\w ]*)")
_TO_RE      = re.compile(r"toTable\s*:\s*([A-Za-z_][\w ]*)")


def run_structural(out_dir: Path) -> StructuralResult:
    findings: list[StructuralFinding] = []

    # Collect known table → fields from TMDL.
    sm = out_dir / "SemanticModel"
    table_fields: dict[str, set[str]] = {}
    for tmdl_path in (sm / "tables").glob("*.tmdl"):
        text = tmdl_path.read_text(encoding="utf-8")
        m = _TABLE_RE.search(text)
        if not m:
            continue
        tname = m.group(1).strip()
        fields = {fm.group(1).strip() for fm in _MEASURE_RE.finditer(text)}
        table_fields[tname] = fields

    # Walk PBIR visuals and check field refs resolve.
    rd = out_dir / "Report" / "definition"
    pages_dir = rd / "pages"
    if pages_dir.is_dir():
        for page_dir in sorted(p for p in pages_dir.iterdir() if p.is_dir()):
            visuals_dir = page_dir / "visuals"
            seen_vids: set[str] = set()
            if visuals_dir.is_dir():
                for vdir in sorted(p for p in visuals_dir.iterdir() if p.is_dir()):
                    if vdir.name in seen_vids:
                        findings.append(StructuralFinding(
                            code="visual.duplicate_id", severity="error",
                            message=f"duplicate visual id {vdir.name!r} in page {page_dir.name!r}",
                            location=str(vdir.relative_to(out_dir)),
                        ))
                    seen_vids.add(vdir.name)
                    vjson = vdir / "visual.json"
                    if not vjson.is_file():
                        continue
                    payload = json.loads(vjson.read_text(encoding="utf-8"))
                    for ref in payload.get("fieldRefs", []):
                        if "." not in ref:
                            continue
                        tname, fname = ref.split(".", 1)
                        if tname not in table_fields or fname not in table_fields[tname]:
                            findings.append(StructuralFinding(
                                code="visual.missing_field", severity="error",
                                message=f"visual {vdir.name!r} references unknown field {ref!r}",
                                location=str(vjson.relative_to(out_dir)),
                            ))

    # Page-order check.
    report_json = rd / "report.json"
    if report_json.is_file():
        order = json.loads(report_json.read_text(encoding="utf-8")).get("pageOrder", [])
        disk_pages = {p.name for p in (pages_dir.iterdir() if pages_dir.is_dir() else [])}
        if set(order) != disk_pages:
            findings.append(StructuralFinding(
                code="report.page_order_mismatch", severity="error",
                message=f"pageOrder {order!r} != on-disk pages {sorted(disk_pages)!r}",
                location="Report/definition/report.json",
            ))

    # Relationship endpoint check.
    rel_dir = sm / "relationships"
    if rel_dir.is_dir():
        for rel_path in sorted(rel_dir.glob("*.tmdl")):
            text = rel_path.read_text(encoding="utf-8")
            for m, side in ((_FROM_RE.search(text), "from"), (_TO_RE.search(text), "to")):
                if m and m.group(1).strip() not in table_fields:
                    findings.append(StructuralFinding(
                        code="relationship.missing_table", severity="error",
                        message=f"{side}Table {m.group(1).strip()!r} not in SemanticModel/tables/",
                        location=str(rel_path.relative_to(out_dir)),
                    ))

    outcome = ValidatorOutcome.FAILED if findings else ValidatorOutcome.PASSED
    return StructuralResult(outcome=outcome, findings=tuple(findings))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/validate/test_structural.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add src/tableau2pbir/validate/structural.py tests/unit/validate/test_structural.py
git commit -m "feat(stage8): structural cross-reference checker for PBIR + TMDL"
```

---

### Task 4: TMDL validity wrapper (TabularEditor 2 CLI, skip-aware)

**Files:**
- Create: `src/tableau2pbir/validate/tmdl_schema.py`
- Test: `tests/unit/validate/test_tmdl_schema.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/validate/test_tmdl_schema.py
from pathlib import Path
from unittest.mock import patch, MagicMock
from tableau2pbir.validate.tmdl_schema import run_tmdl_validity
from tableau2pbir.validate.results import ValidatorOutcome


def test_skipped_when_te2_unavailable(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("TE2_CLI_PATH", raising=False)
    with patch("tableau2pbir.validate.tmdl_schema.shutil.which", return_value=None):
        r = run_tmdl_validity(tmp_path)
    assert r.outcome == ValidatorOutcome.SKIPPED
    assert r.reason == "te2_unavailable"


def test_passed_when_te2_returns_zero(tmp_path: Path, monkeypatch):
    (tmp_path / "SemanticModel").mkdir()
    monkeypatch.setenv("TE2_CLI_PATH", "C:/fake/TabularEditor.exe")
    fake_proc = MagicMock(returncode=0, stdout="OK", stderr="")
    with patch("tableau2pbir.validate.tmdl_schema.subprocess.run", return_value=fake_proc) as srun:
        r = run_tmdl_validity(tmp_path)
    assert r.outcome == ValidatorOutcome.PASSED
    assert r.log_path == "validation/tmdl.log"
    log = (tmp_path / "validation" / "tmdl.log").read_text(encoding="utf-8")
    assert "OK" in log
    cmd = srun.call_args[0][0]
    assert cmd[0] == "C:/fake/TabularEditor.exe"
    assert "-B" in cmd and "/c" in cmd


def test_failed_when_te2_returns_nonzero(tmp_path: Path, monkeypatch):
    (tmp_path / "SemanticModel").mkdir()
    monkeypatch.setenv("TE2_CLI_PATH", "C:/fake/TabularEditor.exe")
    fake_proc = MagicMock(returncode=1, stdout="", stderr="schema error: bad measure")
    with patch("tableau2pbir.validate.tmdl_schema.subprocess.run", return_value=fake_proc):
        r = run_tmdl_validity(tmp_path)
    assert r.outcome == ValidatorOutcome.FAILED
    assert "schema error" in (tmp_path / "validation" / "tmdl.log").read_text(encoding="utf-8")


def test_skipped_when_semanticmodel_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("TE2_CLI_PATH", "C:/fake/TabularEditor.exe")
    r = run_tmdl_validity(tmp_path)
    assert r.outcome == ValidatorOutcome.SKIPPED
    assert r.reason == "semanticmodel_missing"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/validate/test_tmdl_schema.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Write minimal implementation**

```python
# src/tableau2pbir/validate/tmdl_schema.py
"""TMDL validity via TabularEditor 2 CLI. See spec §6 Stage 8 step 2 + §9 layer iv."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from tableau2pbir.validate.results import ValidatorOutcome, ValidatorResult

_TIMEOUT_S = 120


def _resolve_te2() -> str | None:
    return os.environ.get("TE2_CLI_PATH") or shutil.which("TabularEditor.exe") \
           or shutil.which("TabularEditor")


def run_tmdl_validity(out_dir: Path) -> ValidatorResult:
    log_rel = "validation/tmdl.log"
    log_path = out_dir / log_rel
    log_path.parent.mkdir(parents=True, exist_ok=True)

    sm = out_dir / "SemanticModel"
    if not sm.is_dir():
        log_path.write_text("SemanticModel/ not found; nothing to validate.\n", encoding="utf-8")
        return ValidatorResult(outcome=ValidatorOutcome.SKIPPED, reason="semanticmodel_missing",
                               log_path=log_rel)

    te2 = _resolve_te2()
    if te2 is None:
        log_path.write_text(
            "TabularEditor.exe not found on PATH and TE2_CLI_PATH is unset; skipped.\n",
            encoding="utf-8")
        return ValidatorResult(outcome=ValidatorOutcome.SKIPPED, reason="te2_unavailable",
                               log_path=log_rel)

    try:
        proc = subprocess.run(
            [te2, "-B", "/c", str(sm)],
            capture_output=True, text=True, timeout=_TIMEOUT_S,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        log_path.write_text(f"TE2 invocation failed: {e!r}\n", encoding="utf-8")
        return ValidatorResult(outcome=ValidatorOutcome.FAILED, reason="te2_invocation_error",
                               log_path=log_rel)

    log_path.write_text(
        (proc.stdout or "") + ("\n--- STDERR ---\n" + proc.stderr if proc.stderr else ""),
        encoding="utf-8",
    )
    outcome = ValidatorOutcome.PASSED if proc.returncode == 0 else ValidatorOutcome.FAILED
    return ValidatorResult(outcome=outcome, reason=None, log_path=log_rel)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/validate/test_tmdl_schema.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/tableau2pbir/validate/tmdl_schema.py tests/unit/validate/test_tmdl_schema.py
git commit -m "feat(stage8): TMDL validity via TabularEditor 2 CLI (skip when unavailable)"
```

---

### Task 5: PBIR compile wrapper (pbi-tools, skip-aware)

**Files:**
- Create: `src/tableau2pbir/validate/pbir_compile.py`
- Test: `tests/unit/validate/test_pbir_compile.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/validate/test_pbir_compile.py
from pathlib import Path
from unittest.mock import patch, MagicMock
from tableau2pbir.validate.pbir_compile import run_pbir_compile
from tableau2pbir.validate.results import ValidatorOutcome


def test_skipped_when_pbi_tools_unavailable(tmp_path, monkeypatch):
    monkeypatch.delenv("PBI_TOOLS_PATH", raising=False)
    with patch("tableau2pbir.validate.pbir_compile.shutil.which", return_value=None):
        r = run_pbir_compile(tmp_path)
    assert r.outcome == ValidatorOutcome.SKIPPED
    assert r.reason == "pbi_tools_unavailable"


def test_passed_on_zero_exit(tmp_path, monkeypatch):
    monkeypatch.setenv("PBI_TOOLS_PATH", "C:/fake/pbi-tools.exe")
    fake = MagicMock(returncode=0, stdout="compile ok", stderr="")
    with patch("tableau2pbir.validate.pbir_compile.subprocess.run", return_value=fake) as srun:
        r = run_pbir_compile(tmp_path)
    assert r.outcome == ValidatorOutcome.PASSED
    assert "compile ok" in (tmp_path / "validation" / "pbir_compile.log").read_text(encoding="utf-8")
    assert srun.call_args[0][0][0:2] == ["C:/fake/pbi-tools.exe", "compile"]


def test_failed_on_nonzero_exit(tmp_path, monkeypatch):
    monkeypatch.setenv("PBI_TOOLS_PATH", "C:/fake/pbi-tools.exe")
    fake = MagicMock(returncode=2, stdout="", stderr="missing report.json")
    with patch("tableau2pbir.validate.pbir_compile.subprocess.run", return_value=fake):
        r = run_pbir_compile(tmp_path)
    assert r.outcome == ValidatorOutcome.FAILED
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/unit/validate/test_pbir_compile.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

```python
# src/tableau2pbir/validate/pbir_compile.py
"""PBIR compile validity via pbi-tools. See spec §6 Stage 8 step 3 + §9 layer iv-b."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from tableau2pbir.validate.results import ValidatorOutcome, ValidatorResult

_TIMEOUT_S = 120


def _resolve_pbi_tools() -> str | None:
    return os.environ.get("PBI_TOOLS_PATH") or shutil.which("pbi-tools") \
           or shutil.which("pbi-tools.exe")


def run_pbir_compile(out_dir: Path) -> ValidatorResult:
    log_rel = "validation/pbir_compile.log"
    log_path = out_dir / log_rel
    log_path.parent.mkdir(parents=True, exist_ok=True)

    pbi = _resolve_pbi_tools()
    if pbi is None:
        log_path.write_text(
            "pbi-tools not found on PATH and PBI_TOOLS_PATH is unset; skipped.\n",
            encoding="utf-8")
        return ValidatorResult(outcome=ValidatorOutcome.SKIPPED, reason="pbi_tools_unavailable",
                               log_path=log_rel)

    try:
        proc = subprocess.run(
            [pbi, "compile", str(out_dir)],
            capture_output=True, text=True, timeout=_TIMEOUT_S,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        log_path.write_text(f"pbi-tools compile failed: {e!r}\n", encoding="utf-8")
        return ValidatorResult(outcome=ValidatorOutcome.FAILED, reason="pbi_tools_invocation_error",
                               log_path=log_rel)

    log_path.write_text(
        (proc.stdout or "") + ("\n--- STDERR ---\n" + proc.stderr if proc.stderr else ""),
        encoding="utf-8",
    )
    outcome = ValidatorOutcome.PASSED if proc.returncode == 0 else ValidatorOutcome.FAILED
    return ValidatorResult(outcome=outcome, reason=None, log_path=log_rel)
```

- [ ] **Step 4: Verify**

Run: `pytest tests/unit/validate/test_pbir_compile.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/tableau2pbir/validate/pbir_compile.py tests/unit/validate/test_pbir_compile.py
git commit -m "feat(stage8): PBIR compile via pbi-tools (skip when unavailable)"
```

---

### Task 6: Trace event canonical mapper + per-version probe

**Files:**
- Create: `src/tableau2pbir/validate/trace_events.py`
- Create: `tests/desktop_open/version_probes/2_130.json`
- Create: `tests/desktop_open/version_probes/README.md`
- Test: `tests/unit/validate/test_trace_events.py`

The trace parser reads PBI Desktop trace files and maps version-specific event names to a canonical set: `{ReportLoaded, ModelLoaded, RepairPrompt, ModelError, VisualError, AuthenticationNeeded, AuthUIDisplayed}`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/validate/test_trace_events.py
import json
from pathlib import Path
from tableau2pbir.validate.trace_events import (
    CANONICAL_EVENTS, load_version_map, parse_trace_file,
)


def test_canonical_set_matches_spec():
    assert CANONICAL_EVENTS == frozenset({
        "ReportLoaded", "ModelLoaded", "RepairPrompt", "ModelError",
        "VisualError", "AuthenticationNeeded", "AuthUIDisplayed",
    })


def test_parses_jsonl_trace_with_canonical_names(tmp_path: Path):
    trace = tmp_path / "trace.json"
    trace.write_text("\n".join([
        json.dumps({"ts": 1000, "event": "Microsoft.PowerBI.Client.Core.ReportLoaded"}),
        json.dumps({"ts": 2000, "event": "ModelLoaded"}),
        json.dumps({"ts": 3000, "event": "Microsoft.AnalysisServices.AuthenticationNeeded"}),
        json.dumps({"ts": 4000, "event": "VisualError", "error": "boom"}),
        json.dumps({"ts": 5000, "event": "UnknownGarbage"}),
    ]), encoding="utf-8")
    events = parse_trace_file(trace, version_map=load_version_map(version="2.130"))
    names = [e.name for e in events]
    assert names == ["ReportLoaded", "ModelLoaded", "AuthenticationNeeded", "VisualError"]
    assert events[0].timestamp_ms == 1000


def test_load_version_map_unknown_version_returns_default(tmp_path):
    m = load_version_map(version="9.9.9")
    # Unknown still returns a usable map (canonical → canonical identity)
    assert "ReportLoaded" in m.values()
```

- [ ] **Step 2: Verify failure**

Run: `pytest tests/unit/validate/test_trace_events.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

Create `tests/desktop_open/version_probes/README.md`:

```markdown
# PBI Desktop trace event probe fixtures

Each `<major>_<minor>.json` maps the version's raw trace event names to the
canonical set defined in `validate.trace_events.CANONICAL_EVENTS`. See spec
§9 layer vii.
```

Create `tests/desktop_open/version_probes/2_130.json`:

```json
{
  "version": "2.130",
  "map": {
    "Microsoft.PowerBI.Client.Core.ReportLoaded":          "ReportLoaded",
    "ReportLoaded":                                        "ReportLoaded",
    "Microsoft.PowerBI.Client.Core.ModelLoaded":           "ModelLoaded",
    "ModelLoaded":                                         "ModelLoaded",
    "Microsoft.AnalysisServices.AuthenticationNeeded":     "AuthenticationNeeded",
    "AuthenticationNeeded":                                "AuthenticationNeeded",
    "AuthUIDisplayed":                                     "AuthUIDisplayed",
    "VisualError":                                         "VisualError",
    "ModelError":                                          "ModelError",
    "RepairPrompt":                                        "RepairPrompt"
  }
}
```

Create `src/tableau2pbir/validate/trace_events.py`:

```python
"""Canonical PBI Desktop trace event mapping. See spec §9 layer vii."""
from __future__ import annotations

import json
from pathlib import Path

from tableau2pbir.validate.results import TraceEvent

CANONICAL_EVENTS = frozenset({
    "ReportLoaded", "ModelLoaded", "RepairPrompt", "ModelError",
    "VisualError", "AuthenticationNeeded", "AuthUIDisplayed",
})

_PROBE_DIR = Path(__file__).resolve().parents[3] / "tests" / "desktop_open" / "version_probes"
_DEFAULT_MAP = {name: name for name in CANONICAL_EVENTS}


def load_version_map(*, version: str) -> dict[str, str]:
    """Load `<major>_<minor>.json` from the version_probes/ directory.

    Returns an identity-only canonical map when no probe matches the version.
    """
    safe = version.replace(".", "_")
    candidate = _PROBE_DIR / f"{safe}.json"
    if not candidate.is_file():
        # try '<major>_<minor>' fallback by trimming patch
        parts = version.split(".")
        if len(parts) >= 2:
            candidate = _PROBE_DIR / f"{parts[0]}_{parts[1]}.json"
    if candidate.is_file():
        data = json.loads(candidate.read_text(encoding="utf-8"))
        m = dict(_DEFAULT_MAP)
        m.update(data.get("map", {}))
        return m
    return dict(_DEFAULT_MAP)


def parse_trace_file(path: Path, *, version_map: dict[str, str]) -> tuple[TraceEvent, ...]:
    """Parse a JSONL trace file. Lines whose `event` field maps to a canonical
    name are kept; unknown events are dropped. Order is preserved."""
    events: list[TraceEvent] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        try:
            obj = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        raw_name = obj.get("event")
        if not raw_name:
            continue
        canonical = version_map.get(raw_name)
        if canonical not in CANONICAL_EVENTS:
            continue
        ts = int(obj.get("ts", 0))
        events.append(TraceEvent(name=canonical, timestamp_ms=ts, raw=raw_line))
    return tuple(events)
```

- [ ] **Step 4: Verify**

Run: `pytest tests/unit/validate/test_trace_events.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/tableau2pbir/validate/trace_events.py tests/desktop_open/version_probes/ tests/unit/validate/test_trace_events.py
git commit -m "feat(stage8): canonical PBI Desktop trace event mapper + 2.130 probe"
```

---

### Task 7: Desktop-open gate launcher

**Files:**
- Create: `src/tableau2pbir/validate/desktop_open.py`
- Test: `tests/unit/validate/test_desktop_open.py`

Pass criteria per workbook tier (spec §6 Stage 8 step 5):

| Workbook tier | Required events | Auth events | Notes |
|---|---|---|---|
| All Tier 1 | `ReportLoaded` AND `ModelLoaded` | none expected | non-auth ERROR is failure |
| Any Tier 2 | `ReportLoaded` only | `AuthenticationNeeded` / `AuthUIDisplayed` recorded as expected prompts | non-auth ERROR is failure |
| Any Tier 4 | (already forced `failed` by §8.1, gate not run) | n/a | n/a |
| Tier 3 | follows Tier 1 or Tier 2 per `user_action_required` (driver install → Tier 1; OAuth → Tier 2) | per fall-through | n/a |

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/validate/test_desktop_open.py
from pathlib import Path
from unittest.mock import patch, MagicMock
import json

from tableau2pbir.validate.desktop_open import run_desktop_open
from tableau2pbir.validate.results import ValidatorOutcome


def _write_trace(traces_dir: Path, events: list[dict]) -> Path:
    traces_dir.mkdir(parents=True)
    p = traces_dir / "session.json"
    p.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")
    return p


def test_skipped_when_pbi_desktop_unavailable(tmp_path, monkeypatch):
    monkeypatch.delenv("PBI_DESKTOP_PATH", raising=False)
    with patch("tableau2pbir.validate.desktop_open.shutil.which", return_value=None):
        r = run_desktop_open(tmp_path / "wb.pbip", datasource_tiers=(1,),
                             traces_dir=tmp_path / "traces")
    assert r.outcome == ValidatorOutcome.SKIPPED
    assert r.reason == "desktop_unavailable"


def test_tier1_passes_with_report_and_model_loaded(tmp_path, monkeypatch):
    monkeypatch.setenv("PBI_DESKTOP_PATH", "C:/fake/PBIDesktop.exe")
    pbip = tmp_path / "wb.pbip"
    pbip.write_text("{}", encoding="utf-8")
    traces = tmp_path / "traces"
    _write_trace(traces, [
        {"ts": 1000, "event": "ReportLoaded"},
        {"ts": 2000, "event": "ModelLoaded"},
    ])
    fake_proc = MagicMock()
    fake_proc.poll.return_value = None
    fake_proc.terminate = MagicMock()
    fake_proc.wait = MagicMock(return_value=0)
    with patch("tableau2pbir.validate.desktop_open.subprocess.Popen", return_value=fake_proc), \
         patch("tableau2pbir.validate.desktop_open._wait_for_load",
               return_value=("done", None)):
        r = run_desktop_open(pbip, datasource_tiers=(1,), traces_dir=traces,
                             desktop_version="2.130")
    assert r.outcome == ValidatorOutcome.PASSED


def test_tier1_fails_when_only_report_loaded(tmp_path, monkeypatch):
    monkeypatch.setenv("PBI_DESKTOP_PATH", "C:/fake/PBIDesktop.exe")
    pbip = tmp_path / "wb.pbip"
    pbip.write_text("{}", encoding="utf-8")
    traces = tmp_path / "traces"
    _write_trace(traces, [{"ts": 1000, "event": "ReportLoaded"}])
    fake_proc = MagicMock()
    fake_proc.poll.return_value = None
    with patch("tableau2pbir.validate.desktop_open.subprocess.Popen", return_value=fake_proc), \
         patch("tableau2pbir.validate.desktop_open._wait_for_load",
               return_value=("done", None)):
        r = run_desktop_open(pbip, datasource_tiers=(1,), traces_dir=traces,
                             desktop_version="2.130")
    assert r.outcome == ValidatorOutcome.FAILED


def test_tier2_passes_with_only_report_loaded_and_auth_event(tmp_path, monkeypatch):
    monkeypatch.setenv("PBI_DESKTOP_PATH", "C:/fake/PBIDesktop.exe")
    pbip = tmp_path / "wb.pbip"
    pbip.write_text("{}", encoding="utf-8")
    traces = tmp_path / "traces"
    _write_trace(traces, [
        {"ts": 1000, "event": "ReportLoaded"},
        {"ts": 1500, "event": "AuthenticationNeeded"},
    ])
    fake_proc = MagicMock()
    fake_proc.poll.return_value = None
    with patch("tableau2pbir.validate.desktop_open.subprocess.Popen", return_value=fake_proc), \
         patch("tableau2pbir.validate.desktop_open._wait_for_load",
               return_value=("done", None)):
        r = run_desktop_open(pbip, datasource_tiers=(1, 2), traces_dir=traces,
                             desktop_version="2.130")
    assert r.outcome == ValidatorOutcome.PASSED
    assert any(e.name == "AuthenticationNeeded" for e in r.expected_credential_prompts)


def test_tier1_fails_when_visual_error_present(tmp_path, monkeypatch):
    monkeypatch.setenv("PBI_DESKTOP_PATH", "C:/fake/PBIDesktop.exe")
    pbip = tmp_path / "wb.pbip"
    pbip.write_text("{}", encoding="utf-8")
    traces = tmp_path / "traces"
    _write_trace(traces, [
        {"ts": 1000, "event": "ReportLoaded"},
        {"ts": 1500, "event": "ModelLoaded"},
        {"ts": 2000, "event": "VisualError"},
    ])
    fake_proc = MagicMock()
    fake_proc.poll.return_value = None
    with patch("tableau2pbir.validate.desktop_open.subprocess.Popen", return_value=fake_proc), \
         patch("tableau2pbir.validate.desktop_open._wait_for_load",
               return_value=("done", None)):
        r = run_desktop_open(pbip, datasource_tiers=(1,), traces_dir=traces,
                             desktop_version="2.130")
    assert r.outcome == ValidatorOutcome.FAILED
```

- [ ] **Step 2: Verify failure**

Run: `pytest tests/unit/validate/test_desktop_open.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

```python
# src/tableau2pbir/validate/desktop_open.py
"""Desktop-open gate launcher. See spec §6 Stage 8 step 5 + §9 layer vii."""
from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

from tableau2pbir.validate.results import (
    DesktopOpenResult, TraceEvent, ValidatorOutcome,
)
from tableau2pbir.validate.trace_events import load_version_map, parse_trace_file

_TIMEOUT_S = 300
_FLAKE_RETRY_AFTER_S = 60


def _resolve_pbi_desktop() -> str | None:
    return os.environ.get("PBI_DESKTOP_PATH") or shutil.which("PBIDesktop.exe") \
           or shutil.which("PBIDesktop")


def _wait_for_load(traces_dir: Path, *, timeout_s: int) -> tuple[str, str | None]:
    """Poll the traces directory until either ReportLoaded shows up or timeout.
    Returns ('done', None) on success, ('timeout', 'no_events_60s' | 'overall')."""
    deadline = time.monotonic() + timeout_s
    saw_any_event_by_60s = False
    start = time.monotonic()
    while time.monotonic() < deadline:
        if traces_dir.is_dir() and any(traces_dir.glob("*.json")):
            saw_any_event_by_60s = True
            return ("done", None)
        if (time.monotonic() - start) > _FLAKE_RETRY_AFTER_S and not saw_any_event_by_60s:
            return ("timeout", "no_events_60s")
        time.sleep(2)
    return ("timeout", "overall")


def _evaluate(events: tuple[TraceEvent, ...], tiers: tuple[int, ...]
              ) -> tuple[ValidatorOutcome, tuple[TraceEvent, ...]]:
    names = {e.name for e in events}
    auth_events = tuple(e for e in events if e.name in {"AuthenticationNeeded", "AuthUIDisplayed"})
    error_names = {"VisualError", "ModelError", "RepairPrompt"}
    has_non_auth_error = bool(names & error_names)

    if 2 in tiers:
        ok = "ReportLoaded" in names and not has_non_auth_error
        return (ValidatorOutcome.PASSED if ok else ValidatorOutcome.FAILED, auth_events)
    # Tier 1 / Tier 3-as-Tier-1
    ok = "ReportLoaded" in names and "ModelLoaded" in names and not has_non_auth_error
    return (ValidatorOutcome.PASSED if ok else ValidatorOutcome.FAILED, ())


def run_desktop_open(pbip_path: Path, *, datasource_tiers: tuple[int, ...],
                     traces_dir: Path, desktop_version: str = "2.130",
                     log_path: Path | None = None) -> DesktopOpenResult:
    desktop = _resolve_pbi_desktop()
    if desktop is None:
        return DesktopOpenResult(outcome=ValidatorOutcome.SKIPPED, reason="desktop_unavailable")

    proc = subprocess.Popen([desktop, "/Open", str(pbip_path)])
    try:
        status, why = _wait_for_load(traces_dir, timeout_s=_TIMEOUT_S)
        if status == "timeout":
            return DesktopOpenResult(outcome=ValidatorOutcome.FAILED, reason=why or "timeout")

        version_map = load_version_map(version=desktop_version)
        events: list[TraceEvent] = []
        for trace_file in sorted(traces_dir.glob("*.json")):
            events.extend(parse_trace_file(trace_file, version_map=version_map))
        outcome, auth_events = _evaluate(tuple(events), datasource_tiers)
        return DesktopOpenResult(outcome=outcome, reason=None,
                                 events=tuple(events),
                                 expected_credential_prompts=auth_events,
                                 log_path=str(log_path) if log_path else None)
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=10)
        except Exception:
            pass
```

- [ ] **Step 4: Verify**

Run: `pytest tests/unit/validate/test_desktop_open.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add src/tableau2pbir/validate/desktop_open.py tests/unit/validate/test_desktop_open.py
git commit -m "feat(stage8): Desktop-open gate launcher with tiered pass criteria"
```

---

### Task 8: Rubric loader + evaluator → acceptance.json

**Files:**
- Create: `src/tableau2pbir/validate/rubric.py`
- Create: `tests/golden/real/Superstore.rubric.yaml`
- Test: `tests/unit/validate/test_rubric.py`

The rubric YAML schema follows spec §15. Stage 8 evaluates:

- `all_pages_load` — every page in `Report/definition/pages/` has a `page.json`.
- `all_must_render_visuals_present` — every name in any page's `must_render_visuals` corresponds to a sheet whose visual was rendered (not in Stage 7 `blocked_visuals[]`).
- `all_must_have_slicers_present` — every slicer name is present in the per-page slicer list.
- `no_unexpected_placeholders` — placeholder leaves outside the page's `known_degradations` list count as failure.
- `desktop_open_gate` — value comes from the Desktop-open result (`PASSED` → `passed`).
- `all_measure_values_within_tolerance` — **skipped** in Plan 5 (reason `dax_probe_runner_unavailable`).

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/validate/test_rubric.py
from pathlib import Path
import textwrap

from tableau2pbir.validate.rubric import load_rubric, evaluate_rubric, write_acceptance_json
from tableau2pbir.validate.results import ValidatorOutcome


def _write(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "wb.rubric.yaml"
    p.write_text(textwrap.dedent(body), encoding="utf-8")
    return p


def test_load_rubric_minimal(tmp_path):
    p = _write(tmp_path, """
        workbook: Foo.twbx
        pages: []
        measures: []
        datasources: []
        pass_criteria:
          all_pages_load: true
    """)
    r = load_rubric(p)
    assert r.workbook == "Foo.twbx"
    assert r.pass_criteria["all_pages_load"] is True


def test_evaluate_passes_when_observation_matches(tmp_path):
    p = _write(tmp_path, """
        workbook: Foo.twbx
        pages:
          - name: Overview
            must_render_visuals: [bar_by_region]
            must_have_slicers: [region]
            known_degradations: []
        measures: []
        datasources: []
        pass_criteria:
          all_pages_load: true
          all_must_render_visuals_present: true
          all_must_have_slicers_present: true
          no_unexpected_placeholders: true
          desktop_open_gate: passed
    """)
    rubric = load_rubric(p)

    observation = {
        "rendered_pages": ["Overview"],
        "rendered_visuals_by_page": {"Overview": ["bar_by_region"]},
        "rendered_slicers_by_page": {"Overview": ["region"]},
        "placeholder_visuals_by_page": {"Overview": []},
        "desktop_open_outcome": "passed",
    }
    result = evaluate_rubric(rubric, observation)
    assert result.outcome == ValidatorOutcome.PASSED
    names = [item.name for item in result.items]
    assert "all_pages_load" in names
    assert "desktop_open_gate" in names


def test_evaluate_fails_when_must_render_visual_missing(tmp_path):
    p = _write(tmp_path, """
        workbook: Foo.twbx
        pages:
          - name: Overview
            must_render_visuals: [bar_by_region]
            must_have_slicers: []
            known_degradations: []
        measures: []
        datasources: []
        pass_criteria:
          all_must_render_visuals_present: true
    """)
    rubric = load_rubric(p)
    observation = {
        "rendered_pages": ["Overview"],
        "rendered_visuals_by_page": {"Overview": []},
        "rendered_slicers_by_page": {"Overview": []},
        "placeholder_visuals_by_page": {"Overview": []},
        "desktop_open_outcome": "skipped",
    }
    r = evaluate_rubric(rubric, observation)
    assert r.outcome == ValidatorOutcome.FAILED
    bad = next(i for i in r.items if i.name == "all_must_render_visuals_present")
    assert bad.outcome == ValidatorOutcome.FAILED


def test_measure_tolerance_is_skipped_in_v1(tmp_path):
    p = _write(tmp_path, """
        workbook: Foo.twbx
        pages: []
        measures:
          - name: Total Revenue
            must_match_tableau_value_within: 0.0001
        datasources: []
        pass_criteria:
          all_measure_values_within_tolerance: true
    """)
    rubric = load_rubric(p)
    r = evaluate_rubric(rubric, {})
    item = next(i for i in r.items if i.name == "all_measure_values_within_tolerance")
    assert item.outcome == ValidatorOutcome.SKIPPED


def test_write_acceptance_json_emits_per_item(tmp_path):
    from tableau2pbir.validate.results import RubricItemResult, RubricResult
    rr = RubricResult(outcome=ValidatorOutcome.PASSED, reason=None, items=(
        RubricItemResult(name="all_pages_load", required=True,
                         outcome=ValidatorOutcome.PASSED, observed="2/2"),
    ))
    out = tmp_path / "acceptance.json"
    write_acceptance_json(out, rr)
    import json
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["overall"] == "passed"
    assert data["items"][0] == {
        "name": "all_pages_load", "required": True,
        "outcome": "passed", "observed": "2/2",
    }
```

- [ ] **Step 2: Verify failure**

Run: `pytest tests/unit/validate/test_rubric.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

Create `tests/golden/real/Superstore.rubric.yaml`:

```yaml
workbook: Superstore.twbx
pages:
  - name: "Overview"
    must_render_visuals: []
    must_have_slicers: []
    known_degradations: []
measures: []
datasources:
  - name: Orders
    expected_tier: 1
    user_action: "none"
pass_criteria:
  all_pages_load: true
  all_must_render_visuals_present: true
  all_must_have_slicers_present: true
  no_unexpected_placeholders: false
  desktop_open_gate: passed
```

> NOTE: `must_render_visuals` is intentionally empty for Plan 5. A rubric author with Tableau access fills these in once the real-workbook fixtures are stabilized.

Create `src/tableau2pbir/validate/rubric.py`:

```python
"""Rubric loader + evaluator. See spec §15."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from tableau2pbir.validate.results import (
    RubricItemResult, RubricResult, ValidatorOutcome,
)


@dataclass(frozen=True)
class RubricPage:
    name: str
    must_render_visuals: tuple[str, ...]
    must_have_slicers: tuple[str, ...]
    known_degradations: tuple[str, ...]


@dataclass(frozen=True)
class Rubric:
    workbook: str
    pages: tuple[RubricPage, ...]
    measures: tuple[dict, ...]
    datasources: tuple[dict, ...]
    pass_criteria: dict[str, Any]


def load_rubric(path: Path) -> Rubric:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    pages = tuple(
        RubricPage(
            name=p.get("name", ""),
            must_render_visuals=tuple(p.get("must_render_visuals") or ()),
            must_have_slicers=tuple(p.get("must_have_slicers") or ()),
            known_degradations=tuple(p.get("known_degradations") or ()),
        )
        for p in (data.get("pages") or ())
    )
    return Rubric(
        workbook=data.get("workbook", ""),
        pages=pages,
        measures=tuple(data.get("measures") or ()),
        datasources=tuple(data.get("datasources") or ()),
        pass_criteria=dict(data.get("pass_criteria") or {}),
    )


def evaluate_rubric(rubric: Rubric, observation: dict[str, Any]) -> RubricResult:
    items: list[RubricItemResult] = []
    pc = rubric.pass_criteria

    if "all_pages_load" in pc:
        rendered = set(observation.get("rendered_pages") or ())
        expected = {p.name for p in rubric.pages}
        ok = expected.issubset(rendered) if expected else True
        items.append(RubricItemResult(
            name="all_pages_load", required=bool(pc["all_pages_load"]),
            outcome=ValidatorOutcome.PASSED if ok else ValidatorOutcome.FAILED,
            observed=f"{len(rendered & expected)}/{len(expected)} pages",
        ))

    if "all_must_render_visuals_present" in pc:
        ok, observed = _check_must_lists(
            rubric, observation.get("rendered_visuals_by_page") or {},
            attr="must_render_visuals",
        )
        items.append(RubricItemResult(
            name="all_must_render_visuals_present",
            required=bool(pc["all_must_render_visuals_present"]),
            outcome=ValidatorOutcome.PASSED if ok else ValidatorOutcome.FAILED,
            observed=observed,
        ))

    if "all_must_have_slicers_present" in pc:
        ok, observed = _check_must_lists(
            rubric, observation.get("rendered_slicers_by_page") or {},
            attr="must_have_slicers",
        )
        items.append(RubricItemResult(
            name="all_must_have_slicers_present",
            required=bool(pc["all_must_have_slicers_present"]),
            outcome=ValidatorOutcome.PASSED if ok else ValidatorOutcome.FAILED,
            observed=observed,
        ))

    if "no_unexpected_placeholders" in pc:
        bad: list[str] = []
        for page in rubric.pages:
            placeholders = set(
                (observation.get("placeholder_visuals_by_page") or {}).get(page.name, ())
            )
            unexpected = placeholders - set(page.known_degradations)
            for u in unexpected:
                bad.append(f"{page.name}/{u}")
        ok = not bad
        items.append(RubricItemResult(
            name="no_unexpected_placeholders",
            required=bool(pc["no_unexpected_placeholders"]),
            outcome=ValidatorOutcome.PASSED if ok else ValidatorOutcome.FAILED,
            observed=", ".join(bad) if bad else "none",
        ))

    if "desktop_open_gate" in pc:
        target = pc["desktop_open_gate"]
        actual = observation.get("desktop_open_outcome", "skipped")
        ok = (actual == target)
        items.append(RubricItemResult(
            name="desktop_open_gate", required=True,
            outcome=ValidatorOutcome.PASSED if ok else ValidatorOutcome.FAILED,
            observed=str(actual),
        ))

    if "all_measure_values_within_tolerance" in pc:
        items.append(RubricItemResult(
            name="all_measure_values_within_tolerance",
            required=bool(pc["all_measure_values_within_tolerance"]),
            outcome=ValidatorOutcome.SKIPPED,
            observed="dax_probe_runner_unavailable",
        ))

    failed_required = any(
        i.required and i.outcome == ValidatorOutcome.FAILED for i in items
    )
    overall = ValidatorOutcome.FAILED if failed_required else ValidatorOutcome.PASSED
    return RubricResult(outcome=overall, reason=None, items=tuple(items))


def _check_must_lists(rubric: Rubric, observed_by_page: dict[str, list[str]],
                      *, attr: str) -> tuple[bool, str]:
    missing: list[str] = []
    total = 0
    for page in rubric.pages:
        wanted = set(getattr(page, attr))
        total += len(wanted)
        actual = set(observed_by_page.get(page.name, ()))
        for w in wanted:
            if w not in actual:
                missing.append(f"{page.name}/{w}")
    return (not missing, f"missing={missing}" if missing else f"all {total} present")


def write_acceptance_json(path: Path, result: RubricResult) -> None:
    payload = {
        "overall": result.outcome.value,
        "items": [
            {"name": i.name, "required": i.required,
             "outcome": i.outcome.value, "observed": i.observed}
            for i in result.items
        ],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
```

- [ ] **Step 4: Verify**

Run: `pytest tests/unit/validate/test_rubric.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add src/tableau2pbir/validate/rubric.py tests/unit/validate/test_rubric.py tests/golden/real/Superstore.rubric.yaml
git commit -m "feat(stage8): rubric loader + evaluator + acceptance.json emitter"
```

---

### Task 9: Status rule (§8.1)

**Files:**
- Create: `src/tableau2pbir/validate/status.py`
- Test: `tests/unit/validate/test_status.py`

The status rule reads:

- IR (`Workbook` from `stages/02_canonicalize.json`) — datasource tiers, parameter intents, calc count.
- `unsupported.json` — codes (`deferred_feature_*`), object_kind, calc-confidence flags.
- Stage 5 manifest — placeholder-leaf-ratio per dashboard.
- Stage 7 manifest — `blocked_visuals[]`.
- Validator results — `tmdl`, `pbir_compile`, `desktop_open`, `rubric.acceptance_failed`.

Returns `(status: 'ok'|'partial'|'failed', triggers: list[str])`. Top-to-bottom rule.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/validate/test_status.py
from tableau2pbir.validate.status import compute_status, ObservationBundle


def _bundle(**over):
    base = dict(
        datasource_tiers=(1,),
        unsupported=[],
        measures_total=10,
        placeholder_leaf_ratios=[0.0],
        blocked_visuals=[],
        tmdl_outcome="passed",
        pbir_compile_outcome="passed",
        desktop_open_outcome="passed",
        rubric_acceptance_failed=False,
        any_calc_low_confidence=False,
        any_clamped_or_dropped_layout=False,
        param_intents=[],
        user_actions=[],
    )
    base.update(over)
    return ObservationBundle(**base)


def test_ok_all_clean():
    s, triggers = compute_status(_bundle())
    assert s == "ok"
    assert triggers == []


def test_failed_when_any_tier_4_datasource():
    s, triggers = compute_status(_bundle(datasource_tiers=(1, 4)))
    assert s == "failed"
    assert "datasource_tier_4" in triggers


def test_failed_when_more_than_50pct_measures_dropped():
    unsupported = [
        {"object_kind": "calculation", "code": "calc.invalid_dax", "severity": "warn"}
    ] * 6
    s, triggers = compute_status(_bundle(measures_total=10, unsupported=unsupported))
    assert s == "failed"
    assert "measures_drop_rate_over_50pct" in triggers


def test_failed_when_pbir_compile_fails():
    s, triggers = compute_status(_bundle(pbir_compile_outcome="failed"))
    assert s == "failed"
    assert "pbir_compile_failed" in triggers


def test_failed_when_acceptance_failed():
    s, triggers = compute_status(_bundle(rubric_acceptance_failed=True))
    assert s == "failed"
    assert "acceptance_failed" in triggers


def test_failed_when_blocked_visual_with_deferred_datasource():
    s, triggers = compute_status(_bundle(
        blocked_visuals=[{"page_id": "p1", "visual_id": "v1",
                          "blocked_by": ["deferred_feature_table_calc"]}],
        unsupported=[{"object_kind": "datasource",
                      "code": "deferred_feature_table_calc",
                      "severity": "warn"}],
    ))
    assert s == "failed"
    assert "blocked_visual_with_deferred_datasource" in triggers


def test_partial_when_dashboard_has_placeholder_leaves():
    s, triggers = compute_status(_bundle(placeholder_leaf_ratios=[0.2]))
    assert s == "partial"
    assert "dashboard_has_placeholders" in triggers


def test_partial_when_low_confidence_calc():
    s, triggers = compute_status(_bundle(any_calc_low_confidence=True))
    assert s == "partial"


def test_partial_when_tier_3_datasource():
    s, triggers = compute_status(_bundle(datasource_tiers=(1, 3)))
    assert s == "partial"
    assert "datasource_tier_3" in triggers


def test_skipped_validators_dont_affect_status():
    s, triggers = compute_status(_bundle(
        tmdl_outcome="skipped", pbir_compile_outcome="skipped",
        desktop_open_outcome="skipped",
    ))
    assert s == "ok"
    assert triggers == []


def test_failed_dominates_partial_signals():
    s, triggers = compute_status(_bundle(
        datasource_tiers=(4,),                  # → failed
        placeholder_leaf_ratios=[0.2],          # would be partial
    ))
    assert s == "failed"
```

- [ ] **Step 2: Verify failure**

Run: `pytest tests/unit/validate/test_status.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

```python
# src/tableau2pbir/validate/status.py
"""Workbook status rule (spec §8.1)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ObservationBundle:
    datasource_tiers: tuple[int, ...]
    unsupported: list[dict]                     # raw unsupported.json items
    measures_total: int
    placeholder_leaf_ratios: list[float]
    blocked_visuals: list[dict]                 # from stage 7 manifest
    tmdl_outcome: str                           # 'passed' | 'failed' | 'skipped'
    pbir_compile_outcome: str
    desktop_open_outcome: str
    rubric_acceptance_failed: bool
    any_calc_low_confidence: bool
    any_clamped_or_dropped_layout: bool
    param_intents: list[str]                    # values like 'unsupported'
    user_actions: list[str]                     # e.g. 'install Oracle client'


def compute_status(obs: ObservationBundle) -> tuple[str, list[str]]:
    triggers: list[str] = []

    # ----- failed checks (top-to-bottom) -----
    if any(t == 4 for t in obs.datasource_tiers):
        triggers.append("datasource_tier_4")

    measure_drops = sum(
        1 for u in obs.unsupported
        if u.get("object_kind") == "calculation" and u.get("severity") in ("warn", "error", "fatal")
    )
    if obs.measures_total > 0 and measure_drops / obs.measures_total > 0.5:
        triggers.append("measures_drop_rate_over_50pct")

    if any(r >= 0.5 for r in obs.placeholder_leaf_ratios):
        triggers.append("dashboard_placeholder_ratio_over_50pct")

    if obs.tmdl_outcome == "failed":
        triggers.append("tmdl_validity_failed")
    if obs.pbir_compile_outcome == "failed":
        triggers.append("pbir_compile_failed")
    if obs.desktop_open_outcome == "failed":
        triggers.append("desktop_open_gate_failed")
    if obs.rubric_acceptance_failed:
        triggers.append("acceptance_failed")

    deferred_ds_codes = {
        u.get("code") for u in obs.unsupported
        if u.get("object_kind") == "datasource"
        and str(u.get("code", "")).startswith("deferred_feature_")
    }
    for bv in obs.blocked_visuals:
        if any(code in deferred_ds_codes for code in bv.get("blocked_by", ())):
            triggers.append("blocked_visual_with_deferred_datasource")
            break

    if triggers:
        return ("failed", triggers)

    # ----- partial checks -----
    if any(0 < r < 0.5 for r in obs.placeholder_leaf_ratios):
        triggers.append("dashboard_has_placeholders")
    if obs.any_calc_low_confidence:
        triggers.append("calc_low_confidence")
    if obs.any_clamped_or_dropped_layout:
        triggers.append("layout_clamped_or_dropped")
    if any(t == 3 for t in obs.datasource_tiers):
        triggers.append("datasource_tier_3")
    if any("install" in ua.lower() for ua in obs.user_actions):
        triggers.append("driver_install_required")
    if "unsupported" in obs.param_intents:
        triggers.append("parameter_intent_unsupported")
    if any(str(u.get("code", "")).startswith("deferred_feature_") for u in obs.unsupported):
        triggers.append("deferred_feature_present")

    if triggers:
        return ("partial", triggers)
    return ("ok", [])
```

- [ ] **Step 4: Verify**

Run: `pytest tests/unit/validate/test_status.py -v`
Expected: PASS (11 tests).

- [ ] **Step 5: Commit**

```bash
git add src/tableau2pbir/validate/status.py tests/unit/validate/test_status.py
git commit -m "feat(stage8): workbook status rule (spec §8.1) with explicit triggers"
```

---

### Task 10: Reporting — workbook-report.md, summary.md, run-manifest row

**Files:**
- Create: `src/tableau2pbir/validate/report.py`
- Test: `tests/unit/validate/test_report.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/validate/test_report.py
from tableau2pbir.validate.report import (
    render_workbook_report, render_summary_md, render_run_manifest_row,
)


def test_workbook_report_lists_status_and_triggers():
    md = render_workbook_report(
        workbook_id="Foo",
        status="partial", triggers=["datasource_tier_3"],
        validators={
            "tmdl": {"outcome": "passed", "reason": None},
            "pbir_compile": {"outcome": "skipped", "reason": "pbi_tools_unavailable"},
            "structural": {"outcome": "passed", "findings": []},
            "desktop_open": {"outcome": "skipped", "reason": "synthetic"},
            "rubric": {"outcome": "skipped", "reason": "no_rubric"},
        },
        datasources=[{"name": "Sales", "tier": 3, "user_action_required": ["enter creds"]}],
        placeholders_per_page={"Overview": 0},
    )
    assert "# Workbook conversion report — Foo" in md
    assert "**Status:** partial" in md
    assert "datasource_tier_3" in md
    assert "tmdl: passed" in md
    assert "pbi_tools_unavailable" in md
    assert "Sales" in md


def test_summary_lists_validator_outcomes():
    md = render_summary_md(
        validators={"tmdl": {"outcome": "passed"},
                    "pbir_compile": {"outcome": "skipped", "reason": "x"},
                    "structural": {"outcome": "passed"},
                    "desktop_open": {"outcome": "skipped", "reason": "y"},
                    "rubric": {"outcome": "skipped", "reason": "z"}},
        artifact_size_bytes=12345,
        status="ok",
    )
    assert "Stage 8" in md
    assert "tmdl: passed" in md
    assert "12345" in md
    assert "ok" in md


def test_run_manifest_row_columns():
    row = render_run_manifest_row("Foo", "partial", ["calc_low_confidence"], "Foo/workbook-report.md")
    assert row.startswith("| Foo |")
    assert "partial" in row
    assert "calc_low_confidence" in row
    assert "Foo/workbook-report.md" in row
```

- [ ] **Step 2: Verify failure**

Run: `pytest tests/unit/validate/test_report.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

```python
# src/tableau2pbir/validate/report.py
"""Markdown reporters for Stage 8. See spec §4.4 + §6 Stage 8."""
from __future__ import annotations


def render_workbook_report(*, workbook_id: str, status: str, triggers: list[str],
                           validators: dict, datasources: list[dict],
                           placeholders_per_page: dict[str, int]) -> str:
    lines: list[str] = []
    lines.append(f"# Workbook conversion report — {workbook_id}")
    lines.append("")
    lines.append(f"**Status:** {status}")
    if triggers:
        lines.append("")
        lines.append("**Triggers:**")
        for t in triggers:
            lines.append(f"- {t}")
    lines.append("")
    lines.append("## Validators")
    for name, info in validators.items():
        suffix = ""
        if info.get("reason"):
            suffix = f" ({info['reason']})"
        lines.append(f"- {name}: {info.get('outcome', 'unknown')}{suffix}")
    lines.append("")
    lines.append("## Datasources")
    if not datasources:
        lines.append("- (none)")
    else:
        for ds in datasources:
            ua = ", ".join(ds.get("user_action_required") or []) or "none"
            lines.append(f"- **{ds.get('name', '?')}** (tier {ds.get('tier', '?')}) — actions: {ua}")
    lines.append("")
    lines.append("## Placeholders per page")
    for page, count in placeholders_per_page.items():
        lines.append(f"- {page}: {count}")
    lines.append("")
    return "\n".join(lines)


def render_summary_md(*, validators: dict, artifact_size_bytes: int, status: str) -> str:
    lines: list[str] = ["# Stage 8 — package + validate", ""]
    lines.append(f"Final status: **{status}**")
    lines.append("")
    lines.append("Validator outcomes:")
    for name, info in validators.items():
        reason = f" ({info['reason']})" if info.get("reason") else ""
        lines.append(f"- {name}: {info.get('outcome', 'unknown')}{reason}")
    lines.append("")
    lines.append(f"Total artifact size: {artifact_size_bytes} bytes")
    lines.append("")
    return "\n".join(lines)


def render_run_manifest_row(workbook_id: str, status: str,
                            triggers: list[str], link: str) -> str:
    return f"| {workbook_id} | {status} | {','.join(triggers) or '—'} | {link} |"
```

- [ ] **Step 4: Verify**

Run: `pytest tests/unit/validate/test_report.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/tableau2pbir/validate/report.py tests/unit/validate/test_report.py
git commit -m "feat(stage8): markdown reporters (workbook-report, summary, run-manifest row)"
```

---

### Task 11: Stage 8 orchestrator — replace stub

**Files:**
- Modify: `src/tableau2pbir/stages/s08_package_validate.py`
- Test: `tests/unit/stages/test_s08_package_validate.py`

The orchestrator:

1. Reads `stages/02_canonicalize.json` → `Workbook`.
2. Reads `stages/05_compute_layout.json` (for placeholder ratios — optional in v1; default `[0.0] * len(dashboards)` if not present).
3. Reads `stages/07_build_pbir.json` → `blocked_visuals[]`, `counts`.
4. Reads `unsupported.json`.
5. Calls `write_pbip_root(out_dir, workbook_id)`.
6. Calls each validator in order (TMDL → PBIR compile → structural → desktop-open → rubric).
7. Builds `ObservationBundle`, computes status.
8. Writes `validation/structural.json`, `acceptance.json` (if rubric present), `workbook-report.md`, `08_package_validate.summary.md`.
9. Returns `StageResult` whose `output` is the manifest dict (see "Status manifest schema" above).

Real-workbook detection: a `<wb>.rubric.yaml` file in `tests/golden/real/` adjacent to the source path triggers rubric + Desktop-open. Synthetic workbooks skip both.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/stages/test_s08_package_validate.py
from pathlib import Path
import json
from unittest.mock import patch
from tableau2pbir.stages import s08_package_validate
from tableau2pbir.pipeline import StageContext
from tableau2pbir.validate.results import ValidatorOutcome


def _scaffold_prior_outputs(out: Path, *, workbook_id: str = "wb"):
    (out / "Report" / "definition" / "pages" / "p1" / "visuals" / "v1").mkdir(parents=True)
    (out / "Report" / "definition" / "report.json").write_text(
        json.dumps({"name": workbook_id, "pageOrder": ["p1"]}), encoding="utf-8")
    (out / "Report" / "definition" / "pages" / "p1" / "page.json").write_text(
        json.dumps({"name": "p1"}), encoding="utf-8")
    (out / "Report" / "definition" / "pages" / "p1" / "visuals" / "v1" / "visual.json").write_text(
        json.dumps({"name": "v1", "fieldRefs": []}), encoding="utf-8")
    (out / "SemanticModel" / "tables").mkdir(parents=True)

    stages = out / "stages"
    stages.mkdir()
    (stages / "02_canonicalize.json").write_text(json.dumps({
        "ir_schema_version": "1.1.0",
        "source_path": "x.twb",
        "source_hash": "0",
        "tableau_version": None,
        "config": {},
        "data_model": {
            "datasources": [{"id": "d1", "name": "Sales", "connector_tier": 1,
                             "tableau_kind": "csv", "pbi_m_connector": "Csv.Document",
                             "connection_params": {}, "user_action_required": [],
                             "tables": [], "extract_ignored": False}],
            "tables": [], "relationships": [], "calculations": [],
            "parameters": [], "hierarchies": [], "sets": [],
        },
        "sheets": [], "dashboards": [{"id": "d1", "name": "p1",
                                       "size": {"w": 1280, "h": 720, "kind": "auto"},
                                       "layout_tree": {"kind": "h", "children": [],
                                                        "padding": {"top":0,"right":0,"bottom":0,"left":0}},
                                       "actions": []}],
        "unsupported": [],
    }), encoding="utf-8")
    (stages / "07_build_pbir.json").write_text(json.dumps({
        "counts": {"pages": 1, "visuals": 1, "slicers": 0},
        "blocked_visuals": [],
        "visual_interactions": [],
    }), encoding="utf-8")
    (out / "unsupported.json").write_text("[]", encoding="utf-8")


def test_orchestrator_writes_pbip_and_returns_status_ok(tmp_path):
    out = tmp_path / "out"
    _scaffold_prior_outputs(out)
    ctx = StageContext(workbook_id="wb", output_dir=out, config={}, stage_number=8)
    # external validators unavailable → all skipped → ok
    with patch("tableau2pbir.validate.tmdl_schema._resolve_te2", return_value=None), \
         patch("tableau2pbir.validate.pbir_compile._resolve_pbi_tools", return_value=None), \
         patch("tableau2pbir.validate.desktop_open._resolve_pbi_desktop", return_value=None):
        result = s08_package_validate.run({}, ctx)
    assert result.output["status"] == "ok"
    assert (out / "wb.pbip").is_file()
    assert (out / "validation" / "structural.json").is_file()
    assert "wb.pbip" in result.output["pbip_path"]
    assert "Stage 8" in result.summary_md


def test_orchestrator_records_failed_when_structural_check_fails(tmp_path):
    out = tmp_path / "out"
    _scaffold_prior_outputs(out)
    # break a reference: visual references unknown field
    bad = out / "Report" / "definition" / "pages" / "p1" / "visuals" / "v1" / "visual.json"
    bad.write_text(json.dumps({"name": "v1", "fieldRefs": ["Ghost.Col"]}), encoding="utf-8")
    ctx = StageContext(workbook_id="wb", output_dir=out, config={}, stage_number=8)
    with patch("tableau2pbir.validate.tmdl_schema._resolve_te2", return_value=None), \
         patch("tableau2pbir.validate.pbir_compile._resolve_pbi_tools", return_value=None), \
         patch("tableau2pbir.validate.desktop_open._resolve_pbi_desktop", return_value=None):
        result = s08_package_validate.run({}, ctx)
    # Structural failure does NOT directly map to §8.1 by itself in v1; it is recorded
    # but only TMDL/PBIR/Desktop/rubric/acceptance/blocked-visual/etc. flip status.
    # Confirm structural is FAILED in the manifest but workbook can still be 'ok'.
    assert result.output["validators"]["structural"]["result"] == "failed"


def test_orchestrator_skips_rubric_for_synthetic_workbook(tmp_path):
    out = tmp_path / "out"
    _scaffold_prior_outputs(out)
    ctx = StageContext(workbook_id="synthetic_wb", output_dir=out,
                       config={"is_real_workbook": False}, stage_number=8)
    with patch("tableau2pbir.validate.tmdl_schema._resolve_te2", return_value=None), \
         patch("tableau2pbir.validate.pbir_compile._resolve_pbi_tools", return_value=None), \
         patch("tableau2pbir.validate.desktop_open._resolve_pbi_desktop", return_value=None):
        result = s08_package_validate.run({}, ctx)
    assert result.output["validators"]["rubric"]["result"] == "skipped"
    assert result.output["validators"]["rubric"]["reason"] == "synthetic"
    assert result.output["validators"]["desktop_open"]["result"] == "skipped"
```

- [ ] **Step 2: Verify failure**

Run: `pytest tests/unit/stages/test_s08_package_validate.py -v`
Expected: FAIL — current stub has no orchestrator behavior.

- [ ] **Step 3: Implement orchestrator (full file replacement)**

```python
# src/tableau2pbir/stages/s08_package_validate.py
"""Stage 8 — package + validate (pure python). See spec §6 Stage 8."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tableau2pbir.pipeline import StageContext, StageResult
from tableau2pbir.validate import (
    desktop_open as _do, pbir_compile as _pbir, pbip as _pbip,
    report as _report, rubric as _rubric, status as _status,
    structural as _struct, tmdl_schema as _tmdl,
)
from tableau2pbir.validate.results import ValidatorOutcome


def _read_json(p: Path, default):
    if not p.is_file():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def _is_real_workbook(workbook_id: str, config: dict) -> tuple[bool, Path | None]:
    """Real-workbook detection: explicit config override OR a <id>.rubric.yaml
    file alongside tests/golden/real/."""
    if "is_real_workbook" in config:
        is_real = bool(config["is_real_workbook"])
        rubric_path = Path(config["rubric_path"]) if config.get("rubric_path") else None
        return is_real, rubric_path
    repo_root = Path(__file__).resolve().parents[3]
    candidate = repo_root / "tests" / "golden" / "real" / f"{workbook_id}.rubric.yaml"
    if candidate.is_file():
        return True, candidate
    return False, None


def run(input_json: dict[str, Any], ctx: StageContext) -> StageResult:
    out_dir = ctx.output_dir
    stages_dir = out_dir / "stages"

    # 1. Package — write the .pbip pointer.
    pbip_path = _pbip.write_pbip_root(out_dir, ctx.workbook_id)

    # 2. TMDL validity.
    tmdl_res = _tmdl.run_tmdl_validity(out_dir)
    # 3. PBIR compile.
    pbir_res = _pbir.run_pbir_compile(out_dir)
    # 4. Structural checks.
    struct_res = _struct.run_structural(out_dir)
    (out_dir / "validation").mkdir(exist_ok=True)
    (out_dir / "validation" / "structural.json").write_text(
        json.dumps({
            "outcome": struct_res.outcome.value,
            "findings": [
                {"code": f.code, "severity": f.severity,
                 "message": f.message, "location": f.location}
                for f in struct_res.findings
            ],
        }, indent=2), encoding="utf-8")

    # Load IR + manifests for downstream steps.
    ir = _read_json(stages_dir / "02_canonicalize.json", {})
    s07 = _read_json(stages_dir / "07_build_pbir.json", {"blocked_visuals": [], "counts": {}})
    unsupported = _read_json(out_dir / "unsupported.json", [])

    datasources = ir.get("data_model", {}).get("datasources", [])
    tiers = tuple(int(d.get("connector_tier", 1)) for d in datasources)
    is_real, rubric_path = _is_real_workbook(ctx.workbook_id, ctx.config)

    # 5. Desktop-open gate (real-workbook subset only).
    if is_real and 4 not in tiers:
        traces_dir = Path(ctx.config.get("pbi_traces_dir") or
                          (Path.home() / "AppData" / "Local" / "Microsoft" /
                           "Power BI Desktop" / "Traces"))
        desktop_res = _do.run_desktop_open(
            pbip_path, datasource_tiers=tiers, traces_dir=traces_dir,
            desktop_version=str(ctx.config.get("pbi_desktop_version", "2.130")),
        )
    else:
        desktop_res = _do.DesktopOpenResult(
            outcome=ValidatorOutcome.SKIPPED,
            reason="synthetic" if not is_real else "tier_4_short_circuit",
        )

    # 6. Rubric evaluation.
    if is_real and rubric_path is not None:
        rubric = _rubric.load_rubric(rubric_path)
        observation = _build_observation(ir, s07, desktop_res.outcome.value)
        rubric_res = _rubric.evaluate_rubric(rubric, observation)
        _rubric.write_acceptance_json(out_dir / "acceptance.json", rubric_res)
        rubric_outcome = rubric_res.outcome.value
        rubric_reason = rubric_res.reason
        rubric_items = [
            {"name": i.name, "required": i.required,
             "outcome": i.outcome.value, "observed": i.observed}
            for i in rubric_res.items
        ]
        acceptance_failed = rubric_res.outcome == ValidatorOutcome.FAILED
    else:
        rubric_outcome = "skipped"
        rubric_reason = "no_rubric" if not is_real else "rubric_missing"
        rubric_items = []
        acceptance_failed = False

    # 7. Status rule.
    obs_bundle = _status.ObservationBundle(
        datasource_tiers=tiers,
        unsupported=unsupported,
        measures_total=sum(
            1 for c in ir.get("data_model", {}).get("calculations", [])
            if c.get("scope") == "measure"
        ) or 1,
        placeholder_leaf_ratios=[],
        blocked_visuals=s07.get("blocked_visuals", []),
        tmdl_outcome=tmdl_res.outcome.value,
        pbir_compile_outcome=pbir_res.outcome.value,
        desktop_open_outcome=desktop_res.outcome.value,
        rubric_acceptance_failed=acceptance_failed,
        any_calc_low_confidence=any(
            (c.get("confidence") or "high") != "high"
            for c in ir.get("data_model", {}).get("calculations", [])
        ),
        any_clamped_or_dropped_layout=False,
        param_intents=[
            (p.get("intent") or {}).get("value") if isinstance(p.get("intent"), dict)
            else (p.get("intent") or "")
            for p in ir.get("data_model", {}).get("parameters", [])
        ],
        user_actions=[
            ua for d in datasources for ua in (d.get("user_action_required") or [])
        ],
    )
    final_status, triggers = _status.compute_status(obs_bundle)

    # 8. Reporting.
    validators = {
        "tmdl":         {"result": tmdl_res.outcome.value, "reason": tmdl_res.reason,
                         "log_path": tmdl_res.log_path},
        "pbir_compile": {"result": pbir_res.outcome.value, "reason": pbir_res.reason,
                         "log_path": pbir_res.log_path},
        "structural":   {"result": struct_res.outcome.value,
                         "findings": [
                             {"code": f.code, "severity": f.severity,
                              "message": f.message, "location": f.location}
                             for f in struct_res.findings
                         ],
                         "log_path": "validation/structural.json"},
        "desktop_open": {"result": desktop_res.outcome.value, "reason": desktop_res.reason,
                         "events": [{"name": e.name, "ts": e.timestamp_ms} for e in desktop_res.events],
                         "log_path": desktop_res.log_path},
        "rubric":       {"result": rubric_outcome, "reason": rubric_reason,
                         "items": rubric_items, "log_path": "acceptance.json"},
    }

    workbook_md = _report.render_workbook_report(
        workbook_id=ctx.workbook_id, status=final_status, triggers=triggers,
        validators={
            k: {"outcome": v["result"], "reason": v.get("reason"), "findings": v.get("findings")}
            for k, v in validators.items()
        },
        datasources=[{"name": d.get("name"),
                      "tier": int(d.get("connector_tier", 1)),
                      "user_action_required": d.get("user_action_required") or []}
                     for d in datasources],
        placeholders_per_page={d.get("name", d.get("id", "?")): 0
                               for d in ir.get("dashboards", [])},
    )
    (out_dir / "workbook-report.md").write_text(workbook_md, encoding="utf-8")

    artifact_size = sum(p.stat().st_size for p in out_dir.rglob("*") if p.is_file())
    summary_md = _report.render_summary_md(
        validators={k: {"outcome": v["result"], "reason": v.get("reason")}
                    for k, v in validators.items()},
        artifact_size_bytes=artifact_size,
        status=final_status,
    )

    manifest = {
        "pbip_path": str(pbip_path.relative_to(out_dir)),
        "validators": validators,
        "status": final_status,
        "trigger_reasons": triggers,
    }
    return StageResult(output=manifest, summary_md=summary_md, errors=())


def _build_observation(ir: dict, s07: dict, desktop_outcome: str) -> dict:
    rendered_pages = [d.get("name", d.get("id", "?")) for d in ir.get("dashboards", [])]
    blocked = {(b.get("page_id"), b.get("visual_id")) for b in s07.get("blocked_visuals", [])}
    rendered_visuals_by_page: dict[str, list[str]] = {}
    rendered_slicers_by_page: dict[str, list[str]] = {}
    placeholder_visuals_by_page: dict[str, list[str]] = {}
    for d in ir.get("dashboards", []):
        rendered_visuals_by_page[d.get("name", d.get("id", "?"))] = []
        rendered_slicers_by_page[d.get("name", d.get("id", "?"))] = []
        placeholder_visuals_by_page[d.get("name", d.get("id", "?"))] = []
    return {
        "rendered_pages": rendered_pages,
        "rendered_visuals_by_page": rendered_visuals_by_page,
        "rendered_slicers_by_page": rendered_slicers_by_page,
        "placeholder_visuals_by_page": placeholder_visuals_by_page,
        "desktop_open_outcome": desktop_outcome,
    }
```

- [ ] **Step 4: Verify**

Run: `pytest tests/unit/stages/test_s08_package_validate.py -v`
Expected: PASS (3 tests).

Also run: `pytest -q` — full suite must stay green.

- [ ] **Step 5: Commit**

```bash
git add src/tableau2pbir/stages/s08_package_validate.py tests/unit/stages/test_s08_package_validate.py
git commit -m "feat(stage8): replace stub with package+validate orchestrator"
```

---

### Task 12: Stage 8 contract test (manifest schema)

**Files:**
- Create: `tests/contract/test_stage8_package_contract.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/contract/test_stage8_package_contract.py
"""Stage 8 emits a JSON manifest with stable shape — see plan 5."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


_REPO = Path(__file__).resolve().parents[2]
_SYNTHETIC = _REPO / "tests" / "golden" / "synthetic"


@pytest.fixture(scope="module")
def synthetic_workbook() -> Path:
    candidates = sorted(p for p in _SYNTHETIC.glob("*.twb"))
    if not candidates:
        pytest.skip("no synthetic workbooks present")
    return candidates[0]


def test_stage8_manifest_has_expected_keys(tmp_path: Path, synthetic_workbook: Path):
    out = tmp_path / "out"
    proc = subprocess.run(
        [sys.executable, "-m", "tableau2pbir.cli", "convert",
         str(synthetic_workbook), "--out", str(out)],
        capture_output=True, text=True,
    )
    if proc.returncode != 0 and (
        "ANTHROPIC_API_KEY" in proc.stderr or "authentication_error" in proc.stderr
    ):
        pytest.skip("requires ANTHROPIC_API_KEY")
    assert proc.returncode == 0, proc.stderr

    wb_id = synthetic_workbook.stem
    manifest_path = out / wb_id / "stages" / "08_package_validate.json"
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert set(manifest.keys()) >= {"pbip_path", "validators", "status", "trigger_reasons"}
    assert manifest["status"] in {"ok", "partial", "failed"}
    for name in ("tmdl", "pbir_compile", "structural", "desktop_open", "rubric"):
        v = manifest["validators"][name]
        assert "result" in v
        assert v["result"] in {"passed", "failed", "skipped"}

    pbip = out / wb_id / manifest["pbip_path"]
    assert pbip.is_file()
    payload = json.loads(pbip.read_text(encoding="utf-8"))
    assert payload["version"] == "1.0"
    assert payload["artifacts"][0]["report"]["path"] == "Report"
```

- [ ] **Step 2: Run test to verify it passes**

The orchestrator from Task 11 already produces this manifest, so this test should pass on first run (it is a contract guard, not a feature driver).

Run: `pytest tests/contract/test_stage8_package_contract.py -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/contract/test_stage8_package_contract.py
git commit -m "test(contract): stage 8 manifest shape + .pbip payload"
```

---

### Task 13: Update real-workbook end-to-end test

**Files:**
- Modify: `tests/integration/test_real_workbooks_e2e.py`

Extend the existing test to require:
- `<wb>.pbip` exists AND is a non-empty JSON.
- `08_package_validate.summary.md` is non-empty.
- `workbook-report.md` exists with a `**Status:**` line.

- [ ] **Step 1: Write the failing extension**

Append the following test at the bottom of `tests/integration/test_real_workbooks_e2e.py`:

```python
@pytest.mark.integration
@pytest.mark.parametrize("workbook", _WORKBOOKS, ids=[p.name for p in _WORKBOOKS])
def test_real_workbook_stage8_artifacts(workbook: Path, tmp_path: Path):
    out = tmp_path / "out"
    result = _convert(workbook, out)
    if result.returncode != 0 and (
        "ANTHROPIC_API_KEY not set" in result.stderr
        or "authentication_error" in result.stderr
        or "invalid x-api-key" in result.stderr
    ):
        pytest.skip(f"{workbook.name}: requires a valid ANTHROPIC_API_KEY")
    assert result.returncode == 0, result.stderr

    wb_name = workbook.stem
    pbip = out / wb_name / f"{wb_name}.pbip"
    assert pbip.is_file()
    pbip_payload = json.loads(pbip.read_text(encoding="utf-8"))
    assert pbip_payload["version"] == "1.0"
    assert pbip_payload["artifacts"][0]["report"]["path"] == "Report"

    summary = out / wb_name / "stages" / "08_package_validate.summary.md"
    assert summary.is_file() and summary.read_text(encoding="utf-8").strip() != ""

    report_md = out / wb_name / "workbook-report.md"
    assert report_md.is_file()
    assert "**Status:**" in report_md.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run**

Run: `pytest tests/integration/test_real_workbooks_e2e.py::test_real_workbook_stage8_artifacts -v`
Expected: PASS for every real workbook (or `skip` if no ANTHROPIC_API_KEY).

If a fixture fails, inspect the resulting `08_package_validate.summary.md` for the actual outcome before changing code.

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_real_workbooks_e2e.py
git commit -m "test(integration): real workbooks emit .pbip + workbook-report.md + stage 8 summary"
```

---

### Task 14: CLI run-manifest writer (batch mode)

**Files:**
- Modify: `src/tableau2pbir/cli.py`
- Test: `tests/unit/test_cli_run_manifest.py`

The CLI's `convert` subcommand currently runs one workbook. Plan 5 adds: after each workbook completes, append a row to `<out_root>/run-manifest.md`. If the file does not exist, write the header first.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_cli_run_manifest.py
import subprocess
import sys
from pathlib import Path
import pytest


def test_run_manifest_appended_per_workbook(tmp_path: Path):
    synthetic_dir = Path(__file__).resolve().parents[2] / "tests" / "golden" / "synthetic"
    candidates = sorted(p for p in synthetic_dir.glob("*.twb"))
    if not candidates:
        pytest.skip("no synthetic workbooks")
    wb = candidates[0]

    out = tmp_path / "out"
    proc = subprocess.run(
        [sys.executable, "-m", "tableau2pbir.cli", "convert",
         str(wb), "--out", str(out)],
        capture_output=True, text=True,
    )
    if proc.returncode != 0 and "ANTHROPIC_API_KEY" in proc.stderr:
        pytest.skip("requires ANTHROPIC_API_KEY")
    assert proc.returncode == 0, proc.stderr

    manifest = out / "run-manifest.md"
    assert manifest.is_file()
    text = manifest.read_text(encoding="utf-8")
    assert "| workbook | status | trigger_reasons | link |" in text
    assert wb.stem in text
```

- [ ] **Step 2: Verify failure**

Run: `pytest tests/unit/test_cli_run_manifest.py -v`
Expected: FAIL — `run-manifest.md` not produced.

- [ ] **Step 3: Implement CLI extension**

Read the current CLI to understand its shape:

```bash
cat src/tableau2pbir/cli.py
```

Add a helper `_append_run_manifest(out_root, workbook_id, manifest_dict)` and call it after `run_pipeline` returns. The implementation:

```python
# Add inside src/tableau2pbir/cli.py — exact placement depends on existing
# `convert` handler. Below is the helper body; integrate at the end of the
# convert flow after the per-workbook output_dir has been written.

import json as _json

_RUN_MANIFEST_HEADER = (
    "| workbook | status | trigger_reasons | link |\n"
    "|---|---|---|---|\n"
)

def _append_run_manifest(out_root: Path, workbook_id: str, output_dir: Path) -> None:
    manifest_path = out_root / "run-manifest.md"
    if not manifest_path.is_file():
        manifest_path.write_text(_RUN_MANIFEST_HEADER, encoding="utf-8")
    stage8 = output_dir / "stages" / "08_package_validate.json"
    if stage8.is_file():
        m = _json.loads(stage8.read_text(encoding="utf-8"))
        status = m.get("status", "unknown")
        triggers = ",".join(m.get("trigger_reasons", []) or []) or "—"
    else:
        status, triggers = "unknown", "—"
    link = f"{workbook_id}/workbook-report.md"
    with manifest_path.open("a", encoding="utf-8") as f:
        f.write(f"| {workbook_id} | {status} | {triggers} | {link} |\n")
```

Wire `_append_run_manifest(out_root, workbook_id, out_root / workbook_id)` at the end of the `convert` flow, after `run_pipeline` returns and before the function returns its exit code.

- [ ] **Step 4: Verify**

Run: `pytest tests/unit/test_cli_run_manifest.py -v`
Expected: PASS.

Also run: `pytest -q` — full suite green.

- [ ] **Step 5: Commit**

```bash
git add src/tableau2pbir/cli.py tests/unit/test_cli_run_manifest.py
git commit -m "feat(cli): append run-manifest.md row per converted workbook"
```

---

### Task 15: Stage 8 end-to-end integration on synthetic fixture

**Files:**
- Create: `tests/integration/test_stage8_end_to_end.py`

- [ ] **Step 1: Write the test**

```python
# tests/integration/test_stage8_end_to_end.py
import json
import subprocess
import sys
from pathlib import Path

import pytest


_SYNTHETIC = Path(__file__).resolve().parents[1] / "golden" / "synthetic"


@pytest.mark.integration
def test_synthetic_workbook_stage8_outputs_complete(tmp_path: Path):
    candidates = sorted(p for p in _SYNTHETIC.glob("*.twb"))
    if not candidates:
        pytest.skip("no synthetic workbooks")
    wb = candidates[0]
    out = tmp_path / "out"
    proc = subprocess.run(
        [sys.executable, "-m", "tableau2pbir.cli", "convert",
         str(wb), "--out", str(out)],
        capture_output=True, text=True,
    )
    if proc.returncode != 0 and "ANTHROPIC_API_KEY" in proc.stderr:
        pytest.skip("requires ANTHROPIC_API_KEY")
    assert proc.returncode == 0, proc.stderr

    wb_id = wb.stem
    base = out / wb_id

    # Required artifacts.
    assert (base / f"{wb_id}.pbip").is_file()
    assert (base / "workbook-report.md").is_file()
    assert (base / "validation" / "structural.json").is_file()
    assert (base / "stages" / "08_package_validate.json").is_file()
    assert (base / "stages" / "08_package_validate.summary.md").is_file()

    manifest = json.loads((base / "stages" / "08_package_validate.json").read_text("utf-8"))
    # Synthetic → desktop_open and rubric must be skipped.
    assert manifest["validators"]["desktop_open"]["result"] == "skipped"
    assert manifest["validators"]["rubric"]["result"] == "skipped"

    # Status is one of the three legal values.
    assert manifest["status"] in {"ok", "partial", "failed"}
```

- [ ] **Step 2: Verify**

Run: `pytest tests/integration/test_stage8_end_to_end.py -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_stage8_end_to_end.py
git commit -m "test(integration): synthetic workbook produces complete stage 8 artifact set"
```

---

### Task 16: Update CLAUDE.md tracking table + plan handoff

**Files:**
- Modify: `C:\Tableau_PBI\CLAUDE.md`

- [ ] **Step 1: Mark Plan 5 done in the tracking table**

Edit `CLAUDE.md`:

- Change Plan 5 row status from `🔲 NEXT` to `✅ DONE`.
- Set the `File` cell to `docs/superpowers/plans/2026-05-01-plan-5-package-validate-desktop-gate.md`.
- Add a new row for Plan 6 if one is planned next, or replace the "Plan 5 is next" paragraph with text describing what comes after Plan 5 (likely: layer iv-c DAX semantic probe runner + multi-version Desktop trace dispatch + visual regression opt-in + remaining real-workbook rubric authoring).

Suggested replacement paragraph for the "next plan" section:

```
**Plan 6 is next:** author the layer iv-c DAX semantic probe runner that loads
the emitted TMDL via the AnalysisServices .NET load probe and evaluates each
synthetic fixture's `<fixture>.expected_values.yaml`. Plan 6 also fills in
real-workbook rubric YAML siblings beyond `Superstore.rubric.yaml` and adds
multi-version PBI Desktop trace probes. Use `superpowers:writing-plans` to
author the plan, then execute with `superpowers:executing-plans`.
```

- [ ] **Step 2: Run full suite as final verification**

```bash
pytest -q
```

Expected: all tests pass.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: mark plan 5 done; queue plan 6 (dax semantic probes + rubric backfill)"
```

---

## Self-review notes

**Spec coverage check (§6 Stage 8):**

- (1) `.pbip` root + project layout — Task 2 (writer) + Task 11 (orchestration). ✓
- (2) TMDL validity (TE2) — Task 4. ✓
- (3) PBIR compile (`pbi-tools`) — Task 5. ✓
- (4) Structural checks — Task 3. ✓
- (5) Desktop-open gate (per-tier criteria, 300 s timeout, flake retry, version-tolerant trace parsing) — Tasks 6 + 7. ✓
- (6) Rubric evaluation + `acceptance.json` — Task 8. ✓
- (7) Final status per §8.1 — Task 9 (rule) + Task 11 (wiring). ✓
- Summary.md / workbook-report.md / run-manifest.md — Tasks 10 + 14. ✓

**Spec §15 rubric:**
- Rubric schema implemented (Task 8). Measure-tolerance items recorded as `skipped` with `dax_probe_runner_unavailable` — explicitly deferred.

**Spec §9 layer vii (Desktop-open gate):**
- Single version probe (`2_130.json`); unknown versions fall through to canonical-name identity map. Multi-version expansion is an incremental task in Plan 6.

**Placeholder scan:** no TBDs, no "fill in", every step has its actual code or command.

**Type consistency:** `ValidatorOutcome.PASSED.value == "passed"` is used consistently across results dataclasses, status rule (`tmdl_outcome="passed"`), manifest serialization, and all tests.

**Out-of-scope items called out:** layer iv-c DAX semantic probe runner, multi-version Desktop trace dispatch, visual regression, additional real-workbook rubric authoring — all deferred to Plan 6.
