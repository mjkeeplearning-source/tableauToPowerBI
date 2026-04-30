"""Render relationships/<id>.tmdl."""
from __future__ import annotations

from tableau2pbir.emit.tmdl.escape import tmdl_ident
from tableau2pbir.ir.model import Relationship


_CARD_MAP = {
    "one_to_one":   ("one", "one"),
    "one_to_many":  ("one", "many"),
    "many_to_one":  ("many", "one"),
    "many_to_many": ("many", "many"),
}


def render_relationship(rel: Relationship, from_table_name: str, to_table_name: str) -> str:
    fr, to = _CARD_MAP.get(rel.cardinality, ("many", "one"))
    cf = "bothDirections" if rel.cross_filter == "both" else "oneDirection"
    return (
        f"relationship {tmdl_ident(rel.id)}\n"
        f"\tfromColumn: {from_table_name}.{rel.from_ref.column_id}\n"
        f"\ttoColumn: {to_table_name}.{rel.to_ref.column_id}\n"
        f"\tfromCardinality: {fr}\n"
        f"\ttoCardinality: {to}\n"
        f"\tcrossFilteringBehavior: {cf}\n"
    )
