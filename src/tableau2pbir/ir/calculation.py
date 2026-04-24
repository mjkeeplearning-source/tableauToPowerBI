from __future__ import annotations

from enum import Enum

from tableau2pbir.ir.common import FieldRef, IRBase


class CalculationScope(str, Enum):
    MEASURE = "measure"
    COLUMN = "column"


class CalculationKind(str, Enum):
    ROW = "row"
    AGGREGATE = "aggregate"
    TABLE_CALC = "table_calc"
    LOD_FIXED = "lod_fixed"
    LOD_INCLUDE = "lod_include"
    LOD_EXCLUDE = "lod_exclude"


class CalculationPhase(str, Enum):
    ROW = "row"
    AGGREGATE = "aggregate"
    VIZ = "viz"


class TableCalcFrameType(str, Enum):
    CUMULATIVE = "cumulative"
    WINDOW = "window"
    LOOKUP = "lookup"
    RANK = "rank"


class TableCalcFrame(IRBase):
    type: TableCalcFrameType
    offset: int | None = None
    window_size: int | None = None


class TableCalcSortEntry(IRBase):
    field: FieldRef
    direction: str  # "asc" | "desc"


class TableCalc(IRBase):
    partitioning: tuple[FieldRef, ...]
    addressing: tuple[FieldRef, ...]
    sort: tuple[TableCalcSortEntry, ...]
    frame: TableCalcFrame
    restart_every: FieldRef | None = None


class LodFixed(IRBase):
    dimensions: tuple[FieldRef, ...]


class LodRelative(IRBase):
    # exactly one of extra_dims (INCLUDE) or excluded_dims (EXCLUDE) is populated
    extra_dims: tuple[FieldRef, ...] | None = None
    excluded_dims: tuple[FieldRef, ...] | None = None


class Calculation(IRBase):
    id: str
    name: str
    scope: CalculationScope
    tableau_expr: str
    dax_expr: str | None = None         # populated by stage 3
    depends_on: tuple[str, ...] = ()    # other Calculation ids

    kind: CalculationKind
    phase: CalculationPhase

    table_calc: TableCalc | None = None
    lod_fixed: LodFixed | None = None
    lod_relative: LodRelative | None = None

    # back-ref for quick-table-calc records and per-sheet LOD variants
    owner_sheet_id: str | None = None
