"""Render a column or calculated-column block (nested under a table)."""
from __future__ import annotations

from textwrap import indent

from tableau2pbir.emit.tmdl.escape import tmdl_ident
from tableau2pbir.ir.model import Column, ColumnKind

_DATATYPE_MAP: dict[str, str] = {
    "integer":  "int64",
    "real":     "double",
    "datetime": "dateTime",
    "date":     "dateTime",
    "boolean":  "boolean",
    "string":   "string",
}


def render_column(col: Column) -> str:
    if col.datatype == "table":
        return ""
    if col.kind == ColumnKind.CALCULATED and col.dax_expr is None:
        return ""
    tmdl_type = _DATATYPE_MAP.get(col.datatype, col.datatype)
    if col.kind == ColumnKind.CALCULATED:
        col_name = col.name
        name_q = tmdl_ident(col_name)
        dax = col.dax_expr.strip()
        body = indent(f"dataType: {tmdl_type}", "\t\t")
        return f"\tcolumn {name_q} = {dax}\n{body}\n"
    col_name = col.source_column if col.source_column is not None else col.name
    body_lines = [f"dataType: {tmdl_type}", f"sourceColumn: {col_name}"]
    head = "column " + tmdl_ident(col_name)
    body = indent("\n".join(body_lines), "\t\t")
    return f"\t{head}\n{body}\n"
