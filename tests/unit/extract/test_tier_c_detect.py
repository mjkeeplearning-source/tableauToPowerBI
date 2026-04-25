from __future__ import annotations

from tableau2pbir.extract.tier_c_detect import detect_tier_c
from tableau2pbir.util.xml import parse_workbook_xml


def test_story_points_detected():
    xml = b"<workbook><stories><story name='Tour'/></stories></workbook>"
    items = detect_tier_c(parse_workbook_xml(xml))
    assert any(i["code"] == "unsupported_story_points" for i in items)


def test_r_script_calculation_detected():
    xml = b"""<workbook><datasources><datasource name='ds'>
      <column name='[r_calc]'>
        <calculation class='tableau' formula='SCRIPT_REAL(&quot;mean(.arg1)&quot;, SUM([Sales]))'/>
      </column>
    </datasource></datasources></workbook>"""
    items = detect_tier_c(parse_workbook_xml(xml))
    codes = [i["code"] for i in items]
    assert "unsupported_r_python_script" in codes


def test_polygon_mark_detected():
    xml = b"""<workbook><worksheets><worksheet name='w1'>
      <view><pane><mark class='Polygon'/></pane></view>
    </worksheet></worksheets></workbook>"""
    items = detect_tier_c(parse_workbook_xml(xml))
    assert any(i["code"] == "unsupported_mark_polygon" for i in items)


def test_annotation_detected():
    xml = b"""<workbook><worksheets><worksheet name='w1'>
      <view><pane><mark class='Bar'/></pane></view>
      <annotations>
        <annotation type='mark' text='Outlier'/>
      </annotations>
    </worksheet></worksheets></workbook>"""
    items = detect_tier_c(parse_workbook_xml(xml))
    assert any(i["code"] == "unsupported_annotation" for i in items)


def test_empty_workbook_produces_no_items():
    items = detect_tier_c(parse_workbook_xml(b"<workbook/>"))
    assert items == []
