from __future__ import annotations

from tableau2pbir.ir.parameter import ParameterExposure, ParameterIntent
from tableau2pbir.stages._build_data_model import build_parameters


def test_range_with_card_becomes_numeric_what_if():
    raw = [{
        "name": "Parameter 1", "caption": "Discount",
        "datatype": "real", "domain_type": "range", "default": "0.1",
        "allowed_values": (), "range": {"min": "0.0", "max": "0.5", "granularity": "0.05"},
    }]
    usage = {"Parameter 1": "card"}
    params = build_parameters(raw, usage)
    assert len(params) == 1
    p = params[0]
    assert p.intent == ParameterIntent.NUMERIC_WHAT_IF
    assert p.exposure == ParameterExposure.CARD
    assert p.default == "0.1"
    # For range parameters, allowed_values are synthesized from min/max/granularity
    # (used by Plan 4 to generate the GENERATESERIES table).
    assert len(p.allowed_values) >= 2


def test_list_with_card_becomes_categorical_selector():
    raw = [{
        "name": "Parameter 2", "caption": "Region",
        "datatype": "string", "domain_type": "list", "default": '"West"',
        "allowed_values": ('"West"', '"East"'),
        "range": None,
    }]
    params = build_parameters(raw, {"Parameter 2": "card"})
    assert params[0].intent == ParameterIntent.CATEGORICAL_SELECTOR
    assert params[0].allowed_values == ('"West"', '"East"')


def test_calc_only_becomes_internal_constant():
    raw = [{
        "name": "AxisMax", "caption": "AxisMax",
        "datatype": "integer", "domain_type": "any", "default": "100",
        "allowed_values": (), "range": None,
    }]
    params = build_parameters(raw, {})
    assert params[0].intent == ParameterIntent.INTERNAL_CONSTANT
    assert params[0].exposure == ParameterExposure.CALC_ONLY


def test_range_on_shelf_is_unsupported():
    raw = [{
        "name": "Threshold", "caption": None,
        "datatype": "real", "domain_type": "range", "default": "0",
        "allowed_values": (), "range": {"min": "0", "max": "1", "granularity": "0.1"},
    }]
    params = build_parameters(raw, {"Threshold": "shelf"})
    assert params[0].intent == ParameterIntent.UNSUPPORTED


def test_parameter_id_is_stable():
    raw = [{
        "name": "Discount", "caption": None,
        "datatype": "real", "domain_type": "range", "default": "0",
        "allowed_values": (), "range": {"min": "0", "max": "1", "granularity": "0.1"},
    }]
    first = build_parameters(raw, {"Discount": "card"})[0].id
    second = build_parameters(raw, {"Discount": "card"})[0].id
    assert first == second
    assert first.startswith("param__")
