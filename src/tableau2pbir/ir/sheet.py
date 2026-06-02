"""Sheet IR — §5.1."""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

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
    text: FieldRef | None = None


class FilterBase(IRBase):
    id: str
    field: FieldRef


class CategoricalFilter(FilterBase):
    kind: Literal["categorical"] = "categorical"
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()


class RangeFilter(FilterBase):
    kind: Literal["range"] = "range"
    min_val: str | None = None
    max_val: str | None = None
    agg_prefix: str | None = None


class TopNFilter(FilterBase):
    kind: Literal["top_n"] = "top_n"
    n: int = 10
    direction: str = "Top"          # "Top" | "Bottom"
    by_field: FieldRef | None = None
    by_agg: str | None = None


class ContextFilter(FilterBase):
    kind: Literal["context"] = "context"
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()


class ConditionalFilter(FilterBase):
    kind: Literal["conditional"] = "conditional"
    expr: str | None = None


Filter = Annotated[
    CategoricalFilter | RangeFilter | TopNFilter | ContextFilter | ConditionalFilter,
    Field(discriminator="kind"),
]


class SortSpec(IRBase):
    field: FieldRef
    direction: str                          # "asc" | "desc"


class ReferenceLine(IRBase):
    id: str
    scope_field: FieldRef
    kind: str                               # "constant" | "average" | "median" | "lod"
    value: float | None = None
    lod_expr: str | None = None


class MarkStyle(IRBase):
    mark_color: str | None = None
    labels_show: bool = False


class Sheet(IRBase):
    id: str
    name: str
    datasource_refs: tuple[str, ...]
    mark_type: str
    encoding: Encoding
    filters: tuple[Filter, ...]
    sort: tuple[SortSpec, ...]
    dual_axis: bool
    reference_lines: tuple[ReferenceLine, ...]
    mark_style: MarkStyle | None = None
    format: dict[str, str] | None = None
    uses_calculations: tuple[str, ...]
    pbir_visual: PbirVisual | None = None


class EncodingBinding(IRBase):
    """One channel→field binding in a PBIR visual."""
    channel: str
    source_field_id: str


class PbirVisual(IRBase):
    """Stage 4 annotation attached to a Sheet."""
    visual_type: str
    encoding_bindings: tuple[EncodingBinding, ...]
    format: dict[str, list[dict]] = {}


Sheet.model_rebuild()
