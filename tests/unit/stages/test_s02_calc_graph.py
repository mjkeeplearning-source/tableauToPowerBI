from __future__ import annotations

from tableau2pbir.ir.calculation import (
    Calculation, CalculationKind, CalculationPhase, CalculationScope,
)
from tableau2pbir.stages._calc_graph import detect_cycles


def _calc(id_: str, name: str, depends_on: tuple[str, ...] = ()) -> Calculation:
    return Calculation(
        id=id_, name=name, scope=CalculationScope.MEASURE,
        tableau_expr="dummy", kind=CalculationKind.ROW,
        phase=CalculationPhase.ROW, depends_on=depends_on,
    )


def test_no_cycle_returns_empty():
    calcs = (
        _calc("c1", "A"),
        _calc("c2", "B", ("c1",)),
        _calc("c3", "C", ("c2",)),
    )
    assert detect_cycles(calcs) == ()


def test_self_loop_detected():
    calcs = (_calc("c1", "A", ("c1",)),)
    items = detect_cycles(calcs)
    assert len(items) == 1
    assert items[0].code == "calc_cycle"
    assert items[0].object_id == "c1"


def test_two_cycle_detected():
    calcs = (
        _calc("c1", "A", ("c2",)),
        _calc("c2", "B", ("c1",)),
    )
    ids = {i.object_id for i in detect_cycles(calcs)}
    assert ids == {"c1", "c2"}


def test_cycle_with_leaves_only_reports_cycle_members():
    calcs = (
        _calc("c1", "A"),
        _calc("c2", "B", ("c3",)),
        _calc("c3", "C", ("c2",)),
        _calc("c4", "D", ("c1",)),
    )
    ids = {i.object_id for i in detect_cycles(calcs)}
    assert ids == {"c2", "c3"}
