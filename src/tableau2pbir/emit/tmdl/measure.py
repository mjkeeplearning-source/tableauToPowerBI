"""Render a measure block (nested under a table)."""
from __future__ import annotations

from tableau2pbir.emit.tmdl.escape import tmdl_ident
from tableau2pbir.ir.calculation import Calculation, CalculationScope


def render_measure(calc: Calculation) -> str:
    if calc.scope != CalculationScope.MEASURE or not calc.dax_expr:
        return ""
    name_q = tmdl_ident(calc.name)
    dax = calc.dax_expr.strip()
    if not dax:
        return ""
    if "\n" not in dax:
        return f"\tmeasure {name_q} = {dax}\n"
    lines = [f"\tmeasure {name_q} ="]
    for line in dax.splitlines():
        if not line.strip():
            lines.append("")
        else:
            lines.append("\t\t\t" + line.lstrip())
    return "\n".join(lines) + "\n"
