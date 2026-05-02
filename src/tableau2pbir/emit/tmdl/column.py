"""Render a column or calculated-column block (nested under a table)."""
from __future__ import annotations

from textwrap import indent

from tableau2pbir.emit.tmdl.escape import tmdl_ident
from tableau2pbir.ir.model import Column, ColumnKind

_DATATYPE_MAP: dict[str, str] = {
    "integer":  "int64",
    "real":     "double",
    "datetime": "dateTime",
    "date":     "date",
    "boolean":  "boolean",
    "string":   "string",
}


def render_column(col: Column) -> str:
    if col.datatype == "table":
        return ""   # Tableau internal join-tracking column — not a real DB column
    if col.kind == ColumnKind.CALCULATED and col.dax_expr is None:
        return ""   # deferred / unsupported / not yet translated
    head = "column " + tmdl_ident(col.name)
    tmdl_type = _DATATYPE_MAP.get(col.datatype, col.datatype)
    body_lines = [f"dataType: {tmdl_type}"]
    if col.kind == ColumnKind.CALCULATED:
        body_lines.append(f"expression: {col.dax_expr}")
    else:
        src = col.source_column if col.source_column is not None else col.name
        body_lines.append(f"sourceColumn: {src}")
    body = indent("\n".join(body_lines), "\t\t")
    return f"\t{head}\n{body}\n"
