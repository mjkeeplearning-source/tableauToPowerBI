"""Aggregate-calc rules. Returns DAX or None on no match."""
from __future__ import annotations

import re

_AGG_RENAMES = {
    "AVG": "AVERAGE",
    "COUNTD": "DISTINCTCOUNT",
}

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
        # SUM(IF c THEN x END)  →  CALCULATE(SUM(x), FILTER(ALLSELECTED(), c))
        # Table context is unknown here; ALLSELECTED() preserves slicer filters.
        inner = cond.group("then").strip()
        predicate = cond.group("cond").strip()
        return (
            f"CALCULATE({fn}({inner}), "
            f"FILTER(ALLSELECTED(), {predicate}))"
        )
    return f"{fn}({arg})"
