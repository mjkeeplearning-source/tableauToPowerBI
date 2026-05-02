from tableau2pbir.emit.tmdl.measure import render_measure
from tableau2pbir.ir.calculation import Calculation, CalculationKind, CalculationPhase, CalculationScope


def test_aggregate_measure():
    calc = Calculation(
        id="m1", name="Total Sales", scope=CalculationScope.MEASURE,
        tableau_expr="SUM([Sales])", dax_expr="SUM('Sales'[Sales])",
        kind=CalculationKind.AGGREGATE, phase=CalculationPhase.AGGREGATE,
    )
    out = render_measure(calc)
    assert "measure 'Total Sales'" in out
    assert "expression: SUM('Sales'[Sales])" in out


def test_measure_with_no_dax_returns_empty():
    calc = Calculation(
        id="m2", name="Deferred Calc", scope=CalculationScope.MEASURE,
        tableau_expr="WINDOW_SUM(SUM([x]))", dax_expr=None,
        kind=CalculationKind.TABLE_CALC, phase=CalculationPhase.VIZ,
    )
    assert render_measure(calc) == ""


def test_measure_expression_is_indented_under_measure_keyword():
    calc = Calculation(
        id="m3", name="Count Orders", scope=CalculationScope.MEASURE,
        tableau_expr="COUNTD([order_id])", dax_expr="DISTINCTCOUNT('Orders'[order_id])",
        kind=CalculationKind.AGGREGATE, phase=CalculationPhase.AGGREGATE,
    )
    out = render_measure(calc)
    lines = out.splitlines()
    measure_line = next(l for l in lines if "measure" in l)
    expr_line    = next(l for l in lines if "expression:" in l)
    # measure is at 1 tab; expression: must be at 2 tabs (nested child in TMDL)
    assert measure_line.startswith("\t") and not measure_line.startswith("\t\t")
    assert expr_line.startswith("\t\t")


def test_column_scope_is_not_a_measure():
    calc = Calculation(
        id="c1", name="Row Calc", scope=CalculationScope.COLUMN,
        tableau_expr="[A]+[B]", dax_expr="'T'[A]+'T'[B]",
        kind=CalculationKind.ROW, phase=CalculationPhase.ROW,
    )
    assert render_measure(calc) == ""
