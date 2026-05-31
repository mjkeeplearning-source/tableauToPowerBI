from __future__ import annotations

from tableau2pbir.extract.worksheets import extract_worksheets
from tableau2pbir.util.xml import parse_workbook_xml


# Synthetic fixtures mirror real Tableau structure:
# <worksheet>/<table>/<view> with <rows>/<cols>/<panes> as siblings of <view>.

_XML_BASIC = b"""<?xml version='1.0'?>
<workbook><worksheets>
  <worksheet name='Revenue'>
    <table>
      <view>
        <datasources>
          <datasource name='sample.csv'/>
        </datasources>
      </view>
      <panes>
        <pane>
          <mark class='Bar'/>
          <encodings>
            <color column='[region]'/>
          </encodings>
        </pane>
      </panes>
      <rows>[amount]</rows>
      <cols>[month]</cols>
    </table>
  </worksheet>
</worksheets></workbook>
"""

_XML_WITH_FILTER = b"""<?xml version='1.0'?>
<workbook><worksheets>
  <worksheet name='Filtered'>
    <table>
      <view>
        <datasources><datasource name='ds1'/></datasources>
        <filter class='categorical' column='[region]'>
          <groupfilter function='member' level='[region]' member='&quot;West&quot;'/>
          <groupfilter function='member' level='[region]' member='&quot;East&quot;'/>
        </filter>
      </view>
      <panes>
        <pane><mark class='Bar'/></pane>
      </panes>
      <rows>[amount]</rows>
      <cols>[region]</cols>
    </table>
  </worksheet>
</worksheets></workbook>
"""

_XML_QUICK_TABLE_CALC = b"""<?xml version='1.0'?>
<workbook><worksheets>
  <worksheet name='Running Sum'>
    <table>
      <view>
        <datasources><datasource name='ds1'/></datasources>
        <table-calculations>
          <table-calculation column='[amount]' type='running_sum'/>
        </table-calculations>
      </view>
      <panes>
        <pane><mark class='Line'/></pane>
      </panes>
      <rows>[amount]</rows>
      <cols>[month]</cols>
    </table>
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
    assert w["mark_type"] == "bar"
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


_XML_WITH_MARK_STYLE = b"""<?xml version='1.0'?>
<workbook><worksheets>
  <worksheet name='Sales'>
    <table>
      <view>
        <datasources><datasource name='ds1'/></datasources>
      </view>
      <panes>
        <pane>
          <mark class='Bar'/>
          <style>
            <style-rule element='mark'>
              <format attr='mark-color' value='#ffaa7f'/>
              <format attr='mark-labels-show' value='true'/>
              <format attr='mark-labels-cull' value='true'/>
            </style-rule>
          </style>
        </pane>
      </panes>
      <rows>[amount]</rows>
      <cols>[month]</cols>
    </table>
  </worksheet>
</worksheets></workbook>
"""

_XML_NO_MARK_STYLE = b"""<?xml version='1.0'?>
<workbook><worksheets>
  <worksheet name='Sales'>
    <table>
      <view>
        <datasources><datasource name='ds1'/></datasources>
      </view>
      <panes>
        <pane><mark class='Bar'/></pane>
      </panes>
      <rows>[amount]</rows>
      <cols>[month]</cols>
    </table>
  </worksheet>
</worksheets></workbook>
"""


def test_mark_style_extracted_when_present():
    root = parse_workbook_xml(_XML_WITH_MARK_STYLE)
    ws = extract_worksheets(root)
    ms = ws[0]["mark_style"]
    assert ms["mark_color"] == "#ffaa7f"
    assert ms["labels_show"] is True


def test_mark_style_defaults_when_absent():
    root = parse_workbook_xml(_XML_NO_MARK_STYLE)
    ws = extract_worksheets(root)
    ms = ws[0]["mark_style"]
    assert ms["mark_color"] is None
    assert ms["labels_show"] is False


def test_mark_style_labels_cull_not_propagated():
    """mark-labels-cull has no PBI equivalent — it must not appear in mark_style output."""
    root = parse_workbook_xml(_XML_WITH_MARK_STYLE)
    ws = extract_worksheets(root)
    ms = ws[0]["mark_style"]
    assert "labels_cull" not in ms
