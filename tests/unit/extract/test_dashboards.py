from __future__ import annotations

from tableau2pbir.extract.dashboards import extract_dashboards
from tableau2pbir.util.xml import parse_workbook_xml


_XML_TILED = b"""<?xml version='1.0'?>
<workbook><dashboards>
  <dashboard name='Main'>
    <size maxheight='800' maxwidth='1200' minheight='800' minwidth='1200'/>
    <zones>
      <zone name='Revenue' type='worksheet' id='1' h='800' w='1200' x='0' y='0'/>
    </zones>
  </dashboard>
</dashboards></workbook>
"""

_XML_FLOATING = b"""<?xml version='1.0'?>
<workbook><dashboards>
  <dashboard name='Float'>
    <size maxheight='600' maxwidth='800' minheight='600' minwidth='800'/>
    <zones>
      <zone name='bg' type='worksheet' id='1' h='600' w='800' x='0' y='0'/>
      <zone name='Overlay' type='worksheet' id='2' h='200' w='300' x='100' y='100' floating='true'/>
    </zones>
  </dashboard>
</dashboards></workbook>
"""

_XML_LEAF_TYPES = b"""<?xml version='1.0'?>
<workbook><dashboards>
  <dashboard name='Kitchen Sink'>
    <size maxheight='768' maxwidth='1366' minheight='768' minwidth='1366'/>
    <zones>
      <zone type='text' id='1' h='50' w='1366' x='0' y='0' param='Header'/>
      <zone type='filter' id='2' h='50' w='300' x='0' y='50' param='[region]'/>
      <zone type='parameter' id='3' h='50' w='300' x='300' y='50' param='[Parameter 1]'/>
      <zone type='legend' id='4' h='50' w='300' x='600' y='50' param='Revenue'/>
      <zone type='bitmap' id='5' h='200' w='300' x='0' y='100'/>
      <zone type='blank' id='6' h='200' w='300' x='300' y='100'/>
      <zone type='webpage' id='7' h='200' w='300' x='600' y='100'/>
    </zones>
  </dashboard>
</dashboards></workbook>
"""


def test_tiled_dashboard_single_worksheet():
    root = parse_workbook_xml(_XML_TILED)
    dbs = extract_dashboards(root)
    assert len(dbs) == 1
    d = dbs[0]
    assert d["name"] == "Main"
    assert d["size"] == {"w": 1200, "h": 800, "kind": "exact"}
    assert len(d["leaves"]) == 1
    leaf = d["leaves"][0]
    assert leaf["leaf_kind"] == "sheet"
    assert leaf["payload"]["sheet_name"] == "Revenue"
    assert leaf["position"] == {"x": 0, "y": 0, "w": 1200, "h": 800}
    assert leaf["floating"] is False


def test_floating_zones_flagged():
    root = parse_workbook_xml(_XML_FLOATING)
    d = extract_dashboards(root)[0]
    assert len(d["leaves"]) == 2
    floating = [lf for lf in d["leaves"] if lf["floating"]]
    assert len(floating) == 1
    assert floating[0]["payload"]["sheet_name"] == "Overlay"


def test_leaf_kind_mapping():
    root = parse_workbook_xml(_XML_LEAF_TYPES)
    d = extract_dashboards(root)[0]
    kinds = [lf["leaf_kind"] for lf in d["leaves"]]
    assert kinds == ["text", "filter_card", "parameter_card", "legend",
                     "image", "blank", "web_page"]


def test_no_dashboards_returns_empty():
    root = parse_workbook_xml(b"<workbook><dashboards/></workbook>")
    assert extract_dashboards(root) == []
