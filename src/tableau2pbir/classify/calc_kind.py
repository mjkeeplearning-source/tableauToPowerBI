"""§5.6 calc-kind/phase discrimination. Pure-Python token scan over the
Tableau expression. Rule order is stable; tests pin specific cases."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal


Kind = Literal["row", "aggregate", "table_calc", "lod_fixed", "lod_include", "lod_exclude"]
Phase = Literal["row", "aggregate", "viz"]


_AGG_FUNCS = {
    "SUM", "AVG", "COUNT", "COUNTD", "MIN", "MAX",
    "MEDIAN", "STDEV", "STDEVP", "VAR", "VARP", "ATTR",
}

_TABLE_CALC_FUNCS = {
    "RUNNING_SUM", "RUNNING_AVG", "RUNNING_COUNT", "RUNNING_MIN", "RUNNING_MAX",
    "WINDOW_SUM", "WINDOW_AVG", "WINDOW_COUNT", "WINDOW_MIN", "WINDOW_MAX",
    "WINDOW_MEDIAN", "WINDOW_VAR", "WINDOW_STDEV",
    "LOOKUP", "RANK", "RANK_DENSE", "RANK_UNIQUE", "RANK_MODIFIED", "RANK_PERCENTILE",
    "INDEX", "FIRST", "LAST", "PREVIOUS_VALUE", "SIZE", "TOTAL",
}

_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


@dataclass(frozen=True)
class CalcClassification:
    kind: Kind
    phase: Phase


def _strip_string_literals(expr: str) -> str:
    """Replace everything inside "..." or '...' with equivalent-length spaces
    so downstream substring checks are literal-free. Tableau uses both
    single- and double-quoted strings."""
    out = []
    in_str: str | None = None
    for ch in expr:
        if in_str:
            out.append(" ")
            if ch == in_str:
                in_str = None
        else:
            if ch in ('"', "'"):
                in_str = ch
                out.append(" ")
            else:
                out.append(ch)
    return "".join(out)


def _starts_with_lod(stripped: str) -> str | None:
    text = stripped.lstrip()
    if not text.startswith("{"):
        return None
    inner = text[1:].lstrip().upper()
    if inner.startswith("FIXED"):
        return "lod_fixed"
    if inner.startswith("INCLUDE"):
        return "lod_include"
    if inner.startswith("EXCLUDE"):
        return "lod_exclude"
    return None


def _has_identifier(stripped: str, names: set[str]) -> bool:
    for tok in _IDENT.findall(stripped):
        if tok.upper() in names:
            return True
    return False


def classify_calc_kind(tableau_expr: str) -> CalcClassification:
    stripped = _strip_string_literals(tableau_expr)

    lod = _starts_with_lod(stripped)
    if lod == "lod_fixed":
        return CalcClassification(kind="lod_fixed", phase="aggregate")
    if lod == "lod_include":
        return CalcClassification(kind="lod_include", phase="aggregate")
    if lod == "lod_exclude":
        return CalcClassification(kind="lod_exclude", phase="aggregate")

    if _has_identifier(stripped, _TABLE_CALC_FUNCS):
        return CalcClassification(kind="table_calc", phase="viz")

    if _has_identifier(stripped, _AGG_FUNCS):
        return CalcClassification(kind="aggregate", phase="aggregate")

    return CalcClassification(kind="row", phase="row")
