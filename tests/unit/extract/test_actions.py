from __future__ import annotations

from tableau2pbir.extract.actions import extract_actions
from tableau2pbir.util.xml import parse_workbook_xml


_XML = b"""<?xml version='1.0'?>
<workbook>
  <dashboards>
    <dashboard name='Main'>
      <actions>
        <filter-action caption='By Region' name='a1' trigger='select' clearing-behavior='keep-filter'>
          <source><worksheet>Revenue</worksheet></source>
          <target><worksheet>Detail</worksheet></target>
        </filter-action>
        <highlight-action caption='Highlight' name='a2' trigger='hover'>
          <source><worksheet>Revenue</worksheet></source>
          <target><worksheet>Detail</worksheet></target>
        </highlight-action>
      </actions>
    </dashboard>
  </dashboards>
  <actions>
    <url-action caption='Open' name='a3' trigger='menu' url='https://x/?p=[Parameter 1]'>
      <source><worksheet>Revenue</worksheet></source>
      <target/>
    </url-action>
  </actions>
</workbook>
"""


def test_extract_actions_mixed_kinds():
    root = parse_workbook_xml(_XML)
    acts = extract_actions(root)
    assert len(acts) == 3
    by_name = {a["name"]: a for a in acts}
    assert by_name["a1"]["kind"] == "filter"
    assert by_name["a1"]["trigger"] == "select"
    assert by_name["a1"]["source_sheets"] == ("Revenue",)
    assert by_name["a1"]["target_sheets"] == ("Detail",)
    assert by_name["a1"]["clearing_behavior"] == "keep_filter"
    assert by_name["a2"]["kind"] == "highlight"
    assert by_name["a3"]["kind"] == "url"
    assert by_name["a3"]["url"] == "https://x/?p=[Parameter 1]"


def test_no_actions_returns_empty():
    root = parse_workbook_xml(b"<workbook/>")
    assert extract_actions(root) == []
