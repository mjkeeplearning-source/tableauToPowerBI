from __future__ import annotations

from tableau2pbir.ir.parameter import (
    Parameter, ParameterBindingTarget, ParameterExposure, ParameterIntent,
)


def test_numeric_what_if_minimal():
    p = Parameter(
        id="p1", name="Discount %", datatype="decimal",
        default="0.1", allowed_values=("0.0", "0.05", "0.1", "0.15"),
        intent=ParameterIntent.NUMERIC_WHAT_IF,
        exposure=ParameterExposure.CARD,
    )
    assert p.intent == ParameterIntent.NUMERIC_WHAT_IF
    assert p.binding_target is None


def test_formatting_control_with_binding():
    p = Parameter(
        id="p2", name="Unit Display", datatype="string",
        default="Thousands", allowed_values=("Ones", "Thousands", "Millions"),
        intent=ParameterIntent.FORMATTING_CONTROL,
        exposure=ParameterExposure.CARD,
        binding_target=ParameterBindingTarget(
            measure_ids=("m1", "m2"),
            format_pattern="#,##0",
        ),
    )
    assert p.binding_target.format_pattern == "#,##0"


def test_internal_constant_calc_only():
    p = Parameter(
        id="p3", name="AxisMax", datatype="integer",
        default="100", allowed_values=(),
        intent=ParameterIntent.INTERNAL_CONSTANT,
        exposure=ParameterExposure.CALC_ONLY,
    )
    assert p.exposure == ParameterExposure.CALC_ONLY
