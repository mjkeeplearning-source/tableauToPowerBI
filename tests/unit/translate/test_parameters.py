"""[ParamName] rewriter — translates Tableau parameter references inside
calc bodies according to Parameter.intent (spec §5.7)."""
from __future__ import annotations

from tableau2pbir.ir.parameter import Parameter, ParameterIntent
from tableau2pbir.translate.parameters import rewrite_parameter_refs


def _param(name: str, intent: ParameterIntent, default: str = "0") -> Parameter:
    return Parameter(
        id=f"p_{name}", name=name, datatype="float",
        default=default, allowed_values=(),
        intent=intent, exposure="card",
    )


def test_numeric_what_if_resolves_to_selected_value():
    params = (_param("Threshold", ParameterIntent.NUMERIC_WHAT_IF, "10"),)
    assert rewrite_parameter_refs("[Threshold] * 2", params) == \
        "[Threshold SelectedValue] * 2"


def test_categorical_selector_resolves_to_selected_value():
    params = (_param("Region", ParameterIntent.CATEGORICAL_SELECTOR, "East"),)
    assert rewrite_parameter_refs("IF [Region] = \"East\" THEN 1 ELSE 0 END", params) == \
        "IF [Region SelectedValue] = \"East\" THEN 1 ELSE 0 END"


def test_internal_constant_inlines_default():
    params = (_param("TaxRate", ParameterIntent.INTERNAL_CONSTANT, "0.07"),)
    assert rewrite_parameter_refs("[Sales] * [TaxRate]", params) == \
        "[Sales] * 0.07"


def test_unknown_param_left_unchanged():
    assert rewrite_parameter_refs("[Sales] + [Unknown]", ()) == "[Sales] + [Unknown]"


def test_multiple_params_in_one_expr():
    params = (
        _param("Threshold", ParameterIntent.NUMERIC_WHAT_IF, "10"),
        _param("TaxRate", ParameterIntent.INTERNAL_CONSTANT, "0.07"),
    )
    out = rewrite_parameter_refs("[Sales] * [TaxRate] + [Threshold]", params)
    assert out == "[Sales] * 0.07 + [Threshold SelectedValue]"
