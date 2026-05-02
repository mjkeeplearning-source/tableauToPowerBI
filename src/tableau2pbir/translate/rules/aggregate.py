"""Aggregate-calc rules. Returns DAX or None on no match."""
from __future__ import annotations

import re

from tableau2pbir.translate.col_qualifier import qualify_bracket_refs

_AGG_RENAMES = {
    "AVG": "AVERAGE",
    "COUNTD": "DISTINCTCOUNT",
}

_OUTER_RE = re.compile(
    r"^(?P<fn>SUM|AVG|COUNT|COUNTD|MIN|MAX)\s*\((?P<arg>.*)\)\s*$",
    re.DOTALL | re.IGNORECASE,
)
_COND_INNER_RE = re.compile(
    r"^IF\s+(?P<cond>.+?)\s+THEN\s+(?P<then>.+?)\s+END$",
    re.DOTALL,
)
# Matches one aggregate term; arg may contain one level of nested parens
# (e.g. column names like [order_id (returns)]).
_TERM_RE = re.compile(
    r"(?P<fn>SUM|AVG|COUNT|COUNTD|MIN|MAX)\s*\((?P<arg>(?:[^()]+|\([^()]*\))+)\)",
    re.IGNORECASE,
)


def _translate_single(
    fn: str, arg: str,
    col_ref_map: dict[str, tuple[str, str]] | None = None,
) -> str:
    dax_fn = _AGG_RENAMES.get(fn.upper(), fn.upper())
    arg = arg.strip()
    if col_ref_map:
        arg = qualify_bracket_refs(arg, col_ref_map)
    cond = _COND_INNER_RE.match(arg)
    if cond:
        inner = cond.group("then").strip()
        predicate = cond.group("cond").strip()
        return f"CALCULATE({dax_fn}({inner}), FILTER(ALLSELECTED(), {predicate}))"
    return f"{dax_fn}({arg})"


def translate_aggregate(
    tableau_expr: str,
    col_ref_map: dict[str, tuple[str, str]] | None = None,
) -> str | None:
    expr = tableau_expr.strip()

    # Compound path first: arithmetic of multiple single aggregate calls (e.g. SUM(x) - SUM(y)).
    # Must be checked before the single-call fast path because _OUTER_RE's greedy .* can
    # over-capture compound expressions into a single spurious match.
    check = _TERM_RE.sub("X", expr)
    if re.fullmatch(r"X(\s*[+\-*/]\s*X)+", check.strip()):
        return _TERM_RE.sub(
            lambda mo: _translate_single(mo.group("fn"), mo.group("arg"), col_ref_map),
            expr,
        )

    # Single aggregate call (including conditional: SUM(IF cond THEN x END)).
    m = _OUTER_RE.match(expr)
    if m:
        return _translate_single(m.group("fn"), m.group("arg"), col_ref_map)

    return None
