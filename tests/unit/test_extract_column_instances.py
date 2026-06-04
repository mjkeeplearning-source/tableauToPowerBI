"""Unit tests for _column_instances() in extract/worksheets.py."""
from __future__ import annotations

import pathlib

import pytest
from lxml import etree

from tableau2pbir.extract.worksheets import _column_instances, extract_worksheets


def _view(xml_body: str) -> etree._Element:
    return etree.fromstring(f"<view>{xml_body}</view>")


# ── _column_instances ──────────────────────────────────────────────────────────

def test_extracts_year_derivation():
    view = _view("""
      <datasource-dependencies datasource="federated.abc">
        <column-instance column="[order_date]" derivation="Year"
                         name="[yr:order_date:ok]" pivot="key" type="ordinal" />
      </datasource-dependencies>
    """)
    result = _column_instances(view)
    assert len(result) == 1
    assert result[0]["slug"] == "yr:order_date:ok"
    assert result[0]["base_column"] == "order_date"
    assert result[0]["derivation"] == "Year"


def test_skips_sum_derivation():
    view = _view("""
      <datasource-dependencies datasource="federated.abc">
        <column-instance column="[sales]" derivation="Sum" name="[sum:sales:qk]" />
      </datasource-dependencies>
    """)
    assert _column_instances(view) == []


def test_skips_none_derivation():
    view = _view("""
      <datasource-dependencies datasource="federated.abc">
        <column-instance column="[region]" derivation="None" name="[none:region:nk]" />
      </datasource-dependencies>
    """)
    assert _column_instances(view) == []


def test_extracts_all_eight_date_derivations():
    view = _view("""
      <datasource-dependencies datasource="federated.abc">
        <column-instance column="[dt]" derivation="Quarter" name="[qr:dt:ok]" />
        <column-instance column="[dt]" derivation="Month"   name="[mn:dt:ok]" />
        <column-instance column="[dt]" derivation="Week"    name="[wk:dt:ok]" />
        <column-instance column="[dt]" derivation="Day"     name="[dy:dt:ok]" />
        <column-instance column="[dt]" derivation="Hour"    name="[hr:dt:ok]" />
        <column-instance column="[dt]" derivation="Minute"  name="[mi:dt:ok]" />
        <column-instance column="[dt]" derivation="Second"  name="[sc:dt:ok]" />
      </datasource-dependencies>
    """)
    result = _column_instances(view)
    assert len(result) == 7
    assert {r["derivation"] for r in result} == {
        "Quarter", "Month", "Week", "Day", "Hour", "Minute", "Second"
    }


def test_ignores_count_and_attribute_derivations():
    view = _view("""
      <datasource-dependencies datasource="federated.abc">
        <column-instance column="[x]" derivation="Count"     name="[cnt:x:qk]" />
        <column-instance column="[x]" derivation="CountD"    name="[ctd:x:qk]" />
        <column-instance column="[x]" derivation="Attribute" name="[attr:x:nk]" />
      </datasource-dependencies>
    """)
    assert _column_instances(view) == []


# ── extract_worksheets integration ────────────────────────────────────────────

def test_extract_worksheets_includes_column_instances_key():
    """Smoke test: every worksheet dict has a column_instances key."""
    _REAL = pathlib.Path(__file__).resolve().parents[2] / "tests" / "golden" / "real"
    twb = _REAL / "simple_join_calculated_line.twb"
    if not twb.exists():
        pytest.skip("simple_join_calculated_line.twb not present")
    from lxml import etree as ET
    root = ET.parse(str(twb)).getroot()
    worksheets = extract_worksheets(root)
    for ws in worksheets:
        assert "column_instances" in ws, f"column_instances missing for {ws['name']}"


def test_extract_worksheets_sheet2_has_year_order_date():
    _REAL = pathlib.Path(__file__).resolve().parents[2] / "tests" / "golden" / "real"
    twb = _REAL / "simple_join_calculated_line.twb"
    if not twb.exists():
        pytest.skip("simple_join_calculated_line.twb not present")
    from lxml import etree as ET
    root = ET.parse(str(twb)).getroot()
    worksheets = extract_worksheets(root)
    sheet2 = next(ws for ws in worksheets if ws["name"] == "Sheet 2")
    ci_list = sheet2["column_instances"]
    assert len(ci_list) == 1
    assert ci_list[0]["slug"] == "yr:order_date:ok"
    assert ci_list[0]["base_column"] == "order_date"
    assert ci_list[0]["derivation"] == "Year"
