from __future__ import annotations

from tableau2pbir.classify.calc_kind import CalcClassification, classify_calc_kind


def test_row_calc():
    r = classify_calc_kind("[Revenue] - [Cost]")
    assert isinstance(r, CalcClassification)
    assert r.kind == "row"
    assert r.phase == "row"


def test_aggregate_sum():
    r = classify_calc_kind("SUM([Sales])")
    assert r.kind == "aggregate"
    assert r.phase == "aggregate"


def test_aggregate_with_if():
    r = classify_calc_kind("IF SUM([Sales]) > 0 THEN AVG([Profit]) END")
    assert r.kind == "aggregate"


def test_lod_fixed():
    r = classify_calc_kind("{FIXED [Region]: SUM([Sales])}")
    assert r.kind == "lod_fixed"
    assert r.phase == "aggregate"


def test_lod_include():
    r = classify_calc_kind("{INCLUDE [Customer]: SUM([Sales])}")
    assert r.kind == "lod_include"


def test_lod_exclude():
    r = classify_calc_kind("{EXCLUDE [Region]: SUM([Sales])}")
    assert r.kind == "lod_exclude"


def test_table_calc_running_sum():
    r = classify_calc_kind("RUNNING_SUM(SUM([Sales]))")
    assert r.kind == "table_calc"
    assert r.phase == "viz"


def test_table_calc_window():
    r = classify_calc_kind("WINDOW_AVG(SUM([Sales]), -2, 0)")
    assert r.kind == "table_calc"


def test_table_calc_rank():
    r = classify_calc_kind("RANK(SUM([Sales]))")
    assert r.kind == "table_calc"


def test_aggregate_string_literal_with_sum_not_misclassified():
    r = classify_calc_kind('"SUM of everything"')
    assert r.kind == "row"


def test_whitespace_insensitive_lod_prefix():
    r = classify_calc_kind("  {  FIXED [x]: SUM([y]) }")
    assert r.kind == "lod_fixed"
