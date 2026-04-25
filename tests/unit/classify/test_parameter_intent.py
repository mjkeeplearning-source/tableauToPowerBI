from __future__ import annotations

from tableau2pbir.classify.parameter_intent import classify_parameter_intent


def test_range_with_card_is_numeric_what_if():
    assert classify_parameter_intent(domain_type="range", exposure="card") \
        == "numeric_what_if"


def test_list_with_card_is_categorical_selector():
    assert classify_parameter_intent(domain_type="list", exposure="card") \
        == "categorical_selector"


def test_calc_only_is_internal_constant_regardless_of_domain():
    for dt in ("range", "list", "any"):
        assert classify_parameter_intent(domain_type=dt, exposure="calc_only") \
            == "internal_constant"


def test_drives_format_switch_returns_formatting_control():
    assert classify_parameter_intent(domain_type="list", exposure="card",
                                     drives_format_switch=True) \
        == "formatting_control"


def test_range_on_shelf_is_unsupported_heuristic():
    # range parameter used on a shelf (not a card) — no clean PBI mapping.
    assert classify_parameter_intent(domain_type="range", exposure="shelf") \
        == "unsupported"


def test_any_with_card_is_unsupported():
    # 'any' (open-ended) parameter with a card — user can type arbitrary values,
    # no PBI equivalent.
    assert classify_parameter_intent(domain_type="any", exposure="card") \
        == "unsupported"
