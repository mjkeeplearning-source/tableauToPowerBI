from __future__ import annotations

import pytest

from tableau2pbir.ir.calculation import (
    Calculation, CalculationKind, CalculationPhase, CalculationScope,
    LodFixed, LodRelative, TableCalc, TableCalcFrame, TableCalcFrameType,
)
from tableau2pbir.ir.common import FieldRef


def test_row_calc_minimal():
    c = Calculation(
        id="calc1",
        name="Profit",
        scope=CalculationScope.COLUMN,
        tableau_expr="[Revenue] - [Cost]",
        kind=CalculationKind.ROW,
        phase=CalculationPhase.ROW,
        depends_on=(),
    )
    assert c.table_calc is None
    assert c.lod_fixed is None


def test_lod_fixed_dimensions():
    c = Calculation(
        id="calc2",
        name="Sales By Region",
        scope=CalculationScope.MEASURE,
        tableau_expr="{FIXED [Region]: SUM([Sales])}",
        kind=CalculationKind.LOD_FIXED,
        phase=CalculationPhase.AGGREGATE,
        depends_on=(),
        lod_fixed=LodFixed(dimensions=(FieldRef(table_id="t1", column_id="region"),)),
    )
    assert c.lod_fixed is not None
    assert len(c.lod_fixed.dimensions) == 1


def test_lod_include_per_sheet_expansion_ready():
    c = Calculation(
        id="calc3",
        name="Sales With Customer",
        scope=CalculationScope.MEASURE,
        tableau_expr="{INCLUDE [Customer]: SUM([Sales])}",
        kind=CalculationKind.LOD_INCLUDE,
        phase=CalculationPhase.AGGREGATE,
        depends_on=(),
        lod_relative=LodRelative(extra_dims=(FieldRef(table_id="t1", column_id="customer"),)),
        owner_sheet_id=None,      # named calc; per-sheet variants set owner_sheet_id
    )
    assert c.lod_relative is not None
    assert c.lod_relative.extra_dims is not None


def test_table_calc_rank_frame():
    tc = TableCalc(
        partitioning=(FieldRef(table_id="t1", column_id="region"),),
        addressing=(FieldRef(table_id="t1", column_id="month"),),
        sort=(),
        frame=TableCalcFrame(type=TableCalcFrameType.RANK),
        restart_every=None,
    )
    c = Calculation(
        id="calc4", name="Rank", scope=CalculationScope.MEASURE,
        tableau_expr="RANK(SUM([Sales]))",
        kind=CalculationKind.TABLE_CALC,
        phase=CalculationPhase.VIZ,
        depends_on=(),
        table_calc=tc,
    )
    assert c.table_calc.frame.type == TableCalcFrameType.RANK


def test_quick_table_calc_has_owner_sheet():
    c = Calculation(
        id="qtc1__sheet42",
        name="_quick_table_calc_1",
        scope=CalculationScope.MEASURE,
        tableau_expr="RUNNING_SUM(SUM([Sales]))",
        kind=CalculationKind.TABLE_CALC,
        phase=CalculationPhase.VIZ,
        depends_on=(),
        table_calc=TableCalc(
            partitioning=(), addressing=(), sort=(),
            frame=TableCalcFrame(type=TableCalcFrameType.CUMULATIVE),
            restart_every=None,
        ),
        owner_sheet_id="sheet42",
    )
    assert c.owner_sheet_id == "sheet42"


def test_calculation_rejects_unknown_kind():
    with pytest.raises(Exception):
        Calculation(
            id="x", name="x", scope=CalculationScope.MEASURE,
            tableau_expr="SUM([x])",
            kind="mystery",                                        # type: ignore[arg-type]
            phase=CalculationPhase.AGGREGATE, depends_on=(),
        )
