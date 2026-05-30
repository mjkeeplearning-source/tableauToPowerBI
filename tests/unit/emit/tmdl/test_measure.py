from tableau2pbir.emit.tmdl.measure import render_measure
from tableau2pbir.ir.calculation import Calculation, CalculationKind, CalculationPhase, CalculationScope


def test_single_line_measure_uses_equals_syntax():
    calc = Calculation(
        id="m1", name="Total Sales", scope=CalculationScope.MEASURE,
        tableau_expr="SUM([Sales])", dax_expr="SUM('Sales'[Sales])",
        kind=CalculationKind.AGGREGATE, phase=CalculationPhase.AGGREGATE,
    )
    out = render_measure(calc)
    assert out == "\tmeasure 'Total Sales' = SUM('Sales'[Sales])\n"


def test_measure_with_no_dax_returns_empty():
    calc = Calculation(
        id="m2", name="Deferred Calc", scope=CalculationScope.MEASURE,
        tableau_expr="WINDOW_SUM(SUM([x]))", dax_expr=None,
        kind=CalculationKind.TABLE_CALC, phase=CalculationPhase.VIZ,
    )
    assert render_measure(calc) == ""


def test_single_line_measure_no_expression_sub_property():
    calc = Calculation(
        id="m3", name="Count Orders", scope=CalculationScope.MEASURE,
        tableau_expr="COUNTD([order_id])", dax_expr="DISTINCTCOUNT('Orders'[order_id])",
        kind=CalculationKind.AGGREGATE, phase=CalculationPhase.AGGREGATE,
    )
    out = render_measure(calc)
    assert out == "\tmeasure 'Count Orders' = DISTINCTCOUNT('Orders'[order_id])\n"
    assert "expression:" not in out


def test_multiline_measure_declaration_line_ends_with_equals():
    dax = "VAR x = SUM('T'[a])\nRETURN x"
    calc = Calculation(
        id="m4", name="Complex", scope=CalculationScope.MEASURE,
        tableau_expr="...", dax_expr=dax,
        kind=CalculationKind.AGGREGATE, phase=CalculationPhase.AGGREGATE,
    )
    out = render_measure(calc)
    lines = out.splitlines()
    assert lines[0] == "\tmeasure Complex ="
    assert lines[1] == "\t\t\tVAR x = SUM('T'[a])"
    assert lines[2] == "\t\t\tRETURN x"
    assert "expression:" not in out


def test_column_scope_is_not_a_measure():
    calc = Calculation(
        id="c1", name="Row Calc", scope=CalculationScope.COLUMN,
        tableau_expr="[A]+[B]", dax_expr="'T'[A]+'T'[B]",
        kind=CalculationKind.ROW, phase=CalculationPhase.ROW,
    )
    assert render_measure(calc) == ""
