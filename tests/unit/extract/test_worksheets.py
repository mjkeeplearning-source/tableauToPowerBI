from __future__ import annotations

from tableau2pbir.extract.worksheets import extract_worksheets
from tableau2pbir.util.xml import parse_workbook_xml


_XML_BASIC = b"""<?xml version='1.0'?>
<workbook><worksheets>
  <worksheet name='Revenue'>
    <view>
      <datasources>
        <datasource name='sample.csv'/>
      </datasources>
      <rows>[amount]</rows>
      <columns>[month]</columns>
      <pane>
        <mark class='Bar'/>
        <encodings>
          <color column='[region]'/>
        </encodings>
      </pane>
    </view>
  </worksheet>
</worksheets></workbook>
"""

_XML_WITH_FILTER = b"""<?xml version='1.0'?>
<workbook><worksheets>
  <worksheet name='Filtered'>
    <view>
      <datasources><datasource name='ds1'/></datasources>
      <rows>[amount]</rows>
      <columns>[region]</columns>
      <filter class='categorical' column='[region]'>
        <groupfilter function='member' level='[region]' member='&quot;West&quot;'/>
        <groupfilter function='member' level='[region]' member='&quot;East&quot;'/>
      </filter>
      <pane><mark class='Bar'/></pane>
    </view>
  </worksheet>
</worksheets></workbook>
"""

_XML_QUICK_TABLE_CALC = b"""<?xml version='1.0'?>
<workbook><worksheets>
  <worksheet name='Running Sum'>
    <view>
      <datasources><datasource name='ds1'/></datasources>
      <rows>[amount]</rows>
      <columns>[month]</columns>
      <table>
        <rows>
          <datasource-dependencies datasource='ds1'>
            <column datatype='integer' name='[amount]' role='measure' type='quantitative'/>
          </datasource-dependencies>
        </rows>
      </table>
      <pane><mark class='Line'/></pane>
      <table-calculations>
        <table-calculation column='[amount]' type='running_sum'/>
      </table-calculations>
    </view>
  </worksheet>
</worksheets></workbook>
"""


def test_basic_worksheet_extract():
    root = parse_workbook_xml(_XML_BASIC)
    ws = extract_worksheets(root)
    assert len(ws) == 1
    w = ws[0]
    assert w["name"] == "Revenue"
    assert w["datasource_refs"] == ("sample.csv",)
    assert w["mark_type"] == "Bar"
    assert w["encodings"]["rows"] == ("amount",)
    assert w["encodings"]["columns"] == ("month",)
    assert w["encodings"]["color"] == "region"
    assert w["filters"] == []
    assert w["quick_table_calcs"] == []


def test_filter_categorical():
    root = parse_workbook_xml(_XML_WITH_FILTER)
    w = extract_worksheets(root)[0]
    assert len(w["filters"]) == 1
    f = w["filters"][0]
    assert f["kind"] == "categorical"
    assert f["column"] == "region"
    assert f["include"] == ('"West"', '"East"')


def test_quick_table_calc_detection():
    root = parse_workbook_xml(_XML_QUICK_TABLE_CALC)
    w = extract_worksheets(root)[0]
    assert len(w["quick_table_calcs"]) == 1
    qtc = w["quick_table_calcs"][0]
    assert qtc["column"] == "amount"
    assert qtc["type"] == "running_sum"


def test_no_worksheets_returns_empty():
    root = parse_workbook_xml(b"<workbook><worksheets/></workbook>")
    assert extract_worksheets(root) == []
