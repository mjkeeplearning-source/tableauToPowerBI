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
