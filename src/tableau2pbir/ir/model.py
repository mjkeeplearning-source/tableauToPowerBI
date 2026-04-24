"""Table / Column / Relationship IR — §5.1."""
from __future__ import annotations

from enum import Enum

from tableau2pbir.ir.common import FieldRef, IRBase


class ColumnRole(str, Enum):
    DIMENSION = "dim"
    MEASURE = "measure"


class ColumnKind(str, Enum):
    RAW = "raw"
    CALCULATED = "calculated"


class Column(IRBase):
    id: str
    name: str
    datatype: str                           # tableau-normalized datatype string
    role: ColumnRole
    kind: ColumnKind
    tableau_expr: str | None = None         # calculated columns only
    dax_expr: str | None = None             # populated by stage 3 for calculated columns


class Table(IRBase):
    id: str
    name: str
    datasource_id: str
    column_ids: tuple[str, ...]
    primary_key: tuple[str, ...] | None = None    # column ids forming the PK (if known)


class RelationshipSource(str, Enum):
    TABLEAU_JOIN = "tableau_join"
    TABLEAU_BLEND = "tableau_blend"
    CROSS_DB_FLATTEN = "cross_db_flatten"


class Relationship(IRBase):
    id: str
    from_ref: FieldRef
    to_ref: FieldRef
    cardinality: str                        # "one_to_one" | "one_to_many" | "many_to_one" | "many_to_many"
    cross_filter: str                       # "single" | "both"
    source: RelationshipSource
