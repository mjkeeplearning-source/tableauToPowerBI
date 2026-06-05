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
    assert f["include"] == ("West", "East")


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


def test_sheet_style_extracted_when_present():
    root = parse_workbook_xml(_XML_WITH_MARK_STYLE)
    ws = extract_worksheets(root)
    ms = ws[0]["sheet_style"]
    assert ms["mark_color"] == "#ffaa7f"
    assert ms["labels_show"] is True


def test_sheet_style_defaults_when_absent():
    root = parse_workbook_xml(_XML_NO_MARK_STYLE)
    ws = extract_worksheets(root)
    ms = ws[0]["sheet_style"]
    assert ms["mark_color"] is None
    assert ms["labels_show"] is False


_XML_SHARED_VIEW_FILTER = b"""<?xml version='1.0' encoding='utf-8'?>
<workbook xmlns:user='http://www.tableausoftware.com/xml/user'>
  <shared-views>
    <shared-view name='ds1'>
      <filter class='categorical' column='[ds1].[none:region:nk]'>
        <groupfilter function='union' user:ui-enumeration='inclusive'>
          <groupfilter function='member' member='East'/>
          <groupfilter function='member' member='West'/>
        </groupfilter>
      </filter>
    </shared-view>
  </shared-views>
  <worksheets>
    <worksheet name='Sheet 1'>
      <table>
        <view>
          <datasources><datasource name='ds1'/></datasources>
          <slices>
            <column>[ds1].[none:region:nk]</column>
          </slices>
        </view>
        <panes><pane><mark class='Bar'/></pane></panes>
        <rows>[amount]</rows>
        <cols>[month]</cols>
      </table>
    </worksheet>
  </worksheets>
</workbook>"""


def test_shared_view_filter_applied_via_slices():
    """Worksheet with no inline filter but a slice pointing to a shared-view filter
    must include the shared filter in its extracted filter list."""
    root = parse_workbook_xml(_XML_SHARED_VIEW_FILTER)
    ws = extract_worksheets(root)
    assert len(ws) == 1
    filters = ws[0]["filters"]
    assert len(filters) == 1, f"Expected 1 filter from shared-view, got {len(filters)}"
    f = filters[0]
    assert f["kind"] == "categorical"
    assert f["column"] == "none:region:nk"
    assert "East" in f["include"]
    assert "West" in f["include"]


def test_shared_view_filter_not_duplicated_when_inline_filter_exists():
    """If a worksheet has both an inline filter and a slice for the same column,
    the filter must appear exactly once."""
    root = parse_workbook_xml(b"""<?xml version='1.0' encoding='utf-8'?>
<workbook xmlns:user='http://www.tableausoftware.com/xml/user'>
  <shared-views>
    <shared-view name='ds1'>
      <filter class='categorical' column='[ds1].[none:region:nk]'>
        <groupfilter function='union' user:ui-enumeration='inclusive'>
          <groupfilter function='member' member='East'/>
        </groupfilter>
      </filter>
    </shared-view>
  </shared-views>
  <worksheets>
    <worksheet name='Sheet 2'>
      <table>
        <view>
          <datasources><datasource name='ds1'/></datasources>
          <filter class='categorical' column='[ds1].[none:region:nk]'>
            <groupfilter function='union' user:ui-enumeration='inclusive'>
              <groupfilter function='member' member='East'/>
            </groupfilter>
          </filter>
          <slices>
            <column>[ds1].[none:region:nk]</column>
          </slices>
        </view>
        <panes><pane><mark class='Bar'/></pane></panes>
        <rows>[sales]</rows>
        <cols>[region]</cols>
      </table>
    </worksheet>
  </worksheets>
</workbook>""")
    ws = extract_worksheets(root)
    assert len(ws[0]["filters"]) == 1, "Inline + slice for same column → exactly one filter"


def test_sheet_style_labels_cull_not_propagated():
    """mark-labels-cull has no PBI equivalent — it must not appear in sheet_style output."""
    root = parse_workbook_xml(_XML_WITH_MARK_STYLE)
    ws = extract_worksheets(root)
    ms = ws[0]["sheet_style"]
    assert "labels_cull" not in ms


_XML_TEXT_ENCODING = b"""<?xml version='1.0'?>
<workbook><worksheets>
  <worksheet name='TextTable'>
    <table>
      <view>
        <datasources><datasource name='ds1'/></datasources>
      </view>
      <panes>
        <pane>
          <mark class='Text'/>
          <encodings>
            <text column='[profit]'/>
          </encodings>
        </pane>
      </panes>
      <rows>[category]</rows>
      <cols />
    </table>
  </worksheet>
</worksheets></workbook>
"""


def test_text_encoding_extracted():
    root = parse_workbook_xml(_XML_TEXT_ENCODING)
    ws = extract_worksheets(root)
    assert ws[0]["encodings"]["text"] == "profit"


_XML_COMPUTED_SORT = b"""<?xml version='1.0'?>
<workbook><worksheets>
  <worksheet name='SortedTable'>
    <table>
      <view>
        <datasources><datasource name='ds1'/></datasources>
        <computed-sort
            column='[federated.ds1].[none:category:nk]'
            direction='DESC'
            using='[federated.ds1].[sum:profit:qk]' />
      </view>
      <panes><pane><mark class='Text'/></pane></panes>
      <rows>[category]</rows>
      <cols />
    </table>
  </worksheet>
</worksheets></workbook>
"""


def test_computed_sort_extracted():
    root = parse_workbook_xml(_XML_COMPUTED_SORT)
    ws = extract_worksheets(root)
    sorts = ws[0]["sort"]
    assert len(sorts) == 1
    s = sorts[0]
    assert s["column"] == "none:category:nk"
    assert s["direction"] == "desc"
    assert s["sort_by"] == "sum:profit:qk"


_XML_TEXT_ENCODING_QUALIFIED = b"""<?xml version='1.0'?>
<workbook><worksheets>
  <worksheet name='QualifiedText'>
    <table>
      <view>
        <datasources><datasource name='federated.17kv7r10vp81pc1g60xgp0re1it8'/></datasources>
      </view>
      <panes>
        <pane>
          <mark class='Automatic'/>
          <encodings>
            <text column='[federated.17kv7r10vp81pc1g60xgp0re1it8].[sum:profit:qk]'/>
          </encodings>
        </pane>
      </panes>
      <rows>[federated.17kv7r10vp81pc1g60xgp0re1it8].[none:category:nk]</rows>
      <cols />
    </table>
  </worksheet>
</worksheets></workbook>
"""


def test_qualified_text_encoding_extracts_instance_only():
    """Real Tableau XML uses qualified refs for pane encodings.
    _encodings must strip the datasource prefix and return only the column-instance name."""
    root = parse_workbook_xml(_XML_TEXT_ENCODING_QUALIFIED)
    ws = extract_worksheets(root)
    assert ws[0]["encodings"]["text"] == "sum:profit:qk"


# ---------------------------------------------------------------------------
# Axis title extraction tests (Plan 20, Task 2)
# ---------------------------------------------------------------------------

_XML_SINGLE_AXIS_TITLE = b"""<?xml version='1.0'?>
<workbook><worksheets>
  <worksheet name='Sales Year'>
    <table>
      <view>
        <datasources><datasource name='ds1'/></datasources>
      </view>
      <style>
        <style-rule element='axis'>
          <format attr='title' class='0' field='[ds1].[sum:sales:qk]' scope='rows' value='#  Revenue' />
        </style-rule>
      </style>
      <panes>
        <pane><mark class='Line'/></pane>
      </panes>
      <rows>[ds1].[sum:sales:qk]</rows>
      <cols>[ds1].[yr:order_date:ok]</cols>
    </table>
  </worksheet>
</worksheets></workbook>
"""

_XML_MULTI_MEASURE_AXIS_TITLES = b"""<?xml version='1.0'?>
<workbook><worksheets>
  <worksheet name='Sales Profit'>
    <table>
      <view>
        <datasources><datasource name='ds1'/></datasources>
      </view>
      <style>
        <style-rule element='axis'>
          <format attr='title' class='0' field='[ds1].[sum:profit:qk]' scope='rows' value='#  Profit' />
          <format attr='title' class='0' field='[ds1].[sum:sales:qk]' scope='rows' value='#  Sales' />
        </style-rule>
      </style>
      <panes>
        <pane><mark class='Automatic'/></pane>
      </panes>
      <rows>([ds1].[sum:profit:qk]+[ds1].[sum:sales:qk])</rows>
      <cols>[ds1].[none:region:nk]</cols>
    </table>
  </worksheet>
</worksheets></workbook>
"""

_XML_AXIS_FONT_ONLY = b"""<?xml version='1.0'?>
<workbook><worksheets>
  <worksheet name='Styled'>
    <table>
      <view>
        <datasources><datasource name='ds1'/></datasources>
      </view>
      <style>
        <style-rule element='axis'>
          <format attr='font-family' scope='cols' value='Verdana' />
          <format attr='font-size' scope='cols' value='22' />
        </style-rule>
      </style>
      <panes>
        <pane><mark class='Bar'/></pane>
      </panes>
      <rows>[ds1].[sum:sales:qk]</rows>
      <cols>[ds1].[none:region:nk]</cols>
    </table>
  </worksheet>
</worksheets></workbook>
"""

_XML_NO_AXIS_RULE = b"""<?xml version='1.0'?>
<workbook><worksheets>
  <worksheet name='Plain'>
    <table>
      <view>
        <datasources><datasource name='ds1'/></datasources>
      </view>
      <panes>
        <pane><mark class='Bar'/></pane>
      </panes>
      <rows>[ds1].[sum:sales:qk]</rows>
      <cols>[ds1].[none:region:nk]</cols>
    </table>
  </worksheet>
</worksheets></workbook>
"""


def test_axis_title_extracted_single_measure():
    root = parse_workbook_xml(_XML_SINGLE_AXIS_TITLE)
    ws = extract_worksheets(root)
    titles = ws[0]["sheet_style"]["axis_titles"]
    assert len(titles) == 1
    assert titles[0]["field"] == "sum_sales_qk"   # slug_id("sum:sales:qk")
    assert titles[0]["scope"] == "rows"
    assert titles[0]["title"] == "#  Revenue"


def test_axis_title_extracted_multi_measure_order_preserved():
    root = parse_workbook_xml(_XML_MULTI_MEASURE_AXIS_TITLES)
    ws = extract_worksheets(root)
    titles = ws[0]["sheet_style"]["axis_titles"]
    assert len(titles) == 2
    assert titles[0]["field"] == "sum_profit_qk"
    assert titles[0]["title"] == "#  Profit"
    assert titles[1]["field"] == "sum_sales_qk"
    assert titles[1]["title"] == "#  Sales"


def test_axis_title_absent_for_font_only_rule():
    """font-family / font-size on scope='cols' must not appear in axis_titles."""
    root = parse_workbook_xml(_XML_AXIS_FONT_ONLY)
    ws = extract_worksheets(root)
    titles = ws[0]["sheet_style"].get("axis_titles", [])
    assert titles == []


def test_axis_title_absent_when_no_axis_rule():
    root = parse_workbook_xml(_XML_NO_AXIS_RULE)
    ws = extract_worksheets(root)
    titles = ws[0]["sheet_style"].get("axis_titles", [])
    assert titles == []
