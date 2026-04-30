"""Render a measure block (nested under a table)."""
from __future__ import annotations

from textwrap import indent

from tableau2pbir.emit.tmdl.escape import tmdl_ident
from tableau2pbir.ir.calculation import Calculation, CalculationScope


def render_measure(calc: Calculation) -> str:
    if calc.scope != CalculationScope.MEASURE or not calc.dax_expr:
        return ""
    head = "measure " + tmdl_ident(calc.name)
    body = indent(f"expression: {calc.dax_expr}", "\t")
    return f"\t{head}\n{body}\n"
