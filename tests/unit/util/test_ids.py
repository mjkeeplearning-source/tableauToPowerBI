from __future__ import annotations

from tableau2pbir.util.ids import slug_id, stable_id


def test_slug_id_lowercases_and_replaces_unsafe_chars():
    assert slug_id("Sales By Region") == "sales_by_region"
    assert slug_id("[Profit Margin %]") == "profit_margin_pct"
    assert slug_id("Column 1") == "column_1"


def test_slug_id_collapses_runs_of_underscores():
    assert slug_id("a  b__c") == "a_b_c"


def test_slug_id_strips_leading_trailing_underscores():
    assert slug_id("__x__") == "x"


def test_slug_id_falls_back_to_hash_when_all_stripped():
    result = slug_id("$$$")
    assert result.startswith("id_")
    assert len(result) > 3


def test_stable_id_is_deterministic():
    assert stable_id("calc", "Profit") == stable_id("calc", "Profit")
    assert stable_id("calc", "Profit") != stable_id("calc", "Revenue")


def test_stable_id_prefixes_with_kind():
    result = stable_id("sheet", "Revenue Overview")
    assert result.startswith("sheet__")
