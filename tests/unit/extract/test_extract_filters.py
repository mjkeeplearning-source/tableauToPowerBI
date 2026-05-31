"""Tests for _filters() class normalisation and child-element capture."""
from __future__ import annotations

from lxml import etree

from tableau2pbir.extract.worksheets import _filters


def _view(xml_body: str) -> etree._Element:
    return etree.fromstring(f"<view>{xml_body}</view>")


def test_quantitative_mapped_to_range():
    v = _view("""
        <filter class='quantitative' column='[Amount]'>
          <min>100</min>
          <max>500</max>
        </filter>
    """)
    result = _filters(v)
    assert len(result) == 1
    f = result[0]
    assert f["kind"] == "range"
    assert f["column"] == "Amount"
    assert f["min_val"] == "100"
    assert f["max_val"] == "500"
    assert f["agg_prefix"] is None


def test_quantitative_min_only():
    v = _view("<filter class='quantitative' column='[Sales]'><min>0</min></filter>")
    f = _filters(v)[0]
    assert f["kind"] == "range"
    assert f["min_val"] == "0"
    assert f["max_val"] is None


def test_top_mapped_to_top_n():
    v = _view("""
        <filter class='top' column='[Customer]'>
          <top-spec-count>10</top-spec-count>
          <top-spec-direction>Top</top-spec-direction>
          <top-spec-field column='[Revenue]' aggregation='SUM'/>
        </filter>
    """)
    result = _filters(v)
    assert len(result) == 1
    f = result[0]
    assert f["kind"] == "top_n"
    assert f["column"] == "Customer"
    assert f["n"] == 10
    assert f["direction"] == "Top"
    assert f["by_column"] == "Revenue"
    assert f["by_agg"] == "SUM"


def test_top_without_spec_field():
    v = _view("""
        <filter class='top' column='[Product]'>
          <top-spec-count>5</top-spec-count>
          <top-spec-direction>Bottom</top-spec-direction>
        </filter>
    """)
    f = _filters(v)[0]
    assert f["kind"] == "top_n"
    assert f["n"] == 5
    assert f["direction"] == "Bottom"
    assert f["by_column"] is None
    assert f["by_agg"] is None


def test_condition_mapped_to_conditional():
    v = _view("<filter class='condition' column='[Profit]' formula='[Profit] &gt; 0'/>")
    f = _filters(v)[0]
    assert f["kind"] == "conditional"
    assert f["expr"] == "[Profit] > 0"


def test_context_kind_preserved():
    v = _view("""
        <filter class='context' column='[Region]'>
          <groupfilter function='member' member='West'/>
        </filter>
    """)
    f = _filters(v)[0]
    assert f["kind"] == "context"
    assert "West" in f["include"]


def test_unknown_class_defaults_to_categorical():
    v = _view("<filter class='unknown_future_type' column='[X]'/>")
    f = _filters(v)[0]
    assert f["kind"] == "categorical"


def test_categorical_members_captured():
    v = _view("""
        <filter class='categorical' column='[Region]'>
          <groupfilter function='member' member='East'/>
          <groupfilter function='member' member='West'/>
          <groupfilter function='except' member='North'/>
        </filter>
    """)
    f = _filters(v)[0]
    assert f["kind"] == "categorical"
    assert "East" in f["include"]
    assert "West" in f["include"]
    assert "North" in f["exclude"]
