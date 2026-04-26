from __future__ import annotations

from tableau2pbir.util.xml import (
    attr,
    child_text,
    iter_children,
    optional_attr,
    parse_workbook_xml,
    require_attr,
)


_XML = b"""<?xml version='1.0'?>
<workbook version='18.1'>
  <datasources>
    <datasource name='Sales' caption='Sales DB'>
      <connection class='sqlserver' server='sql1'/>
    </datasource>
  </datasources>
</workbook>
"""


def test_parse_workbook_xml_returns_root():
    root = parse_workbook_xml(_XML)
    assert root.tag == "workbook"


def test_attr_returns_string_or_default():
    root = parse_workbook_xml(_XML)
    ds = root.find(".//datasource")
    assert attr(ds, "name") == "Sales"
    assert attr(ds, "missing", default="fallback") == "fallback"


def test_optional_attr_returns_none_when_missing():
    root = parse_workbook_xml(_XML)
    ds = root.find(".//datasource")
    assert optional_attr(ds, "caption") == "Sales DB"
    assert optional_attr(ds, "nope") is None


def test_require_attr_raises_when_missing():
    root = parse_workbook_xml(_XML)
    ds = root.find(".//datasource")
    import pytest
    with pytest.raises(ValueError, match="missing attribute"):
        require_attr(ds, "nope")


def test_child_text_handles_missing():
    root = parse_workbook_xml(b"<x><a>hi</a></x>")
    assert child_text(root, "a") == "hi"
    assert child_text(root, "b") is None


def test_iter_children_by_tag():
    root = parse_workbook_xml(b"<x><a/><b/><a/></x>")
    assert [c.tag for c in iter_children(root, "a")] == ["a", "a"]
