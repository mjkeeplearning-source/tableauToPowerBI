"""Tests for _filter_to_pbir per-kind emit."""
from __future__ import annotations

import pytest

from tableau2pbir.emit.pbir.filters import _filter_to_pbir
from tableau2pbir.ir.common import FieldRef
from tableau2pbir.ir.sheet import (
    CategoricalFilter, ConditionalFilter, ContextFilter,
    RangeFilter, TopNFilter,
)

_FIELD = FieldRef(table_id="Sales", column_id="Region")


def _cat(include=(), exclude=()):
    return CategoricalFilter(id="f1", field=_FIELD, include=include, exclude=exclude)


class TestCategoricalEmit:
    def test_include_only(self):
        result = _filter_to_pbir(_cat(include=("East", "West")))
        assert result is not None
        assert result["type"] == "Categorical"
        assert result["name"] == "f1"
        # top-level field uses Entity (StandaloneSourceRef)
        assert result["field"]["Column"]["Expression"]["SourceRef"]["Entity"] == "Sales"
        assert result["field"]["Column"]["Property"] == "Region"
        # filter body
        fd = result["filter"]
        assert fd["Version"] == 2
        assert fd["From"][0] == {"Name": "f", "Entity": "Sales", "Type": 0}
        condition = fd["Where"][0]["Condition"]
        assert "In" in condition
        in_expr = condition["In"]
        # alias-ref inside Where uses Source key
        assert in_expr["Expressions"][0]["Column"]["Expression"]["SourceRef"]["Source"] == "f"
        values = [v[0]["Literal"]["Value"] for v in in_expr["Values"]]
        assert "'East'" in values
        assert "'West'" in values
        assert result["howCreated"] == "User"
        assert result["isHiddenInViewMode"] is False

    def test_exclude_only(self):
        result = _filter_to_pbir(_cat(exclude=("North",)))
        assert result is not None
        condition = result["filter"]["Where"][0]["Condition"]
        assert "Not" in condition
        assert "In" in condition["Not"]["Expression"]

    def test_include_and_exclude(self):
        result = _filter_to_pbir(_cat(include=("East",), exclude=("North",)))
        assert result is not None
        condition = result["filter"]["Where"][0]["Condition"]
        assert "And" in condition
        assert "In" in condition["And"]["Left"]
        assert "Not" in condition["And"]["Right"]

    def test_empty_returns_none(self):
        assert _filter_to_pbir(_cat()) is None

    def test_howcreated_and_hidden(self):
        result = _filter_to_pbir(_cat(include=("East",)))
        assert result["howCreated"] == "User"
        assert result["isHiddenInViewMode"] is False


class TestContextEmit:
    def test_context_same_structure_as_categorical(self):
        f = ContextFilter(id="f2", field=_FIELD, include=("West",))
        result = _filter_to_pbir(f)
        assert result is not None
        assert result["name"] == "f2"
        assert result["type"] == "Categorical"
        condition = result["filter"]["Where"][0]["Condition"]
        assert "In" in condition

    def test_context_empty_returns_none(self):
        f = ContextFilter(id="f3", field=_FIELD)
        assert _filter_to_pbir(f) is None


_AMOUNT_FIELD = FieldRef(table_id="Sales", column_id="Amount")


class TestRangeEmit:
    def test_both_bounds_uses_between(self):
        f = RangeFilter(id="r1", field=_AMOUNT_FIELD, min_val="100", max_val="500")
        result = _filter_to_pbir(f)
        assert result is not None
        assert result["type"] == "Range"
        assert result["field"]["Column"]["Expression"]["SourceRef"]["Entity"] == "Sales"
        condition = result["filter"]["Where"][0]["Condition"]
        assert "Between" in condition
        between = condition["Between"]
        assert between["Expression"]["Column"]["Expression"]["SourceRef"]["Source"] == "f"
        assert between["LowerBound"]["Literal"]["Value"] == "100L"
        assert between["UpperBound"]["Literal"]["Value"] == "500L"

    def test_min_only_uses_gte_comparison(self):
        f = RangeFilter(id="r2", field=_AMOUNT_FIELD, min_val="0")
        result = _filter_to_pbir(f)
        assert result is not None
        assert result["type"] == "Range"
        condition = result["filter"]["Where"][0]["Condition"]
        assert "Comparison" in condition
        comp = condition["Comparison"]
        assert comp["ComparisonKind"] == 2  # GreaterThanOrEqual
        assert comp["Left"]["Column"]["Expression"]["SourceRef"]["Source"] == "f"

    def test_max_only_uses_lte_comparison(self):
        f = RangeFilter(id="r3", field=_AMOUNT_FIELD, max_val="999")
        result = _filter_to_pbir(f)
        assert result is not None
        condition = result["filter"]["Where"][0]["Condition"]
        comp = condition["Comparison"]
        assert comp["ComparisonKind"] == 4  # LessThanOrEqual
        assert comp["Left"]["Column"]["Expression"]["SourceRef"]["Source"] == "f"

    def test_no_bounds_returns_none(self):
        f = RangeFilter(id="r4", field=_AMOUNT_FIELD)
        assert _filter_to_pbir(f) is None

    def test_advanced_post_agg_type(self):
        f = RangeFilter(id="r5", field=_AMOUNT_FIELD, min_val="1000", agg_prefix="SUM")
        result = _filter_to_pbir(f)
        assert result is not None
        assert result["type"] == "Advanced"
        # top-level field is Aggregation wrapping Entity ref
        assert "Aggregation" in result["field"]
        agg_field = result["field"]["Aggregation"]
        assert agg_field["Function"] == 0  # Sum
        assert agg_field["Expression"]["Column"]["Expression"]["SourceRef"]["Entity"] == "Sales"
        # Where condition is Comparison with Aggregation on left
        condition = result["filter"]["Where"][0]["Condition"]
        assert "Comparison" in condition
        left = condition["Comparison"]["Left"]
        assert "Aggregation" in left
        assert left["Aggregation"]["Expression"]["Column"]["Expression"]["SourceRef"]["Source"] == "f"

    def test_advanced_unknown_agg_prefix_returns_none(self):
        f = RangeFilter(id="r6", field=_AMOUNT_FIELD, min_val="1", agg_prefix="UNKNOWN_AGG")
        assert _filter_to_pbir(f) is None

    def test_advanced_post_agg_both_bounds(self):
        f = RangeFilter(id="r7", field=_AMOUNT_FIELD, min_val="1000", max_val="9999", agg_prefix="SUM")
        result = _filter_to_pbir(f)
        assert result is not None
        assert result["type"] == "Advanced"
        assert len(result["filter"]["Where"]) == 2
        kinds = [w["Condition"]["Comparison"]["ComparisonKind"] for w in result["filter"]["Where"]]
        assert 2 in kinds  # GTE
        assert 4 in kinds  # LTE


class TestDeferredEmit:
    def test_topn_returns_none(self):
        f = TopNFilter(id="t1", field=_FIELD, n=10)
        assert _filter_to_pbir(f) is None

    def test_conditional_returns_none(self):
        f = ConditionalFilter(id="c1", field=_FIELD, expr="[x] > 0")
        assert _filter_to_pbir(f) is None
