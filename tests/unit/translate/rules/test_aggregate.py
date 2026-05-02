"""Aggregate-calc rules: SUM/AVG/COUNT/COUNTD/MIN/MAX + conditional
SUM(IF cond THEN x END) → CALCULATE(SUM(x), FILTER(...))."""
from __future__ import annotations

from tableau2pbir.translate.rules.aggregate import translate_aggregate


def test_sum_passthrough():
    assert translate_aggregate("SUM([Sales])") == "SUM([Sales])"


def test_avg_to_average():
    assert translate_aggregate("AVG([Sales])") == "AVERAGE([Sales])"


def test_countd_to_distinctcount():
    assert translate_aggregate("COUNTD([Customer])") == "DISTINCTCOUNT([Customer])"


def test_min_max_passthrough():
    assert translate_aggregate("MIN([Sales])") == "MIN([Sales])"
    assert translate_aggregate("MAX([Sales])") == "MAX([Sales])"


def test_conditional_sum_to_calculate_filter():
    out = translate_aggregate('SUM(IF [Region] = "East" THEN [Sales] END)')
    assert out.startswith("CALCULATE(SUM([Sales])")
    assert 'FILTER' in out
    assert '[Region] = "East"' in out


def test_unmatched_returns_none():
    assert translate_aggregate("WEIRDFN([x])") is None


def test_compound_subtraction_two_countd():
    out = translate_aggregate("COUNTD([order_id]) - COUNTD([order_id (returns)])")
    assert out == "DISTINCTCOUNT([order_id]) - DISTINCTCOUNT([order_id (returns)])", \
        f"COUNTD must become DISTINCTCOUNT in compound expr, got: {out}"


def test_compound_subtraction_two_sum():
    out = translate_aggregate("SUM([profit]) - sum([discount])")
    assert out == "SUM([profit]) - SUM([discount])", \
        f"lowercase sum must be normalised in compound expr, got: {out}"


def test_compound_addition():
    out = translate_aggregate("SUM([a]) + AVG([b])")
    assert out == "SUM([a]) + AVERAGE([b])"


def test_lowercase_single_sum():
    assert translate_aggregate("sum([Sales])") == "SUM([Sales])"


def test_compound_non_agg_returns_none():
    assert translate_aggregate("COUNTD([x]) - [plain_field]") is None
