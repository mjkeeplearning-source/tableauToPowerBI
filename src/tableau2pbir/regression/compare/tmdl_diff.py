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
