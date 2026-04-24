from __future__ import annotations

from tableau2pbir.extract.datasources import extract_datasources
from tableau2pbir.util.xml import parse_workbook_xml


_XML_CSV = b"""<?xml version='1.0'?>
<workbook>
  <datasources>
    <datasource caption='Sample' name='sample.csv' hasconnection='true'>
      <connection class='textscan' directory='.' filename='sample.csv' server=''/>
      <column datatype='integer' name='[id]' role='dimension' type='ordinal'/>
      <column datatype='integer' name='[amount]' role='measure' type='quantitative'/>
    </datasource>
  </datasources>
</workbook>
"""

_XML_WITH_CALC = b"""<?xml version='1.0'?>
<workbook>
  <datasources>
    <datasource caption='Orders' name='orders'>
      <connection class='sqlserver' server='sql1' dbname='Sales'/>
      <column datatype='real' name='[Revenue]' role='measure'/>
      <column datatype='real' name='[Profit Margin]' role='measure'>
        <calculation class='tableau' formula='SUM([Profit])/SUM([Revenue])'/>
      </column>
    </datasource>
  </datasources>
</workbook>
"""

_XML_HYPER_WITH_UPSTREAM = b"""<?xml version='1.0'?>
<workbook>
  <datasources>
    <datasource name='extract_ds'>
      <connection class='federated'>
        <named-connections>
          <named-connection name='upstream' caption='sql1'>
            <connection class='sqlserver' server='sql1' dbname='Sales'/>
          </named-connection>
        </named-connections>
        <extract enabled='true'>
          <connection class='hyper' dbname='Extract/extract.hyper'/>
        </extract>
      </connection>
    </datasource>
  </datasources>
</workbook>
"""


def test_single_csv_datasource():
    root = parse_workbook_xml(_XML_CSV)
    dss = extract_datasources(root)
    assert len(dss) == 1
    ds = dss[0]
    assert ds["name"] == "sample.csv"
    assert ds["caption"] == "Sample"
    assert ds["connection"]["class"] == "textscan"
    assert ds["extract"] is None
    assert len(ds["columns"]) == 2
    assert ds["columns"][0]["name"] == "id"       # [] stripped
    assert ds["columns"][0]["datatype"] == "integer"
    assert ds["columns"][0]["role"] == "dimension"
    assert ds["calculations"] == []


def test_calculated_column_promoted_to_calculations():
    root = parse_workbook_xml(_XML_WITH_CALC)
    ds = extract_datasources(root)[0]
    assert len(ds["columns"]) == 2           # raw column list still includes the calc's host column
    assert len(ds["calculations"]) == 1
    calc = ds["calculations"][0]
    assert calc["host_column_name"] == "Profit Margin"
    assert calc["tableau_expr"] == "SUM([Profit])/SUM([Revenue])"
    assert calc["datatype"] == "real"
    assert calc["role"] == "measure"


def test_hyper_extract_preserves_upstream_connection():
    root = parse_workbook_xml(_XML_HYPER_WITH_UPSTREAM)
    ds = extract_datasources(root)[0]
    assert ds["connection"]["class"] == "federated"
    assert ds["extract"] is not None
    assert ds["extract"]["connection"]["class"] == "hyper"
    # upstream named-connection must be preserved for connector_tier §5.8
    assert len(ds["named_connections"]) == 1
    upstream = ds["named_connections"][0]
    assert upstream["connection"]["class"] == "sqlserver"
    assert upstream["connection"]["server"] == "sql1"


def test_empty_workbook_returns_empty_list():
    root = parse_workbook_xml(b"<workbook><datasources/></workbook>")
    assert extract_datasources(root) == []


def test_parameters_datasource_skipped_here():
    # The special <datasource name='Parameters'> is handled by extract/parameters.py.
    xml = b"""<workbook><datasources>
      <datasource name='Parameters' hasconnection='false'><column name='[p1]'/></datasource>
      <datasource name='real_ds'><connection class='textscan'/></datasource>
    </datasources></workbook>"""
    root = parse_workbook_xml(xml)
    dss = extract_datasources(root)
    assert [d["name"] for d in dss] == ["real_ds"]
