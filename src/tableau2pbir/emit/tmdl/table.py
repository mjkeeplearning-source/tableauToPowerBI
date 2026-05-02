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

_FILE_BASED_KINDS = frozenset({"textscan", "csv", "excel-direct"})


def _partition_mode(datasource: Datasource) -> str:
    return "import" if datasource.tableau_kind in _FILE_BASED_KINDS else "directQuery"


def render_table(name: str, columns: list[Column], measures: list[Calculation],
                 datasource: Datasource,
                 physical_schema: str | None = None,
                 physical_table: str | None = None) -> str:
    parts = [f"table {tmdl_ident(name)}", ""]
    for col in columns:
        frag = render_column(col)
        if frag:
            parts.append(frag.rstrip())
    for calc in measures:
        frag = render_measure(calc)
        if frag:
            parts.append(frag.rstrip())
    m_body = render_m_expression(datasource, table_name=name,
                                 physical_schema=physical_schema,
                                 physical_table=physical_table)
    mode = _partition_mode(datasource)
    partition = (
        f"\tpartition {tmdl_ident(name)} = m\n"
        f"\t\tmode: {mode}\n"
        f"\t\tsource =\n"
        f"{indent(m_body, chr(9) * 3)}"
    )
    parts.append(partition)
    return "\n".join(parts) + "\n"
