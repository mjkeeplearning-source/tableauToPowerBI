# Plan 3 — Stage 3 (translate calcs) + Stage 4 (map visuals)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Plan-1 no-op stubs for stages 3 and 4 with v1-scope implementations. End state: `tableau2pbir convert tests/golden/synthetic/<v1-fixture>.twb --out ./out/` produces `03_translate_calcs.json` (every v1 `Calculation` has `dax_expr` populated, or is in `unsupported[]`) and `04_map_visuals.json` (every `Sheet` has a `pbir_visual` annotation, or its mark is in `unsupported[]`). The Anthropic-SDK-backed `LLMClient.translate_calc` and `LLMClient.map_visual` work in three modes: cache-hit (zero network), snapshot-replay (`PYTEST_SNAPSHOT=replay`, zero network), and live (calls Anthropic, writes cache). Stages 5–8 still run as no-op stubs. The full pytest suite stays green.

**Architecture:** Stage 3 walks `Workbook.data_model.calculations` in two topo-sort lanes — **global** (`row` / `aggregate` / `lod_fixed` / named `table_calc` calcs) and **per-sheet** (`lod_include` / `lod_exclude` / anonymous quick-table-calc records) — and dispatches each calc to a Python rule keyed on `kind × frame/phase`. Rules emit DAX directly. On rule miss the calc is sent to `LLMClient.translate_calc` (Anthropic tool-use, structured-output schema `{dax_expr, confidence, notes}`, content-hash on-disk cache). Every DAX string is gated by a syntax parser (sqlglot tsql); parse failure routes the calc to `unsupported[]` with code `calc_dax_syntax_failed`. Parameter references (`[ParamName]`) are rewritten per `Parameter.intent`. v1 scope means *only* `row` / `aggregate` / `lod_fixed` are translated by Plan 3; `table_calc` / `lod_include` / `lod_exclude` / quick-table-calcs are already pre-routed to `unsupported[]` by Plan 2's `_deferred_routing`, so Stage 3 skips them transparently. The (calc × sheet) lane structure is implemented but empty in v1 — it activates in v1.1 behind `--with-lod-relative` / `--with-table-calcs`.

Stage 4 walks `Workbook.sheets` and dispatches each on `(mark_type, shelf_signature)` to a Python row in the visual-catalog dispatch table. The dispatch returns a `PbirVisual { visual_type, encoding_bindings[], format }` annotation that is attached to the sheet (new IR field). On miss / ambiguity the sheet is sent to `LLMClient.map_visual` (Anthropic tool-use; `visual_type` constrained to the PBIR catalog enum so the model cannot invent a visual). A validator confirms every binding's source field exists in IR and every target slot exists for the chosen visual; failures route the sheet to `unsupported[]` with code `visual_binding_invalid`. v1 visual catalog covers bar, line, area, scatter, text-table (matrix), pie, filled map.

**Tech stack:** Python 3.11+, pydantic v2 (existing IR + new `Sheet.pbir_visual` field — IR schema bumps `1.0.0 → 1.1.0`, optional-field minor bump per §5.4), anthropic SDK ≥ 0.34 (already pinned), sqlglot (NEW runtime dep — for the DAX syntax gate via `sqlglot.parse_one(..., dialect='tsql')`), stdlib `hashlib`, `json`, `os`. No new dev dependencies.

**Spec reference:** `C:\Tableau_PBI\docs\superpowers\specs\2026-04-23-tableau-to-pbir-design.md`. Primary sections: §5.4 (IR versioning), §5.6 (Calculation), §5.7 (Parameter intent), §6 Stage 3 (translate calcs), §6 Stage 4 (map visuals), §7 (LLM call sites), §9 layer iv-c (DAX semantic probes — *out of scope for Plan 3 except for fixture authoring*), §16 (v1 scope), §A.3 (prompt organization), §A.4-2 (syntax-gate naming).

**Plan-1 + Plan-2 outputs this plan builds on (do NOT re-create or restructure):**
- `src/tableau2pbir/ir/calculation.py` — `Calculation` model with `kind`, `phase`, `table_calc`, `lod_fixed`, `lod_relative`, `dax_expr`. v1 calcs already have non-null `kind` + `phase` after Plan 2.
- `src/tableau2pbir/ir/sheet.py` — `Sheet` with `mark_type`, `encoding`, `filters`. **This plan ADDS `pbir_visual` field** (optional, default `None`).
- `src/tableau2pbir/ir/parameter.py` — `Parameter.intent` already populated by Plan 2.
- `src/tableau2pbir/ir/version.py` — `IR_SCHEMA_VERSION = "1.0.0"`. **This plan bumps to `"1.1.0"`** (additive Sheet.pbir_visual field).
- `src/tableau2pbir/llm/client.py` — `LLMClient` with cache + prompt packs wired; `translate_calc` and `map_visual` raise `NotImplementedError`. **This plan implements both.**
- `src/tableau2pbir/llm/prompts/translate_calc/` and `.../map_visual/` — `system.md`, `tool_schema.json`, `VERSION` already present from Plan 1. **This plan keeps tool_schema.json bytes-identical** (so cache keys remain stable) but bumps `VERSION` from whatever it is to `0.2.0` and rewrites `system.md` with v1-scope guidance.
- `src/tableau2pbir/llm/snapshots.py` — `SnapshotStore`, `is_replay_mode()`. Used by AI fallback.
- `src/tableau2pbir/llm/cache.py` — `OnDiskCache`, `make_cache_key`. Used by AI fallback.
- `src/tableau2pbir/stages/_deferred_routing.py` — already routes `table_calc` / `lod_include` / `lod_exclude` / quick-table-calcs to `unsupported[]`.
- `src/tableau2pbir/stages/_calc_graph.py` — `detect_cycles`. **This plan ADDS** `topo_sort_global_lane` + `topo_sort_per_sheet_lane` next to it.
- `tests/golden/synthetic/calc_row.twb`, `calc_aggregate.twb`, `calc_lod_fixed.twb` — already authored; Plan 3 reuses them and adds DAX golden expectations.

**Out of scope for Plan 3 (deferred to Plans 4–5 or v1.1+):**
- Stages 5–8 stay as no-op stubs.
- §9 layer iv-c (`tests/validity/dax_semantic/`) AnalysisServices DAX semantic probes — placeholder fixtures may be authored if convenient but the runner ships in Plan 5.
- `--with-lod-relative` / `--with-table-calcs` / `--with-format-switch` execution paths — flag plumbing stays unimplemented; per-sheet lane stays empty in v1.
- Real-workbook calc translation — the rubric runner ships in Plan 5.
- `LLMClient.cleanup_name` — still raises `NotImplementedError` (no live caller before Plan 4 stage 6).
- TMDL `<calc>__<sheet>` measure naming logic — that is a stage-6 concern; Plan 3 just records `owner_sheet_id` in the per-sheet lane (no v1 emissions).

**v1 detection-vs-execution rule (continued from Plan 2 §16):** Plan 2 already classified deferred calcs and routed them to `unsupported[]` with `code = "deferred_feature_*"`. Plan 3 honors that contract: any calc whose id is referenced by an `UnsupportedItem` with `code` starting `deferred_feature_` is **skipped** by stage 3 (its `dax_expr` stays `None`). The skip is silent — it is not a stage-3 error. Stage 6 (Plan 4) will treat `dax_expr is None` calcs as "do not emit a measure".

---

## File structure (Plan 3)

**Create (new files):**

```
C:\Tableau_PBI\
├── src/tableau2pbir/
│   ├── translate/
│   │   ├── __init__.py
│   │   ├── topo.py                         # global + per-sheet topo lanes
│   │   ├── parameters.py                   # [ParamName] rewriter, intent-aware
│   │   ├── syntax_gate.py                  # sqlglot DAX parse gate
│   │   ├── ai_fallback.py                  # LLMClient.translate_calc orchestration
│   │   ├── summary.py                      # stage 3 summary.md renderer
│   │   └── rules/
│   │       ├── __init__.py
│   │       ├── dispatch.py                 # kind × phase → rule registry
│   │       ├── row.py                      # arithmetic, string, date row calcs
│   │       ├── aggregate.py                # SUM/AVG/COUNT/MIN/MAX + conditional
│   │       └── lod_fixed.py                # CALCULATE+REMOVEFILTERS+KEEPFILTERS
│   └── visualmap/
│       ├── __init__.py
│       ├── catalog.py                      # PBIR visual enum + slot definitions
│       ├── dispatch.py                     # (mark_type, shelf_signature) → visual+bindings
│       ├── validator.py                    # every binding source/slot exists check
│       ├── ai_fallback.py                  # LLMClient.map_visual orchestration
│       └── summary.py                      # stage 4 summary.md renderer
├── tests/
│   ├── unit/
│   │   ├── translate/
│   │   │   ├── __init__.py
│   │   │   ├── test_topo.py
│   │   │   ├── test_parameters.py
│   │   │   ├── test_syntax_gate.py
│   │   │   ├── test_ai_fallback.py
│   │   │   └── rules/
│   │   │       ├── __init__.py
│   │   │       ├── test_dispatch.py
│   │   │       ├── test_row.py
│   │   │       ├── test_aggregate.py
│   │   │       └── test_lod_fixed.py
│   │   ├── visualmap/
│   │   │   ├── __init__.py
│   │   │   ├── test_catalog.py
│   │   │   ├── test_dispatch.py
│   │   │   ├── test_validator.py
│   │   │   └── test_ai_fallback.py
│   │   ├── llm/
│   │   │   ├── __init__.py
│   │   │   └── test_client.py              # cache hit, snapshot replay, validator drop
│   │   └── stages/
│   │       ├── test_s03_translate_calcs.py
│   │       └── test_s04_map_visuals.py
│   ├── contract/
│   │   ├── test_stage3_calcs_contract.py
│   │   └── test_stage4_visual_contract.py
│   ├── integration/
│   │   └── test_stage3_stage4_integration.py
│   ├── llm_snapshots/
│   │   ├── translate_calc/
│   │   │   ├── ai_only_compose.json        # one fixture forces AI fallback
│   │   │   └── ai_only_aggregate_conditional.json
│   │   └── map_visual/
│   │       └── ai_only_combo_chart.json
│   └── golden/synthetic/
│       └── visual_marks_v1.twb             # NEW — one sheet per v1 mark type
└── schemas/
    └── ir-v1.1.0.schema.json               # autogenerated; commits with the IR bump
```

**Modify:**
- `src/tableau2pbir/ir/sheet.py` — add `PbirVisual`, `EncodingBinding`; add `Sheet.pbir_visual: PbirVisual | None = None`.
- `src/tableau2pbir/ir/version.py` — `IR_SCHEMA_VERSION = "1.1.0"`.
- `src/tableau2pbir/llm/client.py` — implement `translate_calc` + `map_visual`.
- `src/tableau2pbir/llm/prompts/translate_calc/system.md` — rewrite; bump `VERSION` to `0.2.0`.
- `src/tableau2pbir/llm/prompts/map_visual/system.md` — rewrite; bump `VERSION` to `0.2.0`.
- `src/tableau2pbir/stages/_calc_graph.py` — append `topo_sort_global_lane`, `topo_sort_per_sheet_lane`.
- `src/tableau2pbir/stages/s03_translate_calcs.py` — replace stub.
- `src/tableau2pbir/stages/s04_map_visuals.py` — replace stub.
- `pyproject.toml` — add `sqlglot>=23,<27` to runtime dependencies.
- `Makefile` — `schema:` target retargets `schemas/ir-v1.1.0.schema.json`; remove the old `ir-v1.0.0.schema.json` artifact (replaced).
- `tests/contract/test_ir_schema.py` — pin to `1.1.0` schema path.
- `tests/integration/test_stage1_stage2_integration.py` — `IR_SCHEMA_VERSION` import is already version-agnostic; no change expected.

**Do NOT touch:**
- Anything under `src/tableau2pbir/extract/`, `src/tableau2pbir/classify/`, `src/tableau2pbir/util/`.
- `src/tableau2pbir/stages/s01_extract.py`, `s02_canonicalize.py`, `s05_*.py`–`s08_*.py`.
- `src/tableau2pbir/llm/cache.py`, `prompt_loader.py`, `snapshots.py` (already fit-for-purpose).
- `src/tableau2pbir/llm/prompts/cleanup_name/*` (no live caller in Plan 3).
- `src/tableau2pbir/llm/prompts/*/tool_schema.json` (changing bytes invalidates every cached AI call from prior runs — keep stable).

---

## Pre-Task: verify Plan-1 + Plan-2 green baseline

```bash
cd C:/Tableau_PBI
source .venv/Scripts/activate
pytest -q
make lint
make typecheck
make schema
git diff --stat schemas/
```

Expected: pytest green, lint clean, typecheck clean on `src/`, `schemas/` diff empty. If anything is red, fix before starting Plan 3.

Also confirm prerequisite IR state: `python -c "from tableau2pbir.ir.version import IR_SCHEMA_VERSION; print(IR_SCHEMA_VERSION)"` → `1.0.0`.

---

## Task 1: bump IR — add `Sheet.pbir_visual` and bump schema version

**Files:**
- Modify: `src/tableau2pbir/ir/sheet.py`
- Modify: `src/tableau2pbir/ir/version.py`
- Modify: `Makefile` (`schema:` target output path)
- Create: `schemas/ir-v1.1.0.schema.json` (autogenerated)
- Delete: `schemas/ir-v1.0.0.schema.json` (replaced)
- Modify: `tests/contract/test_ir_schema.py`

- [x] **Step 1.1: Write the failing test**

Append to `tests/contract/test_ir_schema.py` (or replace its single existing test, depending on Plan-1 contents — `cat tests/contract/test_ir_schema.py` first to see):

```python
# At top of file or near existing imports
from tableau2pbir.ir.sheet import EncodingBinding, PbirVisual, Sheet
from tableau2pbir.ir.version import IR_SCHEMA_VERSION


def test_ir_schema_version_is_1_1_0():
    assert IR_SCHEMA_VERSION == "1.1.0"


def test_sheet_pbir_visual_default_is_none():
    s = Sheet(
        id="s1", name="Sales", datasource_refs=("ds1",),
        mark_type="bar", encoding={"rows": (), "columns": ()},
        filters=(), sort=(), dual_axis=False,
        reference_lines=(), uses_calculations=(),
    )
    assert s.pbir_visual is None


def test_pbir_visual_round_trip():
    binding = EncodingBinding(channel="value", source_field_id="t1__col__amount")
    pv = PbirVisual(
        visual_type="clusteredBarChart",
        encoding_bindings=(binding,),
        format={"title": "Sales"},
    )
    assert pv.visual_type == "clusteredBarChart"
    assert pv.encoding_bindings[0].channel == "value"
    assert pv.format["title"] == "Sales"
```

- [x] **Step 1.2: Run test — verify failure**

```bash
pytest tests/contract/test_ir_schema.py -v
```
Expected: FAIL — `cannot import name 'EncodingBinding'` and the version assertion fails (still `1.0.0`).

- [x] **Step 1.3: Edit `src/tableau2pbir/ir/sheet.py` — add the new types**

Append to the bottom of `sheet.py`:

```python
class EncodingBinding(IRBase):
    """One channel→field binding in a PBIR visual."""
    channel: str                            # "value" | "category" | "series" | "details" | ...
    source_field_id: str                    # IR column id OR calculation id


class PbirVisual(IRBase):
    """Stage 4 annotation attached to a Sheet. See spec §6 Stage 4 output."""
    visual_type: str                        # constrained to visualmap.catalog.VISUAL_TYPES at validate time
    encoding_bindings: tuple[EncodingBinding, ...]
    format: dict[str, str] = {}
```

Then modify the `Sheet` class to add the optional field:

```python
class Sheet(IRBase):
    id: str
    name: str
    datasource_refs: tuple[str, ...]
    mark_type: str
    encoding: Encoding
    filters: tuple[Filter, ...]
    sort: tuple[SortSpec, ...]
    dual_axis: bool
    reference_lines: tuple[ReferenceLine, ...]
    format: dict[str, str] | None = None
    uses_calculations: tuple[str, ...]
    pbir_visual: PbirVisual | None = None    # populated by stage 4
```

- [x] **Step 1.4: Edit `src/tableau2pbir/ir/version.py`**

```python
"""IR schema version (semver). Bump per §5.4."""
IR_SCHEMA_VERSION = "1.1.0"
```

- [x] **Step 1.5: Edit `Makefile` schema target**

Replace the `schema:` block:

```makefile
schema:
	python -m tableau2pbir.ir.schema > schemas/ir-v1.1.0.schema.json
```

- [x] **Step 1.6: Regenerate schema and remove old artifact**

```bash
make schema
git rm schemas/ir-v1.0.0.schema.json
```

Expected: `schemas/ir-v1.1.0.schema.json` exists; `git status` shows it as a new file plus the deletion of the 1.0.0 file.

- [x] **Step 1.7: Run test — verify pass**

```bash
pytest tests/contract/test_ir_schema.py -v
```
Expected: all 3 added tests pass; the rest of the file's existing tests still pass.

- [x] **Step 1.8: Run the full pytest baseline to catch IR-schema-pinned tests**

```bash
pytest -q
```
Expected: any test that hard-pinned to `1.0.0` fails — fix it to `IR_SCHEMA_VERSION` (the constant, not the literal). If a test path-pins `schemas/ir-v1.0.0.schema.json`, retarget to `1.1.0`. Do not commit until pytest is fully green.

- [x] **Step 1.9: Commit**

```bash
git add src/tableau2pbir/ir/sheet.py src/tableau2pbir/ir/version.py \
        Makefile schemas/ir-v1.1.0.schema.json schemas/ir-v1.0.0.schema.json \
        tests/contract/test_ir_schema.py
git commit -m "feat(ir): bump IR schema to 1.1.0; add Sheet.pbir_visual + EncodingBinding"
```

---

## Task 2: add `sqlglot` runtime dependency

**Files:**
- Modify: `pyproject.toml`

- [x] **Step 2.1: Edit `pyproject.toml` `dependencies` block**

Replace:

```toml
dependencies = [
  "anthropic>=0.34,<1.0",
  "pydantic>=2.5,<3.0",
  "lxml>=5.0",
  "tableaudocumentapi>=0.11",
  "PyYAML>=6.0",
]
```

with:

```toml
dependencies = [
  "anthropic>=0.34,<1.0",
  "pydantic>=2.5,<3.0",
  "lxml>=5.0",
  "tableaudocumentapi>=0.11",
  "PyYAML>=6.0",
  "sqlglot>=23,<27",
]
```

- [x] **Step 2.2: Reinstall in editable mode and verify import**

```bash
pip install -e ".[dev]"
python -c "import sqlglot; print(sqlglot.__version__)"
```
Expected: prints a 23.x–26.x version. Tableau-DocumentAPI dep stays.

- [x] **Step 2.3: Commit**

```bash
git add pyproject.toml
git commit -m "build: add sqlglot runtime dep for stage 3 DAX syntax gate"
```

---

## Task 3: `translate/syntax_gate.py` — DAX parse-only validator

**Files:**
- Create: `src/tableau2pbir/translate/__init__.py` (empty)
- Create: `src/tableau2pbir/translate/syntax_gate.py`
- Create: `tests/unit/translate/__init__.py` (empty)
- Create: `tests/unit/translate/test_syntax_gate.py`

- [x] **Step 3.1: Write the failing test**

`tests/unit/translate/test_syntax_gate.py`:

```python
"""Stage-3 DAX syntax gate. We use sqlglot's tsql dialect as a pragmatic
DAX parser — it accepts the SQL-Server-flavored function calls and bracketed
identifiers DAX shares with T-SQL. Goal is to catch unbalanced parens, bare
identifiers without context, etc.; not to fully validate DAX semantics."""
from __future__ import annotations

from tableau2pbir.translate.syntax_gate import is_valid_dax


def test_valid_simple_arithmetic():
    assert is_valid_dax("[Sales] + [Tax]") is True


def test_valid_calculate():
    assert is_valid_dax(
        "CALCULATE(SUM('Orders'[Amount]), REMOVEFILTERS('Orders'[Region]))"
    ) is True


def test_invalid_unbalanced_parens():
    assert is_valid_dax("CALCULATE(SUM('Orders'[Amount])") is False


def test_invalid_empty_string():
    assert is_valid_dax("") is False


def test_invalid_garbage():
    assert is_valid_dax("@@@##$$$ broken") is False
```

- [x] **Step 3.2: Run test — verify failure**

```bash
pytest tests/unit/translate/test_syntax_gate.py -v
```
Expected: `ModuleNotFoundError: No module named 'tableau2pbir.translate'`.

- [x] **Step 3.3: Write `src/tableau2pbir/translate/__init__.py`** as an empty file.

- [x] **Step 3.4: Write `src/tableau2pbir/translate/syntax_gate.py`** (deviation: added DAX→tsql qualified-ref normalizer because tsql rejects `'Table'[Column]`)

```python
"""DAX syntax gate — parse-only check using sqlglot's tsql dialect.

Per spec §6 Stage 3 + §A.4-2: this is the *syntax gate*, not a semantic
verifier. Semantic verification ships in §9 layer iv-c (Plan 5)."""
from __future__ import annotations

import sqlglot
from sqlglot.errors import ParseError


def is_valid_dax(expr: str) -> bool:
    """True iff `expr` parses cleanly under tsql dialect.

    DAX and T-SQL share enough surface syntax (bracketed names, function
    calls, infix operators) that parse failure is a reliable signal of a
    malformed expression. We do not interpret the AST — only that one exists."""
    if not expr or not expr.strip():
        return False
    try:
        sqlglot.parse_one(expr, dialect="tsql")
    except ParseError:
        return False
    except Exception:
        # sqlglot occasionally raises non-ParseError on pathological input.
        return False
    return True
```

- [x] **Step 3.5: Run test — verify pass**

```bash
pytest tests/unit/translate/test_syntax_gate.py -v
```
Expected: 5 passed.

- [x] **Step 3.6: Commit**

```bash
git add src/tableau2pbir/translate/__init__.py \
        src/tableau2pbir/translate/syntax_gate.py \
        tests/unit/translate/__init__.py \
        tests/unit/translate/test_syntax_gate.py
git commit -m "feat(translate): add sqlglot-backed DAX syntax gate"
```

---

## Task 4: `translate/parameters.py` — intent-aware `[Param]` rewriter

**Files:**
- Create: `src/tableau2pbir/translate/parameters.py`
- Create: `tests/unit/translate/test_parameters.py`

- [x] **Step 4.1: Write the failing test**

```python
"""[ParamName] rewriter — translates Tableau parameter references inside
calc bodies according to Parameter.intent (spec §5.7)."""
from __future__ import annotations

from tableau2pbir.ir.parameter import Parameter, ParameterIntent
from tableau2pbir.translate.parameters import rewrite_parameter_refs


def _param(name: str, intent: ParameterIntent, default: str = "0") -> Parameter:
    return Parameter(
        id=f"p_{name}", name=name, datatype="float",
        default=default, allowed_values=(),
        intent=intent, exposure="card",
    )


def test_numeric_what_if_resolves_to_selected_value():
    params = (_param("Threshold", ParameterIntent.NUMERIC_WHAT_IF, "10"),)
    assert rewrite_parameter_refs("[Threshold] * 2", params) == \
        "[Threshold SelectedValue] * 2"


def test_categorical_selector_resolves_to_selected_value():
    params = (_param("Region", ParameterIntent.CATEGORICAL_SELECTOR, "East"),)
    assert rewrite_parameter_refs("IF [Region] = \"East\" THEN 1 ELSE 0 END", params) == \
        "IF [Region SelectedValue] = \"East\" THEN 1 ELSE 0 END"


def test_internal_constant_inlines_default():
    params = (_param("TaxRate", ParameterIntent.INTERNAL_CONSTANT, "0.07"),)
    assert rewrite_parameter_refs("[Sales] * [TaxRate]", params) == \
        "[Sales] * 0.07"


def test_unknown_param_left_unchanged():
    assert rewrite_parameter_refs("[Sales] + [Unknown]", ()) == "[Sales] + [Unknown]"


def test_multiple_params_in_one_expr():
    params = (
        _param("Threshold", ParameterIntent.NUMERIC_WHAT_IF, "10"),
        _param("TaxRate", ParameterIntent.INTERNAL_CONSTANT, "0.07"),
    )
    out = rewrite_parameter_refs("[Sales] * [TaxRate] + [Threshold]", params)
    assert out == "[Sales] * 0.07 + [Threshold SelectedValue]"
```

- [x] **Step 4.2: Run test — verify failure**

```bash
pytest tests/unit/translate/test_parameters.py -v
```
Expected: ModuleNotFoundError on `tableau2pbir.translate.parameters`.

- [x] **Step 4.3: Write `src/tableau2pbir/translate/parameters.py`**

```python
"""Parameter reference rewriter — see spec §5.7 'Stage 3 calc translator'.

`numeric_what_if` / `categorical_selector` → `[<name> SelectedValue]` measure ref.
`internal_constant` → DAX-literal expansion of the default value.
`formatting_control` is v1-deferred; its parameters never reach stage 3
(stage 2 routes them to unsupported[]).
`unsupported` intent → leave the reference as-is and let the syntax gate
or downstream consumer flag it."""
from __future__ import annotations

import re

from tableau2pbir.ir.parameter import Parameter, ParameterIntent

_REF_RE = re.compile(r"\[(?P<name>[^\[\]]+)\]")


def rewrite_parameter_refs(
    tableau_expr: str, parameters: tuple[Parameter, ...],
) -> str:
    """Rewrite every `[ParamName]` token in `tableau_expr` per its intent.
    Tokens that don't match any known parameter are left untouched (they
    may reference fields, not parameters)."""
    by_name = {p.name: p for p in parameters}

    def _sub(match: re.Match[str]) -> str:
        name = match.group("name")
        param = by_name.get(name)
        if param is None:
            return match.group(0)
        if param.intent in (
            ParameterIntent.NUMERIC_WHAT_IF,
            ParameterIntent.CATEGORICAL_SELECTOR,
        ):
            return f"[{name} SelectedValue]"
        if param.intent is ParameterIntent.INTERNAL_CONSTANT:
            return param.default
        return match.group(0)

    return _REF_RE.sub(_sub, tableau_expr)
```

- [x] **Step 4.4: Run test — verify pass**

```bash
pytest tests/unit/translate/test_parameters.py -v
```
Expected: 5 passed.

- [x] **Step 4.5: Commit**

```bash
git add src/tableau2pbir/translate/parameters.py \
        tests/unit/translate/test_parameters.py
git commit -m "feat(translate): add intent-aware Tableau [Param] rewriter"
```

---

## Task 5: `translate/topo.py` — global + per-sheet topo lanes

**Files:**
- Create: `src/tableau2pbir/translate/topo.py`
- Create: `tests/unit/translate/test_topo.py`

- [x] **Step 5.1: Write the failing test**

```python
"""Stage 3 topological order — global lane (row, aggregate, lod_fixed,
named table_calc) and per-sheet lane (lod_include, lod_exclude, anonymous
quick-table-calc). Per spec §5.6 / §6 Stage 3."""
from __future__ import annotations

from tableau2pbir.ir.calculation import (
    Calculation, CalculationKind, CalculationPhase, LodFixed,
)
from tableau2pbir.ir.common import FieldRef
from tableau2pbir.translate.topo import partition_lanes, topo_sort


def _calc(
    cid: str, kind: CalculationKind, depends: tuple[str, ...] = (),
    *, owner_sheet_id: str | None = None,
) -> Calculation:
    return Calculation(
        id=cid, name=cid, scope="measure", tableau_expr="0",
        depends_on=depends, kind=kind, phase=CalculationPhase.AGGREGATE,
        lod_fixed=LodFixed(dimensions=(FieldRef(table_id="t", column_id="c"),))
            if kind is CalculationKind.LOD_FIXED else None,
        owner_sheet_id=owner_sheet_id,
    )


def test_partition_lanes_separates_global_from_per_sheet():
    a = _calc("a", CalculationKind.ROW)
    b = _calc("b", CalculationKind.AGGREGATE)
    c = _calc("c", CalculationKind.LOD_INCLUDE, owner_sheet_id="sheet1")
    d = _calc("d", CalculationKind.TABLE_CALC, owner_sheet_id="sheet2")
    global_lane, per_sheet_lane = partition_lanes((a, b, c, d))
    assert {x.id for x in global_lane} == {"a", "b"}
    assert {x.id for x in per_sheet_lane} == {"c", "d"}


def test_topo_sort_respects_depends_on():
    a = _calc("a", CalculationKind.ROW)
    b = _calc("b", CalculationKind.AGGREGATE, depends=("a",))
    c = _calc("c", CalculationKind.AGGREGATE, depends=("b",))
    ordered = topo_sort((c, a, b))
    ids = [x.id for x in ordered]
    assert ids.index("a") < ids.index("b") < ids.index("c")


def test_topo_sort_skips_unknown_depends():
    """Refs to ids not in the input set are ignored (e.g. dangling refs to
    calcs already routed to unsupported[])."""
    a = _calc("a", CalculationKind.ROW, depends=("missing",))
    ordered = topo_sort((a,))
    assert [x.id for x in ordered] == ["a"]


def test_topo_sort_breaks_ties_by_id_for_determinism():
    a = _calc("a", CalculationKind.ROW)
    b = _calc("b", CalculationKind.ROW)
    c = _calc("c", CalculationKind.ROW)
    ordered = topo_sort((c, a, b))
    assert [x.id for x in ordered] == ["a", "b", "c"]
```

- [x] **Step 5.2: Run test — verify failure**

```bash
pytest tests/unit/translate/test_topo.py -v
```
Expected: ModuleNotFoundError on `tableau2pbir.translate.topo`.

- [x] **Step 5.3: Write `src/tableau2pbir/translate/topo.py`**

```python
"""Topological ordering for stage-3 calc translation. Two lanes per spec
§6 Stage 3 + §5.6: 'global' contains row/aggregate/lod_fixed and named
table_calc; 'per-sheet' contains lod_include/lod_exclude and any calc
with `owner_sheet_id` set (anonymous quick-table-calcs).

Cycle handling lives in `_calc_graph.detect_cycles` (Plan 2). This module
assumes the input is acyclic for the lanes that matter; cycle members
are pre-routed to unsupported[] before reaching here."""
from __future__ import annotations

from collections import defaultdict, deque

from tableau2pbir.ir.calculation import Calculation, CalculationKind

_GLOBAL_KINDS = frozenset({
    CalculationKind.ROW,
    CalculationKind.AGGREGATE,
    CalculationKind.LOD_FIXED,
})


def _is_global(c: Calculation) -> bool:
    if c.owner_sheet_id is not None:
        return False
    if c.kind in _GLOBAL_KINDS:
        return True
    if c.kind is CalculationKind.TABLE_CALC:
        # Named table_calc (no owner_sheet_id) lives in the global lane.
        return True
    # lod_include / lod_exclude — always per-sheet.
    return False


def partition_lanes(
    calcs: tuple[Calculation, ...],
) -> tuple[tuple[Calculation, ...], tuple[Calculation, ...]]:
    """Split into (global_lane, per_sheet_lane)."""
    g: list[Calculation] = []
    p: list[Calculation] = []
    for c in calcs:
        (g if _is_global(c) else p).append(c)
    return tuple(g), tuple(p)


def topo_sort(calcs: tuple[Calculation, ...]) -> tuple[Calculation, ...]:
    """Kahn's algorithm; ties broken by sorted(id) for stable output.
    Edges to ids not in `calcs` are ignored."""
    by_id = {c.id: c for c in calcs}
    incoming: dict[str, set[str]] = defaultdict(set)
    outgoing: dict[str, set[str]] = defaultdict(set)
    for c in calcs:
        for dep in c.depends_on:
            if dep in by_id:
                incoming[c.id].add(dep)
                outgoing[dep].add(c.id)

    ready = sorted(cid for cid in by_id if not incoming[cid])
    result: list[Calculation] = []
    queue: deque[str] = deque(ready)
    while queue:
        n = queue.popleft()
        result.append(by_id[n])
        for m in sorted(outgoing[n]):
            outgoing[n].discard(m)
            incoming[m].discard(n)
            if not incoming[m]:
                # Insert in sorted position to keep id-tiebreak determinism.
                queue.append(m)
                items = sorted(queue)
                queue.clear()
                queue.extend(items)
    return tuple(result)
```

- [x] **Step 5.4: Run test — verify pass**

```bash
pytest tests/unit/translate/test_topo.py -v
```
Expected: 4 passed.

- [x] **Step 5.5: Commit**

```bash
git add src/tableau2pbir/translate/topo.py tests/unit/translate/test_topo.py
git commit -m "feat(translate): add stage-3 lane partition + topo sort"
```

---

## Task 6: `translate/rules/row.py` — row-calc rule library

**Files:**
- Create: `src/tableau2pbir/translate/rules/__init__.py` (empty)
- Create: `src/tableau2pbir/translate/rules/row.py`
- Create: `tests/unit/translate/rules/__init__.py` (empty)
- Create: `tests/unit/translate/rules/test_row.py`

- [x] **Step 6.1: Write the failing test**

```python
"""Row-calc rule. v1 row library: arithmetic, string concat, IF/CASE,
date functions DATEDIFF/DATETRUNC, ISNULL/ZN. Each rule returns the
rewritten DAX expression; on no-match, returns None."""
from __future__ import annotations

from tableau2pbir.translate.rules.row import translate_row


def test_arithmetic_passthrough():
    assert translate_row("[Sales] + [Tax]") == "[Sales] + [Tax]"


def test_iif_to_if():
    assert translate_row("IIF([x] > 0, 1, 0)") == "IF([x] > 0, 1, 0)"


def test_zn_to_coalesce_zero():
    assert translate_row("ZN([Sales])") == "COALESCE([Sales], 0)"


def test_ifnull_to_coalesce():
    assert translate_row("IFNULL([Sales], 0)") == "COALESCE([Sales], 0)"


def test_string_concat_plus_passthrough():
    assert translate_row('"Region: " + [Region]') == '"Region: " + [Region]'


def test_datediff_to_dax_datediff():
    assert translate_row("DATEDIFF('day', [Start], [End])") == \
        "DATEDIFF([Start], [End], DAY)"


def test_datetrunc_month_to_startofmonth():
    assert translate_row("DATETRUNC('month', [OrderDate])") == \
        "STARTOFMONTH([OrderDate])"


def test_unmatched_returns_none():
    assert translate_row("WEIRDFN([x])") is None
```

- [x] **Step 6.2: Run test — verify failure**

```bash
pytest tests/unit/translate/rules/test_row.py -v
```
Expected: ModuleNotFoundError on `tableau2pbir.translate.rules.row`.

- [x] **Step 6.3: Write `src/tableau2pbir/translate/rules/row.py`**

```python
"""Row-calc translation rules (v1). Each rule is a regex-based or string-
substitution pattern. `translate_row(expr)` tries every rule in order and
returns the first transform that fires; returns None on no-match so the
caller can hand off to AI fallback.

The rule list is intentionally small and conservative — anything not
covered is treated as a candidate for `LLMClient.translate_calc`."""
from __future__ import annotations

import re

# Each rule is (compiled_regex, replacement_template) or
# (compiled_regex, callable-mapping-match→str).
_RULES: list[tuple[re.Pattern[str], object]] = [
    # IIF(cond, then, else) → IF(cond, then, else)
    (re.compile(r"\bIIF\s*\("), "IF("),
    # ZN(x) → COALESCE(x, 0)
    (re.compile(r"\bZN\s*\(\s*(?P<x>[^()]+?)\s*\)"),
     lambda m: f"COALESCE({m.group('x')}, 0)"),
    # IFNULL(a, b) → COALESCE(a, b)
    (re.compile(r"\bIFNULL\s*\(\s*(?P<a>[^,()]+?)\s*,\s*(?P<b>[^()]+?)\s*\)"),
     lambda m: f"COALESCE({m.group('a')}, {m.group('b')})"),
    # DATEDIFF('unit', start, end) → DATEDIFF(start, end, UNIT)
    (re.compile(
        r"\bDATEDIFF\s*\(\s*'(?P<u>day|month|year|hour|minute|second)'\s*,\s*"
        r"(?P<a>[^,()]+?)\s*,\s*(?P<b>[^()]+?)\s*\)",
    ), lambda m: f"DATEDIFF({m.group('a')}, {m.group('b')}, {m.group('u').upper()})"),
    # DATETRUNC('month', x) → STARTOFMONTH(x)
    (re.compile(r"\bDATETRUNC\s*\(\s*'month'\s*,\s*(?P<x>[^()]+?)\s*\)"),
     lambda m: f"STARTOFMONTH({m.group('x')})"),
    # DATETRUNC('year', x) → STARTOFYEAR(x)
    (re.compile(r"\bDATETRUNC\s*\(\s*'year'\s*,\s*(?P<x>[^()]+?)\s*\)"),
     lambda m: f"STARTOFYEAR({m.group('x')})"),
    # DATETRUNC('quarter', x) → STARTOFQUARTER(x)
    (re.compile(r"\bDATETRUNC\s*\(\s*'quarter'\s*,\s*(?P<x>[^()]+?)\s*\)"),
     lambda m: f"STARTOFQUARTER({m.group('x')})"),
]

# Patterns that are valid DAX as-is (passthrough). Used to short-circuit
# AI fallback on plain arithmetic / boolean / string-concat expressions.
_PASSTHROUGH = re.compile(
    r"^[\s\[\]\w\d\+\-\*\/\=\<\>\!\,\.\(\)\"\'%]+$"
)


def translate_row(tableau_expr: str) -> str | None:
    """Return DAX expression, or None if no rule matched."""
    expr = tableau_expr
    fired = False
    for pattern, replacement in _RULES:
        if isinstance(replacement, str):
            new_expr, n = pattern.subn(replacement, expr)
        else:
            new_expr, n = pattern.subn(replacement, expr)
        if n:
            fired = True
            expr = new_expr
    if fired:
        return expr
    if _PASSTHROUGH.match(expr) and not re.search(r"[A-Z_][A-Z_]+\s*\(", expr):
        # Pure operators/identifiers/literals — no function calls; passes through.
        return expr
    return None
```

- [x] **Step 6.4: Run test — verify pass**

```bash
pytest tests/unit/translate/rules/test_row.py -v
```
Expected: 8 passed.

- [x] **Step 6.5: Commit**

```bash
git add src/tableau2pbir/translate/rules/__init__.py \
        src/tableau2pbir/translate/rules/row.py \
        tests/unit/translate/rules/__init__.py \
        tests/unit/translate/rules/test_row.py
git commit -m "feat(translate): row-calc rule library (arith, IIF, ZN, DATEDIFF, DATETRUNC)"
```

---

## Task 7: `translate/rules/aggregate.py` — aggregate-calc rule library

**Files:**
- Create: `src/tableau2pbir/translate/rules/aggregate.py`
- Create: `tests/unit/translate/rules/test_aggregate.py`

- [x] **Step 7.1: Write the failing test**

```python
"""Aggregate-calc rules: SUM/AVG/COUNT/COUNTD/MIN/MAX + conditional
SUM(IF cond THEN x END) → CALCULATE(SUM(x), FILTER(...))."""
from __future__ import annotations

from tableau2pbir.translate.rules.aggregate import translate_aggregate


def test_sum_passthrough():
    assert translate_aggregate("SUM([Sales])") == "SUM([Sales])"


def test_avg_to_average():
    assert translate_aggregate("AVG([Sales])") == "AVERAGE([Sales])"


def test_countd_to_distinctcount():
    assert translate_aggregate("COUNTD([Customer])") == "DISTINCTCOUNT([Customer])"


def test_min_max_passthrough():
    assert translate_aggregate("MIN([Sales])") == "MIN([Sales])"
    assert translate_aggregate("MAX([Sales])") == "MAX([Sales])"


def test_conditional_sum_to_calculate_filter():
    out = translate_aggregate('SUM(IF [Region] = "East" THEN [Sales] END)')
    assert out.startswith("CALCULATE(SUM([Sales])")
    assert 'FILTER' in out
    assert '[Region] = "East"' in out


def test_unmatched_returns_none():
    assert translate_aggregate("WEIRDFN([x])") is None
```

- [x] **Step 7.2: Run test — verify failure**

```bash
pytest tests/unit/translate/rules/test_aggregate.py -v
```
Expected: ModuleNotFoundError.

- [x] **Step 7.3: Write `src/tableau2pbir/translate/rules/aggregate.py`**

```python
"""Aggregate-calc rules. Returns DAX or None on no match."""
from __future__ import annotations

import re

_AGG_RENAMES = {
    "AVG": "AVERAGE",
    "COUNTD": "DISTINCTCOUNT",
}

_AGG_FNS = ("SUM", "AVERAGE", "AVG", "COUNT", "COUNTD", "MIN", "MAX")
_OUTER_RE = re.compile(
    r"^(?P<fn>SUM|AVG|COUNT|COUNTD|MIN|MAX)\s*\((?P<arg>.*)\)\s*$",
    re.DOTALL,
)
_COND_INNER_RE = re.compile(
    r"^IF\s+(?P<cond>.+?)\s+THEN\s+(?P<then>.+?)\s+END$",
    re.DOTALL,
)


def translate_aggregate(tableau_expr: str) -> str | None:
    expr = tableau_expr.strip()
    m = _OUTER_RE.match(expr)
    if not m:
        return None
    fn = _AGG_RENAMES.get(m.group("fn"), m.group("fn"))
    arg = m.group("arg").strip()

    cond = _COND_INNER_RE.match(arg)
    if cond:
        # SUM(IF c THEN x END)  →  CALCULATE(SUM(x), FILTER(ALL(<table>), c))
        # We don't know the table here; emit FILTER over the whole model
        # context using ALLSELECTED. Stage-6 may rewrite if needed.
        inner = cond.group("then").strip()
        predicate = cond.group("cond").strip()
        return (
            f"CALCULATE({fn}({inner}), "
            f"FILTER(ALLSELECTED(), {predicate}))"
        )
    return f"{fn}({arg})"
```

- [x] **Step 7.4: Run test — verify pass**

```bash
pytest tests/unit/translate/rules/test_aggregate.py -v
```
Expected: 6 passed.

- [x] **Step 7.5: Commit**

```bash
git add src/tableau2pbir/translate/rules/aggregate.py \
        tests/unit/translate/rules/test_aggregate.py
git commit -m "feat(translate): aggregate-calc rule library"
```

---

## Task 8: `translate/rules/lod_fixed.py` — FIXED-LOD rule

**Files:**
- Create: `src/tableau2pbir/translate/rules/lod_fixed.py`
- Create: `tests/unit/translate/rules/test_lod_fixed.py`

- [x] **Step 8.1: Write the failing test**

```python
"""FIXED LOD → CALCULATE(<agg>, REMOVEFILTERS(<other>), KEEPFILTERS(<dims>)).

We don't know "all other dimensions" at translate time; per spec we use
REMOVEFILTERS over the table containing the dim and KEEPFILTERS over the
listed FIXED dims. The IR Calculation.lod_fixed.dimensions carries the
dim list; the rule consumes that, not the raw expression."""
from __future__ import annotations

from tableau2pbir.ir.calculation import (
    Calculation, CalculationKind, CalculationPhase, LodFixed,
)
from tableau2pbir.ir.common import FieldRef
from tableau2pbir.translate.rules.lod_fixed import translate_lod_fixed


def _calc(expr: str, dims: tuple[FieldRef, ...]) -> Calculation:
    return Calculation(
        id="c1", name="LodCalc", scope="measure", tableau_expr=expr,
        depends_on=(), kind=CalculationKind.LOD_FIXED,
        phase=CalculationPhase.AGGREGATE,
        lod_fixed=LodFixed(dimensions=dims),
    )


def test_fixed_one_dim():
    fr = FieldRef(table_id="orders", column_id="orders__col__customer")
    c = _calc("{FIXED [Customer] : SUM([Sales])}", (fr,))
    out = translate_lod_fixed(c)
    assert out == (
        "CALCULATE(SUM([Sales]), "
        "REMOVEFILTERS(orders), "
        "KEEPFILTERS(VALUES(orders[orders__col__customer])))"
    )


def test_fixed_two_dims():
    a = FieldRef(table_id="orders", column_id="orders__col__customer")
    b = FieldRef(table_id="orders", column_id="orders__col__region")
    c = _calc("{FIXED [Customer], [Region] : AVG([Sales])}", (a, b))
    out = translate_lod_fixed(c)
    assert "AVERAGE([Sales])" in out
    assert "REMOVEFILTERS(orders)" in out
    assert "KEEPFILTERS(VALUES(orders[orders__col__customer]))" in out
    assert "KEEPFILTERS(VALUES(orders[orders__col__region]))" in out


def test_no_inner_aggregation_returns_none():
    fr = FieldRef(table_id="orders", column_id="orders__col__customer")
    c = _calc("{FIXED [Customer] : [Sales]}", (fr,))
    assert translate_lod_fixed(c) is None
```

- [x] **Step 8.2: Run test — verify failure**

```bash
pytest tests/unit/translate/rules/test_lod_fixed.py -v
```
Expected: ModuleNotFoundError.

- [x] **Step 8.3: Write `src/tableau2pbir/translate/rules/lod_fixed.py`**

```python
"""FIXED LOD rule: extract inner aggregation, build CALCULATE pattern.

Pattern produced:
  CALCULATE(<inner_agg_dax>,
            REMOVEFILTERS(<table_of_first_dim>),
            KEEPFILTERS(VALUES(<table>[<col>])),
            KEEPFILTERS(VALUES(<table>[<col>])),
            ...)

The inner aggregation is parsed out of the Tableau expression
`{FIXED <dims> : <agg_expr>}` using a non-greedy split on `:`."""
from __future__ import annotations

import re

from tableau2pbir.ir.calculation import Calculation
from tableau2pbir.translate.rules.aggregate import translate_aggregate

_LOD_RE = re.compile(
    r"^\s*\{\s*FIXED\s+(?P<dims>.+?)\s*:\s*(?P<inner>.+?)\s*\}\s*$",
    re.DOTALL,
)


def translate_lod_fixed(calc: Calculation) -> str | None:
    if calc.lod_fixed is None or not calc.lod_fixed.dimensions:
        return None
    m = _LOD_RE.match(calc.tableau_expr)
    if not m:
        return None
    inner = translate_aggregate(m.group("inner").strip())
    if inner is None:
        return None
    table_id = calc.lod_fixed.dimensions[0].table_id
    keep_clauses = ", ".join(
        f"KEEPFILTERS(VALUES({d.table_id}[{d.column_id}]))"
        for d in calc.lod_fixed.dimensions
    )
    return f"CALCULATE({inner}, REMOVEFILTERS({table_id}), {keep_clauses})"
```

- [x] **Step 8.4: Run test — verify pass**

```bash
pytest tests/unit/translate/rules/test_lod_fixed.py -v
```
Expected: 3 passed.

- [x] **Step 8.5: Commit**

```bash
git add src/tableau2pbir/translate/rules/lod_fixed.py \
        tests/unit/translate/rules/test_lod_fixed.py
git commit -m "feat(translate): FIXED LOD rule (CALCULATE + REMOVEFILTERS + KEEPFILTERS)"
```

---

## Task 9: `translate/rules/dispatch.py` — kind-keyed rule dispatch

**Files:**
- Create: `src/tableau2pbir/translate/rules/dispatch.py`
- Create: `tests/unit/translate/rules/test_dispatch.py`

- [x] **Step 9.1: Write the failing test**

```python
"""Dispatch picks the right rule by Calculation.kind, returns
(dax_expr, rule_name) or (None, None) on miss."""
from __future__ import annotations

from tableau2pbir.ir.calculation import (
    Calculation, CalculationKind, CalculationPhase, LodFixed,
)
from tableau2pbir.ir.common import FieldRef
from tableau2pbir.ir.parameter import Parameter, ParameterIntent
from tableau2pbir.translate.rules.dispatch import dispatch_rule


def _calc(kind: CalculationKind, expr: str, **kw: object) -> Calculation:
    return Calculation(
        id="c1", name="C", scope="measure", tableau_expr=expr,
        depends_on=(), kind=kind, phase=CalculationPhase.AGGREGATE, **kw,
    )


def test_row_dispatch_runs_row_rule():
    c = _calc(CalculationKind.ROW, "ZN([Sales])")
    dax, rule = dispatch_rule(c, parameters=())
    assert dax == "COALESCE([Sales], 0)"
    assert rule == "row"


def test_aggregate_dispatch_runs_aggregate_rule():
    c = _calc(CalculationKind.AGGREGATE, "AVG([Sales])")
    dax, rule = dispatch_rule(c, parameters=())
    assert dax == "AVERAGE([Sales])"
    assert rule == "aggregate"


def test_lod_fixed_dispatch_runs_lod_fixed_rule():
    fr = FieldRef(table_id="orders", column_id="orders__col__cust")
    c = _calc(
        CalculationKind.LOD_FIXED, "{FIXED [Customer] : SUM([Sales])}",
        lod_fixed=LodFixed(dimensions=(fr,)),
    )
    dax, rule = dispatch_rule(c, parameters=())
    assert "REMOVEFILTERS(orders)" in dax
    assert rule == "lod_fixed"


def test_parameters_rewritten_before_rule():
    p = Parameter(id="p", name="TaxRate", datatype="float", default="0.07",
                  allowed_values=(), intent=ParameterIntent.INTERNAL_CONSTANT,
                  exposure="card")
    c = _calc(CalculationKind.ROW, "[Sales] * [TaxRate]")
    dax, _ = dispatch_rule(c, parameters=(p,))
    assert dax == "[Sales] * 0.07"


def test_deferred_kind_returns_none():
    c = _calc(CalculationKind.LOD_INCLUDE, "{INCLUDE [x] : SUM(y)}")
    dax, rule = dispatch_rule(c, parameters=())
    assert dax is None
    assert rule is None


def test_no_rule_match_returns_none():
    c = _calc(CalculationKind.ROW, "WEIRDFN([x])")
    dax, rule = dispatch_rule(c, parameters=())
    assert dax is None
    assert rule == "row"  # row was tried but missed
```

- [x] **Step 9.2: Run test — verify failure**

```bash
pytest tests/unit/translate/rules/test_dispatch.py -v
```
Expected: ModuleNotFoundError.

- [x] **Step 9.3: Write `src/tableau2pbir/translate/rules/dispatch.py`**

```python
"""Rule dispatch — pick row/aggregate/lod_fixed by Calculation.kind. v1
deferred kinds (table_calc / lod_include / lod_exclude) return (None, None)
without trying any rule, since stage 2 has already routed them to
unsupported[]."""
from __future__ import annotations

from tableau2pbir.ir.calculation import Calculation, CalculationKind
from tableau2pbir.ir.parameter import Parameter
from tableau2pbir.translate.parameters import rewrite_parameter_refs
from tableau2pbir.translate.rules.aggregate import translate_aggregate
from tableau2pbir.translate.rules.lod_fixed import translate_lod_fixed
from tableau2pbir.translate.rules.row import translate_row


def dispatch_rule(
    calc: Calculation, *, parameters: tuple[Parameter, ...],
) -> tuple[str | None, str | None]:
    """Return (dax_expr, rule_name).
    `rule_name` records which rule was *attempted* — useful for the stage-3
    summary even on miss. Returns (None, None) for v1-deferred kinds."""
    if calc.kind in (
        CalculationKind.TABLE_CALC,
        CalculationKind.LOD_INCLUDE,
        CalculationKind.LOD_EXCLUDE,
    ):
        return None, None

    expr = rewrite_parameter_refs(calc.tableau_expr, parameters)

    if calc.kind is CalculationKind.ROW:
        return translate_row(expr), "row"
    if calc.kind is CalculationKind.AGGREGATE:
        return translate_aggregate(expr), "aggregate"
    if calc.kind is CalculationKind.LOD_FIXED:
        # Inject the rewritten expr back into the calc for the lod rule
        # which re-parses {FIXED ... : ...}.
        rebuilt = calc.model_copy(update={"tableau_expr": expr})
        return translate_lod_fixed(rebuilt), "lod_fixed"

    return None, None
```

- [x] **Step 9.4: Run test — verify pass**

```bash
pytest tests/unit/translate/rules/test_dispatch.py -v
```
Expected: 6 passed.

- [x] **Step 9.5: Commit**

```bash
git add src/tableau2pbir/translate/rules/dispatch.py \
        tests/unit/translate/rules/test_dispatch.py
git commit -m "feat(translate): kind-keyed rule dispatch with parameter rewriting"
```

---

## Task 10: `LLMClient.translate_calc` — implement Anthropic call w/ cache + snapshot

**Files:**
- Modify: `src/tableau2pbir/llm/client.py`
- Modify: `src/tableau2pbir/llm/prompts/translate_calc/system.md`
- Modify: `src/tableau2pbir/llm/prompts/translate_calc/VERSION`
- Create: `tests/unit/llm/__init__.py` (empty)
- Create: `tests/unit/llm/test_client.py`
- Create: `tests/llm_snapshots/translate_calc/ai_only_compose.json`

- [x] **Step 10.1: Write the failing test**

```python
"""LLMClient.translate_calc — three modes:
1. Cache hit  → returns cached value, no network, no snapshot read.
2. Replay     → PYTEST_SNAPSHOT=replay env: reads from llm_snapshots/.
3. Live       → calls Anthropic SDK; not exercised in unit tests."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from tableau2pbir.llm.client import LLMClient


_FIXTURE_SUBSET = {"id": "calc1", "name": "C1", "kind": "row",
                   "tableau_expr": "WEIRDFN([x])"}


def test_cache_hit_returns_value(tmp_path: Path):
    cache_dir = tmp_path / "cache"
    client = LLMClient(cache_dir=cache_dir)
    # Pre-populate the cache by computing the key the same way the client does.
    pack = client.packs["translate_calc"]
    from tableau2pbir.llm.cache import make_cache_key
    key = make_cache_key(
        model=client.model_by_method["translate_calc"],
        prompt_hash=pack.system_prompt_hash,
        schema_hash=pack.tool_schema_hash,
        payload=_FIXTURE_SUBSET,
    )
    client.cache.put(key, {"dax_expr": "FROM_CACHE",
                           "confidence": "high", "notes": ""})

    out = client.translate_calc(_FIXTURE_SUBSET)
    assert out["dax_expr"] == "FROM_CACHE"


def test_replay_mode_reads_snapshot(tmp_path: Path, monkeypatch):
    """In replay mode we ignore cache and read from the on-disk snapshot
    keyed by the `fixture` name in the payload."""
    monkeypatch.setenv("PYTEST_SNAPSHOT", "replay")
    cache_dir = tmp_path / "cache"
    client = LLMClient(cache_dir=cache_dir)
    payload = {**_FIXTURE_SUBSET, "fixture": "ai_only_compose"}
    out = client.translate_calc(payload)
    # Whatever is in tests/llm_snapshots/translate_calc/ai_only_compose.json
    assert out["confidence"] in ("high", "medium", "low")
    assert isinstance(out["dax_expr"], str)


def test_live_mode_without_api_key_raises(tmp_path: Path, monkeypatch):
    """Without ANTHROPIC_API_KEY, the live path raises a clear error rather
    than silently swallowing the SDK exception."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("PYTEST_SNAPSHOT", raising=False)
    cache_dir = tmp_path / "cache"
    client = LLMClient(cache_dir=cache_dir)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        client.translate_calc({"id": "x", "name": "x",
                               "kind": "row", "tableau_expr": "y"})
```

- [x] **Step 10.2: Create the snapshot fixture**

`tests/llm_snapshots/translate_calc/ai_only_compose.json`:

```json
{
  "dax_expr": "[Sales] * 1.1",
  "confidence": "medium",
  "notes": "Synthetic snapshot — composed from row arithmetic."
}
```

- [x] **Step 10.3: Bump prompt VERSION and rewrite system.md**

`src/tableau2pbir/llm/prompts/translate_calc/VERSION`:

```
0.2.0
```

`src/tableau2pbir/llm/prompts/translate_calc/system.md`:

```markdown
You translate a single Tableau calculation into a single DAX expression.

# Input

A JSON object with these keys (others may be present and should be ignored):
- `id`              — calculation IR id
- `name`            — Tableau calc name
- `kind`            — one of `row`, `aggregate`, `lod_fixed`, `table_calc`, `lod_include`, `lod_exclude`
- `phase`           — one of `row`, `aggregate`, `viz`
- `tableau_expr`    — the verbatim Tableau expression (after `[ParamName]` rewriting)
- `depends_on`      — list of calc ids this calc references (already translated; reference them by their DAX measure name = the calc `name`)
- `lod_fixed.dimensions` — present iff `kind == "lod_fixed"`; list of `{table_id, column_id}` dim refs

# Output

Call the `translate_calc_output` tool with:
- `dax_expr`    — DAX expression string (no leading `=`, no surrounding spaces)
- `confidence`  — `high` / `medium` / `low`
- `notes`       — one short sentence on assumptions or fidelity loss

# Rules

- Use bracketed identifiers for measures (`[Sales]`) and `'Table'[Column]` for columns.
- Aggregations: `SUM`, `AVERAGE`, `COUNT`, `DISTINCTCOUNT`, `MIN`, `MAX`.
- For `lod_fixed`, emit `CALCULATE(<agg>, REMOVEFILTERS(<table>), KEEPFILTERS(VALUES(<table>[<col>])), …)`.
- Never invent fields not present in `tableau_expr` or `depends_on`.
- If you cannot produce a valid DAX expression, return `confidence: "low"` with the closest attempt and explain in `notes`.
```

- [x] **Step 10.4: Edit `src/tableau2pbir/llm/client.py`**

Replace the file with:

```python
"""LLMClient — single AI entry point per spec §7.

Three modes per spec §7 step 4 + §9 layer vi:
1. Cache hit (content-hash) — zero network.
2. Snapshot replay (`PYTEST_SNAPSHOT=replay`) — zero network, read from
   `tests/llm_snapshots/<method>/<payload['fixture']>.json`.
3. Live — calls Anthropic SDK with tool-use; result validated against
   the prompt-pack tool schema; cached on success.

Validator: the response must be a valid tool-use block whose input keys
match the tool_schema.input_schema.required set; otherwise we drop it
(callers treat None / KeyError as a miss and route to unsupported[])."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from tableau2pbir.llm.cache import OnDiskCache, make_cache_key
from tableau2pbir.llm.prompt_loader import PromptPack, load_prompt_pack
from tableau2pbir.llm.snapshots import SnapshotStore, is_replay_mode

_METHODS = ("translate_calc", "map_visual", "cleanup_name")
_DEFAULT_MODEL = "claude-sonnet-4-6"
_SNAPSHOT_ROOT = Path(__file__).resolve().parents[3] / "tests" / "llm_snapshots"


class LLMClient:
    def __init__(
        self,
        *,
        cache_dir: Path,
        model_by_method: dict[str, str] | None = None,
        snapshot_root: Path | None = None,
    ) -> None:
        self.cache = OnDiskCache(cache_dir)
        self.packs: dict[str, PromptPack] = {m: load_prompt_pack(m) for m in _METHODS}
        self.model_by_method = {m: _DEFAULT_MODEL for m in _METHODS}
        if model_by_method:
            self.model_by_method.update(model_by_method)
        self.snapshots = SnapshotStore(snapshot_root or _SNAPSHOT_ROOT)

    # --- public entry points ---

    def translate_calc(self, calc_subset: dict[str, Any]) -> dict[str, Any]:
        return self._call("translate_calc", calc_subset)

    def map_visual(self, sheet_subset: dict[str, Any]) -> dict[str, Any]:
        return self._call("map_visual", sheet_subset)

    def cleanup_name(self, *, raw_name: str, kind: str) -> dict[str, Any]:
        return self._call("cleanup_name", {"raw_name": raw_name, "kind": kind})

    # --- shared dispatch ---

    def _call(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        pack = self.packs[method]
        model = self.model_by_method[method]
        cache_payload = {k: v for k, v in payload.items() if k != "fixture"}

        if is_replay_mode():
            fixture = payload.get("fixture")
            if not fixture:
                raise RuntimeError(
                    f"PYTEST_SNAPSHOT=replay set but no 'fixture' in payload "
                    f"for {method}: {payload!r}"
                )
            return self.snapshots.load(method, fixture)

        key = make_cache_key(
            model=model,
            prompt_hash=pack.system_prompt_hash,
            schema_hash=pack.tool_schema_hash,
            payload=cache_payload,
        )
        cached = self.cache.get(key)
        if cached is not None:
            return cached

        # Live path — strict env check up front.
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError(
                "ANTHROPIC_API_KEY not set — cannot run live LLM call. "
                "Set the env var, populate the cache, or use PYTEST_SNAPSHOT=replay."
            )
        result = self._call_anthropic(pack, model, payload)
        self._validate(pack, result)
        self.cache.put(key, result)
        return result

    def _call_anthropic(
        self, pack: PromptPack, model: str, payload: dict[str, Any],
    ) -> dict[str, Any]:
        # Lazy import so unit tests don't pay for the SDK on cache/replay paths.
        import anthropic

        client = anthropic.Anthropic()
        message = client.messages.create(
            model=model,
            max_tokens=1024,
            system=pack.system_text,
            tools=[pack.tool_schema],
            tool_choice={"type": "tool", "name": pack.tool_schema["name"]},
            messages=[
                {"role": "user", "content": json.dumps(payload, sort_keys=True)},
            ],
        )
        for block in message.content:
            if getattr(block, "type", None) == "tool_use":
                # Anthropic SDK returns dict for tool_use.input.
                return dict(block.input)  # type: ignore[arg-type]
        raise RuntimeError(f"no tool_use block in response for {pack.method}")

    def _validate(self, pack: PromptPack, result: dict[str, Any]) -> None:
        required = pack.tool_schema["input_schema"].get("required", [])
        missing = [k for k in required if k not in result]
        if missing:
            raise RuntimeError(
                f"{pack.method} response missing required keys: {missing}"
            )
```

- [x] **Step 10.5: Run test — verify pass**

```bash
pytest tests/unit/llm/test_client.py -v
```
Expected: 3 passed.

- [x] **Step 10.6: Commit**

```bash
git add src/tableau2pbir/llm/client.py \
        src/tableau2pbir/llm/prompts/translate_calc/VERSION \
        src/tableau2pbir/llm/prompts/translate_calc/system.md \
        tests/unit/llm/__init__.py \
        tests/unit/llm/test_client.py \
        tests/llm_snapshots/translate_calc/ai_only_compose.json
git commit -m "feat(llm): implement LLMClient.translate_calc + map_visual w/ cache + snapshot replay"
```

---

## Task 11: `translate/ai_fallback.py` — wire LLMClient into stage 3 calc loop

**Files:**
- Create: `src/tableau2pbir/translate/ai_fallback.py`
- Create: `tests/unit/translate/test_ai_fallback.py`
- Create: `tests/llm_snapshots/translate_calc/ai_only_aggregate_conditional.json`

- [x] **Step 11.1: Write the failing test**

```python
"""ai_fallback.translate_via_ai — invokes LLMClient and validates the
response: dax_expr must pass the syntax gate, else returns None so the
caller routes the calc to unsupported[]."""
from __future__ import annotations

from pathlib import Path

import pytest

from tableau2pbir.ir.calculation import (
    Calculation, CalculationKind, CalculationPhase,
)
from tableau2pbir.llm.client import LLMClient
from tableau2pbir.translate.ai_fallback import translate_via_ai


def _calc(expr: str) -> Calculation:
    return Calculation(
        id="c1", name="Conditional", scope="measure", tableau_expr=expr,
        depends_on=(), kind=CalculationKind.AGGREGATE,
        phase=CalculationPhase.AGGREGATE,
    )


def test_replay_returns_dax_when_syntax_passes(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PYTEST_SNAPSHOT", "replay")
    client = LLMClient(cache_dir=tmp_path / "cache")
    c = _calc("SUM(IF [r] = 'x' THEN [s] END)")
    out = translate_via_ai(c, fixture="ai_only_aggregate_conditional",
                           client=client)
    assert out is not None
    assert out["dax_expr"]


def test_replay_drops_when_syntax_fails(tmp_path: Path, monkeypatch):
    """A snapshot whose dax_expr is intentionally malformed must be
    rejected by the gate and return None."""
    snapshots_root = tmp_path / "snaps"
    (snapshots_root / "translate_calc").mkdir(parents=True)
    (snapshots_root / "translate_calc" / "broken.json").write_text(
        '{"dax_expr": "@@@ broken", "confidence": "low", "notes": ""}',
        encoding="utf-8",
    )
    monkeypatch.setenv("PYTEST_SNAPSHOT", "replay")
    client = LLMClient(cache_dir=tmp_path / "cache",
                       snapshot_root=snapshots_root)
    c = _calc("SUM([s])")
    out = translate_via_ai(c, fixture="broken", client=client)
    assert out is None
```

- [x] **Step 11.2: Create snapshot for the conditional aggregate**

`tests/llm_snapshots/translate_calc/ai_only_aggregate_conditional.json`:

```json
{
  "dax_expr": "CALCULATE(SUM([s]), FILTER(ALLSELECTED(), [r] = 'x'))",
  "confidence": "medium",
  "notes": "Synthetic snapshot for AI fallback test."
}
```

- [x] **Step 11.3: Write `src/tableau2pbir/translate/ai_fallback.py`**

```python
"""AI fallback for stage 3. Invokes LLMClient.translate_calc, validates
the resulting DAX through the syntax gate, and returns None on validator
fail (caller routes the calc to unsupported[])."""
from __future__ import annotations

from typing import Any

from tableau2pbir.ir.calculation import Calculation
from tableau2pbir.llm.client import LLMClient
from tableau2pbir.translate.syntax_gate import is_valid_dax


def _calc_subset(calc: Calculation, fixture: str | None) -> dict[str, Any]:
    """Stable, content-hashable subset for cache keying."""
    payload: dict[str, Any] = {
        "id": calc.id,
        "name": calc.name,
        "kind": calc.kind.value,
        "phase": calc.phase.value,
        "tableau_expr": calc.tableau_expr,
        "depends_on": list(calc.depends_on),
    }
    if calc.lod_fixed is not None:
        payload["lod_fixed"] = {
            "dimensions": [
                {"table_id": d.table_id, "column_id": d.column_id}
                for d in calc.lod_fixed.dimensions
            ],
        }
    if fixture is not None:
        payload["fixture"] = fixture
    return payload


def translate_via_ai(
    calc: Calculation, *, fixture: str | None, client: LLMClient,
) -> dict[str, Any] | None:
    """Returns the validated AI response, or None if the gate fails."""
    response = client.translate_calc(_calc_subset(calc, fixture))
    if not is_valid_dax(response.get("dax_expr", "")):
        return None
    return response
```

- [x] **Step 11.4: Run test — verify pass**

```bash
pytest tests/unit/translate/test_ai_fallback.py -v
```
Expected: 2 passed.

- [x] **Step 11.5: Commit**

```bash
git add src/tableau2pbir/translate/ai_fallback.py \
        tests/unit/translate/test_ai_fallback.py \
        tests/llm_snapshots/translate_calc/ai_only_aggregate_conditional.json
git commit -m "feat(translate): AI fallback w/ syntax-gate validation"
```

---

## Task 12: `translate/summary.py` — stage 3 summary renderer

**Files:**
- Create: `src/tableau2pbir/translate/summary.py`
- Append to existing test or create: `tests/unit/translate/test_summary.py`

- [x] **Step 12.1: Write the failing test**

`tests/unit/translate/test_summary.py`:

```python
"""Stage 3 summary.md — counts by translation source, rule hit histogram,
AI confidence histogram, cache hit rate, validator failures."""
from __future__ import annotations

from tableau2pbir.translate.summary import TranslationStats, render_stage3_summary


def test_summary_renders_counts_and_histograms():
    stats = TranslationStats(
        total=10, by_source={"rule": 6, "ai": 3, "skip": 1},
        rule_hits={"row": 3, "aggregate": 2, "lod_fixed": 1},
        ai_confidence={"high": 1, "medium": 2, "low": 0},
        ai_cache_hits=2, ai_cache_misses=1,
        validator_failed=1,
    )
    md = render_stage3_summary(stats)
    assert "# Stage 3" in md
    assert "rule: 6" in md
    assert "ai: 3" in md
    assert "row: 3" in md
    assert "high: 1" in md
    assert "cache hit rate: 67%" in md
    assert "validator-failed: 1" in md


def test_summary_handles_zero_calcs():
    stats = TranslationStats(
        total=0, by_source={}, rule_hits={}, ai_confidence={},
        ai_cache_hits=0, ai_cache_misses=0, validator_failed=0,
    )
    md = render_stage3_summary(stats)
    assert "total calculations: 0" in md
    assert "cache hit rate: n/a" in md
```

- [x] **Step 12.2: Run test — verify failure**

```bash
pytest tests/unit/translate/test_summary.py -v
```
Expected: ModuleNotFoundError.

- [x] **Step 12.3: Write `src/tableau2pbir/translate/summary.py`**

```python
"""Stage 3 summary.md renderer."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TranslationStats:
    total: int
    by_source: dict[str, int]               # "rule" | "ai" | "skip"
    rule_hits: dict[str, int]               # rule name → count
    ai_confidence: dict[str, int]           # "high" | "medium" | "low" → count
    ai_cache_hits: int
    ai_cache_misses: int
    validator_failed: int


def _fmt_hist(items: dict[str, int]) -> list[str]:
    if not items:
        return ["- (none)"]
    return [f"- {k}: {items[k]}" for k in sorted(items)]


def render_stage3_summary(stats: TranslationStats) -> str:
    cache_total = stats.ai_cache_hits + stats.ai_cache_misses
    if cache_total == 0:
        cache_rate = "n/a"
    else:
        cache_rate = f"{round(100 * stats.ai_cache_hits / cache_total)}%"

    lines = [
        "# Stage 3 — translate calcs",
        "",
        f"- total calculations: {stats.total}",
        f"- validator-failed: {stats.validator_failed}",
        f"- cache hit rate: {cache_rate}",
        "",
        "## Translation source",
        "",
        *_fmt_hist(stats.by_source),
        "",
        "## Rule hit histogram",
        "",
        *_fmt_hist(stats.rule_hits),
        "",
        "## AI confidence histogram",
        "",
        *_fmt_hist(stats.ai_confidence),
        "",
    ]
    return "\n".join(lines) + "\n"
```

- [x] **Step 12.4: Run test — verify pass**

```bash
pytest tests/unit/translate/test_summary.py -v
```
Expected: 2 passed.

- [x] **Step 12.5: Commit**

```bash
git add src/tableau2pbir/translate/summary.py \
        tests/unit/translate/test_summary.py
git commit -m "feat(translate): stage 3 summary renderer"
```

---

## Task 13: `s03_translate_calcs.py` — replace stub with real stage

**Files:**
- Modify: `src/tableau2pbir/stages/s03_translate_calcs.py`
- Create: `tests/unit/stages/test_s03_translate_calcs.py`
- Create: `tests/contract/test_stage3_calcs_contract.py`

- [x] **Step 13.1: Write the failing unit test**

`tests/unit/stages/test_s03_translate_calcs.py`:

```python
"""Stage 3 orchestrator. Reads stage-2 IR JSON, populates dax_expr on every
v1 calc, leaves deferred calcs untouched (their ids are already in
unsupported[]), routes syntax-gate failures to unsupported[]."""
from __future__ import annotations

import json
from pathlib import Path

from tableau2pbir.pipeline import StageContext
from tableau2pbir.stages.s03_translate_calcs import run


def _ctx(tmp_path: Path) -> StageContext:
    return StageContext(
        workbook_id="wb", output_dir=tmp_path, config={}, stage_number=3,
    )


def _ir_with_one_row_calc() -> dict:
    return {
        "ir_schema_version": "1.1.0",
        "source_path": "x.twb", "source_hash": "0" * 64,
        "tableau_version": "18.1", "config": {},
        "data_model": {
            "datasources": [], "tables": [], "relationships": [],
            "calculations": [{
                "id": "c_zn_sales", "name": "ZNSales", "scope": "measure",
                "tableau_expr": "ZN([Sales])", "dax_expr": None,
                "depends_on": [], "kind": "row", "phase": "row",
                "table_calc": None, "lod_fixed": None, "lod_relative": None,
                "owner_sheet_id": None,
            }],
            "parameters": [], "hierarchies": [], "sets": [],
        },
        "sheets": [], "dashboards": [], "unsupported": [],
    }


def test_stage3_populates_dax_via_rule(tmp_path: Path):
    result = run(_ir_with_one_row_calc(), _ctx(tmp_path))
    out = result.output
    [calc] = out["data_model"]["calculations"]
    assert calc["dax_expr"] == "COALESCE([Sales], 0)"
    # Stage 3 preserves every other field.
    assert calc["id"] == "c_zn_sales"


def test_stage3_skips_deferred_calcs(tmp_path: Path):
    ir = _ir_with_one_row_calc()
    # Mark the calc as already deferred (e.g. quick-table-calc).
    ir["data_model"]["calculations"][0]["kind"] = "table_calc"
    ir["unsupported"].append({
        "object_kind": "calc", "object_id": "c_zn_sales",
        "source_excerpt": "ZN([Sales])",
        "reason": "table calcs deferred", "code": "deferred_feature_table_calcs",
    })
    result = run(ir, _ctx(tmp_path))
    [calc] = result.output["data_model"]["calculations"]
    assert calc["dax_expr"] is None
```

- [x] **Step 13.2: Write the failing contract test**

`tests/contract/test_stage3_calcs_contract.py`:

```python
"""Contract: after stage 3, every non-deferred Calculation has
either a non-null dax_expr OR an UnsupportedItem with a stage-3 code."""
from __future__ import annotations

from pathlib import Path

from tableau2pbir.pipeline import StageContext
from tableau2pbir.stages.s03_translate_calcs import run

_STAGE3_CODES = frozenset({
    "calc_dax_syntax_failed", "calc_no_rule_or_ai",
})
_DEFERRED_PREFIX = "deferred_feature_"


def test_every_v1_calc_has_dax_or_is_unsupported(tmp_path: Path):
    ir = {
        "ir_schema_version": "1.1.0",
        "source_path": "x.twb", "source_hash": "0" * 64,
        "tableau_version": "18.1", "config": {},
        "data_model": {
            "datasources": [], "tables": [], "relationships": [],
            "calculations": [
                {
                    "id": "c1", "name": "C1", "scope": "measure",
                    "tableau_expr": "AVG([Sales])", "dax_expr": None,
                    "depends_on": [], "kind": "aggregate", "phase": "aggregate",
                    "table_calc": None, "lod_fixed": None, "lod_relative": None,
                    "owner_sheet_id": None,
                },
            ],
            "parameters": [], "hierarchies": [], "sets": [],
        },
        "sheets": [], "dashboards": [], "unsupported": [],
    }
    out = run(ir, StageContext(workbook_id="w", output_dir=tmp_path,
                                config={}, stage_number=3)).output
    deferred_ids = {
        u["object_id"] for u in out["unsupported"]
        if u["code"].startswith(_DEFERRED_PREFIX)
        or u["code"] in _STAGE3_CODES
    }
    for c in out["data_model"]["calculations"]:
        if c["id"] in deferred_ids:
            continue
        assert c["dax_expr"] is not None, \
            f"calc {c['id']} has no dax_expr and is not unsupported"
```

- [x] **Step 13.3: Run tests — verify failure**

```bash
pytest tests/unit/stages/test_s03_translate_calcs.py \
       tests/contract/test_stage3_calcs_contract.py -v
```
Expected: stage-3 stub returns no `data_model` key, so all assertions fail.

- [x] **Step 13.4: Replace `src/tableau2pbir/stages/s03_translate_calcs.py`**

```python
"""Stage 3 — translate calcs. See spec §6 Stage 3 + §16 v1 scope.

For every Calculation: parameter-rewrite, dispatch to row/aggregate/lod_fixed
rule, fall back to LLM on miss, syntax-gate the resulting DAX. Calcs already
in unsupported[] (with `deferred_feature_*` code from stage 2) are skipped."""
from __future__ import annotations

from typing import Any

from tableau2pbir.ir.common import UnsupportedItem
from tableau2pbir.ir.parameter import Parameter
from tableau2pbir.ir.workbook import Workbook
from tableau2pbir.llm.client import LLMClient
from tableau2pbir.pipeline import StageContext, StageResult
from tableau2pbir.translate.ai_fallback import translate_via_ai
from tableau2pbir.translate.rules.dispatch import dispatch_rule
from tableau2pbir.translate.summary import TranslationStats, render_stage3_summary
from tableau2pbir.translate.syntax_gate import is_valid_dax
from tableau2pbir.translate.topo import partition_lanes, topo_sort


def _make_client(ctx: StageContext) -> LLMClient:
    cache_dir = ctx.output_dir / ".llm-cache"
    return LLMClient(cache_dir=cache_dir)


def run(input_json: dict[str, Any], ctx: StageContext) -> StageResult:
    wb = Workbook.model_validate(input_json)
    deferred_ids = {
        u.object_id for u in wb.unsupported
        if u.code.startswith("deferred_feature_") or u.code == "calc_cycle"
    }
    parameters: tuple[Parameter, ...] = wb.data_model.parameters

    global_lane, per_sheet_lane = partition_lanes(wb.data_model.calculations)
    ordered = (*topo_sort(global_lane), *topo_sort(per_sheet_lane))

    by_source: dict[str, int] = {}
    rule_hits: dict[str, int] = {}
    ai_confidence: dict[str, int] = {}
    ai_cache_hits = 0
    ai_cache_misses = 0
    validator_failed = 0
    new_unsupported: list[UnsupportedItem] = list(wb.unsupported)
    new_calcs_by_id: dict[str, Any] = {}

    client: LLMClient | None = None
    for calc in ordered:
        if calc.id in deferred_ids:
            by_source["skip"] = by_source.get("skip", 0) + 1
            new_calcs_by_id[calc.id] = calc
            continue

        dax, rule_name = dispatch_rule(calc, parameters=parameters)
        if dax is not None and is_valid_dax(dax):
            by_source["rule"] = by_source.get("rule", 0) + 1
            if rule_name:
                rule_hits[rule_name] = rule_hits.get(rule_name, 0) + 1
            new_calcs_by_id[calc.id] = calc.model_copy(update={"dax_expr": dax})
            continue

        # AI fallback.
        if client is None:
            client = _make_client(ctx)
        cache_before = sum(
            1 for _ in client.cache.root.iterdir()
        ) if client.cache.root.exists() else 0
        ai = translate_via_ai(calc, fixture=None, client=client)
        cache_after = sum(
            1 for _ in client.cache.root.iterdir()
        ) if client.cache.root.exists() else 0
        if cache_after > cache_before:
            ai_cache_misses += 1
        else:
            ai_cache_hits += 1

        if ai is None:
            validator_failed += 1
            new_unsupported.append(UnsupportedItem(
                object_kind="calc", object_id=calc.id,
                source_excerpt=calc.tableau_expr[:200],
                reason=f"DAX syntax gate rejected output for {calc.name!r}",
                code="calc_dax_syntax_failed",
            ))
            new_calcs_by_id[calc.id] = calc
            continue

        by_source["ai"] = by_source.get("ai", 0) + 1
        conf = ai.get("confidence", "low")
        ai_confidence[conf] = ai_confidence.get(conf, 0) + 1
        new_calcs_by_id[calc.id] = calc.model_copy(
            update={"dax_expr": ai["dax_expr"]},
        )

    new_calcs = tuple(
        new_calcs_by_id[c.id] for c in wb.data_model.calculations
    )
    new_data_model = wb.data_model.model_copy(update={"calculations": new_calcs})
    new_wb = wb.model_copy(update={
        "data_model": new_data_model,
        "unsupported": tuple(new_unsupported),
    })

    stats = TranslationStats(
        total=len(wb.data_model.calculations),
        by_source=by_source, rule_hits=rule_hits,
        ai_confidence=ai_confidence,
        ai_cache_hits=ai_cache_hits, ai_cache_misses=ai_cache_misses,
        validator_failed=validator_failed,
    )
    return StageResult(
        output=new_wb.model_dump(mode="json"),
        summary_md=render_stage3_summary(stats),
        errors=(),
    )
```

- [x] **Step 13.5: Run tests — verify pass**

```bash
pytest tests/unit/stages/test_s03_translate_calcs.py \
       tests/contract/test_stage3_calcs_contract.py -v
```
Expected: all tests pass.

- [x] **Step 13.6: Run the wider suite to catch regressions**

```bash
pytest -q
```
Expected: green.

- [x] **Step 13.7: Commit**

```bash
git add src/tableau2pbir/stages/s03_translate_calcs.py \
        tests/unit/stages/test_s03_translate_calcs.py \
        tests/contract/test_stage3_calcs_contract.py
git commit -m "feat(stage3): translate calcs (rule + AI fallback + syntax gate)"
```

---

## Task 14: `visualmap/catalog.py` — PBIR visual catalog enum + slots

**Files:**
- Create: `src/tableau2pbir/visualmap/__init__.py` (empty)
- Create: `src/tableau2pbir/visualmap/catalog.py`
- Create: `tests/unit/visualmap/__init__.py` (empty)
- Create: `tests/unit/visualmap/test_catalog.py`

- [x] **Step 14.1: Write the failing test**

```python
"""PBIR visual catalog. v1 scope: bar (clustered + stacked), line, area,
scatter, table, pie, filledMap. Each visual type has a fixed set of
encoding slots (channel names) the validator enforces."""
from __future__ import annotations

from tableau2pbir.visualmap.catalog import VISUAL_TYPES, slots_for


def test_v1_visuals_present():
    expected = {
        "clusteredBarChart", "stackedBarChart",
        "lineChart", "areaChart", "scatterChart",
        "tableEx", "pieChart", "filledMap",
    }
    assert expected.issubset(VISUAL_TYPES)


def test_slots_for_clustered_bar():
    s = slots_for("clusteredBarChart")
    assert "category" in s
    assert "value" in s


def test_slots_for_unknown_visual_raises():
    import pytest
    with pytest.raises(KeyError):
        slots_for("doesNotExist")
```

- [x] **Step 14.2: Run test — verify failure**

```bash
pytest tests/unit/visualmap/test_catalog.py -v
```
Expected: ModuleNotFoundError.

- [x] **Step 14.3: Write `src/tableau2pbir/visualmap/catalog.py`**

```python
"""PBIR visual-type catalog (v1). Maps each supported visual_type to its
allowed encoding-channel slots. The set is what stage 4 emits; the AI
fallback's tool schema enumerates the same set so the model cannot invent
a non-existent visual."""
from __future__ import annotations

_SLOTS: dict[str, frozenset[str]] = {
    "clusteredBarChart": frozenset({"category", "value", "series", "tooltip"}),
    "stackedBarChart":   frozenset({"category", "value", "series", "tooltip"}),
    "lineChart":         frozenset({"category", "value", "series", "tooltip"}),
    "areaChart":         frozenset({"category", "value", "series", "tooltip"}),
    "scatterChart":      frozenset({"x", "y", "size", "color", "details", "tooltip"}),
    "tableEx":           frozenset({"values", "tooltip"}),  # matrix-like text-table
    "pieChart":          frozenset({"category", "value", "tooltip"}),
    "filledMap":         frozenset({"location", "value", "color", "tooltip"}),
}

VISUAL_TYPES: frozenset[str] = frozenset(_SLOTS)


def slots_for(visual_type: str) -> frozenset[str]:
    return _SLOTS[visual_type]
```

- [x] **Step 14.4: Run test — verify pass**

```bash
pytest tests/unit/visualmap/test_catalog.py -v
```
Expected: 3 passed.

- [x] **Step 14.5: Commit**

```bash
git add src/tableau2pbir/visualmap/__init__.py \
        src/tableau2pbir/visualmap/catalog.py \
        tests/unit/visualmap/__init__.py \
        tests/unit/visualmap/test_catalog.py
git commit -m "feat(visualmap): v1 PBIR visual catalog with channel slots"
```

---

## Task 15: `visualmap/dispatch.py` — `(mark_type, shelf_signature)` table

**Files:**
- Create: `src/tableau2pbir/visualmap/dispatch.py`
- Create: `tests/unit/visualmap/test_dispatch.py`

- [x] **Step 15.1: Write the failing test**

```python
"""Dispatch maps Tableau (mark_type, shelf_signature) to PBIR visual_type
+ channel bindings. shelf_signature is a tuple summarizing which shelves
are bound: ('rows', 'cols', 'color'?, ...)."""
from __future__ import annotations

from tableau2pbir.ir.common import FieldRef
from tableau2pbir.ir.sheet import Encoding, Sheet
from tableau2pbir.visualmap.dispatch import dispatch_visual


def _sheet(mark: str, *, rows=(), cols=(), color=None) -> Sheet:
    return Sheet(
        id="s1", name="S", datasource_refs=("ds1",),
        mark_type=mark,
        encoding=Encoding(rows=rows, columns=cols, color=color),
        filters=(), sort=(), dual_axis=False, reference_lines=(),
        uses_calculations=(),
    )


def _fr(col: str) -> FieldRef:
    return FieldRef(table_id="t", column_id=col)


def test_bar_with_dim_on_rows_and_measure_on_cols():
    sh = _sheet("bar", rows=(_fr("region"),), cols=(_fr("sales"),))
    pv = dispatch_visual(sh)
    assert pv is not None
    assert pv.visual_type == "clusteredBarChart"
    channels = {b.channel for b in pv.encoding_bindings}
    assert "category" in channels and "value" in channels


def test_line_chart():
    sh = _sheet("line", rows=(_fr("sales"),), cols=(_fr("date"),))
    pv = dispatch_visual(sh)
    assert pv is not None and pv.visual_type == "lineChart"


def test_pie_with_color_dim_and_measure_size():
    sh = _sheet("pie", rows=(_fr("sales"),), color=_fr("region"))
    pv = dispatch_visual(sh)
    assert pv is not None and pv.visual_type == "pieChart"


def test_text_mark_to_table():
    sh = _sheet("text", rows=(_fr("sales"),), cols=(_fr("region"),))
    pv = dispatch_visual(sh)
    assert pv is not None and pv.visual_type == "tableEx"


def test_unsupported_mark_returns_none():
    sh = _sheet("polygon", rows=(_fr("x"),))
    assert dispatch_visual(sh) is None
```

- [x] **Step 15.2: Run test — verify failure**

```bash
pytest tests/unit/visualmap/test_dispatch.py -v
```
Expected: ModuleNotFoundError.

- [x] **Step 15.3: Write `src/tableau2pbir/visualmap/dispatch.py`**

```python
"""Tableau (mark_type, shelf_signature) → PBIR (visual_type, bindings).

v1 dispatch table. Mark types not covered return None so the caller falls
back to AI or routes to unsupported[]."""
from __future__ import annotations

from tableau2pbir.ir.common import FieldRef
from tableau2pbir.ir.sheet import EncodingBinding, PbirVisual, Sheet


def _bind(channel: str, fr: FieldRef) -> EncodingBinding:
    return EncodingBinding(channel=channel, source_field_id=fr.column_id)


def _has(rows: tuple[FieldRef, ...]) -> FieldRef | None:
    return rows[0] if rows else None


def dispatch_visual(sheet: Sheet) -> PbirVisual | None:
    mark = sheet.mark_type
    enc = sheet.encoding
    rows = enc.rows
    cols = enc.columns
    color = enc.color

    if mark in ("bar", "automatic") and rows and cols:
        bindings = [_bind("category", rows[0]), _bind("value", cols[0])]
        if color:
            bindings.append(_bind("series", color))
        return PbirVisual(
            visual_type="clusteredBarChart",
            encoding_bindings=tuple(bindings),
            format={},
        )

    if mark == "line" and rows and cols:
        bindings = [_bind("category", cols[0]), _bind("value", rows[0])]
        if color:
            bindings.append(_bind("series", color))
        return PbirVisual(
            visual_type="lineChart",
            encoding_bindings=tuple(bindings),
            format={},
        )

    if mark == "area" and rows and cols:
        return PbirVisual(
            visual_type="areaChart",
            encoding_bindings=(
                _bind("category", cols[0]), _bind("value", rows[0]),
            ),
            format={},
        )

    if mark in ("circle", "shape", "scatter") and rows and cols:
        bindings = [_bind("x", cols[0]), _bind("y", rows[0])]
        if enc.size:
            bindings.append(_bind("size", enc.size))
        if color:
            bindings.append(_bind("color", color))
        return PbirVisual(
            visual_type="scatterChart",
            encoding_bindings=tuple(bindings),
            format={},
        )

    if mark == "pie" and rows:
        bindings = [_bind("value", rows[0])]
        if color:
            bindings.insert(0, _bind("category", color))
        return PbirVisual(
            visual_type="pieChart",
            encoding_bindings=tuple(bindings),
            format={},
        )

    if mark == "text":
        bindings = []
        for r in rows:
            bindings.append(_bind("values", r))
        for c in cols:
            bindings.append(_bind("values", c))
        if not bindings:
            return None
        return PbirVisual(
            visual_type="tableEx",
            encoding_bindings=tuple(bindings),
            format={},
        )

    if mark == "map" and rows and cols:
        return PbirVisual(
            visual_type="filledMap",
            encoding_bindings=(
                _bind("location", cols[0]), _bind("value", rows[0]),
            ),
            format={},
        )

    return None
```

- [x] **Step 15.4: Run test — verify pass**

```bash
pytest tests/unit/visualmap/test_dispatch.py -v
```
Expected: 5 passed.

- [x] **Step 15.5: Commit**

```bash
git add src/tableau2pbir/visualmap/dispatch.py \
        tests/unit/visualmap/test_dispatch.py
git commit -m "feat(visualmap): v1 (mark_type, shelf) dispatch table"
```

---

## Task 16: `visualmap/validator.py` — binding source/slot validator

**Files:**
- Create: `src/tableau2pbir/visualmap/validator.py`
- Create: `tests/unit/visualmap/test_validator.py`

- [x] **Step 16.1: Write the failing test**

```python
"""Validator: every binding's source_field_id resolves to an IR column or
calc; every binding.channel is in the visual's slot set."""
from __future__ import annotations

from tableau2pbir.ir.sheet import EncodingBinding, PbirVisual
from tableau2pbir.visualmap.validator import validate_visual


def test_valid_visual_passes():
    pv = PbirVisual(
        visual_type="clusteredBarChart",
        encoding_bindings=(
            EncodingBinding(channel="category", source_field_id="t__col__region"),
            EncodingBinding(channel="value", source_field_id="t__col__sales"),
        ),
        format={},
    )
    known_field_ids = frozenset({"t__col__region", "t__col__sales"})
    errors = validate_visual(pv, known_field_ids=known_field_ids)
    assert errors == ()


def test_unknown_source_field_reported():
    pv = PbirVisual(
        visual_type="clusteredBarChart",
        encoding_bindings=(
            EncodingBinding(channel="value", source_field_id="t__col__missing"),
        ),
        format={},
    )
    errors = validate_visual(pv, known_field_ids=frozenset())
    assert any("missing" in e for e in errors)


def test_invalid_slot_reported():
    pv = PbirVisual(
        visual_type="clusteredBarChart",
        encoding_bindings=(
            EncodingBinding(channel="bogus", source_field_id="t__col__sales"),
        ),
        format={},
    )
    errors = validate_visual(
        pv, known_field_ids=frozenset({"t__col__sales"}),
    )
    assert any("bogus" in e for e in errors)


def test_unknown_visual_type_reported():
    pv = PbirVisual(
        visual_type="madeUp",
        encoding_bindings=(),
        format={},
    )
    errors = validate_visual(pv, known_field_ids=frozenset())
    assert any("madeUp" in e for e in errors)
```

- [x] **Step 16.2: Run test — verify failure**

```bash
pytest tests/unit/visualmap/test_validator.py -v
```
Expected: ModuleNotFoundError.

- [x] **Step 16.3: Write `src/tableau2pbir/visualmap/validator.py`**

```python
"""Stage-4 validator: returns a tuple of human-readable error strings.
Empty tuple means valid."""
from __future__ import annotations

from tableau2pbir.ir.sheet import PbirVisual
from tableau2pbir.visualmap.catalog import VISUAL_TYPES, slots_for


def validate_visual(
    pv: PbirVisual, *, known_field_ids: frozenset[str],
) -> tuple[str, ...]:
    errors: list[str] = []
    if pv.visual_type not in VISUAL_TYPES:
        errors.append(f"unknown visual_type: {pv.visual_type!r}")
        return tuple(errors)
    allowed = slots_for(pv.visual_type)
    for b in pv.encoding_bindings:
        if b.channel not in allowed:
            errors.append(
                f"channel {b.channel!r} not allowed for {pv.visual_type}"
            )
        if b.source_field_id not in known_field_ids:
            errors.append(f"unknown source_field_id: {b.source_field_id!r}")
    return tuple(errors)
```

- [x] **Step 16.4: Run test — verify pass**

```bash
pytest tests/unit/visualmap/test_validator.py -v
```
Expected: 4 passed.

- [x] **Step 16.5: Commit**

```bash
git add src/tableau2pbir/visualmap/validator.py \
        tests/unit/visualmap/test_validator.py
git commit -m "feat(visualmap): visual binding validator"
```

---

## Task 17: `visualmap/ai_fallback.py` + map_visual prompt + snapshot

**Files:**
- Modify: `src/tableau2pbir/llm/prompts/map_visual/system.md`
- Modify: `src/tableau2pbir/llm/prompts/map_visual/VERSION`
- Create: `src/tableau2pbir/visualmap/ai_fallback.py`
- Create: `tests/unit/visualmap/test_ai_fallback.py`
- Create: `tests/llm_snapshots/map_visual/ai_only_combo_chart.json`

- [x] **Step 17.1: Write the failing test**

```python
"""map_visual AI fallback — snapshot replay returns a PbirVisual; if
visual_type is not in the catalog, the validator drops the response."""
from __future__ import annotations

from pathlib import Path

from tableau2pbir.ir.common import FieldRef
from tableau2pbir.ir.sheet import Encoding, Sheet
from tableau2pbir.llm.client import LLMClient
from tableau2pbir.visualmap.ai_fallback import map_visual_via_ai


def _sheet() -> Sheet:
    return Sheet(
        id="s1", name="Combo", datasource_refs=("ds1",),
        mark_type="bar",
        encoding=Encoding(
            rows=(FieldRef(table_id="t", column_id="t__col__sales"),),
            columns=(FieldRef(table_id="t", column_id="t__col__region"),),
        ),
        filters=(), sort=(), dual_axis=True,
        reference_lines=(), uses_calculations=(),
    )


def test_replay_returns_visual_passing_validation(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PYTEST_SNAPSHOT", "replay")
    client = LLMClient(cache_dir=tmp_path / "cache")
    pv = map_visual_via_ai(
        _sheet(), fixture="ai_only_combo_chart", client=client,
        known_field_ids=frozenset({"t__col__sales", "t__col__region"}),
    )
    assert pv is not None
    assert pv.visual_type in ("clusteredBarChart", "lineChart")


def test_replay_drops_unknown_visual_type(tmp_path: Path, monkeypatch):
    snaps = tmp_path / "snaps"
    (snaps / "map_visual").mkdir(parents=True)
    (snaps / "map_visual" / "broken.json").write_text(
        '{"visual_type": "madeUp", "encoding_bindings": [], '
        '"confidence": "low", "notes": ""}',
        encoding="utf-8",
    )
    monkeypatch.setenv("PYTEST_SNAPSHOT", "replay")
    client = LLMClient(cache_dir=tmp_path / "cache", snapshot_root=snaps)
    pv = map_visual_via_ai(
        _sheet(), fixture="broken", client=client,
        known_field_ids=frozenset(),
    )
    assert pv is None
```

- [x] **Step 17.2: Bump map_visual prompt VERSION + system.md**

`src/tableau2pbir/llm/prompts/map_visual/VERSION`:

```
0.2.0
```

`src/tableau2pbir/llm/prompts/map_visual/system.md`:

```markdown
You map a Tableau worksheet to a single PBIR visual + encoding plan.

# Input

A JSON object summarizing the sheet:
- `id`           — sheet IR id
- `mark_type`    — Tableau mark (`bar`, `line`, `area`, `circle`, `pie`, `text`, `map`, ...)
- `shelves`     — `{rows, columns, color, size, label, tooltip, detail, shape, angle}` mapping shelf name → list of `{table_id, column_id}` field refs
- `dual_axis`   — bool

# Output

Call the `map_visual_output` tool with:
- `visual_type`    — must be one of:
  `clusteredBarChart`, `stackedBarChart`, `lineChart`, `areaChart`,
  `scatterChart`, `tableEx`, `pieChart`, `filledMap`
- `encoding_bindings` — list of `{channel, field_ref}`. `channel` must be one of the
  visual's allowed slots; `field_ref` must be a `column_id` from the input shelves.
- `confidence`  — `high` / `medium` / `low`
- `notes`       — one short sentence explaining the choice

# Rules

- Never invent a visual_type outside the list above.
- Never reference a `field_ref` not present in `shelves`.
- For dual-axis with mismatched mark types, prefer the closest single visual and report `medium` confidence.
```

- [x] **Step 17.3: Create snapshot**

`tests/llm_snapshots/map_visual/ai_only_combo_chart.json`:

```json
{
  "visual_type": "clusteredBarChart",
  "encoding_bindings": [
    {"channel": "category", "field_ref": "t__col__region"},
    {"channel": "value",    "field_ref": "t__col__sales"}
  ],
  "confidence": "medium",
  "notes": "Synthetic snapshot — combo collapsed to bar."
}
```

- [x] **Step 17.4: Write `src/tableau2pbir/visualmap/ai_fallback.py`**

```python
"""AI fallback for stage 4. Calls LLMClient.map_visual, builds a PbirVisual,
runs the validator, returns None on failure (caller routes to unsupported[])."""
from __future__ import annotations

from typing import Any

from tableau2pbir.ir.sheet import EncodingBinding, PbirVisual, Sheet
from tableau2pbir.llm.client import LLMClient
from tableau2pbir.visualmap.validator import validate_visual


def _sheet_subset(sheet: Sheet, fixture: str | None) -> dict[str, Any]:
    enc = sheet.encoding
    payload: dict[str, Any] = {
        "id": sheet.id,
        "mark_type": sheet.mark_type,
        "dual_axis": sheet.dual_axis,
        "shelves": {
            "rows":    [_ref(f) for f in enc.rows],
            "columns": [_ref(f) for f in enc.columns],
            "color":   [_ref(enc.color)] if enc.color else [],
            "size":    [_ref(enc.size)]  if enc.size  else [],
            "label":   [_ref(enc.label)] if enc.label else [],
            "tooltip": [_ref(enc.tooltip)] if enc.tooltip else [],
            "detail":  [_ref(f) for f in enc.detail],
            "shape":   [_ref(enc.shape)] if enc.shape else [],
            "angle":   [_ref(enc.angle)] if enc.angle else [],
        },
    }
    if fixture is not None:
        payload["fixture"] = fixture
    return payload


def _ref(fr: Any) -> dict[str, str]:
    return {"table_id": fr.table_id, "column_id": fr.column_id}


def map_visual_via_ai(
    sheet: Sheet, *, fixture: str | None, client: LLMClient,
    known_field_ids: frozenset[str],
) -> PbirVisual | None:
    response = client.map_visual(_sheet_subset(sheet, fixture))
    bindings = tuple(
        EncodingBinding(
            channel=str(b["channel"]),
            source_field_id=str(b["field_ref"]),
        )
        for b in response.get("encoding_bindings", [])
    )
    pv = PbirVisual(
        visual_type=str(response.get("visual_type", "")),
        encoding_bindings=bindings,
        format={},
    )
    if validate_visual(pv, known_field_ids=known_field_ids):
        return None
    return pv
```

- [x] **Step 17.5: Run test — verify pass**

```bash
pytest tests/unit/visualmap/test_ai_fallback.py -v
```
Expected: 2 passed.

- [x] **Step 17.6: Commit**

```bash
git add src/tableau2pbir/llm/prompts/map_visual/VERSION \
        src/tableau2pbir/llm/prompts/map_visual/system.md \
        src/tableau2pbir/visualmap/ai_fallback.py \
        tests/unit/visualmap/test_ai_fallback.py \
        tests/llm_snapshots/map_visual/ai_only_combo_chart.json
git commit -m "feat(visualmap): map_visual AI fallback w/ catalog-constrained validation"
```

---

## Task 18: `visualmap/summary.py` — stage 4 summary renderer

**Files:**
- Create: `src/tableau2pbir/visualmap/summary.py`
- Create: `tests/unit/visualmap/test_summary.py`

- [x] **Step 18.1: Write the failing test**

```python
"""Stage-4 summary: visual-type histogram, rule-vs-AI rate, low-confidence
flags, unsupported mark types."""
from __future__ import annotations

from tableau2pbir.visualmap.summary import VisualMapStats, render_stage4_summary


def test_summary_includes_required_sections():
    stats = VisualMapStats(
        total_sheets=5,
        by_source={"rule": 3, "ai": 1, "skip": 1},
        visual_type_hist={"clusteredBarChart": 2, "lineChart": 1, "tableEx": 1},
        ai_low_confidence_sheet_ids=("s_low_conf",),
        unsupported_mark_types={"polygon": 1},
    )
    md = render_stage4_summary(stats)
    assert "# Stage 4" in md
    assert "rule: 3" in md
    assert "clusteredBarChart: 2" in md
    assert "s_low_conf" in md
    assert "polygon: 1" in md
```

- [x] **Step 18.2: Run test — verify failure**

```bash
pytest tests/unit/visualmap/test_summary.py -v
```
Expected: ModuleNotFoundError.

- [x] **Step 18.3: Write `src/tableau2pbir/visualmap/summary.py`**

```python
"""Stage 4 summary.md renderer."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VisualMapStats:
    total_sheets: int
    by_source: dict[str, int]
    visual_type_hist: dict[str, int]
    ai_low_confidence_sheet_ids: tuple[str, ...]
    unsupported_mark_types: dict[str, int]


def _hist(items: dict[str, int]) -> list[str]:
    if not items:
        return ["- (none)"]
    return [f"- {k}: {items[k]}" for k in sorted(items)]


def render_stage4_summary(stats: VisualMapStats) -> str:
    lines = [
        "# Stage 4 — map visuals",
        "",
        f"- total sheets: {stats.total_sheets}",
        "",
        "## Translation source",
        "",
        *_hist(stats.by_source),
        "",
        "## Visual type histogram",
        "",
        *_hist(stats.visual_type_hist),
        "",
        "## Low-confidence AI decisions",
        "",
    ]
    if stats.ai_low_confidence_sheet_ids:
        lines.extend(f"- {sid}" for sid in sorted(stats.ai_low_confidence_sheet_ids))
    else:
        lines.append("- (none)")
    lines.extend([
        "",
        "## Unsupported mark types",
        "",
        *_hist(stats.unsupported_mark_types),
        "",
    ])
    return "\n".join(lines) + "\n"
```

- [x] **Step 18.4: Run test — verify pass**

```bash
pytest tests/unit/visualmap/test_summary.py -v
```
Expected: 1 passed.

- [x] **Step 18.5: Commit**

```bash
git add src/tableau2pbir/visualmap/summary.py \
        tests/unit/visualmap/test_summary.py
git commit -m "feat(visualmap): stage 4 summary renderer"
```

---

## Task 19: `s04_map_visuals.py` — replace stub with real stage

**Files:**
- Modify: `src/tableau2pbir/stages/s04_map_visuals.py`
- Create: `tests/unit/stages/test_s04_map_visuals.py`
- Create: `tests/contract/test_stage4_visual_contract.py`

- [ ] **Step 19.1: Write the failing unit test**

```python
"""Stage 4 orchestrator. Reads stage-3 IR, attaches PbirVisual to every
sheet whose mark is in the v1 catalog; routes the rest to unsupported[]."""
from __future__ import annotations

from pathlib import Path

from tableau2pbir.pipeline import StageContext
from tableau2pbir.stages.s04_map_visuals import run


def _ir_one_bar_sheet() -> dict:
    return {
        "ir_schema_version": "1.1.0",
        "source_path": "x.twb", "source_hash": "0" * 64,
        "tableau_version": "18.1", "config": {},
        "data_model": {
            "datasources": [], "tables": [{
                "id": "t", "name": "Sales", "datasource_id": "ds",
                "column_ids": ("t__col__region", "t__col__sales"),
                "primary_key": None,
            }], "relationships": [],
            "calculations": [], "parameters": [],
            "hierarchies": [], "sets": [],
        },
        "sheets": [{
            "id": "s1", "name": "Bars",
            "datasource_refs": ("ds",), "mark_type": "bar",
            "encoding": {
                "rows": [{"table_id": "t", "column_id": "t__col__region"}],
                "columns": [{"table_id": "t", "column_id": "t__col__sales"}],
                "color": None, "size": None, "label": None,
                "tooltip": None, "detail": [],
                "shape": None, "angle": None,
            },
            "filters": [], "sort": [], "dual_axis": False,
            "reference_lines": [], "uses_calculations": [],
            "pbir_visual": None,
        }],
        "dashboards": [], "unsupported": [],
    }


def test_stage4_attaches_pbir_visual_for_bar(tmp_path: Path):
    ctx = StageContext(workbook_id="w", output_dir=tmp_path,
                        config={}, stage_number=4)
    out = run(_ir_one_bar_sheet(), ctx).output
    [sh] = out["sheets"]
    pv = sh["pbir_visual"]
    assert pv is not None
    assert pv["visual_type"] == "clusteredBarChart"


def test_stage4_routes_unsupported_mark(tmp_path: Path):
    ir = _ir_one_bar_sheet()
    ir["sheets"][0]["mark_type"] = "polygon"
    ctx = StageContext(workbook_id="w", output_dir=tmp_path,
                        config={}, stage_number=4)
    out = run(ir, ctx).output
    [sh] = out["sheets"]
    assert sh["pbir_visual"] is None
    codes = [u["code"] for u in out["unsupported"]]
    assert "unsupported_mark_polygon" in codes
```

- [ ] **Step 19.2: Write the failing contract test**

`tests/contract/test_stage4_visual_contract.py`:

```python
"""Contract: every Sheet either has pbir_visual set OR an UnsupportedItem
with a stage-4 code."""
from __future__ import annotations

from pathlib import Path

from tableau2pbir.pipeline import StageContext
from tableau2pbir.stages.s04_map_visuals import run

_STAGE4_CODES_PREFIXES = ("unsupported_mark_", "visual_binding_invalid")


def test_every_sheet_has_visual_or_unsupported(tmp_path: Path):
    ir = {
        "ir_schema_version": "1.1.0",
        "source_path": "x.twb", "source_hash": "0" * 64,
        "tableau_version": "18.1", "config": {},
        "data_model": {
            "datasources": [], "tables": [{
                "id": "t", "name": "T", "datasource_id": "ds",
                "column_ids": ("t__col__a",), "primary_key": None,
            }], "relationships": [],
            "calculations": [], "parameters": [],
            "hierarchies": [], "sets": [],
        },
        "sheets": [{
            "id": "s1", "name": "Polly",
            "datasource_refs": ("ds",), "mark_type": "polygon",
            "encoding": {
                "rows": [], "columns": [],
                "color": None, "size": None, "label": None,
                "tooltip": None, "detail": [], "shape": None, "angle": None,
            },
            "filters": [], "sort": [], "dual_axis": False,
            "reference_lines": [], "uses_calculations": [],
            "pbir_visual": None,
        }],
        "dashboards": [], "unsupported": [],
    }
    out = run(ir, StageContext(workbook_id="w", output_dir=tmp_path,
                                config={}, stage_number=4)).output
    unsupported_sheet_ids = {
        u["object_id"] for u in out["unsupported"]
        if any(u["code"].startswith(p) or u["code"] == p
               for p in _STAGE4_CODES_PREFIXES)
    }
    for sh in out["sheets"]:
        assert sh["pbir_visual"] is not None or sh["id"] in unsupported_sheet_ids
```

- [ ] **Step 19.3: Run tests — verify failure**

```bash
pytest tests/unit/stages/test_s04_map_visuals.py \
       tests/contract/test_stage4_visual_contract.py -v
```
Expected: stub stage 4 has no `sheets` key in output → assertions fail.

- [ ] **Step 19.4: Replace `src/tableau2pbir/stages/s04_map_visuals.py`**

```python
"""Stage 4 — map visuals. See spec §6 Stage 4 + §16 v1 mark scope."""
from __future__ import annotations

from typing import Any

from tableau2pbir.ir.common import UnsupportedItem
from tableau2pbir.ir.workbook import Workbook
from tableau2pbir.llm.client import LLMClient
from tableau2pbir.pipeline import StageContext, StageResult
from tableau2pbir.visualmap.ai_fallback import map_visual_via_ai
from tableau2pbir.visualmap.dispatch import dispatch_visual
from tableau2pbir.visualmap.summary import VisualMapStats, render_stage4_summary
from tableau2pbir.visualmap.validator import validate_visual


def _make_client(ctx: StageContext) -> LLMClient:
    return LLMClient(cache_dir=ctx.output_dir / ".llm-cache")


def _known_field_ids(wb: Workbook) -> frozenset[str]:
    fids: set[str] = set()
    for tbl in wb.data_model.tables:
        fids.update(tbl.column_ids)
    fids.update(c.id for c in wb.data_model.calculations)
    return frozenset(fids)


def run(input_json: dict[str, Any], ctx: StageContext) -> StageResult:
    wb = Workbook.model_validate(input_json)
    known_fids = _known_field_ids(wb)

    by_source: dict[str, int] = {}
    visual_hist: dict[str, int] = {}
    low_conf: list[str] = []
    unsupported_marks: dict[str, int] = {}
    new_unsupported: list[UnsupportedItem] = list(wb.unsupported)
    new_sheets = []

    client: LLMClient | None = None
    for sheet in wb.sheets:
        pv = dispatch_visual(sheet)
        chose_source = "rule" if pv is not None else None

        if pv is None and sheet.mark_type in ("bar", "line", "area",
                                                "circle", "shape", "scatter",
                                                "pie", "text", "map",
                                                "automatic"):
            # Mark is in the v1 family but dispatch missed (e.g. dual-axis).
            if client is None:
                client = _make_client(ctx)
            pv = map_visual_via_ai(
                sheet, fixture=None, client=client,
                known_field_ids=known_fids,
            )
            chose_source = "ai" if pv is not None else None

        if pv is None:
            mt = sheet.mark_type
            unsupported_marks[mt] = unsupported_marks.get(mt, 0) + 1
            new_unsupported.append(UnsupportedItem(
                object_kind="mark", object_id=sheet.id,
                source_excerpt=mt,
                reason=f"Mark type {mt!r} not in v1 visual catalog",
                code=f"unsupported_mark_{mt}",
            ))
            new_sheets.append(sheet)
            by_source["skip"] = by_source.get("skip", 0) + 1
            continue

        errors = validate_visual(pv, known_field_ids=known_fids)
        if errors:
            new_unsupported.append(UnsupportedItem(
                object_kind="mark", object_id=sheet.id,
                source_excerpt="; ".join(errors)[:200],
                reason="visual binding validation failed",
                code="visual_binding_invalid",
            ))
            new_sheets.append(sheet)
            by_source["skip"] = by_source.get("skip", 0) + 1
            continue

        new_sheets.append(sheet.model_copy(update={"pbir_visual": pv}))
        by_source[chose_source or "rule"] = by_source.get(chose_source or "rule", 0) + 1
        visual_hist[pv.visual_type] = visual_hist.get(pv.visual_type, 0) + 1

    new_wb = wb.model_copy(update={
        "sheets": tuple(new_sheets),
        "unsupported": tuple(new_unsupported),
    })
    stats = VisualMapStats(
        total_sheets=len(wb.sheets), by_source=by_source,
        visual_type_hist=visual_hist,
        ai_low_confidence_sheet_ids=tuple(low_conf),
        unsupported_mark_types=unsupported_marks,
    )
    return StageResult(
        output=new_wb.model_dump(mode="json"),
        summary_md=render_stage4_summary(stats),
        errors=(),
    )
```

- [ ] **Step 19.5: Run tests — verify pass**

```bash
pytest tests/unit/stages/test_s04_map_visuals.py \
       tests/contract/test_stage4_visual_contract.py -v
```
Expected: all pass.

- [ ] **Step 19.6: Commit**

```bash
git add src/tableau2pbir/stages/s04_map_visuals.py \
        tests/unit/stages/test_s04_map_visuals.py \
        tests/contract/test_stage4_visual_contract.py
git commit -m "feat(stage4): map visuals (dispatch + AI fallback + validator)"
```

---

## Task 20: synthetic fixture `visual_marks_v1.twb` + integration test

**Files:**
- Create: `tests/golden/synthetic/visual_marks_v1.twb`
- Create: `tests/integration/test_stage3_stage4_integration.py`

- [ ] **Step 20.1: Author the fixture**

`tests/golden/synthetic/visual_marks_v1.twb` — author by hand or by adapting an existing fixture. Minimum content: one CSV datasource (`Orders`) with columns `Region` (string, dim) and `Sales` (number, measure); seven worksheets named `bars`, `lines`, `areas`, `scatters`, `pies`, `tables`, `maps` (the last with a `Country` column added) — each binding the appropriate shelves; one dashboard tiling all seven. Author by copying the structure of `tests/golden/synthetic/trivial.twb` (already in repo) and changing one `<mark class>` per sheet. After authoring, sanity-check it loads:

```bash
python -c "from tableau2pbir.util.zip import read_workbook; from pathlib import Path; print(len(read_workbook(Path('tests/golden/synthetic/visual_marks_v1.twb')).xml_bytes))"
```

Expected: prints a non-zero byte count without an exception.

- [ ] **Step 20.2: Write the failing integration test**

`tests/integration/test_stage3_stage4_integration.py`:

```python
"""End-to-end stage 1 → 4 against synthetic fixtures. Stages 5–8 still
run as no-op stubs."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


def _convert(fixture: Path, out: Path, *, env: dict[str, str] | None = None):
    return subprocess.run(
        [sys.executable, "-m", "tableau2pbir.cli", "convert",
         str(fixture), "--out", str(out)],
        capture_output=True, text=True,
        env={**os.environ, **(env or {})},
    )


def _stage_json(out: Path, wb_name: str, n: int, name: str) -> dict:
    return json.loads(
        (out / wb_name / "stages" / f"{n:02d}_{name}.json")
        .read_text(encoding="utf-8"),
    )


@pytest.mark.integration
def test_stage3_translates_row_calc(tmp_path: Path, synthetic_fixtures_dir: Path):
    out = tmp_path / "out"
    result = _convert(synthetic_fixtures_dir / "calc_row.twb", out,
                      env={"PYTEST_SNAPSHOT": "replay"})
    assert result.returncode == 0, result.stderr
    ir3 = _stage_json(out, "calc_row", 3, "translate_calcs")
    [calc] = [c for c in ir3["data_model"]["calculations"]
              if c["kind"] == "row"]
    assert calc["dax_expr"] is not None


@pytest.mark.integration
def test_stage3_skips_deferred_table_calc(tmp_path: Path, synthetic_fixtures_dir: Path):
    out = tmp_path / "out"
    result = _convert(synthetic_fixtures_dir / "calc_quick_table.twb", out,
                      env={"PYTEST_SNAPSHOT": "replay"})
    assert result.returncode == 0, result.stderr
    ir3 = _stage_json(out, "calc_quick_table", 3, "translate_calcs")
    deferred_codes = [u["code"] for u in ir3["unsupported"]
                      if u["code"].startswith("deferred_feature_")]
    assert "deferred_feature_table_calcs" in deferred_codes
    # The deferred calc has no dax_expr.
    for c in ir3["data_model"]["calculations"]:
        if c["kind"] == "table_calc":
            assert c["dax_expr"] is None


@pytest.mark.integration
def test_stage4_attaches_visual_for_bar_fixture(
    tmp_path: Path, synthetic_fixtures_dir: Path,
):
    out = tmp_path / "out"
    result = _convert(synthetic_fixtures_dir / "visual_marks_v1.twb", out,
                      env={"PYTEST_SNAPSHOT": "replay"})
    assert result.returncode == 0, result.stderr
    ir4 = _stage_json(out, "visual_marks_v1", 4, "map_visuals")
    visual_types = {sh["pbir_visual"]["visual_type"]
                    for sh in ir4["sheets"]
                    if sh["pbir_visual"] is not None}
    # At least the bar and line marks should map to v1 visuals.
    assert "clusteredBarChart" in visual_types
    assert "lineChart" in visual_types
```

- [ ] **Step 20.3: Run tests — verify pass**

```bash
pytest tests/integration/test_stage3_stage4_integration.py -v
```
Expected: 3 passed.

- [ ] **Step 20.4: Run full suite — verify no regressions**

```bash
pytest -q
make lint
make typecheck
```
Expected: all green.

- [ ] **Step 20.5: Commit**

```bash
git add tests/golden/synthetic/visual_marks_v1.twb \
        tests/integration/test_stage3_stage4_integration.py
git commit -m "test(integration): stage 3+4 end-to-end on synthetic fixtures"
```

---

## Task 21: update `CLAUDE.md` plan tracking and write next-plan placeholder

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 21.1: Update the implementation tracking table**

In `CLAUDE.md`, replace the Plan 3 row:

```
| 3 | Stage 3 & 4 — Calc Translation + Visual Mapping | 🔲 NEXT | TBD |
```

with:

```
| 3 | Stage 3 & 4 — Calc Translation + Visual Mapping | ✅ DONE | `docs/superpowers/plans/2026-04-26-plan-3-calc-translation-visual-mapping.md` |
```

and update Plan 4 status from `🔲 TODO` to `🔲 NEXT` (no other table edits).

- [ ] **Step 21.2: Run lint to confirm no markdown trailing-whitespace etc.**

```bash
make lint
```

Expected: clean.

- [ ] **Step 21.3: Commit**

```bash
git add CLAUDE.md
git commit -m "chore(plan3): mark Plan 3 complete; advance CLAUDE.md to Plan 4 NEXT"
```

---

## Self-review checklist (run before declaring Plan 3 complete)

- [ ] Every spec §6 Stage 3 bullet has a task: topo two-lane (Task 5); rule library row/aggregate/lod_fixed (Tasks 6–8); LLM fallback (Task 11); syntax gate (Task 3); param-intent rewriting (Task 4); skipping deferred kinds (Task 13); summary.md (Task 12). Per-sheet measure naming for LOD INCLUDE/EXCLUDE — out of scope (v1 §16) but lane scaffolding present (Task 5).
- [ ] Every spec §6 Stage 4 bullet has a task: dispatch table (Task 15); LLM fallback constrained to PBIR enum (Task 17); validator on bindings/slots (Task 16); summary (Task 18); IR Sheet annotation (Task 1).
- [ ] No placeholders, no "TBD", no "similar to Task N", no "fill in details" in any step.
- [ ] Type names are consistent: `PbirVisual`, `EncodingBinding`, `TranslationStats`, `VisualMapStats` used identically wherever referenced.
- [ ] `is_valid_dax`, `dispatch_rule`, `translate_via_ai`, `map_visual_via_ai`, `dispatch_visual`, `validate_visual`, `slots_for`, `VISUAL_TYPES` — every function/symbol used in a later task is defined in an earlier task.
- [ ] IR schema bump (1.0.0 → 1.1.0) wired everywhere (Task 1) including the contract test.
- [ ] `sqlglot` declared as a runtime dep before any code uses it (Task 2 precedes Task 3).
- [ ] Snapshot fixtures committed for every AI-fallback test path (Tasks 10, 11, 17).
- [ ] Prompt VERSION bumps committed alongside `system.md` rewrites (Tasks 10, 17). `tool_schema.json` bytes left unchanged so existing cache files survive.
- [ ] CLAUDE.md tracking table updated as the final task (Task 21).
