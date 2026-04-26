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
