"""FIXED LOD → CALCULATE(<agg>, REMOVEFILTERS(<other>), KEEPFILTERS(<dims>)).

We don't know "all other dimensions" at translate time; per spec we use
REMOVEFILTERS over the table containing the dim and KEEPFILTERS over the
listed FIXED dims. The IR Calculation.lod_fixed.dimensions carries the
dim list; the rule consumes that, not the raw expression."""
from __future__ import annotations

from tableau2pbir.ir.calculation import (
    Calculation, CalculationKind, CalculationPhase, LodFixed,
)
from tableau2pbir.ir.common import FieldRef
from tableau2pbir.translate.rules.lod_fixed import translate_lod_fixed


def _calc(expr: str, dims: tuple[FieldRef, ...]) -> Calculation:
    return Calculation(
        id="c1", name="LodCalc", scope="measure", tableau_expr=expr,
        depends_on=(), kind=CalculationKind.LOD_FIXED,
        phase=CalculationPhase.AGGREGATE,
        lod_fixed=LodFixed(dimensions=dims),
    )


def test_fixed_one_dim():
    fr = FieldRef(table_id="orders", column_id="orders__col__customer")
    c = _calc("{FIXED [Customer] : SUM([Sales])}", (fr,))
    out = translate_lod_fixed(c)
    assert out == (
        "CALCULATE(SUM([Sales]), "
        "REMOVEFILTERS(orders), "
        "KEEPFILTERS(VALUES(orders[orders__col__customer])))"
    )


def test_fixed_two_dims():
    a = FieldRef(table_id="orders", column_id="orders__col__customer")
    b = FieldRef(table_id="orders", column_id="orders__col__region")
    c = _calc("{FIXED [Customer], [Region] : AVG([Sales])}", (a, b))
    out = translate_lod_fixed(c)
    assert "AVERAGE([Sales])" in out
    assert "REMOVEFILTERS(orders)" in out
    assert "KEEPFILTERS(VALUES(orders[orders__col__customer]))" in out
    assert "KEEPFILTERS(VALUES(orders[orders__col__region]))" in out


def test_no_inner_aggregation_returns_none():
    fr = FieldRef(table_id="orders", column_id="orders__col__customer")
    c = _calc("{FIXED [Customer] : [Sales]}", (fr,))
    assert translate_lod_fixed(c) is None
