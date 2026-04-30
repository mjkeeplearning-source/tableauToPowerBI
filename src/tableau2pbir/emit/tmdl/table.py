"""Render tables/<name>.tmdl."""
from __future__ import annotations

from textwrap import indent

from tableau2pbir.emit.tmdl.column import render_column
from tableau2pbir.emit.tmdl.escape import tmdl_ident
from tableau2pbir.emit.tmdl.measure import render_measure
from tableau2pbir.emit.tmdl.m_expression import render_m_expression
from tableau2pbir.ir.calculation import Calculation
from tableau2pbir.ir.datasource import Datasource
from tableau2pbir.ir.model import Column


def render_table(name: str, columns: list[Column], measures: list[Calculation],
                 datasource: Datasource) -> str:
    parts = [f"table {tmdl_ident(name)}", ""]
    for col in columns:
        frag = render_column(col)
        if frag:
            parts.append(frag.rstrip())
    for calc in measures:
        frag = render_measure(calc)
        if frag:
            parts.append(frag.rstrip())
    m_body = render_m_expression(datasource, table_name=name)
    partition = (
        f"\tpartition {tmdl_ident(name)} = m\n"
        f"\t\tmode: import\n"
        f"\t\tsource =\n"
        f"{indent(m_body, chr(9) * 3)}"
    )
    parts.append(partition)
    return "\n".join(parts) + "\n"
