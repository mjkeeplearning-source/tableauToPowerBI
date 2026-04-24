"""Sheet IR — §5.1."""
from __future__ import annotations

from tableau2pbir.ir.common import FieldRef, IRBase


class Encoding(IRBase):
    """Visual encoding channels. Only channels actually bound are populated."""
    rows: tuple[FieldRef, ...] = ()
    columns: tuple[FieldRef, ...] = ()
    color: FieldRef | None = None
    size: FieldRef | None = None
    label: FieldRef | None = None
    tooltip: FieldRef | None = None
    detail: tuple[FieldRef, ...] = ()
    shape: FieldRef | None = None
    angle: FieldRef | None = None


class Filter(IRBase):
    id: str
    kind: str                               # "categorical" | "range" | "top_n" | "context" | "conditional"
    field: FieldRef
    include: tuple[str, ...] = ()           # for categorical
    exclude: tuple[str, ...] = ()           # for categorical
    expr: str | None = None                 # for conditional


class SortSpec(IRBase):
    field: FieldRef
    direction: str                          # "asc" | "desc"


class ReferenceLine(IRBase):
    id: str
    scope_field: FieldRef
    kind: str                               # "constant" | "average" | "median" | "lod"
    value: float | None = None              # for constant
    lod_expr: str | None = None             # for lod-based


class Sheet(IRBase):
    id: str
    name: str
    datasource_refs: tuple[str, ...]        # Datasource ids
    mark_type: str
    encoding: Encoding
    filters: tuple[Filter, ...]
    sort: tuple[SortSpec, ...]
    dual_axis: bool
    reference_lines: tuple[ReferenceLine, ...]
    format: dict[str, str] | None = None
    uses_calculations: tuple[str, ...]      # Calculation ids — back-ref for topo-sort
