from __future__ import annotations

from tableau2pbir.extract.parameters import extract_parameters
from tableau2pbir.util.xml import parse_workbook_xml


_XML_RANGE = b"""<?xml version='1.0'?>
<workbook><datasources>
  <datasource name='Parameters' hasconnection='false'>
    <column caption='Discount' datatype='real' name='[Parameter 1]'
            param-domain-type='range' role='measure' type='quantitative' value='0.1'>
      <calculation class='tableau' formula='0.1'/>
      <range granularity='0.05' max='0.5' min='0.0'/>
    </column>
  </datasource>
</datasources></workbook>
"""

_XML_LIST = b"""<?xml version='1.0'?>
<workbook><datasources>
  <datasource name='Parameters' hasconnection='false'>
    <column caption='Region' datatype='string' name='[Parameter 2]'
            param-domain-type='list' role='dimension' type='nominal' value='&quot;West&quot;'>
      <calculation class='tableau' formula='&quot;West&quot;'/>
      <members>
        <member value='&quot;West&quot;'/>
        <member value='&quot;East&quot;'/>
        <member value='&quot;North&quot;'/>
      </members>
    </column>
  </datasource>
</datasources></workbook>
"""

_XML_ANY = b"""<?xml version='1.0'?>
<workbook><datasources>
  <datasource name='Parameters'>
    <column caption='AxisMax' datatype='integer' name='[Parameter 3]'
            param-domain-type='any' role='measure' value='100'>
      <calculation class='tableau' formula='100'/>
    </column>
  </datasource>
</datasources></workbook>
"""


def test_range_parameter():
    root = parse_workbook_xml(_XML_RANGE)
    params = extract_parameters(root)
    assert len(params) == 1
    p = params[0]
    assert p["caption"] == "Discount"
    assert p["datatype"] == "real"
    assert p["domain_type"] == "range"
    assert p["default"] == "0.1"
    assert p["range"] == {"min": "0.0", "max": "0.5", "granularity": "0.05"}
    assert p["allowed_values"] == ()


def test_list_parameter():
    root = parse_workbook_xml(_XML_LIST)
    p = extract_parameters(root)[0]
    assert p["domain_type"] == "list"
    assert p["allowed_values"] == ('"West"', '"East"', '"North"')
    assert p["range"] is None


def test_any_parameter_has_no_allowed_values():
    root = parse_workbook_xml(_XML_ANY)
    p = extract_parameters(root)[0]
    assert p["domain_type"] == "any"
    assert p["allowed_values"] == ()
    assert p["range"] is None


def test_no_parameters_datasource_returns_empty():
    root = parse_workbook_xml(b"<workbook><datasources/></workbook>")
    assert extract_parameters(root) == []
