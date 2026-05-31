"""Tests for _build_filter factory dispatch and UnsupportedItem recording."""
from __future__ import annotations

from tableau2pbir.ir.common import FieldRef
from tableau2pbir.ir.sheet import (
    CategoricalFilter, ConditionalFilter, ContextFilter, RangeFilter, TopNFilter,
)
from tableau2pbir.stages._build_sheets import _build_filter, build_sheets


def _field(col: str) -> FieldRef:
    return FieldRef(table_id="tbl__sales", column_id=col)


def test_categorical_dispatch():
    f = _build_filter({"kind": "categorical", "column": "Region",
                       "include": ("East",), "exclude": (), "expr": None},
                      sheet_idx=0, filter_idx=0, table_id="tbl__sales")
    assert isinstance(f, CategoricalFilter)
    assert f.include == ("East",)
    assert f.field == _field("region")


def test_range_dispatch():
    f = _build_filter({"kind": "range", "column": "Amount",
                       "min_val": "10", "max_val": "500", "agg_prefix": None},
                      sheet_idx=0, filter_idx=1, table_id="tbl__sales")
    assert isinstance(f, RangeFilter)
    assert f.min_val == "10"
    assert f.max_val == "500"
    assert f.agg_prefix is None


def test_top_n_dispatch():
    f = _build_filter({"kind": "top_n", "column": "Customer",
                       "n": 10, "direction": "Top",
                       "by_column": "Revenue", "by_agg": "SUM"},
                      sheet_idx=0, filter_idx=2, table_id="tbl__sales")
    assert isinstance(f, TopNFilter)
    assert f.n == 10
    assert f.by_agg == "SUM"
    assert f.by_field == _field("revenue")


def test_context_dispatch():
    f = _build_filter({"kind": "context", "column": "Year",
                       "include": ("2023",), "exclude": (), "expr": None},
                      sheet_idx=0, filter_idx=3, table_id="tbl__sales")
    assert isinstance(f, ContextFilter)
    assert f.include == ("2023",)


def test_conditional_dispatch():
    f = _build_filter({"kind": "conditional", "column": "Profit",
                       "include": (), "exclude": (), "expr": "[Profit] > 0"},
                      sheet_idx=0, filter_idx=4, table_id="tbl__sales")
    assert isinstance(f, ConditionalFilter)
    assert f.expr == "[Profit] > 0"


def test_topn_filter_adds_unsupported_item():
    raw_worksheets = [{
        "name": "Top Customers",
        "datasource_refs": ("ds1",),
        "mark_type": "bar",
        "encodings": {"rows": (), "columns": (), "color": None, "size": None,
                      "label": None, "tooltip": None, "detail": (), "shape": None, "angle": None},
        "filters": [{"kind": "top_n", "column": "Customer",
                     "n": 5, "direction": "Top", "by_column": None, "by_agg": None}],
        "sort": [], "dual_axis": False, "reference_lines": [], "quick_table_calcs": [],
    }]
    sheets, unsupported = build_sheets(raw_worksheets, set(), {"ds1": "tbl__sales"})
    assert len(sheets) == 1
    assert isinstance(sheets[0].filters[0], TopNFilter)
    assert any(u.code == "deferred_feature_topn_filter" for u in unsupported)


def test_conditional_filter_adds_unsupported_item():
    raw_worksheets = [{
        "name": "Conditions",
        "datasource_refs": ("ds1",),
        "mark_type": "bar",
        "encodings": {"rows": (), "columns": (), "color": None, "size": None,
                      "label": None, "tooltip": None, "detail": (), "shape": None, "angle": None},
        "filters": [{"kind": "conditional", "column": "Profit",
                     "include": (), "exclude": (), "expr": "[Profit] > 0"}],
        "sort": [], "dual_axis": False, "reference_lines": [], "quick_table_calcs": [],
    }]
    sheets, unsupported = build_sheets(raw_worksheets, set(), {"ds1": "tbl__sales"})
    assert any(u.code == "deferred_feature_conditional_filter" for u in unsupported)
