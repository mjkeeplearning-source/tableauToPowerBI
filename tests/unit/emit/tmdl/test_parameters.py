from tableau2pbir.emit.tmdl.parameters import render_parameter
from tableau2pbir.ir.parameter import Parameter, ParameterExposure, ParameterIntent


def test_numeric_what_if_emits_table_and_measure():
    p = Parameter(
        id="p1", name="Discount Rate", datatype="real", default="0.1",
        allowed_values=("0", "1", "0.05"),
        intent=ParameterIntent.NUMERIC_WHAT_IF, exposure=ParameterExposure.CARD,
    )
    files = render_parameter(p)
    body = files["tables/Discount Rate.tmdl"]
    assert "GENERATESERIES(0,1,0.05)" in body
    assert "measure 'Discount Rate SelectedValue'" in body


def test_categorical_selector_emits_rows_table():
    p = Parameter(
        id="p2", name="Region", datatype="string", default="West",
        allowed_values=("North", "South", "East", "West"),
        intent=ParameterIntent.CATEGORICAL_SELECTOR, exposure=ParameterExposure.CARD,
    )
    files = render_parameter(p)
    body = files["tables/Region.tmdl"]
    assert '{"North"}' in body or '"North"' in body
    assert "measure 'Region SelectedValue'" in body


def test_internal_constant_hidden_measure():
    p = Parameter(
        id="p3", name="Threshold", datatype="real", default="100",
        allowed_values=(),
        intent=ParameterIntent.INTERNAL_CONSTANT, exposure=ParameterExposure.CALC_ONLY,
    )
    files = render_parameter(p)
    assert any("measure Threshold" in body and "isHidden: true" in body for body in files.values())


def test_unsupported_intent_emits_nothing():
    p = Parameter(
        id="p4", name="X", datatype="string", default="",
        allowed_values=(), intent=ParameterIntent.UNSUPPORTED,
        exposure=ParameterExposure.SHELF,
    )
    assert render_parameter(p) == {}
