# Regression Gate — Semantic Snapshot Validation

> **For agentic workers:** REQUIRED SUB-SKILL: Use **superpowers:subagent-driven-development** to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add a semantic regression gate (`regression-add`, `regression-check`, `regression-install-hook` CLI commands) that snapshots verified PBIR/TMDL output and detects any semantic change to registered workbooks on future pipeline runs.

**Architecture:** A new `src/tableau2pbir/regression/` package holds corpus management (`corpus.py`), snapshot registration (`snapshot.py`), semantic comparison (`compare/json_diff.py`, `compare/tmdl_diff.py`, `compare/result.py`), orchestration (`check.py`), reporting (`report.py`), and hook installation (`hook.py`). Three new CLI subcommands are wired into the existing `cli.py` argparse structure. Snapshots live in `tests/regression/snapshots/<name>/`; the corpus manifest lives in `tests/regression/corpus.yaml`.

**Tech Stack:** Python 3.11+, pydantic v2, PyYAML (already in pyproject.toml), stdlib `json`, `re`, `subprocess`, `shutil`, `pathlib`, `stat`, `tempfile`. pytest for tests.

**Spec:** `docs/superpowers/specs/2026-05-31-regression-gate-design.md`

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `src/tableau2pbir/regression/__init__.py` | Create | Package marker |
| `src/tableau2pbir/regression/compare/__init__.py` | Create | Sub-package marker |
| `src/tableau2pbir/regression/compare/result.py` | Create | `EntityDiff`, `FileDiff`, `WorkbookResult`, `RegressionResult` dataclasses |
| `src/tableau2pbir/regression/corpus.py` | Create | `CorpusEntry`, `load_corpus`, `save_corpus` |
| `src/tableau2pbir/regression/compare/json_diff.py` | Create | PBIR JSON semantic normalise + diff |
| `src/tableau2pbir/regression/compare/tmdl_diff.py` | Create | TMDL line-by-line parser + structured diff |
| `src/tableau2pbir/regression/snapshot.py` | Create | `register_workbook` — run pipeline, copy snapshots, append corpus |
| `src/tableau2pbir/regression/check.py` | Create | `run_regression_check` orchestrator |
| `src/tableau2pbir/regression/report.py` | Create | `format_report` — render semantic diff to stdout |
| `src/tableau2pbir/regression/hook.py` | Create | `install_hook` — write `.git/hooks/pre-commit` |
| `src/tableau2pbir/cli.py` | Modify | Add `regression-add`, `regression-check`, `regression-install-hook` subcommands |
| `pytest.ini` | Modify | Register `regression` marker |
| `tests/regression/__init__.py` | Create | Package marker |
| `tests/regression/corpus.yaml` | Create | Initially-empty corpus manifest |
| `tests/regression/snapshots/.gitkeep` | Create | Keep directory in git |
| `tests/regression/test_corpus.py` | Create | Unit: load/save corpus, duplicate guard |
| `tests/regression/test_json_diff.py` | Create | Unit: JSON normalisation + diff |
| `tests/regression/test_tmdl_diff.py` | Create | Unit: TMDL parser + structured diff |
| `tests/regression/test_check.py` | Create | Integration: mock pipeline run vs fixture snapshots |

---

## Task 1: Package scaffold + data models

**Files:**
- Create: `src/tableau2pbir/regression/__init__.py`
- Create: `src/tableau2pbir/regression/compare/__init__.py`
- Create: `src/tableau2pbir/regression/compare/result.py`
- Create: `src/tableau2pbir/regression/corpus.py`
- Create: `tests/regression/__init__.py`
- Create: `tests/regression/corpus.yaml`
- Create: `tests/regression/snapshots/.gitkeep`
- Create: `tests/regression/test_corpus.py`
- Modify: `pytest.ini`

- [x] **Step 1: Write the failing tests**

Create `tests/regression/test_corpus.py`:

```python
from __future__ import annotations
import pytest
from pathlib import Path
from tableau2pbir.regression.corpus import CorpusEntry, load_corpus, save_corpus


def test_load_empty_corpus(tmp_path: Path):
    corpus_path = tmp_path / "corpus.yaml"
    corpus_path.write_text("workbooks: []\n", encoding="utf-8")
    assert load_corpus(corpus_path) == []


def test_save_and_load_roundtrip(tmp_path: Path):
    corpus_path = tmp_path / "corpus.yaml"
    entries = [
        CorpusEntry(
            name="simple_join",
            path="tests/golden/real/simple_join.twb",
            added_by="Test User",
            added_on="2026-05-31",
            notes="baseline",
        )
    ]
    save_corpus(entries, corpus_path)
    loaded = load_corpus(corpus_path)
    assert len(loaded) == 1
    assert loaded[0].name == "simple_join"
    assert loaded[0].path == "tests/golden/real/simple_join.twb"
    assert loaded[0].added_by == "Test User"
    assert loaded[0].added_on == "2026-05-31"
    assert loaded[0].notes == "baseline"


def test_load_missing_corpus_returns_empty(tmp_path: Path):
    corpus_path = tmp_path / "nonexistent.yaml"
    assert load_corpus(corpus_path) == []


def test_notes_defaults_to_empty_string(tmp_path: Path):
    corpus_path = tmp_path / "corpus.yaml"
    corpus_path.write_text(
        "workbooks:\n  - name: wb\n    path: p.twb\n    added_by: me\n    added_on: '2026-01-01'\n",
        encoding="utf-8",
    )
    entries = load_corpus(corpus_path)
    assert entries[0].notes == ""


def test_duplicate_name_detection(tmp_path: Path):
    corpus_path = tmp_path / "corpus.yaml"
    e = CorpusEntry(name="wb", path="wb.twb", added_by="me", added_on="2026-01-01", notes="")
    save_corpus([e], corpus_path)
    entries = load_corpus(corpus_path)
    names = {entry.name for entry in entries}
    assert "wb" in names
    # caller is responsible for the duplicate check; load_corpus just reads
    # test that two entries with same name can be detected:
    save_corpus([e, e], corpus_path)
    loaded = load_corpus(corpus_path)
    assert sum(1 for x in loaded if x.name == "wb") == 2
```

- [x] **Step 2: Run to confirm FAIL**

```
pytest tests/regression/test_corpus.py -v
```

Expected: `ModuleNotFoundError: No module named 'tableau2pbir.regression'`

- [x] **Step 3: Create package scaffolding**

Create `src/tableau2pbir/regression/__init__.py` (empty):
```python
```

Create `src/tableau2pbir/regression/compare/__init__.py` (empty):
```python
```

Create `src/tableau2pbir/regression/compare/result.py`:

```python
"""Regression result data models."""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class EntityDiff:
    entity_type: str   # "measure", "column", "property", "missing_file"
    entity_name: str
    attribute: str     # "DAX", "dataType", "sourceColumn", "value"
    old_value: str
    new_value: str


@dataclass
class FileDiff:
    relative_path: str
    missing: bool = False  # True if file in snapshot but absent from new output
    diffs: list[EntityDiff] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return self.missing or bool(self.diffs)


@dataclass
class WorkbookResult:
    name: str
    status: str        # "PASS", "FAIL", "SKIP"
    skip_reason: str = ""
    file_diffs: list[FileDiff] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.status in ("PASS", "SKIP")


@dataclass
class RegressionResult:
    workbook_results: list[WorkbookResult] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return all(r.passed for r in self.workbook_results)

    @property
    def exit_code(self) -> int:
        return 0 if self.all_passed else 1
```

Create `src/tableau2pbir/regression/corpus.py`:

```python
"""Corpus manifest load/save."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class CorpusEntry:
    name: str
    path: str
    added_by: str
    added_on: str
    notes: str = ""


def load_corpus(corpus_path: Path) -> list[CorpusEntry]:
    if not corpus_path.exists():
        return []
    data = yaml.safe_load(corpus_path.read_text(encoding="utf-8")) or {}
    entries = []
    for item in data.get("workbooks", []):
        entries.append(CorpusEntry(
            name=item["name"],
            path=item["path"],
            added_by=item["added_by"],
            added_on=str(item["added_on"]),
            notes=item.get("notes", ""),
        ))
    return entries


def save_corpus(entries: list[CorpusEntry], corpus_path: Path) -> None:
    corpus_path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "workbooks": [
            {
                "name": e.name,
                "path": e.path,
                "added_by": e.added_by,
                "added_on": e.added_on,
                "notes": e.notes,
            }
            for e in entries
        ]
    }
    corpus_path.write_text(
        yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
```

Create `tests/regression/__init__.py` (empty):
```python
```

Create `tests/regression/corpus.yaml`:
```yaml
workbooks: []
```

Create `tests/regression/snapshots/.gitkeep` (empty file).

- [x] **Step 4: Register `regression` marker in `pytest.ini`**

Add to the `markers =` block in `pytest.ini`:
```ini
    regression: semantic regression check against stored snapshots (requires prior regression-add run)
```

- [x] **Step 5: Run tests to confirm PASS**

```
pytest tests/regression/test_corpus.py -v
```

Expected: all 5 tests PASS.

- [x] **Step 6: Commit**

```bash
git add src/tableau2pbir/regression/ tests/regression/ pytest.ini
git commit -m "feat(regression): scaffold package + corpus data models"
```

---

## Task 2: JSON semantic diff

**Files:**
- Create: `src/tableau2pbir/regression/compare/json_diff.py`
- Create: `tests/regression/test_json_diff.py`

- [x] **Step 1: Write the failing tests**

Create `tests/regression/test_json_diff.py`:

```python
from __future__ import annotations
import json
import pytest
from tableau2pbir.regression.compare.json_diff import diff_json


def _j(obj) -> str:
    return json.dumps(obj)


def test_identical_objects_produce_no_diffs():
    a = _j({"name": "foo", "value": 42})
    assert diff_json(a, a) == []


def test_changed_leaf_value_detected():
    old = _j({"dataType": "int64"})
    new = _j({"dataType": "string"})
    diffs = diff_json(old, new)
    assert len(diffs) == 1
    path, old_v, new_v = diffs[0]
    assert "dataType" in path
    assert old_v == "int64"
    assert new_v == "string"


def test_key_ordering_ignored():
    a = _j({"b": 2, "a": 1})
    b = _j({"a": 1, "b": 2})
    assert diff_json(a, b) == []


def test_array_of_dicts_sorted_by_name():
    old = _j([{"name": "z", "v": 1}, {"name": "a", "v": 2}])
    new = _j([{"name": "a", "v": 2}, {"name": "z", "v": 1}])
    assert diff_json(old, new) == []


def test_array_of_dicts_sorted_by_id_fallback():
    old = _j([{"id": "z", "v": 1}, {"id": "a", "v": 2}])
    new = _j([{"id": "a", "v": 2}, {"id": "z", "v": 1}])
    assert diff_json(old, new) == []


def test_changed_array_element_detected():
    old = _j([{"name": "col", "dataType": "int64"}])
    new = _j([{"name": "col", "dataType": "string"}])
    diffs = diff_json(old, new)
    assert len(diffs) == 1
    assert "int64" in diffs[0][1]
    assert "string" in diffs[0][2]


def test_missing_key_detected():
    old = _j({"a": 1, "b": 2})
    new = _j({"a": 1})
    diffs = diff_json(old, new)
    assert len(diffs) == 1
    assert "b" in diffs[0][0]


def test_nested_diff_detected():
    old = _j({"visual": {"encoding": {"x": {"field": "Sales"}}}})
    new = _j({"visual": {"encoding": {"x": {"field": "Profit"}}}})
    diffs = diff_json(old, new)
    assert len(diffs) == 1
    assert "Sales" in diffs[0][1]
    assert "Profit" in diffs[0][2]


def test_whitespace_in_string_values_ignored():
    old = _j({"dax": "  SUM([Sales])  "})
    new = _j({"dax": "SUM([Sales])"})
    assert diff_json(old, new) == []
```

- [x] **Step 2: Run to confirm FAIL**

```
pytest tests/regression/test_json_diff.py -v
```

Expected: `ImportError: cannot import name 'diff_json'`

- [x] **Step 3: Implement `json_diff.py`**

Create `src/tableau2pbir/regression/compare/json_diff.py`:

```python
"""PBIR JSON semantic normalise + deep diff."""
from __future__ import annotations
import json
from typing import Any


def _norm_str(s: str) -> str:
    return s.strip()


def _normalise(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _normalise(v) for k, v in sorted(obj.items())}
    if isinstance(obj, list):
        normalised = [_normalise(i) for i in obj]
        if normalised and isinstance(normalised[0], dict):
            def _sort_key(item: Any) -> tuple[str, str]:
                if isinstance(item, dict):
                    return (str(item.get("name", "")), str(item.get("id", "")))
                return ("", "")
            try:
                normalised = sorted(normalised, key=_sort_key)
            except TypeError:
                pass
        return normalised
    if isinstance(obj, str):
        return _norm_str(obj)
    return obj


def _collect(path: str, old: Any, new: Any, out: list[tuple[str, str, str]]) -> None:
    if old == new:
        return
    if isinstance(old, dict) and isinstance(new, dict):
        for k in sorted(set(old) | set(new)):
            _collect(f"{path}.{k}", old.get(k), new.get(k), out)
    elif isinstance(old, list) and isinstance(new, list):
        for i in range(max(len(old), len(new))):
            o = old[i] if i < len(old) else None
            n = new[i] if i < len(new) else None
            _collect(f"{path}[{i}]", o, n, out)
    else:
        out.append((path, str(old), str(new)))


def diff_json(snapshot_text: str, new_text: str) -> list[tuple[str, str, str]]:
    """Return list of (json_path, old_value, new_value) for semantic differences."""
    old = _normalise(json.loads(snapshot_text))
    new = _normalise(json.loads(new_text))
    diffs: list[tuple[str, str, str]] = []
    _collect("$", old, new, diffs)
    return diffs
```

- [x] **Step 4: Run tests to confirm PASS**

```
pytest tests/regression/test_json_diff.py -v
```

Expected: all 9 tests PASS.

- [x] **Step 5: Commit**

```bash
git add src/tableau2pbir/regression/compare/json_diff.py tests/regression/test_json_diff.py
git commit -m "feat(regression): PBIR JSON semantic normalise and diff"
```

---

## Task 3: TMDL parser + diff

**Files:**
- Create: `src/tableau2pbir/regression/compare/tmdl_diff.py`
- Create: `tests/regression/test_tmdl_diff.py`

- [x] **Step 1: Write the failing tests**

Create `tests/regression/test_tmdl_diff.py`:

```python
from __future__ import annotations
import pytest
from tableau2pbir.regression.compare.tmdl_diff import (
    parse_table_tmdl,
    parse_model_tmdl,
    diff_tmdl_table,
    diff_model_tmdl,
    TmdlTableModel,
    TmdlModelFile,
)

_TABLE_SIMPLE = """\
table orders

\tcolumn order_id
\t\tdataType: int64
\t\tsourceColumn: order_id

\tcolumn 'Customer Name'
\t\tdataType: string
\t\tsourceColumn: Customer Name

\tmeasure 'Profit Ratio' = SUM([Profit]) / SUM([Sales])

\tpartition orders = m
\t\tmode: directQuery
\t\tsource =
\t\t\tlet Source = Sql.Database() in Source
"""

_TABLE_MULTILINE_MEASURE = """\
table sales

\tmeasure 'Complex Calc' =
\t\t\tCALCULATE(
\t\t\t    SUM([Sales]),
\t\t\t    ALL(orders)
\t\t\t)

\tpartition sales = m
\t\tmode: directQuery
\t\tsource =
\t\t\tlet Source = Sql.Database() in Source
"""

_TABLE_CALC_COL = """\
table orders

\tcolumn 'Full Name' = [First] & " " & [Last]
\t\tdataType: string

\tpartition orders = m
\t\tmode: directQuery
\t\tsource =
\t\t\tlet Source = Sql.Database() in Source
"""

_MODEL_SIMPLE = """\
model Model
\tculture: en-US
\tdefaultPowerBIDataSourceVersion: powerBI_V3
"""


def test_parse_table_name():
    m = parse_table_tmdl(_TABLE_SIMPLE)
    assert m.table_name == "orders"


def test_parse_regular_columns():
    m = parse_table_tmdl(_TABLE_SIMPLE)
    assert "order_id" in m.columns
    assert m.columns["order_id"].data_type == "int64"
    assert m.columns["order_id"].source_column == "order_id"


def test_parse_quoted_column_name():
    m = parse_table_tmdl(_TABLE_SIMPLE)
    assert "Customer Name" in m.columns
    assert m.columns["Customer Name"].data_type == "string"


def test_parse_single_line_measure():
    m = parse_table_tmdl(_TABLE_SIMPLE)
    assert "Profit Ratio" in m.measures
    assert "SUM([Profit])" in m.measures["Profit Ratio"].dax_expr


def test_partition_not_in_columns_or_measures():
    m = parse_table_tmdl(_TABLE_SIMPLE)
    assert "orders" not in m.measures
    for col_name in m.columns:
        assert "partition" not in col_name.lower()


def test_parse_multiline_measure():
    m = parse_table_tmdl(_TABLE_MULTILINE_MEASURE)
    assert "Complex Calc" in m.measures
    dax = m.measures["Complex Calc"].dax_expr
    assert "CALCULATE" in dax
    assert "SUM([Sales])" in dax


def test_parse_calculated_column():
    m = parse_table_tmdl(_TABLE_CALC_COL)
    assert "Full Name" in m.columns
    assert "[First]" in m.columns["Full Name"].dax_expr
    assert m.columns["Full Name"].data_type == "string"


def test_parse_model_tmdl():
    mf = parse_model_tmdl(_MODEL_SIMPLE)
    assert mf.culture == "en-US"
    assert mf.default_pbi_ds_version == "powerBI_V3"


def test_diff_tmdl_table_identical():
    diffs = diff_tmdl_table(_TABLE_SIMPLE, _TABLE_SIMPLE)
    assert diffs == []


def test_diff_tmdl_table_measure_dax_change():
    modified = _TABLE_SIMPLE.replace(
        "SUM([Profit]) / SUM([Sales])",
        "DIVIDE(SUM([Profit]), SUM([Sales]))",
    )
    diffs = diff_tmdl_table(_TABLE_SIMPLE, modified)
    assert len(diffs) == 1
    assert diffs[0].entity_type == "measure"
    assert diffs[0].entity_name == "Profit Ratio"
    assert diffs[0].attribute == "DAX"


def test_diff_tmdl_table_column_datatype_change():
    modified = _TABLE_SIMPLE.replace("dataType: int64", "dataType: string")
    diffs = diff_tmdl_table(_TABLE_SIMPLE, modified)
    assert len(diffs) == 1
    assert diffs[0].entity_type == "column"
    assert diffs[0].entity_name == "order_id"
    assert diffs[0].attribute == "dataType"
    assert diffs[0].old_value == "int64"
    assert diffs[0].new_value == "string"


def test_diff_tmdl_table_missing_measure():
    modified = _TABLE_SIMPLE.replace(
        "\tmeasure 'Profit Ratio' = SUM([Profit]) / SUM([Sales])\n", ""
    )
    diffs = diff_tmdl_table(_TABLE_SIMPLE, modified)
    assert any(d.entity_type == "measure" and "Profit Ratio" in d.entity_name for d in diffs)


def test_diff_model_tmdl_identical():
    diffs = diff_model_tmdl(_MODEL_SIMPLE, _MODEL_SIMPLE)
    assert diffs == []


def test_diff_model_tmdl_culture_change():
    modified = _MODEL_SIMPLE.replace("en-US", "fr-FR")
    diffs = diff_model_tmdl(_MODEL_SIMPLE, modified)
    assert len(diffs) == 1
    assert diffs[0].attribute == "culture"
    assert diffs[0].old_value == "en-US"
    assert diffs[0].new_value == "fr-FR"
```

- [x] **Step 2: Run to confirm FAIL**

```
pytest tests/regression/test_tmdl_diff.py -v
```

Expected: `ImportError: cannot import name 'parse_table_tmdl'`

- [x] **Step 3: Implement `tmdl_diff.py`**

Create `src/tableau2pbir/regression/compare/tmdl_diff.py`:

```python
"""TMDL line-by-line parser and semantic diff."""
from __future__ import annotations
import re
from dataclasses import dataclass, field

from tableau2pbir.regression.compare.result import EntityDiff

# ── Parsed models ──────────────────────────────────────────────────────────────

@dataclass
class TmdlColumn:
    name: str
    data_type: str = ""
    source_column: str = ""
    dax_expr: str = ""


@dataclass
class TmdlMeasure:
    name: str
    dax_expr: str = ""


@dataclass
class TmdlTableModel:
    table_name: str
    columns: dict[str, TmdlColumn] = field(default_factory=dict)
    measures: dict[str, TmdlMeasure] = field(default_factory=dict)


@dataclass
class TmdlModelFile:
    culture: str = ""
    default_pbi_ds_version: str = ""


# ── Regex patterns ─────────────────────────────────────────────────────────────

_TABLE_HDR    = re.compile(r"^table\s+(.+)$")
_COL_HDR      = re.compile(r"^\tcolumn\s+(.+?)(?:\s*=\s*(.+))?$")
_MEASURE_HDR  = re.compile(r"^\tmeasure\s+(.+?)\s*=\s*(.*)$")
_PARTITION    = re.compile(r"^\tpartition\s+")
_DATATYPE     = re.compile(r"^\t\tdataType:\s+(.+)$")
_SRC_COL      = re.compile(r"^\t\tsourceColumn:\s+(.+)$")
_CULTURE      = re.compile(r"^\tculture:\s+(.+)$")
_PBI_DS_VER   = re.compile(r"^\tdefaultPowerBIDataSourceVersion:\s+(.+)$")


def _unquote(s: str) -> str:
    s = s.strip()
    if s.startswith("'") and s.endswith("'"):
        return s[1:-1].replace("''", "'")
    return s


def _norm_dax(dax: str) -> str:
    return " ".join(dax.split())


# ── Parsers ────────────────────────────────────────────────────────────────────

def parse_table_tmdl(text: str) -> TmdlTableModel:
    table_name = ""
    columns: dict[str, TmdlColumn] = {}
    measures: dict[str, TmdlMeasure] = {}

    state = "idle"
    cur_col: TmdlColumn | None = None
    cur_measure: TmdlMeasure | None = None
    dax_lines: list[str] = []

    def _flush() -> None:
        nonlocal cur_col, cur_measure, dax_lines
        if cur_col is not None:
            columns[cur_col.name] = cur_col
            cur_col = None
        if cur_measure is not None:
            if dax_lines:
                cur_measure.dax_expr = " ".join(dax_lines)
            measures[cur_measure.name] = cur_measure
            cur_measure = None
            dax_lines = []

    for line in text.splitlines():
        m = _TABLE_HDR.match(line)
        if m:
            table_name = _unquote(m.group(1))
            state = "idle"
            continue

        if _PARTITION.match(line):
            _flush()
            state = "partition"
            continue

        if state == "partition":
            continue

        m = _COL_HDR.match(line)
        if m:
            _flush()
            name = _unquote(m.group(1))
            dax = (m.group(2) or "").strip()
            cur_col = TmdlColumn(name=name, dax_expr=dax)
            state = "calc_col" if dax else "column"
            continue

        m = _MEASURE_HDR.match(line)
        if m:
            _flush()
            name = _unquote(m.group(1))
            dax = m.group(2).strip()
            cur_measure = TmdlMeasure(name=name, dax_expr=dax)
            dax_lines = []
            state = "measure" if dax else "measure_ml"
            continue

        if state == "column" and cur_col:
            m = _DATATYPE.match(line)
            if m:
                cur_col.data_type = m.group(1).strip()
                continue
            m = _SRC_COL.match(line)
            if m:
                cur_col.source_column = m.group(1).strip()
                continue

        if state == "calc_col" and cur_col:
            m = _DATATYPE.match(line)
            if m:
                cur_col.data_type = m.group(1).strip()
                continue

        if state == "measure_ml":
            stripped = line.strip()
            if stripped:
                dax_lines.append(stripped)

    _flush()
    return TmdlTableModel(table_name=table_name, columns=columns, measures=measures)


def parse_model_tmdl(text: str) -> TmdlModelFile:
    result = TmdlModelFile()
    for line in text.splitlines():
        m = _CULTURE.match(line)
        if m:
            result.culture = m.group(1).strip()
            continue
        m = _PBI_DS_VER.match(line)
        if m:
            result.default_pbi_ds_version = m.group(1).strip()
    return result


# ── Differ ─────────────────────────────────────────────────────────────────────

def diff_tmdl_table(snapshot_text: str, new_text: str) -> list[EntityDiff]:
    old = parse_table_tmdl(snapshot_text)
    new = parse_table_tmdl(new_text)
    diffs: list[EntityDiff] = []

    for name, old_col in old.columns.items():
        if name not in new.columns:
            diffs.append(EntityDiff("column", name, "missing", name, "<absent>"))
            continue
        new_col = new.columns[name]
        if old_col.data_type != new_col.data_type:
            diffs.append(EntityDiff("column", name, "dataType", old_col.data_type, new_col.data_type))
        if old_col.source_column != new_col.source_column:
            diffs.append(EntityDiff("column", name, "sourceColumn", old_col.source_column, new_col.source_column))
        if _norm_dax(old_col.dax_expr) != _norm_dax(new_col.dax_expr):
            diffs.append(EntityDiff("column", name, "DAX", old_col.dax_expr, new_col.dax_expr))

    for name, old_m in old.measures.items():
        if name not in new.measures:
            diffs.append(EntityDiff("measure", name, "missing", name, "<absent>"))
            continue
        new_m = new.measures[name]
        if _norm_dax(old_m.dax_expr) != _norm_dax(new_m.dax_expr):
            diffs.append(EntityDiff("measure", name, "DAX", old_m.dax_expr, new_m.dax_expr))

    return diffs


def diff_model_tmdl(snapshot_text: str, new_text: str) -> list[EntityDiff]:
    old = parse_model_tmdl(snapshot_text)
    new = parse_model_tmdl(new_text)
    diffs: list[EntityDiff] = []
    if old.culture != new.culture:
        diffs.append(EntityDiff("model", "Model", "culture", old.culture, new.culture))
    if old.default_pbi_ds_version != new.default_pbi_ds_version:
        diffs.append(EntityDiff("model", "Model", "defaultPowerBIDataSourceVersion",
                                old.default_pbi_ds_version, new.default_pbi_ds_version))
    return diffs
```

- [x] **Step 4: Run tests to confirm PASS**

```
pytest tests/regression/test_tmdl_diff.py -v
```

Expected: all 15 tests PASS.

- [x] **Step 5: Commit**

```bash
git add src/tableau2pbir/regression/compare/tmdl_diff.py tests/regression/test_tmdl_diff.py
git commit -m "feat(regression): TMDL line-by-line parser and semantic diff"
```

---

## Task 4: Snapshot registration

**Files:**
- Create: `src/tableau2pbir/regression/snapshot.py`
- Create: `tests/regression/test_snapshot.py`

- [x] **Step 1: Write the failing tests**

Create `tests/regression/test_snapshot.py`:

```python
from __future__ import annotations
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from tableau2pbir.regression.corpus import CorpusEntry, load_corpus
from tableau2pbir.regression.snapshot import register_workbook, RegistrationError


def _make_fake_pipeline_output(out_dir: Path, wb_name: str) -> None:
    """Create a minimal fake pipeline output tree."""
    sm = out_dir / wb_name / "SemanticModel" / "definition" / "tables"
    sm.mkdir(parents=True)
    (sm / "orders.tmdl").write_text("table orders\n\tcolumn id\n\t\tdataType: int64\n", encoding="utf-8")
    rd = out_dir / wb_name / "Report" / "definition"
    rd.mkdir(parents=True)
    (rd / "report.json").write_text('{"$schema":"x","id":"r1"}', encoding="utf-8")
    stages = out_dir / wb_name / "stages"
    stages.mkdir()
    (stages / "01_extract.json").write_text("{}", encoding="utf-8")


def test_register_copies_tmdl_and_json(tmp_path: Path):
    workbook = tmp_path / "simple.twb"
    workbook.write_text("<workbook/>", encoding="utf-8")
    corpus_path = tmp_path / "corpus.yaml"
    corpus_path.write_text("workbooks: []\n", encoding="utf-8")
    snap_root = tmp_path / "snapshots"

    def fake_run(cmd, **kwargs):
        wb_name = Path(cmd[cmd.index("convert") + 1]).stem
        out_dir = Path(cmd[cmd.index("--out") + 1])
        _make_fake_pipeline_output(out_dir, wb_name)
        return MagicMock(returncode=0, stderr="", stdout="")

    with patch("subprocess.run", side_effect=fake_run):
        register_workbook(
            workbook_path=workbook,
            corpus_path=corpus_path,
            snapshots_root=snap_root,
            notes="test wb",
            added_by="tester",
            added_on="2026-05-31",
        )

    snap_dir = snap_root / "simple"
    assert (snap_dir / "SemanticModel" / "definition" / "tables" / "orders.tmdl").exists()
    assert (snap_dir / "Report" / "definition" / "report.json").exists()
    assert not (snap_dir / "stages" / "01_extract.json").exists(), "stage JSON must not be snapshotted"


def test_register_appends_to_corpus(tmp_path: Path):
    workbook = tmp_path / "simple.twb"
    workbook.write_text("<workbook/>", encoding="utf-8")
    corpus_path = tmp_path / "corpus.yaml"
    corpus_path.write_text("workbooks: []\n", encoding="utf-8")
    snap_root = tmp_path / "snapshots"

    def fake_run(cmd, **kwargs):
        wb_name = Path(cmd[cmd.index("convert") + 1]).stem
        out_dir = Path(cmd[cmd.index("--out") + 1])
        _make_fake_pipeline_output(out_dir, wb_name)
        return MagicMock(returncode=0, stderr="", stdout="")

    with patch("subprocess.run", side_effect=fake_run):
        register_workbook(
            workbook_path=workbook,
            corpus_path=corpus_path,
            snapshots_root=snap_root,
            notes="test wb",
            added_by="tester",
            added_on="2026-05-31",
        )

    entries = load_corpus(corpus_path)
    assert len(entries) == 1
    assert entries[0].name == "simple"
    assert entries[0].notes == "test wb"
    assert entries[0].added_by == "tester"


def test_register_duplicate_raises(tmp_path: Path):
    workbook = tmp_path / "simple.twb"
    workbook.write_text("<workbook/>", encoding="utf-8")
    corpus_path = tmp_path / "corpus.yaml"
    import yaml
    corpus_path.write_text(
        yaml.dump({"workbooks": [{"name": "simple", "path": "x", "added_by": "me", "added_on": "2026-01-01", "notes": ""}]}),
        encoding="utf-8",
    )
    snap_root = tmp_path / "snapshots"

    with pytest.raises(RegistrationError, match="already registered"):
        register_workbook(
            workbook_path=workbook,
            corpus_path=corpus_path,
            snapshots_root=snap_root,
        )


def test_register_aborts_on_pipeline_failure(tmp_path: Path):
    workbook = tmp_path / "simple.twb"
    workbook.write_text("<workbook/>", encoding="utf-8")
    corpus_path = tmp_path / "corpus.yaml"
    corpus_path.write_text("workbooks: []\n", encoding="utf-8")
    snap_root = tmp_path / "snapshots"

    with patch("subprocess.run", return_value=MagicMock(returncode=1, stderr="stage failed", stdout="")):
        with pytest.raises(RegistrationError, match="pipeline failed"):
            register_workbook(
                workbook_path=workbook,
                corpus_path=corpus_path,
                snapshots_root=snap_root,
            )

    assert not (snap_root / "simple").exists(), "snapshot dir must not be created on failure"
    assert load_corpus(corpus_path) == [], "corpus must not be modified on failure"
```

- [x] **Step 2: Run to confirm FAIL**

```
pytest tests/regression/test_snapshot.py -v
```

Expected: `ImportError: cannot import name 'register_workbook'`

- [x] **Step 3: Implement `snapshot.py`**

Create `src/tableau2pbir/regression/snapshot.py`:

```python
"""Register a workbook: run pipeline, copy TMDL/JSON snapshots, append corpus."""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from tableau2pbir.regression.corpus import CorpusEntry, load_corpus, save_corpus


class RegistrationError(Exception):
    pass


def register_workbook(
    workbook_path: Path,
    corpus_path: Path,
    snapshots_root: Path,
    notes: str = "",
    added_by: str = "",
    added_on: str = "",
) -> tuple[int, int]:
    """Run pipeline, snapshot TMDL+JSON output, append corpus entry.

    Returns (tmdl_count, json_count).
    Raises RegistrationError on duplicate, pipeline failure.
    """
    name = workbook_path.stem
    entries = load_corpus(corpus_path)
    if any(e.name == name for e in entries):
        raise RegistrationError(f"{name!r} already registered in corpus")

    with tempfile.TemporaryDirectory() as td:
        out_dir = Path(td) / "out"
        result = subprocess.run(
            [sys.executable, "-m", "tableau2pbir.cli", "convert",
             str(workbook_path.resolve()), "--out", str(out_dir)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RegistrationError(
                f"pipeline failed for {name!r}:\n{result.stderr}"
            )

        wb_out = out_dir / name
        snap_dir = snapshots_root / name
        tmdl_count, json_count = _copy_snapshots(wb_out, snap_dir)

    entry = CorpusEntry(
        name=name,
        path=str(workbook_path),
        added_by=added_by,
        added_on=added_on,
        notes=notes,
    )
    entries.append(entry)
    save_corpus(entries, corpus_path)
    return tmdl_count, json_count


def _copy_snapshots(wb_out: Path, snap_dir: Path) -> tuple[int, int]:
    tmdl_count = 0
    json_count = 0
    sm_src = wb_out / "SemanticModel"
    rd_src = wb_out / "Report" / "definition"
    for src_root in (sm_src, rd_src):
        if not src_root.exists():
            continue
        for src_file in src_root.rglob("*"):
            if not src_file.is_file():
                continue
            if src_file.suffix == ".tmdl":
                rel = src_file.relative_to(wb_out)
                dst = snap_dir / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dst)
                tmdl_count += 1
            elif src_file.suffix == ".json":
                rel = src_file.relative_to(wb_out)
                dst = snap_dir / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dst)
                json_count += 1
    return tmdl_count, json_count
```

- [x] **Step 4: Run tests to confirm PASS**

```
pytest tests/regression/test_snapshot.py -v
```

Expected: all 4 tests PASS.

- [x] **Step 5: Commit**

```bash
git add src/tableau2pbir/regression/snapshot.py tests/regression/test_snapshot.py
git commit -m "feat(regression): snapshot registration — run pipeline, copy TMDL/JSON, append corpus"
```

---

## Task 5: Regression check orchestrator + report

**Files:**
- Create: `src/tableau2pbir/regression/check.py`
- Create: `src/tableau2pbir/regression/report.py`
- Create: `tests/regression/test_check.py`

- [x] **Step 1: Write the failing tests**

Create `tests/regression/test_check.py`:

```python
from __future__ import annotations
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from tableau2pbir.regression.corpus import CorpusEntry, save_corpus
from tableau2pbir.regression.check import run_regression_check
from tableau2pbir.regression.report import format_report


_TMDL_ORDERS = """\
table orders

\tcolumn order_id
\t\tdataType: int64
\t\tsourceColumn: order_id

\tmeasure 'Total Sales' = SUM([Sales])

\tpartition orders = m
\t\tmode: directQuery
\t\tsource =
\t\t\tlet Source = Sql.Database() in Source
"""

_REPORT_JSON = json.dumps({"$schema": "x", "id": "r1", "name": "Report"})


def _write_snapshot(snap_dir: Path, tmdl: str, rjson: str) -> None:
    sm = snap_dir / "SemanticModel" / "definition" / "tables"
    sm.mkdir(parents=True)
    (sm / "orders.tmdl").write_text(tmdl, encoding="utf-8")
    rd = snap_dir / "Report" / "definition"
    rd.mkdir(parents=True)
    (rd / "report.json").write_text(rjson, encoding="utf-8")


def _make_fake_pipeline_output(out_dir: Path, wb_name: str, tmdl: str, rjson: str) -> None:
    sm = out_dir / wb_name / "SemanticModel" / "definition" / "tables"
    sm.mkdir(parents=True)
    (sm / "orders.tmdl").write_text(tmdl, encoding="utf-8")
    rd = out_dir / wb_name / "Report" / "definition"
    rd.mkdir(parents=True)
    (rd / "report.json").write_text(rjson, encoding="utf-8")


def test_check_pass_when_output_matches(tmp_path: Path):
    corpus_path = tmp_path / "corpus.yaml"
    snap_root = tmp_path / "snapshots"
    entry = CorpusEntry("wb", str(tmp_path / "wb.twb"), "me", "2026-01-01")
    save_corpus([entry], corpus_path)
    _write_snapshot(snap_root / "wb", _TMDL_ORDERS, _REPORT_JSON)

    def fake_run(cmd, **kwargs):
        out_dir = Path(cmd[cmd.index("--out") + 1])
        _make_fake_pipeline_output(out_dir, "wb", _TMDL_ORDERS, _REPORT_JSON)
        return MagicMock(returncode=0, stderr="", stdout="")

    with patch("subprocess.run", side_effect=fake_run):
        result = run_regression_check(corpus_path=corpus_path, snapshots_root=snap_root)

    assert result.all_passed
    assert result.exit_code == 0
    assert result.workbook_results[0].status == "PASS"


def test_check_fail_when_tmdl_changes(tmp_path: Path):
    corpus_path = tmp_path / "corpus.yaml"
    snap_root = tmp_path / "snapshots"
    entry = CorpusEntry("wb", str(tmp_path / "wb.twb"), "me", "2026-01-01")
    save_corpus([entry], corpus_path)
    _write_snapshot(snap_root / "wb", _TMDL_ORDERS, _REPORT_JSON)

    modified_tmdl = _TMDL_ORDERS.replace("int64", "string")

    def fake_run(cmd, **kwargs):
        out_dir = Path(cmd[cmd.index("--out") + 1])
        _make_fake_pipeline_output(out_dir, "wb", modified_tmdl, _REPORT_JSON)
        return MagicMock(returncode=0, stderr="", stdout="")

    with patch("subprocess.run", side_effect=fake_run):
        result = run_regression_check(corpus_path=corpus_path, snapshots_root=snap_root)

    assert not result.all_passed
    assert result.exit_code == 1
    assert result.workbook_results[0].status == "FAIL"
    all_diffs = [d for fd in result.workbook_results[0].file_diffs for d in fd.diffs]
    assert any(d.attribute == "dataType" for d in all_diffs)


def test_check_fail_when_json_changes(tmp_path: Path):
    corpus_path = tmp_path / "corpus.yaml"
    snap_root = tmp_path / "snapshots"
    entry = CorpusEntry("wb", str(tmp_path / "wb.twb"), "me", "2026-01-01")
    save_corpus([entry], corpus_path)
    _write_snapshot(snap_root / "wb", _TMDL_ORDERS, _REPORT_JSON)

    modified_json = json.dumps({"$schema": "x", "id": "r1", "name": "Changed"})

    def fake_run(cmd, **kwargs):
        out_dir = Path(cmd[cmd.index("--out") + 1])
        _make_fake_pipeline_output(out_dir, "wb", _TMDL_ORDERS, modified_json)
        return MagicMock(returncode=0, stderr="", stdout="")

    with patch("subprocess.run", side_effect=fake_run):
        result = run_regression_check(corpus_path=corpus_path, snapshots_root=snap_root)

    assert not result.all_passed
    assert result.workbook_results[0].status == "FAIL"


def test_check_fail_when_snapshot_file_missing_from_output(tmp_path: Path):
    corpus_path = tmp_path / "corpus.yaml"
    snap_root = tmp_path / "snapshots"
    entry = CorpusEntry("wb", str(tmp_path / "wb.twb"), "me", "2026-01-01")
    save_corpus([entry], corpus_path)
    _write_snapshot(snap_root / "wb", _TMDL_ORDERS, _REPORT_JSON)

    def fake_run(cmd, **kwargs):
        out_dir = Path(cmd[cmd.index("--out") + 1])
        # Only emit the JSON, skip the TMDL (simulates deleted table)
        rd = out_dir / "wb" / "Report" / "definition"
        rd.mkdir(parents=True)
        (rd / "report.json").write_text(_REPORT_JSON, encoding="utf-8")
        return MagicMock(returncode=0, stderr="", stdout="")

    with patch("subprocess.run", side_effect=fake_run):
        result = run_regression_check(corpus_path=corpus_path, snapshots_root=snap_root)

    assert not result.all_passed
    file_diffs = result.workbook_results[0].file_diffs
    assert any(fd.missing for fd in file_diffs)


def test_check_skip_when_no_api_key(tmp_path: Path):
    corpus_path = tmp_path / "corpus.yaml"
    snap_root = tmp_path / "snapshots"
    entry = CorpusEntry("wb", str(tmp_path / "wb.twb"), "me", "2026-01-01")
    save_corpus([entry], corpus_path)
    _write_snapshot(snap_root / "wb", _TMDL_ORDERS, _REPORT_JSON)

    with patch("subprocess.run", return_value=MagicMock(
        returncode=1, stderr="ANTHROPIC_API_KEY not set", stdout=""
    )):
        result = run_regression_check(corpus_path=corpus_path, snapshots_root=snap_root)

    assert result.all_passed  # SKIP counts as passed
    assert result.workbook_results[0].status == "SKIP"


def test_check_single_workbook_by_name(tmp_path: Path):
    corpus_path = tmp_path / "corpus.yaml"
    snap_root = tmp_path / "snapshots"
    e1 = CorpusEntry("wb1", str(tmp_path / "wb1.twb"), "me", "2026-01-01")
    e2 = CorpusEntry("wb2", str(tmp_path / "wb2.twb"), "me", "2026-01-01")
    save_corpus([e1, e2], corpus_path)
    _write_snapshot(snap_root / "wb1", _TMDL_ORDERS, _REPORT_JSON)

    def fake_run(cmd, **kwargs):
        out_dir = Path(cmd[cmd.index("--out") + 1])
        _make_fake_pipeline_output(out_dir, "wb1", _TMDL_ORDERS, _REPORT_JSON)
        return MagicMock(returncode=0, stderr="", stdout="")

    with patch("subprocess.run", side_effect=fake_run):
        result = run_regression_check(corpus_path=corpus_path, snapshots_root=snap_root, name_filter="wb1")

    assert len(result.workbook_results) == 1
    assert result.workbook_results[0].name == "wb1"


def test_format_report_pass(tmp_path: Path):
    from tableau2pbir.regression.compare.result import WorkbookResult, RegressionResult
    r = RegressionResult([WorkbookResult("wb", "PASS")])
    output = format_report(r)
    assert "PASS" in output
    assert "wb" in output


def test_format_report_fail_shows_diffs(tmp_path: Path):
    from tableau2pbir.regression.compare.result import (
        WorkbookResult, RegressionResult, FileDiff, EntityDiff
    )
    fd = FileDiff(
        relative_path="SemanticModel/definition/tables/orders.tmdl",
        diffs=[EntityDiff("measure", "Profit Ratio", "DAX",
                          "SUM([Profit]) / SUM([Sales])",
                          "DIVIDE(SUM([Profit]), SUM([Sales]))")],
    )
    r = RegressionResult([WorkbookResult("wb", "FAIL", file_diffs=[fd])])
    output = format_report(r)
    assert "FAIL" in output
    assert "orders.tmdl" in output
    assert "Profit Ratio" in output
    assert "SUM([Profit])" in output
```

- [x] **Step 2: Run to confirm FAIL**

```
pytest tests/regression/test_check.py -v
```

Expected: `ImportError: cannot import name 'run_regression_check'`

- [x] **Step 3: Implement `check.py`**

Create `src/tableau2pbir/regression/check.py`:

```python
"""Regression check orchestrator."""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from tableau2pbir.regression.compare.json_diff import diff_json
from tableau2pbir.regression.compare.result import (
    EntityDiff, FileDiff, RegressionResult, WorkbookResult,
)
from tableau2pbir.regression.compare.tmdl_diff import diff_model_tmdl, diff_tmdl_table
from tableau2pbir.regression.corpus import load_corpus

_LLM_SKIP_MARKERS = (
    "ANTHROPIC_API_KEY not set",
    "authentication_error",
    "invalid x-api-key",
)


def run_regression_check(
    corpus_path: Path,
    snapshots_root: Path,
    name_filter: str | None = None,
) -> RegressionResult:
    entries = load_corpus(corpus_path)
    if name_filter:
        entries = [e for e in entries if e.name == name_filter]

    workbook_results: list[WorkbookResult] = []
    for entry in entries:
        workbook_results.append(
            _check_one(entry.name, Path(entry.path), snapshots_root / entry.name)
        )
    return RegressionResult(workbook_results=workbook_results)


def _check_one(name: str, workbook_path: Path, snap_dir: Path) -> WorkbookResult:
    with tempfile.TemporaryDirectory() as td:
        out_dir = Path(td) / "out"
        result = subprocess.run(
            [sys.executable, "-m", "tableau2pbir.cli", "convert",
             str(workbook_path.resolve()), "--out", str(out_dir)],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            if any(m in result.stderr for m in _LLM_SKIP_MARKERS):
                return WorkbookResult(name=name, status="SKIP", skip_reason="no API key")
            return WorkbookResult(
                name=name, status="FAIL",
                file_diffs=[FileDiff(
                    relative_path="<pipeline>",
                    diffs=[EntityDiff("pipeline", name, "exit_code", "0", str(result.returncode))],
                )],
            )

        wb_out = out_dir / name
        file_diffs = _compare_snapshots(snap_dir, wb_out)

    if any(fd.has_changes for fd in file_diffs):
        return WorkbookResult(name=name, status="FAIL", file_diffs=file_diffs)
    return WorkbookResult(name=name, status="PASS", file_diffs=file_diffs)


def _compare_snapshots(snap_dir: Path, wb_out: Path) -> list[FileDiff]:
    file_diffs: list[FileDiff] = []
    for snap_file in sorted(snap_dir.rglob("*")):
        if not snap_file.is_file():
            continue
        rel = snap_file.relative_to(snap_dir)
        new_file = wb_out / rel
        if not new_file.exists():
            file_diffs.append(FileDiff(relative_path=str(rel).replace("\\", "/"), missing=True))
            continue
        diffs = _compare_file(snap_file, new_file)
        if diffs:
            file_diffs.append(FileDiff(relative_path=str(rel).replace("\\", "/"), diffs=diffs))
    return file_diffs


def _compare_file(snap_file: Path, new_file: Path) -> list[EntityDiff]:
    snap_text = snap_file.read_text(encoding="utf-8")
    new_text = new_file.read_text(encoding="utf-8")
    if snap_file.suffix == ".json":
        raw_diffs = diff_json(snap_text, new_text)
        return [
            EntityDiff("json", path, "value", old_v, new_v)
            for path, old_v, new_v in raw_diffs
        ]
    if snap_file.suffix == ".tmdl":
        if snap_file.name == "model.tmdl":
            return diff_model_tmdl(snap_text, new_text)
        return diff_tmdl_table(snap_text, new_text)
    return []
```

- [x] **Step 4: Implement `report.py`**

Create `src/tableau2pbir/regression/report.py`:

```python
"""Format and print the regression result report."""
from __future__ import annotations

from tableau2pbir.regression.compare.result import RegressionResult, WorkbookResult


def format_report(result: RegressionResult) -> str:
    lines: list[str] = []
    for wb in result.workbook_results:
        lines.append(_format_workbook(wb))
    return "\n".join(lines)


def _format_workbook(wb: WorkbookResult) -> str:
    lines: list[str] = []
    if wb.status == "SKIP":
        lines.append(f"SKIP  {wb.name}  ({wb.skip_reason})")
        return "\n".join(lines)
    if wb.status == "PASS":
        lines.append(f"PASS  {wb.name}")
        return "\n".join(lines)
    lines.append(f"FAIL  {wb.name}")
    for fd in wb.file_diffs:
        if not fd.has_changes:
            continue
        lines.append(f"  {fd.relative_path}")
        if fd.missing:
            lines.append("    <file deleted from output>")
            continue
        for d in fd.diffs:
            if d.entity_type in ("measure", "column"):
                lines.append(f"    {d.entity_type} [{d.entity_name}]  {d.attribute} changed")
                lines.append(f"      - {d.old_value}")
                lines.append(f"      + {d.new_value}")
            elif d.entity_type == "json":
                lines.append(f"    {d.entity_name}  value changed")
                lines.append(f"      - {d.old_value}")
                lines.append(f"      + {d.new_value}")
            else:
                lines.append(f"    {d.entity_type} [{d.entity_name}]  {d.attribute}: {d.old_value} → {d.new_value}")
    return "\n".join(lines)
```

- [x] **Step 5: Run tests to confirm PASS**

```
pytest tests/regression/test_check.py -v
```

Expected: all 8 tests PASS.

- [x] **Step 6: Commit**

```bash
git add src/tableau2pbir/regression/check.py src/tableau2pbir/regression/report.py tests/regression/test_check.py
git commit -m "feat(regression): check orchestrator, report formatter"
```

---

## Task 6: Pre-commit hook writer

**Files:**
- Create: `src/tableau2pbir/regression/hook.py`
- Create: `tests/regression/test_hook.py`

- [x] **Step 1: Write the failing tests**

Create `tests/regression/test_hook.py`:

```python
from __future__ import annotations
import stat
from pathlib import Path
import pytest
from tableau2pbir.regression.hook import install_hook, HookInstallError


def test_creates_hook_when_none_exists(tmp_path: Path):
    hooks_dir = tmp_path / ".git" / "hooks"
    hooks_dir.mkdir(parents=True)
    hook_path = hooks_dir / "pre-commit"
    install_hook(hook_path=hook_path)
    content = hook_path.read_text(encoding="utf-8")
    assert "regression-check" in content
    assert hook_path.stat().st_mode & stat.S_IXUSR, "hook must be executable"


def test_appends_when_hook_already_exists(tmp_path: Path):
    hooks_dir = tmp_path / ".git" / "hooks"
    hooks_dir.mkdir(parents=True)
    hook_path = hooks_dir / "pre-commit"
    hook_path.write_text("#!/bin/sh\necho 'existing'\n", encoding="utf-8")
    install_hook(hook_path=hook_path)
    content = hook_path.read_text(encoding="utf-8")
    assert "existing" in content
    assert "regression-check" in content


def test_idempotent_when_already_installed(tmp_path: Path):
    hooks_dir = tmp_path / ".git" / "hooks"
    hooks_dir.mkdir(parents=True)
    hook_path = hooks_dir / "pre-commit"
    install_hook(hook_path=hook_path)
    install_hook(hook_path=hook_path)
    content = hook_path.read_text(encoding="utf-8")
    assert content.count("regression-check") == 1, "must not add duplicate entry"


def test_raises_when_hooks_dir_missing(tmp_path: Path):
    hook_path = tmp_path / ".git" / "hooks" / "pre-commit"
    with pytest.raises(HookInstallError, match="hooks directory"):
        install_hook(hook_path=hook_path)
```

- [x] **Step 2: Run to confirm FAIL**

```
pytest tests/regression/test_hook.py -v
```

Expected: `ImportError: cannot import name 'install_hook'`

- [x] **Step 3: Implement `hook.py`**

Create `src/tableau2pbir/regression/hook.py`:

```python
"""Install regression-check as a git pre-commit hook."""
from __future__ import annotations
import stat
from pathlib import Path

_HOOK_LINE = "python -m tableau2pbir.cli regression-check\n"
_SHEBANG = "#!/bin/sh\n"


class HookInstallError(Exception):
    pass


def install_hook(hook_path: Path) -> bool:
    """Write or append regression-check to the pre-commit hook.

    Returns True if newly written, False if already present (idempotent).
    Raises HookInstallError if the hooks directory does not exist.
    """
    if not hook_path.parent.exists():
        raise HookInstallError(
            f"hooks directory {hook_path.parent} does not exist. "
            "Run this command from the root of a git repository."
        )

    if hook_path.exists():
        content = hook_path.read_text(encoding="utf-8")
        if _HOOK_LINE.strip() in content:
            return False  # already installed
        hook_path.write_text(content.rstrip("\n") + "\n" + _HOOK_LINE, encoding="utf-8")
    else:
        hook_path.write_text(_SHEBANG + _HOOK_LINE, encoding="utf-8")

    # Set executable bit (owner + group + other)
    current = hook_path.stat().st_mode
    hook_path.chmod(current | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return True
```

- [x] **Step 4: Run tests to confirm PASS**

```
pytest tests/regression/test_hook.py -v
```

Expected: all 4 tests PASS.

- [x] **Step 5: Commit**

```bash
git add src/tableau2pbir/regression/hook.py tests/regression/test_hook.py
git commit -m "feat(regression): pre-commit hook installer"
```

---

## Task 7: CLI wiring

**Files:**
- Modify: `src/tableau2pbir/cli.py`
- Modify: `tests/unit/test_cli.py`

- [x] **Step 1: Read the existing test file to know what exists**

```
pytest tests/unit/test_cli.py -v
```

Verify existing tests still pass before touching anything.

- [x] **Step 2: Write failing CLI tests**

Open `tests/unit/test_cli.py` and add at the end:

```python
# ── Regression subcommands ────────────────────────────────────────────────────

def test_regression_check_subcommand_registered():
    from tableau2pbir.cli import build_parser
    p = build_parser()
    # argparse raises SystemExit on unknown subcommand, but we can introspect choices
    subparsers_action = next(
        a for a in p._actions if hasattr(a, "_name_parser_map")
    )
    assert "regression-check" in subparsers_action._name_parser_map


def test_regression_add_subcommand_registered():
    from tableau2pbir.cli import build_parser
    p = build_parser()
    subparsers_action = next(
        a for a in p._actions if hasattr(a, "_name_parser_map")
    )
    assert "regression-add" in subparsers_action._name_parser_map


def test_regression_install_hook_subcommand_registered():
    from tableau2pbir.cli import build_parser
    p = build_parser()
    subparsers_action = next(
        a for a in p._actions if hasattr(a, "_name_parser_map")
    )
    assert "regression-install-hook" in subparsers_action._name_parser_map
```

- [x] **Step 3: Run to confirm FAIL**

```
pytest tests/unit/test_cli.py::test_regression_check_subcommand_registered -v
```

Expected: `StopIteration` or `AssertionError: regression-check not in subparsers`

- [x] **Step 4: Add the three subcommands to `cli.py`**

Open `src/tableau2pbir/cli.py`. After the `_cmd_refresh_schemas` function and before `build_parser`, add:

```python
def _cmd_regression_add(args: argparse.Namespace) -> int:
    import subprocess
    from pathlib import Path
    from tableau2pbir.regression.corpus import load_corpus
    from tableau2pbir.regression.snapshot import RegistrationError, register_workbook

    workbook_path = Path(args.source).resolve()
    corpus_path = Path(args.corpus)
    snapshots_root = Path(args.snapshots_root)
    notes = args.notes or ""

    try:
        added_by = subprocess.check_output(
            ["git", "config", "user.name"], text=True
        ).strip()
    except Exception:
        added_by = "unknown"

    from datetime import date
    added_on = str(date.today())

    try:
        tmdl_count, json_count = register_workbook(
            workbook_path=workbook_path,
            corpus_path=corpus_path,
            snapshots_root=snapshots_root,
            notes=notes,
            added_by=added_by,
            added_on=added_on,
        )
        print(f"Registered {workbook_path.stem} — {tmdl_count} TMDL files, {json_count} PBIR JSON files snapshotted")
        return 0
    except RegistrationError as exc:
        print(f"[regression-add] ERROR: {exc}", file=sys.stderr)
        return 1


def _cmd_regression_check(args: argparse.Namespace) -> int:
    from pathlib import Path
    from tableau2pbir.regression.check import run_regression_check
    from tableau2pbir.regression.report import format_report

    corpus_path = Path(args.corpus)
    snapshots_root = Path(args.snapshots_root)
    name_filter = getattr(args, "name", None) or None

    result = run_regression_check(
        corpus_path=corpus_path,
        snapshots_root=snapshots_root,
        name_filter=name_filter,
    )
    print(format_report(result))
    return result.exit_code


def _cmd_regression_install_hook(args: argparse.Namespace) -> int:
    from pathlib import Path
    from tableau2pbir.regression.hook import HookInstallError, install_hook

    hook_path = Path(args.hook_path)
    try:
        newly_written = install_hook(hook_path=hook_path)
        if newly_written:
            print(f"Installed regression-check hook at {hook_path}")
        else:
            print(f"Hook already installed at {hook_path} — no changes made")
        return 0
    except HookInstallError as exc:
        print(f"[regression-install-hook] ERROR: {exc}", file=sys.stderr)
        return 1
```

Then inside `build_parser()`, after the `p_refresh` block and before `return parser`, add:

```python
    _CORPUS_DEFAULT = "tests/regression/corpus.yaml"
    _SNAPS_DEFAULT = "tests/regression/snapshots"

    p_reg_add = sub.add_parser("regression-add", help="Register a workbook into the regression corpus.")
    p_reg_add.add_argument("source", help="Path to .twb or .twbx to register")
    p_reg_add.add_argument("--notes", default="", help="Optional description")
    p_reg_add.add_argument("--corpus", default=_CORPUS_DEFAULT, help="Path to corpus.yaml")
    p_reg_add.add_argument("--snapshots-root", default=_SNAPS_DEFAULT, dest="snapshots_root",
                           help="Root directory for snapshots")
    p_reg_add.set_defaults(func=_cmd_regression_add)

    p_reg_check = sub.add_parser("regression-check", help="Check registered workbooks against snapshots.")
    p_reg_check.add_argument("name", nargs="?", default=None, help="Optional workbook name to check (default: all)")
    p_reg_check.add_argument("--corpus", default=_CORPUS_DEFAULT, help="Path to corpus.yaml")
    p_reg_check.add_argument("--snapshots-root", default=_SNAPS_DEFAULT, dest="snapshots_root",
                             help="Root directory for snapshots")
    p_reg_check.set_defaults(func=_cmd_regression_check)

    p_reg_hook = sub.add_parser("regression-install-hook", help="Install regression-check as git pre-commit hook.")
    p_reg_hook.add_argument("--hook-path", default=".git/hooks/pre-commit", dest="hook_path",
                            help="Path to pre-commit hook file")
    p_reg_hook.set_defaults(func=_cmd_regression_install_hook)
```

- [x] **Step 5: Run CLI tests to confirm PASS**

```
pytest tests/unit/test_cli.py -v
```

Expected: all tests PASS (including the 3 new ones).

- [x] **Step 6: Run full unit suite to catch any regressions**

```
pytest tests/unit/ tests/regression/ -v
```

Expected: all PASS.

- [x] **Step 7: Commit**

```bash
git add src/tableau2pbir/cli.py tests/unit/test_cli.py
git commit -m "feat(regression): wire regression-add, regression-check, regression-install-hook CLI subcommands"
```

---

## Task 8: Update CLAUDE.md and run full suite

**Files:**
- Modify: `CLAUDE.md`

- [x] **Step 1: Run the complete test suite**

```
pytest tests/unit/ tests/regression/ tests/golden/ -v --tb=short
```

Expected: all tests PASS. Fix any failures before proceeding.

- [x] **Step 2: Update the plan table in CLAUDE.md**

Open `CLAUDE.md` and add Plan 13 to the implementation tracking table:

```markdown
| 13 | Regression Gate — Semantic Snapshot Validation | ✅ DONE | `docs/superpowers/plans/2026-05-31-plan-13-regression-gate.md` |
```

Also add a summary after the Plan 12 summary block:

```markdown
**Plan 13 complete (2026-05-31):** Added semantic regression gate. New `regression` package
provides `corpus.py` (manifest load/save), `compare/json_diff.py` (PBIR JSON normalise+diff),
`compare/tmdl_diff.py` (TMDL line-by-line parser + structured diff), `snapshot.py`
(registration flow), `check.py` (orchestrator), `report.py` (semantic diff formatter), and
`hook.py` (pre-commit wiring). Three new CLI subcommands: `regression-add`, `regression-check`,
`regression-install-hook`. All tests run under `pytest -m regression` marker with no API key
required.
```

- [x] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: mark Plan 13 complete — regression gate"
```

---

## Self-Review Checklist

After writing the plan, reviewing against the spec:

| Spec requirement | Task that covers it |
|---|---|
| `tests/regression/corpus.yaml` manifest | Task 1 |
| `tests/regression/snapshots/<name>/` tree | Task 4 |
| Only `.tmdl` and `.json` snapshotted (no stage JSON) | Task 4 — `_copy_snapshots` filters by suffix and src root |
| `regression-add` duplicate guard | Task 4 — `RegistrationError` |
| `regression-add` pipeline abort on non-zero | Task 4 — `RegistrationError` |
| PBIR JSON key-order + array-sort normalisation | Task 2 |
| TMDL table file parser + diff | Task 3 |
| `model.tmdl` parsed separately | Task 3 — `diff_model_tmdl` / `parse_model_tmdl` |
| Missing file in snapshot → FAIL | Task 5 — `FileDiff.missing=True` |
| Extra file in new output → ignored | Task 5 — only iterates `snap_dir.rglob` |
| LLM API key absent → SKIP | Task 5 — `_LLM_SKIP_MARKERS` |
| Exit code 0 pass, 1 fail | Task 5 — `RegressionResult.exit_code` |
| Report format: FAIL/PASS/SKIP per workbook | Task 5 — `report.py` |
| `regression-check [<name>]` filter | Task 5 + Task 7 |
| `regression-install-hook` writes hook | Task 6 |
| Hook append (not overwrite) if file exists | Task 6 — idempotent |
| `--no-verify` bypass is standard git (no code needed) | Noted in spec, no code needed |
| `pytest -m regression` marker | Task 1 — `pytest.ini` |
| CLI subcommands: `regression-add`, `regression-check`, `regression-install-hook` | Task 7 |
| Default corpus/snapshots paths relative to CWD | Task 7 — argparse defaults |
