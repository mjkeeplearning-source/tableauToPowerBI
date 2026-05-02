"""Column reference qualification for DAX emission.

Tableau formulas reference columns as [col_name] or [col_name (table)] for
cross-table disambiguation.  DAX requires 'TableName'[col_name].  This module
provides helpers to build the mapping from the DataModel IR and apply it.
"""
from __future__ import annotations

import re

from tableau2pbir.ir.model import ColumnKind
from tableau2pbir.ir.workbook import DataModel

# Matches [col_name] NOT preceded by a single-quote (which would mean it's
# already part of a qualified 'Table'[col] reference).
_BRACKET_RE = re.compile(r"(?<!')\[([^\[\]]+)\]")


def qualify_bracket_refs(
    expr: str,
    col_ref_map: dict[str, tuple[str, str]],
) -> str:
    """Replace [col_ref] with 'table'[col] for every known column ref."""
    if not col_ref_map:
        return expr

    def _replace(m: re.Match) -> str:
        name = m.group(1)
        entry = col_ref_map.get(name)
        if entry is None:
            return m.group(0)
        table_name, col_name = entry
        return f"'{table_name}'[{col_name}]"

    return _BRACKET_RE.sub(_replace, expr)


def build_col_context(
    data_model: DataModel,
) -> tuple[dict[str, tuple[str, str]], dict[str, list[str]]]:
    """Return (col_ref_map, columns_by_table) built from the DataModel.

    col_ref_map maps Tableau column reference names (including disambiguation
    suffix like "order_id (returns)") to (table_name, col_name) tuples.

    columns_by_table maps table names to their list of RAW column names; used
    to give the AI fallback context about the data model structure.
    """
    col_by_id = {c.id: c for c in data_model.columns}
    col_ref_map: dict[str, tuple[str, str]] = {}
    columns_by_table: dict[str, list[str]] = {}

    for table in data_model.tables:
        table_cols: list[str] = []
        for col_id in table.column_ids:
            col = col_by_id.get(col_id)
            if col is None or col.kind != ColumnKind.RAW:
                continue
            # DAX column name = TMDL column identifier = source_column (physical DB name).
            # Stage 2 stores the Tableau display name in col.name (e.g. "order_id (returns)")
            # and the physical DB column in col.source_column (e.g. "order_id").
            dax_col = col.source_column if col.source_column is not None else col.name
            entry = (table.name, dax_col)
            # Register Tableau display name as key (may already be a disambiguation form).
            if col.name not in col_ref_map:
                col_ref_map[col.name] = entry
            # Always register DAX-col-based disambiguation: "dax_col (table_name)".
            col_ref_map[f"{dax_col} ({table.name})"] = entry
            table_cols.append(dax_col)
        columns_by_table[table.name] = table_cols

    return col_ref_map, columns_by_table
