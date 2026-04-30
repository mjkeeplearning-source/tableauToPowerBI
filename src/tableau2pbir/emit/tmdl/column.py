"""Render a column or calculated-column block (nested under a table)."""
from __future__ import annotations

from textwrap import indent

from tableau2pbir.emit.tmdl.escape import tmdl_ident
from tableau2pbir.ir.model import Column, ColumnKind


def render_column(col: Column) -> str:
    if col.kind == ColumnKind.CALCULATED and col.dax_expr is None:
        return ""  # deferred / unsupported / not yet translated
    head = "column " + tmdl_ident(col.name)
    body_lines = [f"dataType: {col.datatype or 'string'}"]
    if col.kind == ColumnKind.CALCULATED:
        body_lines.append(f"expression: {col.dax_expr}")
    body = indent("\n".join(body_lines), "\t")
    return f"\t{head}\n{body}\n"
