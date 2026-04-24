# Plan 1 — Scaffolding & Infra — Tableau → PBIR Converter

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a runnable skeleton of the `tableau2pbir` package. End state: `tableau2pbir convert tests/golden/synthetic/trivial.twb --out ./out/` runs through all 8 stages (each a no-op), writes the `./out/<wb>/stages/*.json` artifacts and `unsupported.json`, exits 0, and the full pytest suite is green.

**Architecture:** Python library with a thin `argparse` CLI on top. IR dataclasses use **pydantic v2** so JSON Schema is auto-generated via `.model_json_schema()`. Each stage is a pure function `run(input_json, ctx) -> StageResult`, sequenced by a runner that persists output to disk between stages and honors `--gate`/`--from`. LLMClient is fully wired (cache + snapshot replay + prompt-folder loader) but the three methods raise `NotImplementedError` until Plan 3. Eight stage modules each return an empty `StageResult`, so the pipeline runs end-to-end without real logic. Test harness spans all 7 layers from §9; only layers i, ii, iii, and vi have real tests in Plan 1 (iv / iv-b / iv-c / vii are empty directories with README stubs).

**Tech stack:** Python 3.11+, pydantic v2, anthropic SDK, lxml, tableaudocumentapi, PyYAML, pytest, multiprocessing (stdlib). No runtime dependency on tableauhyperapi (per spec §5.8 change).

**Spec reference:** `C:\Tableau_PBI\docs\superpowers\specs\2026-04-23-tableau-to-pbir-design.md`. Plan 1 targets infrastructure for v1 scope per §16.

**Out of scope for Plan 1 (deferred to Plans 2–5):**
- Any real extract/canonicalize/translate/layout/emit logic — stages 1–8 are stubs.
- Real Anthropic API calls — LLMClient methods raise `NotImplementedError`.
- TMDL / PBIR / DAX-semantic / Desktop-open validators — directories stubbed with README only.
- Feature-flag gating of deferred fixtures at the runner level — only pytest marker plumbing in Plan 1.

---

## File structure (Plan 1)

**Create:**
```
C:\Tableau_PBI\
├── pyproject.toml
├── README.md
├── config.yaml.example
├── .python-version
├── Makefile
├── pytest.ini
├── src/tableau2pbir/
│   ├── __init__.py
│   ├── cli.py
│   ├── pipeline.py
│   ├── ir/
│   │   ├── __init__.py
│   │   ├── version.py
│   │   ├── schema.py
│   │   ├── common.py
│   │   ├── datasource.py
│   │   ├── model.py
│   │   ├── calculation.py
│   │   ├── parameter.py
│   │   ├── sheet.py
│   │   ├── dashboard.py
│   │   ├── workbook.py
│   │   └── migrations/__init__.py
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── client.py
│   │   ├── cache.py
│   │   ├── snapshots.py
│   │   ├── prompt_loader.py
│   │   └── prompts/
│   │       ├── translate_calc/{system.md, tool_schema.json, VERSION, examples/.gitkeep}
│   │       ├── map_visual/{system.md, tool_schema.json, VERSION, examples/.gitkeep}
│   │       └── cleanup_name/{system.md, tool_schema.json, VERSION, examples/.gitkeep}
│   ├── stages/
│   │   ├── __init__.py
│   │   ├── s01_extract.py
│   │   ├── s02_canonicalize.py
│   │   ├── s03_translate_calcs.py
│   │   ├── s04_map_visuals.py
│   │   ├── s05_compute_layout.py
│   │   ├── s06_build_tmdl.py
│   │   ├── s07_build_pbir.py
│   │   └── s08_package_validate.py
│   └── util/
│       └── __init__.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── unit/stages/__init__.py
│   ├── contract/__init__.py
│   ├── integration/__init__.py
│   ├── golden/
│   │   ├── synthetic/trivial.twb
│   │   ├── real/README.md
│   │   └── expected/.gitkeep
│   ├── validity/
│   │   ├── tmdl/README.md
│   │   ├── pbir/README.md
│   │   └── dax_semantic/README.md
│   ├── desktop_open/README.md
│   └── llm_snapshots/
│       ├── translate_calc/.gitkeep
│       ├── map_visual/.gitkeep
│       └── cleanup_name/.gitkeep
├── schemas/
│   └── ir-v1.0.0.schema.json        # committed artifact from ir/schema.py
└── docs/
    └── architecture.md
```

**Modify:** none (existing `.gitignore` already covers `.venv/`, `__pycache__/`, `.tableau2pbir-cache/`, `/out/`).

---

## Pre-Task: Ensure Python 3.11+ available

Run in PowerShell / bash:
```bash
python --version
```
Expected: `Python 3.11.x` or newer. If not, install 3.11+ before starting. On Windows, `py -3.11 --version` if multiple versions installed.

---

## Task 1: Initialize Python project

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `config.yaml.example`
- Create: `.python-version`
- Create: `Makefile`

- [x] **Step 1.1: Write `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling>=1.18"]
build-backend = "hatchling.build"

[project]
name = "tableau2pbir"
version = "0.1.0"
description = "Deterministic Tableau (.twb/.twbx) to Power BI (PBIR) converter"
readme = "README.md"
requires-python = ">=3.11"
license = {text = "Proprietary"}
dependencies = [
  "anthropic>=0.34,<1.0",
  "pydantic>=2.5,<3.0",
  "lxml>=5.0",
  "tableaudocumentapi>=0.11",
  "PyYAML>=6.0",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.0",
  "pytest-cov>=5.0",
  "pytest-xdist>=3.5",
  "ruff>=0.4",
  "mypy>=1.10",
]

[project.scripts]
tableau2pbir = "tableau2pbir.cli:main"

[tool.hatch.build.targets.wheel]
packages = ["src/tableau2pbir"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.mypy]
python_version = "3.11"
strict = true
```

- [x] **Step 1.2: Write `README.md`**

```markdown
# tableau2pbir

Deterministic converter from Tableau workbooks (`.twb` / `.twbx`) to Power BI projects in PBIR format.
Design spec: `docs/superpowers/specs/2026-04-23-tableau-to-pbir-design.md`.

## Install (dev)

```bash
python -m venv .venv
source .venv/Scripts/activate    # bash on Windows
# or: .venv\Scripts\activate       # PowerShell
pip install -e ".[dev]"
```

## Run

```bash
tableau2pbir convert path/to/workbook.twbx --out ./out/
```

## Test

```bash
make test          # v1 scope
make test-v1.1     # v1 + v1.1-preview features
```
```

- [x] **Step 1.3: Write `config.yaml.example`**

```yaml
# Copy to config.yaml and edit. Values shown are defaults.

llm:
  translate_calc:
    model: claude-sonnet-4-6
  map_visual:
    model: claude-sonnet-4-6
  cleanup_name:
    model: claude-sonnet-4-6

cache:
  dir: .tableau2pbir-cache/llm

canvas:
  default_size: [1366, 768]

feature_flags: []   # e.g. ["with_table_calcs", "with_tier3"]
```

- [x] **Step 1.4: Write `.python-version`**

```
3.11
```

- [x] **Step 1.5: Write `Makefile`**

```makefile
.PHONY: install test test-v1.1 test-v1.2 lint typecheck schema clean

install:
	pip install -e ".[dev]"

test:
	pytest -q -m "not feature_flag"

test-v1.1:
	pytest -q -m "not feature_flag or feature_flag_v1_1"

test-v1.2:
	pytest -q -m "not feature_flag or feature_flag_v1_1 or feature_flag_v1_2"

lint:
	ruff check src tests

typecheck:
	mypy src

schema:
	python -m tableau2pbir.ir.schema > schemas/ir-v1.0.0.schema.json

clean:
	rm -rf .tableau2pbir-cache .pytest_cache .mypy_cache .ruff_cache dist build
```

- [x] **Step 1.6: Create virtual environment and install**

```bash
python -m venv .venv
source .venv/Scripts/activate
pip install -e ".[dev]"
```

Expected: `Successfully installed tableau2pbir-0.1.0 ...` plus dev deps.

- [x] **Step 1.7: Commit**

```bash
git add pyproject.toml README.md config.yaml.example .python-version Makefile
git commit -m "chore: initialize python project with pyproject and dev deps"
```

---

## Task 2: Configure pytest with feature-flag markers

**Files:**
- Create: `pytest.ini`
- Create: `tests/__init__.py` (empty)
- Create: `tests/conftest.py`

- [x] **Step 2.1: Write `pytest.ini`**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -ra --strict-markers
markers =
    feature_flag: base marker for flag-gated tests (selected out of default runs)
    feature_flag_v1_1: test exercises a v1.1-preview feature flag
    feature_flag_v1_2: test exercises a v1.2-preview feature flag
    integration: end-to-end test (slower, may touch disk)
    ai_snapshot: uses LLM snapshot fixtures (PYTEST_SNAPSHOT=replay required)
    validity_tmdl: requires TE2 CLI + AS .NET load probe
    validity_pbir: requires pbi-tools compile
    validity_dax_semantic: requires AS load probe + expected_values.yaml
    desktop_open: requires PBI Desktop install and Windows CI runner
```

- [x] **Step 2.2: Write `tests/__init__.py`** — empty file.

- [x] **Step 2.3: Write `tests/conftest.py`**

```python
"""Shared pytest fixtures for the tableau2pbir test suite."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def synthetic_fixtures_dir() -> Path:
    return REPO_ROOT / "tests" / "golden" / "synthetic"


@pytest.fixture
def snapshot_replay_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Turn on LLM snapshot replay mode (§7 step 4 of LLMClient)."""
    monkeypatch.setenv("PYTEST_SNAPSHOT", "replay")
```

- [x] **Step 2.4: Write a trivial meta-test to verify markers load**

Create `tests/unit/test_pytest_config.py`:

```python
"""Verify pytest markers are registered correctly."""
import subprocess


def test_feature_flag_markers_registered():
    result = subprocess.run(
        ["pytest", "--markers"],
        capture_output=True, text=True, check=True,
    )
    for marker in (
        "feature_flag",
        "feature_flag_v1_1",
        "feature_flag_v1_2",
        "integration",
        "ai_snapshot",
        "validity_tmdl",
        "validity_pbir",
        "validity_dax_semantic",
        "desktop_open",
    ):
        assert f"@pytest.mark.{marker}" in result.stdout, f"missing marker: {marker}"
```

Also create `tests/unit/__init__.py` (empty).

- [x] **Step 2.5: Run test — verify pass**

```bash
pytest tests/unit/test_pytest_config.py -v
```

Expected: `1 passed`.

- [x] **Step 2.6: Commit**

```bash
git add pytest.ini tests/__init__.py tests/conftest.py tests/unit/__init__.py tests/unit/test_pytest_config.py
git commit -m "test: configure pytest with feature-flag markers per spec §16"
```

---

## Task 3: IR — common types + UnsupportedItem

**Files:**
- Create: `src/tableau2pbir/__init__.py`
- Create: `src/tableau2pbir/ir/__init__.py`
- Create: `src/tableau2pbir/ir/version.py`
- Create: `src/tableau2pbir/ir/common.py`
- Create: `tests/unit/ir/__init__.py`
- Create: `tests/unit/ir/test_common.py`

- [x] **Step 3.1: Write failing test**

`tests/unit/ir/test_common.py`:

```python
"""Unit tests for IR common types."""
from __future__ import annotations

import pytest

from tableau2pbir.ir.common import FieldRef, UnsupportedItem
from tableau2pbir.ir.version import IR_SCHEMA_VERSION


def test_ir_schema_version_is_semver_1_0_0():
    assert IR_SCHEMA_VERSION == "1.0.0"


def test_field_ref_accepts_table_and_column():
    ref = FieldRef(table_id="orders", column_id="customer_id")
    assert ref.table_id == "orders"
    assert ref.column_id == "customer_id"


def test_unsupported_item_captures_source_excerpt():
    item = UnsupportedItem(
        object_kind="mark",
        object_id="sheet_42::polygon",
        source_excerpt="<mark class='Polygon'/>",
        reason="polygon marks not mapped",
        code="unsupported_mark_polygon",
    )
    assert item.object_kind == "mark"
    assert item.code == "unsupported_mark_polygon"


def test_unsupported_item_rejects_missing_fields():
    with pytest.raises(Exception):
        UnsupportedItem()  # type: ignore[call-arg]
```

- [x] **Step 3.2: Run test to verify failure**

```bash
pytest tests/unit/ir/test_common.py -v
```
Expected: `ModuleNotFoundError: No module named 'tableau2pbir'` (or similar import error).

- [x] **Step 3.3: Write `src/tableau2pbir/__init__.py`**

```python
"""tableau2pbir — Tableau to Power BI (PBIR) converter."""
__version__ = "0.1.0"
```

- [x] **Step 3.4: Write `src/tableau2pbir/ir/__init__.py`**

```python
"""Intermediate Representation (IR) for the conversion pipeline. See spec §5."""
from tableau2pbir.ir.version import IR_SCHEMA_VERSION

__all__ = ["IR_SCHEMA_VERSION"]
```

- [x] **Step 3.5: Write `src/tableau2pbir/ir/version.py`**

```python
"""IR schema version (semver). Bump per §5.4."""
IR_SCHEMA_VERSION = "1.0.0"
```

- [x] **Step 3.6: Write `src/tableau2pbir/ir/common.py`**

```python
"""Common IR types shared across IR modules. See spec §5."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class IRBase(BaseModel):
    """Base class for all IR pydantic models. Frozen so IR objects are hashable
    after canonicalization, and extra fields are rejected so drift is caught
    by the stage 2 contract test."""
    model_config = ConfigDict(frozen=True, extra="forbid")


class FieldRef(IRBase):
    """Reference to a column inside a table. Used by encodings, table_calc
    addressing/partitioning/sort, lod_fixed.dimensions, etc."""
    table_id: str
    column_id: str


class UnsupportedItem(IRBase):
    """One entry in Workbook.unsupported[] (§5.1) or workbook-level
    unsupported.json (§4.4). Must carry enough context for the
    workbook-report.md renderer to produce a human-readable entry."""
    object_kind: str            # "mark" | "calc" | "datasource" | "parameter" | "action" | ...
    object_id: str              # IR id of the affected object
    source_excerpt: str         # short XML/expr excerpt for debugging
    reason: str                 # human-readable reason
    code: str = Field(          # stable code for status-rule matching (§8.1)
        description="Stable identifier, e.g. 'unsupported_mark_polygon', "
                    "'deferred_feature_table_calcs', 'datasource_tier_4'.",
    )
```

- [x] **Step 3.7: Run test — verify pass**

```bash
pytest tests/unit/ir/test_common.py -v
```
Expected: `4 passed`.

- [x] **Step 3.8: Commit**

```bash
git add src/tableau2pbir/__init__.py src/tableau2pbir/ir/__init__.py \
        src/tableau2pbir/ir/version.py src/tableau2pbir/ir/common.py \
        tests/unit/ir/__init__.py tests/unit/ir/test_common.py
git commit -m "feat(ir): add common types (IRBase, FieldRef, UnsupportedItem) per §5"
```

---

## Task 4: IR — Datasource and ConnectorTier enum

**Files:**
- Create: `src/tableau2pbir/ir/datasource.py`
- Create: `tests/unit/ir/test_datasource.py`

- [x] **Step 4.1: Write failing test**

`tests/unit/ir/test_datasource.py`:

```python
from __future__ import annotations

import pytest

from tableau2pbir.ir.datasource import ConnectorTier, Datasource


def test_connector_tier_values():
    assert ConnectorTier.TIER_1.value == 1
    assert ConnectorTier.TIER_4.value == 4


def test_datasource_minimal():
    ds = Datasource(
        id="ds1",
        name="Sales",
        tableau_kind="sqlserver",
        connector_tier=ConnectorTier.TIER_1,
        pbi_m_connector="Sql.Database",
        connection_params={"server": "sql.example", "database": "Sales"},
        user_action_required=[],
        table_ids=[],
        extract_ignored=False,
    )
    assert ds.connector_tier == ConnectorTier.TIER_1
    assert ds.pbi_m_connector == "Sql.Database"


def test_datasource_tier_4_has_no_m_connector():
    ds = Datasource(
        id="ds2",
        name="Orphan",
        tableau_kind="published-datasource",
        connector_tier=ConnectorTier.TIER_4,
        pbi_m_connector=None,
        connection_params={},
        user_action_required=[],
        table_ids=[],
        extract_ignored=False,
    )
    assert ds.pbi_m_connector is None


def test_datasource_rejects_extra_fields():
    with pytest.raises(Exception):
        Datasource(
            id="ds3", name="X", tableau_kind="csv",
            connector_tier=ConnectorTier.TIER_1, pbi_m_connector="Csv.Document",
            connection_params={}, user_action_required=[], table_ids=[], extract_ignored=False,
            mystery_field="nope",                                      # type: ignore[call-arg]
        )
```

- [x] **Step 4.2: Run test to verify failure**

```bash
pytest tests/unit/ir/test_datasource.py -v
```
Expected: `ModuleNotFoundError: No module named 'tableau2pbir.ir.datasource'`.

- [x] **Step 4.3: Write `src/tableau2pbir/ir/datasource.py`**

```python
"""Datasource IR — §5.1 and §5.8 connector matrix."""
from __future__ import annotations

from enum import IntEnum

from tableau2pbir.ir.common import IRBase


class ConnectorTier(IntEnum):
    """Connector classification per §5.8.

    Tier 1: full fidelity (file/DB connectors emitting real M).
    Tier 2: credential placeholders (user enters creds on first Desktop open).
    Tier 3: degraded fidelity (cross-DB joins, blends, custom SQL).
    Tier 4: unsupported (forces workbook status → failed)."""
    TIER_1 = 1
    TIER_2 = 2
    TIER_3 = 3
    TIER_4 = 4


class Datasource(IRBase):
    """One `<datasource>` from the Tableau workbook, canonicalized.

    `pbi_m_connector` is None iff `connector_tier == TIER_4`. Credentials
    are never persisted here (§5.8 credentials policy)."""
    id: str
    name: str
    tableau_kind: str                       # e.g. "sqlserver", "csv", "hyper"
    connector_tier: ConnectorTier
    pbi_m_connector: str | None             # e.g. "Sql.Database"; None for Tier 4
    connection_params: dict[str, str]       # server, database, path, ...
    user_action_required: tuple[str, ...]   # ("enter credentials", "install oracle client")
    table_ids: tuple[str, ...]              # Tables that read from this datasource
    extract_ignored: bool                   # True when .hyper skipped in favor of <connection>
```

- [x] **Step 4.4: Run test — verify pass**

```bash
pytest tests/unit/ir/test_datasource.py -v
```
Expected: `4 passed`.

- [x] **Step 4.5: Commit**

```bash
git add src/tableau2pbir/ir/datasource.py tests/unit/ir/test_datasource.py
git commit -m "feat(ir): add Datasource + ConnectorTier per §5.8 connector matrix"
```

---

## Task 5: IR — Table, Column, Relationship

**Files:**
- Create: `src/tableau2pbir/ir/model.py`
- Create: `tests/unit/ir/test_model.py`

- [x] **Step 5.1: Write failing test**

`tests/unit/ir/test_model.py`:

```python
from __future__ import annotations

import pytest

from tableau2pbir.ir.common import FieldRef
from tableau2pbir.ir.model import Column, ColumnKind, ColumnRole, Relationship, RelationshipSource, Table


def test_column_minimal_raw():
    c = Column(id="c1", name="Amount", datatype="decimal",
               role=ColumnRole.MEASURE, kind=ColumnKind.RAW)
    assert c.tableau_expr is None
    assert c.dax_expr is None


def test_column_calculated_has_tableau_expr():
    c = Column(id="c2", name="Profit Margin", datatype="decimal",
               role=ColumnRole.MEASURE, kind=ColumnKind.CALCULATED,
               tableau_expr="SUM([Profit])/SUM([Sales])",
               dax_expr=None)
    assert c.tableau_expr.startswith("SUM")


def test_table_has_columns_and_datasource():
    tbl = Table(id="t1", name="Orders", datasource_id="ds1",
                column_ids=("c1", "c2"), primary_key=None)
    assert tbl.datasource_id == "ds1"


def test_relationship_cardinality_enum():
    rel = Relationship(
        id="r1",
        from_ref=FieldRef(table_id="t1", column_id="customer_id"),
        to_ref=FieldRef(table_id="t2", column_id="id"),
        cardinality="many_to_one",
        cross_filter="single",
        source=RelationshipSource.TABLEAU_JOIN,
    )
    assert rel.source == RelationshipSource.TABLEAU_JOIN


def test_column_rejects_invalid_role():
    with pytest.raises(Exception):
        Column(id="c3", name="X", datatype="string",
               role="wrong_role",                                  # type: ignore[arg-type]
               kind=ColumnKind.RAW)
```

- [x] **Step 5.2: Run test — verify failure**

```bash
pytest tests/unit/ir/test_model.py -v
```
Expected: `ModuleNotFoundError: No module named 'tableau2pbir.ir.model'`.

- [x] **Step 5.3: Write `src/tableau2pbir/ir/model.py`**

```python
"""Table / Column / Relationship IR — §5.1."""
from __future__ import annotations

from enum import Enum

from tableau2pbir.ir.common import FieldRef, IRBase


class ColumnRole(str, Enum):
    DIMENSION = "dim"
    MEASURE = "measure"


class ColumnKind(str, Enum):
    RAW = "raw"
    CALCULATED = "calculated"


class Column(IRBase):
    id: str
    name: str
    datatype: str                           # tableau-normalized datatype string
    role: ColumnRole
    kind: ColumnKind
    tableau_expr: str | None = None         # calculated columns only
    dax_expr: str | None = None             # populated by stage 3 for calculated columns


class Table(IRBase):
    id: str
    name: str
    datasource_id: str
    column_ids: tuple[str, ...]
    primary_key: tuple[str, ...] | None = None    # column ids forming the PK (if known)


class RelationshipSource(str, Enum):
    TABLEAU_JOIN = "tableau_join"
    TABLEAU_BLEND = "tableau_blend"
    CROSS_DB_FLATTEN = "cross_db_flatten"


class Relationship(IRBase):
    id: str
    from_ref: FieldRef
    to_ref: FieldRef
    cardinality: str                        # "one_to_one" | "one_to_many" | "many_to_one" | "many_to_many"
    cross_filter: str                       # "single" | "both"
    source: RelationshipSource
```

- [x] **Step 5.4: Run test — verify pass**

```bash
pytest tests/unit/ir/test_model.py -v
```
Expected: `5 passed`.

- [x] **Step 5.5: Commit**

```bash
git add src/tableau2pbir/ir/model.py tests/unit/ir/test_model.py
git commit -m "feat(ir): add Table, Column, Relationship per §5.1"
```

---

## Task 6: IR — Calculation (enriched per §5.6)

**Files:**
- Create: `src/tableau2pbir/ir/calculation.py`
- Create: `tests/unit/ir/test_calculation.py`

- [x] **Step 6.1: Write failing test**

`tests/unit/ir/test_calculation.py`:

```python
from __future__ import annotations

import pytest

from tableau2pbir.ir.calculation import (
    Calculation, CalculationKind, CalculationPhase, CalculationScope,
    LodFixed, LodRelative, TableCalc, TableCalcFrame, TableCalcFrameType,
)
from tableau2pbir.ir.common import FieldRef


def test_row_calc_minimal():
    c = Calculation(
        id="calc1",
        name="Profit",
        scope=CalculationScope.COLUMN,
        tableau_expr="[Revenue] - [Cost]",
        kind=CalculationKind.ROW,
        phase=CalculationPhase.ROW,
        depends_on=(),
    )
    assert c.table_calc is None
    assert c.lod_fixed is None


def test_lod_fixed_dimensions():
    c = Calculation(
        id="calc2",
        name="Sales By Region",
        scope=CalculationScope.MEASURE,
        tableau_expr="{FIXED [Region]: SUM([Sales])}",
        kind=CalculationKind.LOD_FIXED,
        phase=CalculationPhase.AGGREGATE,
        depends_on=(),
        lod_fixed=LodFixed(dimensions=(FieldRef(table_id="t1", column_id="region"),)),
    )
    assert c.lod_fixed is not None
    assert len(c.lod_fixed.dimensions) == 1


def test_lod_include_per_sheet_expansion_ready():
    c = Calculation(
        id="calc3",
        name="Sales With Customer",
        scope=CalculationScope.MEASURE,
        tableau_expr="{INCLUDE [Customer]: SUM([Sales])}",
        kind=CalculationKind.LOD_INCLUDE,
        phase=CalculationPhase.AGGREGATE,
        depends_on=(),
        lod_relative=LodRelative(extra_dims=(FieldRef(table_id="t1", column_id="customer"),)),
        owner_sheet_id=None,      # named calc; per-sheet variants set owner_sheet_id
    )
    assert c.lod_relative is not None
    assert c.lod_relative.extra_dims is not None


def test_table_calc_rank_frame():
    tc = TableCalc(
        partitioning=(FieldRef(table_id="t1", column_id="region"),),
        addressing=(FieldRef(table_id="t1", column_id="month"),),
        sort=(),
        frame=TableCalcFrame(type=TableCalcFrameType.RANK),
        restart_every=None,
    )
    c = Calculation(
        id="calc4", name="Rank", scope=CalculationScope.MEASURE,
        tableau_expr="RANK(SUM([Sales]))",
        kind=CalculationKind.TABLE_CALC,
        phase=CalculationPhase.VIZ,
        depends_on=(),
        table_calc=tc,
    )
    assert c.table_calc.frame.type == TableCalcFrameType.RANK


def test_quick_table_calc_has_owner_sheet():
    c = Calculation(
        id="qtc1__sheet42",
        name="_quick_table_calc_1",
        scope=CalculationScope.MEASURE,
        tableau_expr="RUNNING_SUM(SUM([Sales]))",
        kind=CalculationKind.TABLE_CALC,
        phase=CalculationPhase.VIZ,
        depends_on=(),
        table_calc=TableCalc(
            partitioning=(), addressing=(), sort=(),
            frame=TableCalcFrame(type=TableCalcFrameType.CUMULATIVE),
            restart_every=None,
        ),
        owner_sheet_id="sheet42",
    )
    assert c.owner_sheet_id == "sheet42"


def test_calculation_rejects_unknown_kind():
    with pytest.raises(Exception):
        Calculation(
            id="x", name="x", scope=CalculationScope.MEASURE,
            tableau_expr="SUM([x])",
            kind="mystery",                                        # type: ignore[arg-type]
            phase=CalculationPhase.AGGREGATE, depends_on=(),
        )
```

- [x] **Step 6.2: Run test — verify failure**

```bash
pytest tests/unit/ir/test_calculation.py -v
```
Expected: `ModuleNotFoundError: No module named 'tableau2pbir.ir.calculation'`.

- [x] **Step 6.3: Write `src/tableau2pbir/ir/calculation.py`**

```python
"""Calculation IR — enriched per §5.6. Kind + phase + optional
table_calc/lod_fixed/lod_relative records drive deterministic stage-3
rule matching; owner_sheet_id supports per-sheet LOD INCLUDE/EXCLUDE
measure expansion and quick-table-calc anonymous records."""
from __future__ import annotations

from enum import Enum

from tableau2pbir.ir.common import FieldRef, IRBase


class CalculationScope(str, Enum):
    MEASURE = "measure"
    COLUMN = "column"


class CalculationKind(str, Enum):
    ROW = "row"
    AGGREGATE = "aggregate"
    TABLE_CALC = "table_calc"
    LOD_FIXED = "lod_fixed"
    LOD_INCLUDE = "lod_include"
    LOD_EXCLUDE = "lod_exclude"


class CalculationPhase(str, Enum):
    ROW = "row"
    AGGREGATE = "aggregate"
    VIZ = "viz"


class TableCalcFrameType(str, Enum):
    CUMULATIVE = "cumulative"
    WINDOW = "window"
    LOOKUP = "lookup"
    RANK = "rank"


class TableCalcFrame(IRBase):
    type: TableCalcFrameType
    offset: int | None = None                   # for LOOKUP
    window_size: int | None = None              # for WINDOW


class TableCalcSortEntry(IRBase):
    field: FieldRef
    direction: str                              # "asc" | "desc"


class TableCalc(IRBase):
    partitioning: tuple[FieldRef, ...]
    addressing: tuple[FieldRef, ...]
    sort: tuple[TableCalcSortEntry, ...]
    frame: TableCalcFrame
    restart_every: FieldRef | None = None


class LodFixed(IRBase):
    dimensions: tuple[FieldRef, ...]


class LodRelative(IRBase):
    """Relative-LOD record; exactly one of extra_dims (INCLUDE) or
    excluded_dims (EXCLUDE) is populated — mutual exclusion is enforced
    by stage 2 and asserted in contract tests."""
    extra_dims: tuple[FieldRef, ...] | None = None
    excluded_dims: tuple[FieldRef, ...] | None = None


class Calculation(IRBase):
    # Core
    id: str
    name: str
    scope: CalculationScope
    tableau_expr: str
    dax_expr: str | None = None                 # populated by stage 3
    depends_on: tuple[str, ...] = ()            # other Calculation ids

    # Semantic normalization (filled by stage 2)
    kind: CalculationKind
    phase: CalculationPhase

    # Kind-discriminated payloads
    table_calc: TableCalc | None = None
    lod_fixed: LodFixed | None = None
    lod_relative: LodRelative | None = None

    # Back-ref for quick-table-calc anonymous records and per-sheet LOD variants
    owner_sheet_id: str | None = None
```

- [x] **Step 6.4: Run test — verify pass**

```bash
pytest tests/unit/ir/test_calculation.py -v
```
Expected: `6 passed`.

- [x] **Step 6.5: Commit**

```bash
git add src/tableau2pbir/ir/calculation.py tests/unit/ir/test_calculation.py
git commit -m "feat(ir): add Calculation with enriched semantics per §5.6"
```

---

## Task 7: IR — Parameter (enriched per §5.7)

**Files:**
- Create: `src/tableau2pbir/ir/parameter.py`
- Create: `tests/unit/ir/test_parameter.py`

- [x] **Step 7.1: Write failing test**

`tests/unit/ir/test_parameter.py`:

```python
from __future__ import annotations

from tableau2pbir.ir.parameter import (
    Parameter, ParameterBindingTarget, ParameterExposure, ParameterIntent,
)


def test_numeric_what_if_minimal():
    p = Parameter(
        id="p1", name="Discount %", datatype="decimal",
        default="0.1", allowed_values=("0.0", "0.05", "0.1", "0.15"),
        intent=ParameterIntent.NUMERIC_WHAT_IF,
        exposure=ParameterExposure.CARD,
    )
    assert p.intent == ParameterIntent.NUMERIC_WHAT_IF
    assert p.binding_target is None


def test_formatting_control_with_binding():
    p = Parameter(
        id="p2", name="Unit Display", datatype="string",
        default="Thousands", allowed_values=("Ones", "Thousands", "Millions"),
        intent=ParameterIntent.FORMATTING_CONTROL,
        exposure=ParameterExposure.CARD,
        binding_target=ParameterBindingTarget(
            measure_ids=("m1", "m2"),
            format_pattern="#,##0",
        ),
    )
    assert p.binding_target.format_pattern == "#,##0"


def test_internal_constant_calc_only():
    p = Parameter(
        id="p3", name="AxisMax", datatype="integer",
        default="100", allowed_values=(),
        intent=ParameterIntent.INTERNAL_CONSTANT,
        exposure=ParameterExposure.CALC_ONLY,
    )
    assert p.exposure == ParameterExposure.CALC_ONLY
```

- [x] **Step 7.2: Run test — verify failure**

```bash
pytest tests/unit/ir/test_parameter.py -v
```
Expected: `ModuleNotFoundError`.

- [x] **Step 7.3: Write `src/tableau2pbir/ir/parameter.py`**

```python
"""Parameter IR — enriched per §5.7 with intent classification."""
from __future__ import annotations

from enum import Enum

from tableau2pbir.ir.common import IRBase


class ParameterIntent(str, Enum):
    NUMERIC_WHAT_IF = "numeric_what_if"
    CATEGORICAL_SELECTOR = "categorical_selector"
    INTERNAL_CONSTANT = "internal_constant"
    FORMATTING_CONTROL = "formatting_control"
    UNSUPPORTED = "unsupported"


class ParameterExposure(str, Enum):
    CARD = "card"                # has a parameter card on a dashboard
    SHELF = "shelf"              # used on a viz shelf
    CALC_ONLY = "calc_only"      # referenced only in calc bodies


class ParameterBindingTarget(IRBase):
    """Present only when intent == FORMATTING_CONTROL."""
    measure_ids: tuple[str, ...]
    format_pattern: str | None = None


class Parameter(IRBase):
    id: str
    name: str
    datatype: str
    default: str
    allowed_values: tuple[str, ...]
    intent: ParameterIntent
    exposure: ParameterExposure
    binding_target: ParameterBindingTarget | None = None
```

- [x] **Step 7.4: Run test — verify pass**

```bash
pytest tests/unit/ir/test_parameter.py -v
```
Expected: `3 passed`.

- [x] **Step 7.5: Commit**

```bash
git add src/tableau2pbir/ir/parameter.py tests/unit/ir/test_parameter.py
git commit -m "feat(ir): add Parameter with intent per §5.7"
```

---

## Task 8: IR — Sheet (encodings, filters, back-refs)

**Files:**
- Create: `src/tableau2pbir/ir/sheet.py`
- Create: `tests/unit/ir/test_sheet.py`

- [x] **Step 8.1: Write failing test**

`tests/unit/ir/test_sheet.py`:

```python
from __future__ import annotations

from tableau2pbir.ir.common import FieldRef
from tableau2pbir.ir.sheet import Encoding, Filter, Sheet


def test_sheet_minimal():
    s = Sheet(
        id="sheet1", name="Revenue",
        datasource_refs=("ds1",),
        mark_type="bar",
        encoding=Encoding(
            rows=(FieldRef(table_id="t1", column_id="month"),),
            columns=(FieldRef(table_id="t1", column_id="revenue"),),
        ),
        filters=(),
        sort=(),
        dual_axis=False,
        reference_lines=(),
        format=None,
        uses_calculations=(),
    )
    assert s.mark_type == "bar"
    assert s.encoding.color is None


def test_sheet_with_categorical_filter():
    f = Filter(
        id="f1", kind="categorical", field=FieldRef(table_id="t1", column_id="region"),
        include=("West", "East"), exclude=(), expr=None,
    )
    s = Sheet(
        id="sheet2", name="Regional",
        datasource_refs=("ds1",),
        mark_type="bar",
        encoding=Encoding(rows=(), columns=()),
        filters=(f,),
        sort=(), dual_axis=False, reference_lines=(),
        format=None, uses_calculations=("calc1",),
    )
    assert s.filters[0].include == ("West", "East")
    assert s.uses_calculations == ("calc1",)
```

- [x] **Step 8.2: Run test — verify failure**

```bash
pytest tests/unit/ir/test_sheet.py -v
```
Expected: `ModuleNotFoundError`.

- [x] **Step 8.3: Write `src/tableau2pbir/ir/sheet.py`**

```python
"""Sheet IR — §5.1."""
from __future__ import annotations

from tableau2pbir.ir.common import FieldRef, IRBase


class Encoding(IRBase):
    """Visual encoding channels. Only channels actually bound are populated."""
    rows: tuple[FieldRef, ...] = ()
    columns: tuple[FieldRef, ...] = ()
    color: FieldRef | None = None
    size: FieldRef | None = None
    label: FieldRef | None = None
    tooltip: FieldRef | None = None
    detail: tuple[FieldRef, ...] = ()
    shape: FieldRef | None = None
    angle: FieldRef | None = None


class Filter(IRBase):
    id: str
    kind: str                               # "categorical" | "range" | "top_n" | "context" | "conditional"
    field: FieldRef
    include: tuple[str, ...] = ()           # for categorical
    exclude: tuple[str, ...] = ()           # for categorical
    expr: str | None = None                 # for conditional


class SortSpec(IRBase):
    field: FieldRef
    direction: str                          # "asc" | "desc"


class ReferenceLine(IRBase):
    id: str
    scope_field: FieldRef
    kind: str                               # "constant" | "average" | "median" | "lod"
    value: float | None = None              # for constant
    lod_expr: str | None = None             # for lod-based


class Sheet(IRBase):
    id: str
    name: str
    datasource_refs: tuple[str, ...]        # Datasource ids
    mark_type: str
    encoding: Encoding
    filters: tuple[Filter, ...]
    sort: tuple[SortSpec, ...]
    dual_axis: bool
    reference_lines: tuple[ReferenceLine, ...]
    format: dict[str, str] | None = None
    uses_calculations: tuple[str, ...]      # Calculation ids — back-ref for topo-sort
```

- [x] **Step 8.4: Run test — verify pass**

```bash
pytest tests/unit/ir/test_sheet.py -v
```
Expected: `2 passed`.

- [x] **Step 8.5: Commit**

```bash
git add src/tableau2pbir/ir/sheet.py tests/unit/ir/test_sheet.py
git commit -m "feat(ir): add Sheet with encoding, filters, back-refs per §5.1"
```

---

## Task 9: IR — Dashboard, Layout tree, Action

**Files:**
- Create: `src/tableau2pbir/ir/dashboard.py`
- Create: `tests/unit/ir/test_dashboard.py`

- [x] **Step 9.1: Write failing test**

`tests/unit/ir/test_dashboard.py`:

```python
from __future__ import annotations

from tableau2pbir.ir.dashboard import (
    Action, ActionKind, ActionTrigger,
    Container, ContainerKind, Dashboard, DashboardSize, Leaf, LeafKind, Position,
)


def test_leaf_sheet_position_none_at_extract_time():
    leaf = Leaf(kind=LeafKind.SHEET, payload={"sheet_id": "sheet1"}, position=None)
    assert leaf.position is None


def test_container_with_children():
    child = Leaf(kind=LeafKind.TEXT, payload={"text": "Hello"}, position=None)
    c = Container(kind=ContainerKind.H, children=(child,), padding=4, background=None)
    assert len(c.children) == 1


def test_dashboard_minimal():
    root = Container(kind=ContainerKind.V, children=(), padding=0, background=None)
    d = Dashboard(
        id="d1", name="Main",
        size=DashboardSize(w=1200, h=800, kind="exact"),
        layout_tree=root,
        actions=(),
    )
    assert d.size.w == 1200


def test_action_filter_kind():
    a = Action(
        id="a1", name="Filter By Region",
        kind=ActionKind.FILTER, trigger=ActionTrigger.SELECT,
        source_sheet_ids=("sheet1",), target_sheet_ids=("sheet2",),
        source_fields=(), target_fields=(),
        clearing_behavior="keep_filter",
    )
    assert a.kind == ActionKind.FILTER


def test_position_fields():
    p = Position(x=10, y=20, w=300, h=200)
    assert p.w == 300
```

- [x] **Step 9.2: Run test — verify failure**

```bash
pytest tests/unit/ir/test_dashboard.py -v
```
Expected: `ModuleNotFoundError`.

- [x] **Step 9.3: Write `src/tableau2pbir/ir/dashboard.py`**

```python
"""Dashboard IR, layout tree, and Action — §5.1, §5.2, §5.3."""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import Field

from tableau2pbir.ir.common import IRBase


class ContainerKind(str, Enum):
    H = "h"
    V = "v"
    FLOATING = "floating"


class LeafKind(str, Enum):
    SHEET = "sheet"
    TEXT = "text"
    IMAGE = "image"
    FILTER_CARD = "filter_card"
    PARAMETER_CARD = "parameter_card"
    LEGEND = "legend"
    NAVIGATION = "navigation"
    BLANK = "blank"
    WEB_PAGE = "web_page"


class Position(IRBase):
    x: int
    y: int
    w: int
    h: int


class Leaf(IRBase):
    kind: LeafKind
    payload: dict[str, Any]                   # shape depends on kind (§5.2)
    position: Position | None = None          # None at extract; filled by stage 5


class Container(IRBase):
    kind: ContainerKind
    children: tuple["Container | Leaf", ...]
    padding: int = 0
    background: str | None = None


# Let pydantic resolve the recursive ref
Container.model_rebuild()


class DashboardSize(IRBase):
    w: int
    h: int
    kind: str                                 # "exact" | "automatic" | "range"


class ActionKind(str, Enum):
    FILTER = "filter"
    HIGHLIGHT = "highlight"
    URL = "url"
    PARAMETER = "parameter"


class ActionTrigger(str, Enum):
    SELECT = "select"
    HOVER = "hover"
    MENU = "menu"


class Action(IRBase):
    id: str
    name: str
    kind: ActionKind
    trigger: ActionTrigger
    source_sheet_ids: tuple[str, ...]
    target_sheet_ids: tuple[str, ...]
    source_fields: tuple[str, ...] = ()
    target_fields: tuple[str, ...] = ()
    clearing_behavior: str = "keep_filter"    # "keep_filter" | "show_all" | "exclude"


class Dashboard(IRBase):
    id: str
    name: str
    size: DashboardSize
    layout_tree: Container | Leaf = Field(discriminator=None)   # root is usually a Container
    actions: tuple[Action, ...] = ()
```

- [x] **Step 9.4: Run test — verify pass**

```bash
pytest tests/unit/ir/test_dashboard.py -v
```
Expected: `5 passed`.

- [x] **Step 9.5: Commit**

```bash
git add src/tableau2pbir/ir/dashboard.py tests/unit/ir/test_dashboard.py
git commit -m "feat(ir): add Dashboard with layout tree and Action per §5.1-§5.3"
```

---

## Task 10: IR — Workbook top-level + DataModel aggregate

**Files:**
- Create: `src/tableau2pbir/ir/workbook.py`
- Create: `tests/unit/ir/test_workbook.py`

- [x] **Step 10.1: Write failing test**

`tests/unit/ir/test_workbook.py`:

```python
from __future__ import annotations

from tableau2pbir.ir.version import IR_SCHEMA_VERSION
from tableau2pbir.ir.workbook import DataModel, Workbook


def test_empty_workbook_stamps_schema_version():
    wb = Workbook(
        ir_schema_version=IR_SCHEMA_VERSION,
        source_path="fixtures/trivial.twb",
        source_hash="abc123",
        tableau_version="2024.1",
        config={},
        data_model=DataModel(),
        sheets=(), dashboards=(), unsupported=(),
    )
    assert wb.ir_schema_version == "1.0.0"
    assert wb.data_model.datasources == ()


def test_workbook_round_trip_json():
    wb = Workbook(
        ir_schema_version=IR_SCHEMA_VERSION,
        source_path="fixtures/trivial.twb",
        source_hash="abc123",
        tableau_version="2024.1",
        config={},
        data_model=DataModel(),
        sheets=(), dashboards=(), unsupported=(),
    )
    as_json = wb.model_dump_json()
    wb2 = Workbook.model_validate_json(as_json)
    assert wb2 == wb
```

- [x] **Step 10.2: Run test — verify failure**

```bash
pytest tests/unit/ir/test_workbook.py -v
```
Expected: `ModuleNotFoundError`.

- [x] **Step 10.3: Write `src/tableau2pbir/ir/workbook.py`**

```python
"""Top-level Workbook IR + DataModel aggregate — §5.1."""
from __future__ import annotations

from tableau2pbir.ir.calculation import Calculation
from tableau2pbir.ir.common import IRBase, UnsupportedItem
from tableau2pbir.ir.dashboard import Dashboard
from tableau2pbir.ir.datasource import Datasource
from tableau2pbir.ir.model import Relationship, Table
from tableau2pbir.ir.parameter import Parameter
from tableau2pbir.ir.sheet import Sheet


class Hierarchy(IRBase):
    id: str
    name: str
    level_column_ids: tuple[str, ...]


class Set(IRBase):
    id: str
    name: str
    source_column: str                      # column id
    definition: str                         # free-form; TBD in stage 2


class DataModel(IRBase):
    datasources: tuple[Datasource, ...] = ()
    tables: tuple[Table, ...] = ()
    relationships: tuple[Relationship, ...] = ()
    calculations: tuple[Calculation, ...] = ()
    parameters: tuple[Parameter, ...] = ()
    hierarchies: tuple[Hierarchy, ...] = ()
    sets: tuple[Set, ...] = ()


class Workbook(IRBase):
    ir_schema_version: str
    source_path: str
    source_hash: str
    tableau_version: str
    config: dict[str, str]

    data_model: DataModel
    sheets: tuple[Sheet, ...]
    dashboards: tuple[Dashboard, ...]
    unsupported: tuple[UnsupportedItem, ...]
```

- [x] **Step 10.4: Run test — verify pass**

```bash
pytest tests/unit/ir/test_workbook.py -v
```
Expected: `2 passed`.

- [x] **Step 10.5: Commit**

```bash
git add src/tableau2pbir/ir/workbook.py tests/unit/ir/test_workbook.py
git commit -m "feat(ir): add Workbook and DataModel aggregates per §5.1"
```

---

## Task 11: IR — JSON Schema autogen + committed artifact

**Files:**
- Create: `src/tableau2pbir/ir/schema.py`
- Create: `schemas/ir-v1.0.0.schema.json`
- Create: `tests/contract/__init__.py`
- Create: `tests/contract/test_ir_schema.py`

- [x] **Step 11.1: Write failing test**

`tests/contract/test_ir_schema.py`:

```python
"""Contract tests — the committed IR JSON Schema must match the pydantic-generated
schema. Bumping IR_SCHEMA_VERSION without regenerating the artifact fails CI."""
from __future__ import annotations

import json
from pathlib import Path

from tableau2pbir.ir.schema import generate_ir_schema
from tableau2pbir.ir.version import IR_SCHEMA_VERSION


def test_committed_schema_matches_generated(repo_root: Path):
    artifact_path = repo_root / "schemas" / f"ir-v{IR_SCHEMA_VERSION}.schema.json"
    assert artifact_path.exists(), \
        f"committed schema missing; run `make schema` to regenerate."

    committed = json.loads(artifact_path.read_text(encoding="utf-8"))
    generated = generate_ir_schema()
    assert committed == generated, (
        "committed IR JSON Schema is out of date; run `make schema` and commit."
    )


def test_generated_schema_has_expected_top_level_keys():
    schema = generate_ir_schema()
    assert schema.get("title") == "Workbook"
    assert "properties" in schema
    assert "ir_schema_version" in schema["properties"]
```

- [x] **Step 11.2: Run test — verify failure**

```bash
pytest tests/contract/test_ir_schema.py -v
```
Expected: `ModuleNotFoundError: No module named 'tableau2pbir.ir.schema'`.

- [x] **Step 11.3: Write `src/tableau2pbir/ir/schema.py`**

```python
"""JSON Schema autogeneration from IR pydantic models.

This module is also a CLI entry-point. Run `python -m tableau2pbir.ir.schema`
to emit the schema JSON to stdout (wired via `make schema`)."""
from __future__ import annotations

import json
import sys
from typing import Any

from tableau2pbir.ir.workbook import Workbook


def generate_ir_schema() -> dict[str, Any]:
    """Return the JSON Schema for the top-level Workbook IR model."""
    return Workbook.model_json_schema()


def main() -> None:
    json.dump(generate_ir_schema(), sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
```

- [x] **Step 11.4: Generate the committed artifact**

```bash
mkdir -p schemas
python -m tableau2pbir.ir.schema > schemas/ir-v1.0.0.schema.json
```

Expected: `schemas/ir-v1.0.0.schema.json` is created with pydantic-generated JSON Schema.

- [x] **Step 11.5: Create `tests/contract/__init__.py`** — empty file.

- [x] **Step 11.6: Run test — verify pass**

```bash
pytest tests/contract/test_ir_schema.py -v
```
Expected: `2 passed`.

- [x] **Step 11.7: Commit**

```bash
git add src/tableau2pbir/ir/schema.py schemas/ir-v1.0.0.schema.json \
        tests/contract/__init__.py tests/contract/test_ir_schema.py
git commit -m "feat(ir): autogen JSON Schema + commit v1.0.0 artifact per §5.4"
```

---

## Task 12: Stage contract — StageError, StageResult, StageContext

**Files:**
- Create: `src/tableau2pbir/pipeline.py`
- Create: `tests/unit/test_pipeline_contract.py`

- [x] **Step 12.1: Write failing test**

`tests/unit/test_pipeline_contract.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from tableau2pbir.pipeline import StageContext, StageError, StageResult


def test_stage_error_severity_levels():
    err = StageError(
        severity="warn", code="test.code", object_id="obj1",
        message="x", fix_hint=None,
    )
    assert err.severity == "warn"


def test_stage_error_rejects_unknown_severity():
    with pytest.raises(Exception):
        StageError(severity="bogus", code="c", object_id="o", message="m", fix_hint=None)


def test_stage_result_defaults():
    r = StageResult()
    assert r.output == {}
    assert r.summary_md == ""
    assert r.errors == ()


def test_stage_context_fields(tmp_path: Path):
    ctx = StageContext(
        workbook_id="wb1",
        output_dir=tmp_path,
        config={},
        stage_number=1,
    )
    assert ctx.stage_number == 1
```

- [x] **Step 12.2: Run test — verify failure**

```bash
pytest tests/unit/test_pipeline_contract.py -v
```
Expected: `ModuleNotFoundError: No module named 'tableau2pbir.pipeline'`.

- [x] **Step 12.3: Write minimal `src/tableau2pbir/pipeline.py`**

```python
"""Pipeline runner and stage contract — §4.3 + §8.2.

Only the contract types are defined in this task. Registry and runner
are added in Task 13/14."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict


Severity = Literal["info", "warn", "error", "fatal"]


class _ContractBase(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class StageError(_ContractBase):
    severity: Severity
    code: str
    object_id: str
    message: str
    fix_hint: str | None


class StageResult(_ContractBase):
    output: dict = {}
    summary_md: str = ""
    errors: tuple[StageError, ...] = ()


class StageContext(_ContractBase):
    workbook_id: str
    output_dir: Path
    config: dict
    stage_number: int

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True, extra="forbid")
```

- [x] **Step 12.4: Run test — verify pass**

```bash
pytest tests/unit/test_pipeline_contract.py -v
```
Expected: `4 passed`.

- [x] **Step 12.5: Commit**

```bash
git add src/tableau2pbir/pipeline.py tests/unit/test_pipeline_contract.py
git commit -m "feat(pipeline): add stage contract (StageResult, StageError, StageContext)"
```

---

## Task 13: 8 empty stage modules

**Files:**
- Create: `src/tableau2pbir/stages/__init__.py`
- Create: `src/tableau2pbir/stages/s01_extract.py`
- Create: `src/tableau2pbir/stages/s02_canonicalize.py`
- Create: `src/tableau2pbir/stages/s03_translate_calcs.py`
- Create: `src/tableau2pbir/stages/s04_map_visuals.py`
- Create: `src/tableau2pbir/stages/s05_compute_layout.py`
- Create: `src/tableau2pbir/stages/s06_build_tmdl.py`
- Create: `src/tableau2pbir/stages/s07_build_pbir.py`
- Create: `src/tableau2pbir/stages/s08_package_validate.py`
- Create: `tests/unit/stages/__init__.py`
- Create: `tests/unit/stages/test_all_stages_stub.py`

- [x] **Step 13.1: Write failing test**

`tests/unit/stages/test_all_stages_stub.py`:

```python
"""Every stage module exports a `run(input_json, ctx) -> StageResult` function.
Verified here to pin the contract."""
from __future__ import annotations

from pathlib import Path

import pytest

from tableau2pbir.pipeline import StageContext, StageResult

STAGE_MODULES = [
    "tableau2pbir.stages.s01_extract",
    "tableau2pbir.stages.s02_canonicalize",
    "tableau2pbir.stages.s03_translate_calcs",
    "tableau2pbir.stages.s04_map_visuals",
    "tableau2pbir.stages.s05_compute_layout",
    "tableau2pbir.stages.s06_build_tmdl",
    "tableau2pbir.stages.s07_build_pbir",
    "tableau2pbir.stages.s08_package_validate",
]


@pytest.mark.parametrize("module_path", STAGE_MODULES)
def test_each_stage_has_run_returning_stage_result(module_path: str, tmp_path: Path):
    import importlib
    mod = importlib.import_module(module_path)
    assert hasattr(mod, "run"), f"{module_path} missing run()"
    ctx = StageContext(workbook_id="wb", output_dir=tmp_path, config={}, stage_number=1)
    result = mod.run({}, ctx)
    assert isinstance(result, StageResult)
```

- [x] **Step 13.2: Run test — verify failure**

```bash
pytest tests/unit/stages/test_all_stages_stub.py -v
```
Expected: all 8 parametrized cases fail with `ModuleNotFoundError`.

- [x] **Step 13.3: Write `src/tableau2pbir/stages/__init__.py`** — empty file.

- [x] **Step 13.4: Write all 8 stage stubs**

Each file has the same template below. Replace `<NAME>` with the module name portion (e.g., `extract`, `canonicalize`):

`src/tableau2pbir/stages/s01_extract.py`:

```python
"""Stage 1 — extract (pure python). See spec §6 Stage 1. This is a
Plan-1 stub; real implementation in Plan 2."""
from __future__ import annotations

from tableau2pbir.pipeline import StageContext, StageResult


def run(input_json: dict, ctx: StageContext) -> StageResult:
    return StageResult(
        output={"stub_stage": "extract", "input_keys": list(input_json.keys())},
        summary_md="# Stage 1 — extract (stub)\n\nNo-op in Plan 1.\n",
        errors=(),
    )
```

Repeat for each stage — use the exact filenames above and update the stage number, name, and summary line. Complete content:

`s02_canonicalize.py`:
```python
"""Stage 2 — canonicalize → IR (pure python). See spec §6 Stage 2. Plan-1 stub."""
from __future__ import annotations

from tableau2pbir.pipeline import StageContext, StageResult


def run(input_json: dict, ctx: StageContext) -> StageResult:
    return StageResult(
        output={"stub_stage": "canonicalize", "input_keys": list(input_json.keys())},
        summary_md="# Stage 2 — canonicalize (stub)\n\nNo-op in Plan 1.\n",
        errors=(),
    )
```

`s03_translate_calcs.py`:
```python
"""Stage 3 — translate calcs (python + AI fallback). See spec §6 Stage 3. Plan-1 stub."""
from __future__ import annotations

from tableau2pbir.pipeline import StageContext, StageResult


def run(input_json: dict, ctx: StageContext) -> StageResult:
    return StageResult(
        output={"stub_stage": "translate_calcs", "input_keys": list(input_json.keys())},
        summary_md="# Stage 3 — translate calcs (stub)\n\nNo-op in Plan 1.\n",
        errors=(),
    )
```

`s04_map_visuals.py`:
```python
"""Stage 4 — map visuals (python + AI fallback). See spec §6 Stage 4. Plan-1 stub."""
from __future__ import annotations

from tableau2pbir.pipeline import StageContext, StageResult


def run(input_json: dict, ctx: StageContext) -> StageResult:
    return StageResult(
        output={"stub_stage": "map_visuals", "input_keys": list(input_json.keys())},
        summary_md="# Stage 4 — map visuals (stub)\n\nNo-op in Plan 1.\n",
        errors=(),
    )
```

`s05_compute_layout.py`:
```python
"""Stage 5 — compute layout (pure python). See spec §6 Stage 5. Plan-1 stub."""
from __future__ import annotations

from tableau2pbir.pipeline import StageContext, StageResult


def run(input_json: dict, ctx: StageContext) -> StageResult:
    return StageResult(
        output={"stub_stage": "compute_layout", "input_keys": list(input_json.keys())},
        summary_md="# Stage 5 — compute layout (stub)\n\nNo-op in Plan 1.\n",
        errors=(),
    )
```

`s06_build_tmdl.py`:
```python
"""Stage 6 — build TMDL (pure python). See spec §6 Stage 6. Plan-1 stub."""
from __future__ import annotations

from tableau2pbir.pipeline import StageContext, StageResult


def run(input_json: dict, ctx: StageContext) -> StageResult:
    return StageResult(
        output={"stub_stage": "build_tmdl", "input_keys": list(input_json.keys())},
        summary_md="# Stage 6 — build TMDL (stub)\n\nNo-op in Plan 1.\n",
        errors=(),
    )
```

`s07_build_pbir.py`:
```python
"""Stage 7 — build report PBIR (pure python). See spec §6 Stage 7. Plan-1 stub."""
from __future__ import annotations

from tableau2pbir.pipeline import StageContext, StageResult


def run(input_json: dict, ctx: StageContext) -> StageResult:
    return StageResult(
        output={"stub_stage": "build_pbir", "input_keys": list(input_json.keys())},
        summary_md="# Stage 7 — build PBIR (stub)\n\nNo-op in Plan 1.\n",
        errors=(),
    )
```

`s08_package_validate.py`:
```python
"""Stage 8 — package + validate (pure python). See spec §6 Stage 8. Plan-1 stub.

In Plan 1 this also writes an empty placeholder .pbip so the end-to-end smoke
test has something to assert on."""
from __future__ import annotations

from tableau2pbir.pipeline import StageContext, StageResult


def run(input_json: dict, ctx: StageContext) -> StageResult:
    pbip_path = ctx.output_dir / f"{ctx.workbook_id}.pbip"
    pbip_path.write_text("", encoding="utf-8")       # 0-byte placeholder for now
    return StageResult(
        output={"stub_stage": "package_validate", "pbip_path": str(pbip_path)},
        summary_md=(
            "# Stage 8 — package + validate (stub)\n\n"
            f"Wrote empty placeholder: `{pbip_path.name}`\n"
        ),
        errors=(),
    )
```

- [x] **Step 13.5: Create `tests/unit/stages/__init__.py`** — empty.

- [x] **Step 13.6: Run test — verify pass**

```bash
pytest tests/unit/stages/test_all_stages_stub.py -v
```
Expected: `8 passed`.

- [x] **Step 13.7: Commit**

```bash
git add src/tableau2pbir/stages/ tests/unit/stages/__init__.py tests/unit/stages/test_all_stages_stub.py
git commit -m "feat(stages): add 8 no-op stage stubs returning StageResult"
```

---

## Task 14: Pipeline runner (sequence, persistence, --gate, --from)

**Files:**
- Modify: `src/tableau2pbir/pipeline.py`
- Create: `tests/unit/test_pipeline_runner.py`

- [x] **Step 14.1: Write failing test**

`tests/unit/test_pipeline_runner.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tableau2pbir.pipeline import (
    STAGE_SEQUENCE, PipelineResult, StageContext, run_pipeline,
)


def test_stage_sequence_has_8_stages():
    assert len(STAGE_SEQUENCE) == 8
    names = [s[0] for s in STAGE_SEQUENCE]
    assert names == ["extract", "canonicalize", "translate_calcs", "map_visuals",
                     "compute_layout", "build_tmdl", "build_pbir", "package_validate"]


def test_run_pipeline_full_run(tmp_path: Path):
    out = tmp_path / "wb"
    result = run_pipeline(
        workbook_id="wb",
        source_path=Path("dummy.twb"),
        output_dir=out,
        config={},
        gate=None,
        resume_from=None,
    )
    assert isinstance(result, PipelineResult)
    assert result.stages_run == 8
    # Per-stage artifacts
    for i, (name, _mod) in enumerate(STAGE_SEQUENCE, start=1):
        assert (out / "stages" / f"{i:02d}_{name}.json").exists()
        assert (out / "stages" / f"{i:02d}_{name}.summary.md").exists()
    # Stage 8 placeholder
    assert (out / "wb.pbip").exists()
    # Cumulative unsupported file exists
    assert (out / "unsupported.json").exists()


def test_run_pipeline_gate_stops_after_named_stage(tmp_path: Path):
    out = tmp_path / "wb"
    result = run_pipeline(
        workbook_id="wb", source_path=Path("d.twb"), output_dir=out,
        config={}, gate="canonicalize", resume_from=None,
    )
    assert result.stages_run == 2                          # extract + canonicalize
    assert (out / "stages" / "02_canonicalize.json").exists()
    assert not (out / "stages" / "03_translate_calcs.json").exists()


def test_run_pipeline_resume_from_reads_prior_output(tmp_path: Path):
    out = tmp_path / "wb"
    # First: gated run stops after stage 2
    run_pipeline(workbook_id="wb", source_path=Path("d.twb"), output_dir=out,
                 config={}, gate="canonicalize", resume_from=None)
    assert (out / "stages" / "02_canonicalize.json").exists()
    assert not (out / "stages" / "08_package_validate.json").exists()
    # Resume: picks up from stage 3
    result = run_pipeline(workbook_id="wb", source_path=Path("d.twb"), output_dir=out,
                          config={}, gate=None, resume_from="translate_calcs")
    assert result.stages_run == 6                          # stages 3..8
    assert (out / "stages" / "08_package_validate.json").exists()


def test_run_pipeline_resume_from_unknown_stage_errors(tmp_path: Path):
    with pytest.raises(ValueError, match="unknown stage"):
        run_pipeline(workbook_id="wb", source_path=Path("d.twb"),
                     output_dir=tmp_path, config={}, gate=None, resume_from="nonsense")
```

- [x] **Step 14.2: Run test — verify failure**

```bash
pytest tests/unit/test_pipeline_runner.py -v
```
Expected: `ImportError: cannot import name 'STAGE_SEQUENCE' ...`.

- [x] **Step 14.3: Extend `src/tableau2pbir/pipeline.py`**

Append below the contract types defined in Task 12:

```python
# ---- Stage registry + runner ----

import importlib
import json as _json
from pydantic import BaseModel as _BaseModel


def _load_stage(name: str):
    """Import a stage module by short name (e.g. 'extract' -> s01_extract)."""
    mapping = {
        "extract": "s01_extract",
        "canonicalize": "s02_canonicalize",
        "translate_calcs": "s03_translate_calcs",
        "map_visuals": "s04_map_visuals",
        "compute_layout": "s05_compute_layout",
        "build_tmdl": "s06_build_tmdl",
        "build_pbir": "s07_build_pbir",
        "package_validate": "s08_package_validate",
    }
    if name not in mapping:
        raise ValueError(f"unknown stage: {name!r}")
    return importlib.import_module(f"tableau2pbir.stages.{mapping[name]}")


STAGE_SEQUENCE: list[tuple[str, str]] = [
    (name, f"s{i:02d}_{name if name != 'package_validate' else 'package_validate'}")
    for i, name in enumerate([
        "extract", "canonicalize", "translate_calcs", "map_visuals",
        "compute_layout", "build_tmdl", "build_pbir", "package_validate",
    ], start=1)
]


class PipelineResult(_BaseModel):
    workbook_id: str
    stages_run: int
    errors: tuple[StageError, ...]
    stopped_at_gate: str | None = None


def run_pipeline(
    *,
    workbook_id: str,
    source_path: Path,
    output_dir: Path,
    config: dict,
    gate: str | None,
    resume_from: str | None,
) -> PipelineResult:
    """Run the 8-stage pipeline. See spec §4.3 and §4.5."""
    if gate is not None and gate not in {name for name, _ in STAGE_SEQUENCE}:
        raise ValueError(f"unknown stage: {gate!r}")
    if resume_from is not None and resume_from not in {name for name, _ in STAGE_SEQUENCE}:
        raise ValueError(f"unknown stage: {resume_from!r}")

    stages_dir = output_dir / "stages"
    stages_dir.mkdir(parents=True, exist_ok=True)

    # Determine the first stage index to run
    resume_idx = 0
    if resume_from is not None:
        resume_idx = next(i for i, (name, _) in enumerate(STAGE_SEQUENCE) if name == resume_from)

    # Load prior stage's output when resuming
    current_input: dict
    if resume_idx == 0:
        current_input = {"source_path": str(source_path)}
    else:
        prior_name = STAGE_SEQUENCE[resume_idx - 1][0]
        prior_path = stages_dir / f"{resume_idx:02d}_{prior_name}.json"
        if not prior_path.exists():
            raise FileNotFoundError(
                f"cannot resume from {resume_from!r}: missing prior artifact {prior_path}"
            )
        current_input = _json.loads(prior_path.read_text(encoding="utf-8"))

    all_errors: list[StageError] = []
    stages_run = 0
    stopped_at_gate: str | None = None

    for idx, (name, _mod) in enumerate(STAGE_SEQUENCE[resume_idx:], start=resume_idx + 1):
        mod = _load_stage(name)
        ctx = StageContext(
            workbook_id=workbook_id, output_dir=output_dir,
            config=config, stage_number=idx,
        )
        result = mod.run(current_input, ctx)
        # Persist artifacts
        (stages_dir / f"{idx:02d}_{name}.json").write_text(
            _json.dumps(result.output, indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )
        (stages_dir / f"{idx:02d}_{name}.summary.md").write_text(
            result.summary_md, encoding="utf-8",
        )
        all_errors.extend(result.errors)
        current_input = result.output
        stages_run += 1
        # fatal errors halt this workbook (per §8.2)
        if any(e.severity == "fatal" for e in result.errors):
            break
        # --gate <stage> pauses after the named stage
        if gate is not None and name == gate:
            stopped_at_gate = name
            break

    # Write cumulative unsupported.json (empty in Plan 1)
    (output_dir / "unsupported.json").write_text(
        _json.dumps([], indent=2), encoding="utf-8",
    )
    return PipelineResult(
        workbook_id=workbook_id,
        stages_run=stages_run,
        errors=tuple(all_errors),
        stopped_at_gate=stopped_at_gate,
    )
```

- [x] **Step 14.4: Run test — verify pass**

```bash
pytest tests/unit/test_pipeline_runner.py -v
```
Expected: `5 passed`.

- [x] **Step 14.5: Commit**

```bash
git add src/tableau2pbir/pipeline.py tests/unit/test_pipeline_runner.py
git commit -m "feat(pipeline): add 8-stage runner with --gate and --from support (§4.3, §4.5)"
```

---

## Task 15: LLM — cache module

**Files:**
- Create: `src/tableau2pbir/llm/__init__.py`
- Create: `src/tableau2pbir/llm/cache.py`
- Create: `tests/unit/llm/__init__.py`
- Create: `tests/unit/llm/test_cache.py`

- [x] **Step 15.1: Write failing test**

`tests/unit/llm/test_cache.py`:

```python
from __future__ import annotations

from pathlib import Path

from tableau2pbir.llm.cache import OnDiskCache, make_cache_key


def test_make_cache_key_is_stable():
    k1 = make_cache_key(model="m", prompt_hash="p", schema_hash="s", payload={"x": 1})
    k2 = make_cache_key(model="m", prompt_hash="p", schema_hash="s", payload={"x": 1})
    assert k1 == k2
    assert len(k1) == 64                 # sha256 hex


def test_cache_roundtrip(tmp_path: Path):
    c = OnDiskCache(tmp_path)
    assert c.get("missing_key") is None
    c.put("k1", {"dax": "SUM([x])"})
    assert c.get("k1") == {"dax": "SUM([x])"}


def test_cache_key_changes_on_payload_change():
    k1 = make_cache_key(model="m", prompt_hash="p", schema_hash="s", payload={"x": 1})
    k2 = make_cache_key(model="m", prompt_hash="p", schema_hash="s", payload={"x": 2})
    assert k1 != k2
```

- [x] **Step 15.2: Run test — verify failure**

```bash
pytest tests/unit/llm/test_cache.py -v
```
Expected: `ModuleNotFoundError`.

- [x] **Step 15.3: Write `src/tableau2pbir/llm/__init__.py`** — empty.

- [x] **Step 15.4: Write `src/tableau2pbir/llm/cache.py`**

```python
"""On-disk LLM response cache — §7. Content-hash keyed; JSON-on-disk."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def make_cache_key(*, model: str, prompt_hash: str, schema_hash: str, payload: dict) -> str:
    """Return a stable 64-char sha256 hex over (model, prompt, schema, payload)."""
    h = hashlib.sha256()
    h.update(model.encode("utf-8"))
    h.update(b"\x00")
    h.update(prompt_hash.encode("utf-8"))
    h.update(b"\x00")
    h.update(schema_hash.encode("utf-8"))
    h.update(b"\x00")
    h.update(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    return h.hexdigest()


class OnDiskCache:
    """Simple read-through cache rooted at a directory. One file per key."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.root / f"{key}.json"

    def get(self, key: str) -> dict | None:
        p = self._path(key)
        if not p.exists():
            return None
        return json.loads(p.read_text(encoding="utf-8"))

    def put(self, key: str, value: dict) -> None:
        self._path(key).write_text(
            json.dumps(value, indent=2, sort_keys=True), encoding="utf-8",
        )
```

- [x] **Step 15.5: Create `tests/unit/llm/__init__.py`** — empty.

- [x] **Step 15.6: Run test — verify pass**

```bash
pytest tests/unit/llm/test_cache.py -v
```
Expected: `3 passed`.

- [x] **Step 15.7: Commit**

```bash
git add src/tableau2pbir/llm/__init__.py src/tableau2pbir/llm/cache.py \
        tests/unit/llm/__init__.py tests/unit/llm/test_cache.py
git commit -m "feat(llm): add content-hash on-disk cache per §7"
```

---

## Task 16: LLM — snapshot replay module

**Files:**
- Create: `src/tableau2pbir/llm/snapshots.py`
- Create: `tests/unit/llm/test_snapshots.py`

- [x] **Step 16.1: Write failing test**

`tests/unit/llm/test_snapshots.py`:

```python
from __future__ import annotations

import os
from pathlib import Path

import pytest

from tableau2pbir.llm.snapshots import SnapshotStore, is_replay_mode


def test_is_replay_mode_reads_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("PYTEST_SNAPSHOT", raising=False)
    assert is_replay_mode() is False
    monkeypatch.setenv("PYTEST_SNAPSHOT", "replay")
    assert is_replay_mode() is True
    monkeypatch.setenv("PYTEST_SNAPSHOT", "record")
    assert is_replay_mode() is False


def test_snapshot_store_load(tmp_path: Path):
    (tmp_path / "translate_calc").mkdir()
    (tmp_path / "translate_calc" / "fixture1.json").write_text(
        '{"dax_expr": "SUM([Sales])", "confidence": "high", "notes": ""}',
        encoding="utf-8",
    )
    store = SnapshotStore(tmp_path)
    data = store.load("translate_calc", "fixture1")
    assert data["dax_expr"] == "SUM([Sales])"


def test_snapshot_store_missing_raises(tmp_path: Path):
    store = SnapshotStore(tmp_path)
    with pytest.raises(FileNotFoundError):
        store.load("translate_calc", "missing")
```

- [x] **Step 16.2: Run test — verify failure**

```bash
pytest tests/unit/llm/test_snapshots.py -v
```
Expected: `ModuleNotFoundError`.

- [x] **Step 16.3: Write `src/tableau2pbir/llm/snapshots.py`**

```python
"""LLM snapshot replay — §9 layer vi + §7 step 4."""
from __future__ import annotations

import json
import os
from pathlib import Path


def is_replay_mode() -> bool:
    """True iff PYTEST_SNAPSHOT=replay is set. Drives zero-network test runs."""
    return os.environ.get("PYTEST_SNAPSHOT") == "replay"


class SnapshotStore:
    """Reads tests/llm_snapshots/<method>/<fixture>.json files."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def load(self, method: str, fixture: str) -> dict:
        path = self.root / method / f"{fixture}.json"
        if not path.exists():
            raise FileNotFoundError(f"no snapshot: {path}")
        return json.loads(path.read_text(encoding="utf-8"))
```

- [x] **Step 16.4: Run test — verify pass**

```bash
pytest tests/unit/llm/test_snapshots.py -v
```
Expected: `3 passed`.

- [x] **Step 16.5: Commit**

```bash
git add src/tableau2pbir/llm/snapshots.py tests/unit/llm/test_snapshots.py
git commit -m "feat(llm): add snapshot replay store per §9 layer vi"
```

---

## Task 17: LLM — prompt loader + per-prompt folder structure

**Files:**
- Create: `src/tableau2pbir/llm/prompt_loader.py`
- Create: `src/tableau2pbir/llm/prompts/translate_calc/system.md`
- Create: `src/tableau2pbir/llm/prompts/translate_calc/tool_schema.json`
- Create: `src/tableau2pbir/llm/prompts/translate_calc/VERSION`
- Create: `src/tableau2pbir/llm/prompts/translate_calc/examples/.gitkeep`
- Create: `src/tableau2pbir/llm/prompts/map_visual/system.md`
- Create: `src/tableau2pbir/llm/prompts/map_visual/tool_schema.json`
- Create: `src/tableau2pbir/llm/prompts/map_visual/VERSION`
- Create: `src/tableau2pbir/llm/prompts/map_visual/examples/.gitkeep`
- Create: `src/tableau2pbir/llm/prompts/cleanup_name/system.md`
- Create: `src/tableau2pbir/llm/prompts/cleanup_name/tool_schema.json`
- Create: `src/tableau2pbir/llm/prompts/cleanup_name/VERSION`
- Create: `src/tableau2pbir/llm/prompts/cleanup_name/examples/.gitkeep`
- Create: `tests/unit/llm/test_prompt_loader.py`

- [x] **Step 17.1: Write failing test**

`tests/unit/llm/test_prompt_loader.py`:

```python
from __future__ import annotations

from tableau2pbir.llm.prompt_loader import PromptPack, load_prompt_pack


def test_load_translate_calc_pack():
    pack = load_prompt_pack("translate_calc")
    assert isinstance(pack, PromptPack)
    assert pack.method == "translate_calc"
    assert pack.version
    assert pack.system_text
    assert "name" in pack.tool_schema
    assert pack.system_prompt_hash
    assert pack.tool_schema_hash


def test_load_map_visual_pack():
    pack = load_prompt_pack("map_visual")
    assert pack.method == "map_visual"
    assert pack.tool_schema.get("name")


def test_load_cleanup_name_pack():
    pack = load_prompt_pack("cleanup_name")
    assert pack.method == "cleanup_name"


def test_version_change_changes_hash():
    pack = load_prompt_pack("translate_calc")
    assert pack.version in pack.system_prompt_hash                 # version folded into hash
```

- [x] **Step 17.2: Run test — verify failure**

```bash
pytest tests/unit/llm/test_prompt_loader.py -v
```
Expected: `ModuleNotFoundError`.

- [x] **Step 17.3: Create prompt folder content**

For each of the three methods (`translate_calc`, `map_visual`, `cleanup_name`), create:

`src/tableau2pbir/llm/prompts/translate_calc/VERSION`:
```
0.1.0
```

`src/tableau2pbir/llm/prompts/translate_calc/system.md`:
```markdown
# translate_calc — system prompt

You convert Tableau calculated-field expressions into DAX for a Power BI semantic model.
The caller passes an IR-derived bundle describing the calc's kind (row, aggregate, table_calc, lod_fixed, lod_include, lod_exclude), phase (row, aggregate, viz), and any kind-specific payload (table_calc frame, lod dimensions).

You MUST emit your response via the `translate_calc_output` tool. Do not reply in prose.
You MUST emit valid DAX. If you cannot, set `confidence: "low"` and leave `dax_expr` empty.
```

`src/tableau2pbir/llm/prompts/translate_calc/tool_schema.json`:
```json
{
  "name": "translate_calc_output",
  "description": "Return the DAX translation of a Tableau calculation with confidence.",
  "input_schema": {
    "type": "object",
    "properties": {
      "dax_expr": {"type": "string"},
      "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
      "notes": {"type": "string"}
    },
    "required": ["dax_expr", "confidence", "notes"],
    "additionalProperties": false
  }
}
```

`src/tableau2pbir/llm/prompts/translate_calc/examples/.gitkeep` — empty.

`src/tableau2pbir/llm/prompts/map_visual/VERSION`: `0.1.0`

`src/tableau2pbir/llm/prompts/map_visual/system.md`:
```markdown
# map_visual — system prompt

You map a Tableau (mark, shelves) pair into a PBIR visual with encoding bindings.
Choose only from the provided `visual_type` enum. Every encoding_binding must reference a field present in the input bundle.

You MUST emit via the `map_visual_output` tool.
```

`src/tableau2pbir/llm/prompts/map_visual/tool_schema.json`:
```json
{
  "name": "map_visual_output",
  "description": "Return the PBIR visual type and encoding bindings for a Tableau sheet.",
  "input_schema": {
    "type": "object",
    "properties": {
      "visual_type": {"type": "string"},
      "encoding_bindings": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "channel": {"type": "string"},
            "field_ref": {"type": "string"}
          },
          "required": ["channel", "field_ref"],
          "additionalProperties": false
        }
      },
      "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
      "notes": {"type": "string"}
    },
    "required": ["visual_type", "encoding_bindings", "confidence", "notes"],
    "additionalProperties": false
  }
}
```

`src/tableau2pbir/llm/prompts/map_visual/examples/.gitkeep` — empty.

`src/tableau2pbir/llm/prompts/cleanup_name/VERSION`: `0.1.0`

`src/tableau2pbir/llm/prompts/cleanup_name/system.md`:
```markdown
# cleanup_name — system prompt

You rewrite Tableau auto-names (e.g., `SUM(Sales)`, `CALC_abc123`) into human-readable PBIR names.
Preserve semantics. Never invent units, business meaning, or abbreviations not present in the input.

You MUST emit via the `cleanup_name_output` tool.
```

`src/tableau2pbir/llm/prompts/cleanup_name/tool_schema.json`:
```json
{
  "name": "cleanup_name_output",
  "description": "Return a cleaned human-readable name.",
  "input_schema": {
    "type": "object",
    "properties": {
      "cleaned_name": {"type": "string"},
      "notes": {"type": "string"}
    },
    "required": ["cleaned_name", "notes"],
    "additionalProperties": false
  }
}
```

`src/tableau2pbir/llm/prompts/cleanup_name/examples/.gitkeep` — empty.

- [x] **Step 17.4: Write `src/tableau2pbir/llm/prompt_loader.py`**

```python
"""Loads a per-prompt folder (§7) and computes its content hashes.

Each prompt method owns a folder containing:
  system.md        — system prompt text
  tool_schema.json — Anthropic tool-use JSON Schema
  VERSION          — semver; bumping invalidates cache + snapshots
  examples/*       — optional few-shot content (concatenated into system text)
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_PROMPTS_ROOT = Path(__file__).parent / "prompts"


@dataclass(frozen=True)
class PromptPack:
    method: str
    version: str
    system_text: str
    tool_schema: dict[str, Any]
    system_prompt_hash: str
    tool_schema_hash: str


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def load_prompt_pack(method: str, root: Path | None = None) -> PromptPack:
    base = (root or _PROMPTS_ROOT) / method
    if not base.is_dir():
        raise FileNotFoundError(f"no prompt folder for method: {method!r}")
    version = (base / "VERSION").read_text(encoding="utf-8").strip()
    system_text = (base / "system.md").read_text(encoding="utf-8")
    # Include any example file content in the system text (concatenated, stable order)
    examples_dir = base / "examples"
    if examples_dir.is_dir():
        for example in sorted(examples_dir.glob("*")):
            if example.is_file() and example.name != ".gitkeep":
                system_text += "\n\n---\n\n" + example.read_text(encoding="utf-8")
    tool_schema = json.loads((base / "tool_schema.json").read_text(encoding="utf-8"))
    # Fold version into the system-prompt hash so a VERSION bump changes the hash
    # and thereby invalidates both the on-disk cache and snapshot entries (§A.3).
    system_hash_input = f"{version}\n---\n{system_text}"
    return PromptPack(
        method=method,
        version=version,
        system_text=system_text,
        tool_schema=tool_schema,
        system_prompt_hash=version + "-" + _hash(system_hash_input),
        tool_schema_hash=_hash(json.dumps(tool_schema, sort_keys=True)),
    )
```

- [x] **Step 17.5: Run test — verify pass**

```bash
pytest tests/unit/llm/test_prompt_loader.py -v
```
Expected: `4 passed`.

- [x] **Step 17.6: Commit**

```bash
git add src/tableau2pbir/llm/prompt_loader.py src/tableau2pbir/llm/prompts/ tests/unit/llm/test_prompt_loader.py
git commit -m "feat(llm): per-prompt folder layout + loader with VERSION-hash invalidation (§7)"
```

---

## Task 18: LLMClient skeleton (3 methods)

**Files:**
- Create: `src/tableau2pbir/llm/client.py`
- Create: `tests/unit/llm/test_client.py`

- [x] **Step 18.1: Write failing test**

`tests/unit/llm/test_client.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from tableau2pbir.llm.client import LLMClient


def test_client_init_loads_three_prompt_packs(tmp_path: Path):
    client = LLMClient(cache_dir=tmp_path, model_by_method={})
    assert set(client.packs.keys()) == {"translate_calc", "map_visual", "cleanup_name"}


def test_translate_calc_raises_not_implemented(tmp_path: Path):
    client = LLMClient(cache_dir=tmp_path, model_by_method={})
    with pytest.raises(NotImplementedError, match="Plan 3"):
        client.translate_calc({"tableau_expr": "SUM([x])"})


def test_map_visual_raises_not_implemented(tmp_path: Path):
    client = LLMClient(cache_dir=tmp_path, model_by_method={})
    with pytest.raises(NotImplementedError, match="Plan 3"):
        client.map_visual({"mark_type": "bar"})


def test_cleanup_name_raises_not_implemented(tmp_path: Path):
    client = LLMClient(cache_dir=tmp_path, model_by_method={})
    with pytest.raises(NotImplementedError, match="Plan 3"):
        client.cleanup_name(raw_name="SUM(Sales)", kind="measure")
```

- [x] **Step 18.2: Run test — verify failure**

```bash
pytest tests/unit/llm/test_client.py -v
```
Expected: `ModuleNotFoundError`.

- [x] **Step 18.3: Write `src/tableau2pbir/llm/client.py`**

```python
"""LLMClient — single AI entry point per spec §7.

This Plan-1 skeleton wires cache + prompt packs but raises NotImplementedError
on the three public methods; Plan 3 (stage 3 + stage 4 implementation) fills
them in with the Anthropic SDK flow (cache -> snapshot -> API -> validator).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from tableau2pbir.llm.cache import OnDiskCache
from tableau2pbir.llm.prompt_loader import PromptPack, load_prompt_pack

_METHODS = ("translate_calc", "map_visual", "cleanup_name")
_DEFAULT_MODEL = "claude-sonnet-4-6"


class LLMClient:
    def __init__(
        self,
        *,
        cache_dir: Path,
        model_by_method: dict[str, str] | None = None,
    ) -> None:
        self.cache = OnDiskCache(cache_dir)
        self.packs: dict[str, PromptPack] = {m: load_prompt_pack(m) for m in _METHODS}
        self.model_by_method = {m: _DEFAULT_MODEL for m in _METHODS}
        if model_by_method:
            self.model_by_method.update(model_by_method)

    # --- Plan-3 targets (stub in Plan 1) ---

    def translate_calc(self, calc_subset: dict[str, Any]) -> dict[str, Any]:
        """Return {dax_expr, confidence, notes}. Implemented in Plan 3."""
        raise NotImplementedError("LLMClient.translate_calc is filled in in Plan 3")

    def map_visual(self, sheet_subset: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError("LLMClient.map_visual is filled in in Plan 3")

    def cleanup_name(self, *, raw_name: str, kind: str) -> dict[str, Any]:
        raise NotImplementedError("LLMClient.cleanup_name is filled in in Plan 3")
```

- [x] **Step 18.4: Run test — verify pass**

```bash
pytest tests/unit/llm/test_client.py -v
```
Expected: `4 passed`.

- [x] **Step 18.5: Commit**

```bash
git add src/tableau2pbir/llm/client.py tests/unit/llm/test_client.py
git commit -m "feat(llm): add LLMClient skeleton with cache + prompt-pack wiring (§7)"
```

---

## Task 19: Trivial synthetic fixture

**Files:**
- Create: `tests/golden/synthetic/trivial.twb`
- Create: `tests/golden/README.md`

- [x] **Step 19.1: Write the minimal valid `.twb` XML**

`tests/golden/synthetic/trivial.twb`:

```xml
<?xml version='1.0' encoding='utf-8' ?>
<workbook xmlns:user='http://www.tableausoftware.com/xml/user' source-build='2024.1' source-platform='win' version='18.1'>
  <datasources>
    <datasource caption='Sample' name='sample.csv' hasconnection='true'>
      <connection class='textscan' directory='.' filename='sample.csv' server='' />
      <column datatype='integer' name='[id]' role='dimension' type='ordinal'/>
      <column datatype='integer' name='[amount]' role='measure' type='quantitative'/>
    </datasource>
  </datasources>
  <worksheets>
    <worksheet name='Revenue'>
      <view>
        <datasources>
          <datasource name='sample.csv'/>
        </datasources>
        <rows>[amount]</rows>
        <columns>[id]</columns>
      </view>
    </worksheet>
  </worksheets>
  <dashboards>
    <dashboard name='Main'>
      <size maxheight='800' maxwidth='1200' minheight='800' minwidth='1200'/>
      <zones>
        <zone name='Revenue' type='worksheet' id='1' h='800' w='1200' x='0' y='0'/>
      </zones>
    </dashboard>
  </dashboards>
</workbook>
```

- [x] **Step 19.2: Write `tests/golden/README.md`**

```markdown
# Golden fixtures

Full-roadmap corpus per spec §9. Plan 1 ships only `synthetic/trivial.twb`;
subsequent plans add fixtures per §9's tables (~25 calc kind×frame,
~5 parameter intent, ~12 connector Tier-1/Tier-2, edge cases).

- `synthetic/` — hand-authored single-feature `.twb` workbooks.
- `real/` — 3–5 production workbooks with paired `<wb>.rubric.yaml` (§15).
- `expected/` — expected `.pbip` trees for the diff-based layer iii tests.
```

- [x] **Step 19.3: Commit**

```bash
git add tests/golden/synthetic/trivial.twb tests/golden/README.md
git commit -m "test(golden): add trivial single-sheet .twb fixture"
```

---

## Task 20: CLI — argparse + convert + resume subcommands

**Files:**
- Create: `src/tableau2pbir/cli.py`
- Create: `tests/unit/test_cli.py`

- [x] **Step 20.1: Write failing test**

`tests/unit/test_cli.py`:

```python
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_cli_convert_runs_empty_pipeline(tmp_path: Path, synthetic_fixtures_dir: Path):
    out = tmp_path / "out"
    result = subprocess.run(
        [sys.executable, "-m", "tableau2pbir.cli", "convert",
         str(synthetic_fixtures_dir / "trivial.twb"), "--out", str(out)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert (out / "trivial" / "trivial.pbip").exists()
    assert (out / "trivial" / "stages" / "08_package_validate.json").exists()
    assert (out / "trivial" / "unsupported.json").exists()


def test_cli_convert_with_gate_stops_early(tmp_path: Path, synthetic_fixtures_dir: Path):
    out = tmp_path / "out"
    result = subprocess.run(
        [sys.executable, "-m", "tableau2pbir.cli", "convert",
         str(synthetic_fixtures_dir / "trivial.twb"),
         "--out", str(out), "--gate", "canonicalize"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert (out / "trivial" / "stages" / "02_canonicalize.json").exists()
    assert not (out / "trivial" / "stages" / "03_translate_calcs.json").exists()


def test_cli_resume_continues_from(tmp_path: Path, synthetic_fixtures_dir: Path):
    out = tmp_path / "out"
    # First: gated run
    subprocess.run(
        [sys.executable, "-m", "tableau2pbir.cli", "convert",
         str(synthetic_fixtures_dir / "trivial.twb"),
         "--out", str(out), "--gate", "canonicalize"],
        capture_output=True, text=True, check=True,
    )
    # Resume
    result = subprocess.run(
        [sys.executable, "-m", "tableau2pbir.cli", "resume",
         str(out / "trivial"), "--from", "translate_calcs"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert (out / "trivial" / "trivial.pbip").exists()


def test_cli_help_lists_subcommands():
    result = subprocess.run(
        [sys.executable, "-m", "tableau2pbir.cli", "--help"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "convert" in result.stdout
    assert "resume" in result.stdout
```

- [x] **Step 20.2: Run test — verify failure**

```bash
pytest tests/unit/test_cli.py -v
```
Expected: `ModuleNotFoundError: No module named 'tableau2pbir.cli'`.

- [x] **Step 20.3: Write `src/tableau2pbir/cli.py`**

```python
"""CLI — `tableau2pbir` with `convert` and `resume` subcommands. See spec §4.1.

Batch support in Plan 1 is single-workbook only (convert one .twb/.twbx per
invocation). Multiprocessing batch pool is added in Plan 5 (§4.1)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tableau2pbir.pipeline import STAGE_SEQUENCE, run_pipeline


def _stage_names() -> list[str]:
    return [name for name, _ in STAGE_SEQUENCE]


def _workbook_id(source_path: Path) -> str:
    return source_path.stem


def _cmd_convert(args: argparse.Namespace) -> int:
    source_path = Path(args.source).resolve()
    out_root = Path(args.out).resolve()
    wb_id = _workbook_id(source_path)
    output_dir = out_root / wb_id
    output_dir.mkdir(parents=True, exist_ok=True)
    result = run_pipeline(
        workbook_id=wb_id,
        source_path=source_path,
        output_dir=output_dir,
        config={},
        gate=args.gate,
        resume_from=None,
    )
    print(
        f"[tableau2pbir] wb={wb_id} stages_run={result.stages_run}"
        f"{' gate=' + result.stopped_at_gate if result.stopped_at_gate else ''}"
    )
    return 0


def _cmd_resume(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir).resolve()
    wb_id = output_dir.name
    # Source path is informational only when resuming — stages read their own prior outputs.
    source_path = output_dir / f"{wb_id}.twb"
    result = run_pipeline(
        workbook_id=wb_id,
        source_path=source_path,
        output_dir=output_dir,
        config={},
        gate=args.gate,
        resume_from=args.from_stage,
    )
    print(f"[tableau2pbir] resumed wb={wb_id} stages_run={result.stages_run}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tableau2pbir",
        description="Convert Tableau workbooks (.twb/.twbx) to Power BI (PBIR).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_conv = sub.add_parser("convert", help="Convert one workbook end-to-end.")
    p_conv.add_argument("source", help="Path to .twb or .twbx")
    p_conv.add_argument("--out", required=True, help="Output root directory")
    p_conv.add_argument("--gate", choices=_stage_names(), default=None,
                        help="Pause after the named stage")
    p_conv.set_defaults(func=_cmd_convert)

    p_res = sub.add_parser("resume", help="Resume a previously-gated workbook.")
    p_res.add_argument("output_dir", help="The ./out/<wb>/ directory from a prior run")
    p_res.add_argument("--from", dest="from_stage", required=True,
                       choices=_stage_names(),
                       help="Stage to resume from (runs this one and all subsequent)")
    p_res.add_argument("--gate", choices=_stage_names(), default=None,
                       help="Optional second gate on resume")
    p_res.set_defaults(func=_cmd_resume)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
```

- [x] **Step 20.4: Run test — verify pass**

```bash
pytest tests/unit/test_cli.py -v
```
Expected: `4 passed`.

- [x] **Step 20.5: Commit**

```bash
git add src/tableau2pbir/cli.py tests/unit/test_cli.py
git commit -m "feat(cli): add argparse CLI with convert and resume subcommands (§4.1)"
```

---

## Task 21: End-to-end smoke (integration test)

**Files:**
- Create: `tests/integration/__init__.py`
- Create: `tests/integration/test_empty_pipeline_end_to_end.py`

- [x] **Step 21.1: Write failing test**

`tests/integration/test_empty_pipeline_end_to_end.py`:

```python
"""Layer iii (§9) smoke: `tableau2pbir convert` on the trivial fixture produces
the full expected artifact tree. Real IR/DAX/PBIR content comes in Plans 2–5."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.integration
def test_end_to_end_empty_pipeline(tmp_path: Path, synthetic_fixtures_dir: Path):
    out = tmp_path / "out"
    fixture = synthetic_fixtures_dir / "trivial.twb"

    result = subprocess.run(
        [sys.executable, "-m", "tableau2pbir.cli", "convert",
         str(fixture), "--out", str(out)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"stderr:\n{result.stderr}\nstdout:\n{result.stdout}"

    wb_dir = out / "trivial"
    stages = wb_dir / "stages"

    expected_stages = [
        (1, "extract"), (2, "canonicalize"), (3, "translate_calcs"),
        (4, "map_visuals"), (5, "compute_layout"), (6, "build_tmdl"),
        (7, "build_pbir"), (8, "package_validate"),
    ]
    for idx, name in expected_stages:
        assert (stages / f"{idx:02d}_{name}.json").exists(), f"missing {idx:02d}_{name}.json"
        assert (stages / f"{idx:02d}_{name}.summary.md").exists(), f"missing {idx:02d}_{name}.summary.md"

    assert (wb_dir / "trivial.pbip").exists()
    assert (wb_dir / "unsupported.json").exists()
```

- [x] **Step 21.2: Create `tests/integration/__init__.py`** — empty file.

- [x] **Step 21.3: Run test — verify pass**

```bash
pytest tests/integration/test_empty_pipeline_end_to_end.py -v
```
Expected: `1 passed` (the stubs + runner + CLI from prior tasks make this work already).

- [x] **Step 21.4: Commit**

```bash
git add tests/integration/__init__.py tests/integration/test_empty_pipeline_end_to_end.py
git commit -m "test(integration): smoke test for empty pipeline end-to-end (layer iii)"
```

---

## Task 22: Stub validity test directories (iv, iv-b, iv-c, vii)

**Files:**
- Create: `tests/validity/__init__.py`
- Create: `tests/validity/tmdl/__init__.py`
- Create: `tests/validity/tmdl/README.md`
- Create: `tests/validity/pbir/__init__.py`
- Create: `tests/validity/pbir/README.md`
- Create: `tests/validity/dax_semantic/__init__.py`
- Create: `tests/validity/dax_semantic/README.md`
- Create: `tests/desktop_open/__init__.py`
- Create: `tests/desktop_open/README.md`
- Create: `tests/llm_snapshots/translate_calc/.gitkeep`
- Create: `tests/llm_snapshots/map_visual/.gitkeep`
- Create: `tests/llm_snapshots/cleanup_name/.gitkeep`
- Create: `tests/golden/real/README.md`
- Create: `tests/golden/expected/.gitkeep`

- [x] **Step 22.1: Create validity layer directories with README stubs**

`tests/validity/__init__.py` — empty.
`tests/validity/tmdl/__init__.py` — empty.
`tests/validity/pbir/__init__.py` — empty.
`tests/validity/dax_semantic/__init__.py` — empty.
`tests/desktop_open/__init__.py` — empty.

`tests/validity/tmdl/README.md`:
```markdown
# Layer iv — TMDL validity

Runs TabularEditor 2 CLI + AnalysisServices .NET load probe against stage-6
TMDL output. See spec §9 layer iv. Populated in Plan 4/5.
```

`tests/validity/pbir/README.md`:
```markdown
# Layer iv-b — PBIR compile validity

Runs `pbi-tools compile` against stage-7 PBIR tree. See spec §9 layer iv-b.
Populated in Plan 4/5.
```

`tests/validity/dax_semantic/README.md`:
```markdown
# Layer iv-c — synthetic DAX semantic probes

Each synthetic calc fixture ships an `<fixture>.expected_values.yaml`.
Runner loads generated TMDL via AS .NET load probe, evaluates
`(calc, filter_context)` tuples as DAX queries, compares within tolerance.
See spec §9 layer iv-c. Populated in Plan 3.
```

`tests/desktop_open/README.md`:
```markdown
# Layer vii — Desktop-open gate (real-workbook subset)

Windows CI runner launches `PBIDesktop.exe /Open <pbip>` and parses the
trace directory for canonical events: ReportLoaded, ModelLoaded,
RepairPrompt, ModelError, VisualError, AuthenticationNeeded,
AuthUIDisplayed. Pass criteria split by datasource tier. See spec §9
layer vii + §6 Stage 8 step 5. Populated in Plan 5.
```

- [x] **Step 22.2: Create llm_snapshots placeholders**

Create empty directories by committing `.gitkeep` files:

```
tests/llm_snapshots/translate_calc/.gitkeep
tests/llm_snapshots/map_visual/.gitkeep
tests/llm_snapshots/cleanup_name/.gitkeep
```

- [x] **Step 22.3: Create tests/golden placeholders**

`tests/golden/real/README.md`:
```markdown
# Real-workbook subset

3–5 production workbooks for end-to-end coverage (§9). Each paired with
`<wb>.rubric.yaml` (§15). Populated in Plan 5.
```

`tests/golden/expected/.gitkeep` — empty.

- [x] **Step 22.4: Sanity: whole test suite still green**

```bash
pytest -q
```
Expected: all tests pass.

- [x] **Step 22.5: Commit**

```bash
git add tests/validity tests/desktop_open tests/llm_snapshots tests/golden/real tests/golden/expected
git commit -m "test: stub directories + README for layers iv, iv-b, iv-c, vi, vii"
```

---

## Task 23: Final suite-wide green run + docs stub

**Files:**
- Create: `docs/architecture.md`

- [x] **Step 23.1: Write `docs/architecture.md`**

```markdown
# tableau2pbir — Architecture

Full design in `docs/superpowers/specs/2026-04-23-tableau-to-pbir-design.md`.
This file is an entry point for new contributors.

## Entry point

- `tableau2pbir.cli:main` → `argparse` dispatcher for `convert` / `resume`.
- `tableau2pbir.pipeline.run_pipeline` → sequences 8 stages from `STAGE_SEQUENCE`.

## Package layout (Plan-1 scope)

```
src/tableau2pbir/
├── cli.py                  # argparse CLI
├── pipeline.py             # runner + StageResult / StageError / StageContext
├── ir/                     # pydantic IR + JSON Schema autogen (§5)
├── llm/                    # LLMClient + cache + snapshots + per-prompt folders (§7)
└── stages/                 # 8 stub modules, one per pipeline stage
```

Plans 2–5 add the `translators/`, `classify/`, `emit/`, `validate/`, and
`util/` packages per spec §10.

## Running the pipeline

```bash
tableau2pbir convert path/to/workbook.twbx --out ./out/
tableau2pbir convert path/to/workbook.twbx --out ./out/ --gate canonicalize
tableau2pbir resume ./out/<workbook>/ --from translate_calcs
```
```

- [x] **Step 23.2: Run the whole suite**

```bash
pytest -q
```
Expected: all tests pass. (Count should be ~40+ across unit + contract + integration.)

- [x] **Step 23.3: Run make targets as acceptance check**

```bash
make lint
make typecheck
make schema
```
Expected: `make lint` clean, `make typecheck` clean on `src/`, `make schema` rewrites `schemas/ir-v1.0.0.schema.json` identically (diff empty).

- [x] **Step 23.4: Commit**

```bash
git add docs/architecture.md
git commit -m "docs: add architecture.md entry point for new contributors"
```

---

## Plan 1 acceptance — done when all true

- [x] `pip install -e ".[dev]"` completes cleanly.
- [x] `pytest -q` is green.
- [x] `make lint` clean.
- [x] `make typecheck` clean on `src/`.
- [x] `make schema` produces a byte-identical `schemas/ir-v1.0.0.schema.json` (no diff).
- [x] `tableau2pbir convert tests/golden/synthetic/trivial.twb --out ./out/` returns exit 0 and produces the full `./out/trivial/stages/*.json` artifact tree plus `trivial.pbip` and `unsupported.json`.
- [x] `tableau2pbir convert ... --gate canonicalize` stops after stage 2.
- [x] `tableau2pbir resume ./out/trivial --from translate_calcs` completes stages 3–8.
- [x] All three prompt folders have `system.md`, `tool_schema.json`, `VERSION`, `examples/.gitkeep`.
- [x] `tests/validity/{tmdl,pbir,dax_semantic}/README.md` and `tests/desktop_open/README.md` all committed with their Plan ownership noted.
- [x] `git log --oneline` shows roughly one commit per task (no squashed "wip" commits).

## Next plan

Plan 2 — Stage 1 (extract) + Stage 2 (canonicalize → IR). Starts against the committed IR schema and pipeline runner from this plan.
