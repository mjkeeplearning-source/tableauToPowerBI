"""Dispatch picks the right rule by Calculation.kind, returns
(dax_expr, rule_name) or (None, None) on miss."""
from __future__ import annotations

from tableau2pbir.ir.calculation import (
    Calculation, CalculationKind, CalculationPhase, LodFixed,
)
from tableau2pbir.ir.common import FieldRef
from tableau2pbir.ir.parameter import Parameter, ParameterIntent
from tableau2pbir.translate.rules.dispatch import dispatch_rule


def _calc(kind: CalculationKind, expr: str, **kw: object) -> Calculation:
    return Calculation(
        id="c1", name="C", scope="measure", tableau_expr=expr,
        depends_on=(), kind=kind, phase=CalculationPhase.AGGREGATE, **kw,
    )


def test_row_dispatch_runs_row_rule():
    c = _calc(CalculationKind.ROW, "ZN([Sales])")
    dax, rule = dispatch_rule(c, parameters=())
    assert dax == "COALESCE([Sales], 0)"
    assert rule == "row"


def test_aggregate_dispatch_runs_aggregate_rule():
    c = _calc(CalculationKind.AGGREGATE, "AVG([Sales])")
    dax, rule = dispatch_rule(c, parameters=())
    assert dax == "AVERAGE([Sales])"
    assert rule == "aggregate"


def test_lod_fixed_dispatch_runs_lod_fixed_rule():
    fr = FieldRef(table_id="orders", column_id="orders__col__cust")
    c = _calc(
        CalculationKind.LOD_FIXED, "{FIXED [Customer] : SUM([Sales])}",
        lod_fixed=LodFixed(dimensions=(fr,)),
    )
    dax, rule = dispatch_rule(c, parameters=())
    assert "REMOVEFILTERS(orders)" in dax
    assert rule == "lod_fixed"


def test_parameters_rewritten_before_rule():
    p = Parameter(id="p", name="TaxRate", datatype="float", default="0.07",
                  allowed_values=(), intent=ParameterIntent.INTERNAL_CONSTANT,
                  exposure="card")
    c = _calc(CalculationKind.ROW, "[Sales] * [TaxRate]")
    dax, _ = dispatch_rule(c, parameters=(p,))
    assert dax == "[Sales] * 0.07"


def test_deferred_kind_returns_none():
    c = _calc(CalculationKind.LOD_INCLUDE, "{INCLUDE [x] : SUM(y)}")
    dax, rule = dispatch_rule(c, parameters=())
    assert dax is None
    assert rule is None


def test_no_rule_match_returns_none():
    c = _calc(CalculationKind.ROW, "WEIRDFN([x])")
    dax, rule = dispatch_rule(c, parameters=())
    assert dax is None
    assert rule == "row"  # row was tried but missed
