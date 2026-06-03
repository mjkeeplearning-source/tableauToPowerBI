from tableau2pbir.visualmap.format_map import build_format_objects
from tableau2pbir.ir.sheet import (
    AxisTitleFormat, TableFormat, TitleFormat, VisualFormat,
)


def _lit(v):
    return {"expr": {"Literal": {"Value": v}}}


def test_none_returns_empty_dicts():
    objects, container = build_format_objects(None, "columnChart")
    assert objects == {}
    assert container == {}


def test_mark_color_emitted_in_objects():
    vf = VisualFormat(mark_color="#f28e2b")
    objects, _ = build_format_objects(vf, "columnChart")
    assert "dataPoint" in objects
    color = objects["dataPoint"][0]["properties"]["fill"]["solid"]["color"]
    assert color == _lit("'#f28e2b'")


def test_labels_show_emitted():
    vf = VisualFormat(labels_show=True)
    objects, _ = build_format_objects(vf, "columnChart")
    assert objects["labels"][0]["properties"]["show"] == _lit("true")


def test_axis_font_emitted_for_column_chart():
    vf = VisualFormat(axis=AxisTitleFormat(font_name="Verdana", font_size=16))
    objects, _ = build_format_objects(vf, "columnChart")
    assert objects["categoryAxis"][0]["properties"]["titleFontFamily"] == _lit("'Verdana'")
    assert objects["categoryAxis"][0]["properties"]["titleFontSize"] == _lit("16D")
    assert objects["valueAxis"][0]["properties"]["titleFontFamily"] == _lit("'Verdana'")


def test_axis_font_not_emitted_for_table():
    vf = VisualFormat(axis=AxisTitleFormat(font_name="Verdana", font_size=16))
    objects, _ = build_format_objects(vf, "tableEx")
    assert "categoryAxis" not in objects
    assert "valueAxis" not in objects


def test_table_fonts_emitted_for_tableex():
    vf = VisualFormat(table=TableFormat(
        cell_font_name="Verdana",
        header_font_name="Arial Black",
        header_font_size=13,
    ))
    objects, _ = build_format_objects(vf, "tableEx")
    assert objects["values"][0]["properties"]["fontFamily"] == _lit("'Verdana'")
    # Arial Black has a space — must use triple-quote form
    assert objects["columnHeaders"][0]["properties"]["fontFamily"] == _lit("'''Arial Black'''")
    assert objects["columnHeaders"][0]["properties"]["fontSize"] == _lit("13D")


def test_table_fonts_not_emitted_for_chart():
    vf = VisualFormat(table=TableFormat(cell_font_name="Verdana"))
    objects, _ = build_format_objects(vf, "columnChart")
    assert "values" not in objects


def test_title_text_and_font_in_container():
    vf = VisualFormat(title=TitleFormat(
        text="Category Based  Profit",
        font_name="Verdana",
        font_size=20,
        bold=True,
        italic=True,
    ))
    _, container = build_format_objects(vf, "tableEx")
    title_props = container["title"][0]["properties"]
    assert title_props["show"] == _lit("true")
    assert title_props["text"] == _lit("'Category Based  Profit'")
    assert title_props["fontFamily"] == _lit("'Verdana'")
    assert title_props["fontSize"] == _lit("20D")
    assert title_props["bold"] == _lit("true")
    assert title_props["italic"] == _lit("true")
    assert "underline" not in title_props   # underline=False → not emitted


def test_title_underline_emitted_when_true():
    vf = VisualFormat(title=TitleFormat(text="T", underline=True))
    _, container = build_format_objects(vf, "columnChart")
    assert container["title"][0]["properties"]["underline"] == _lit("true")


def test_title_font_color_emitted():
    vf = VisualFormat(title=TitleFormat(text="T", font_color="#e15759"))
    _, container = build_format_objects(vf, "tableEx")
    color = container["title"][0]["properties"]["fontColor"]
    assert color == {"solid": {"color": _lit("'#e15759'")}}


def test_font_name_with_spaces_triple_quoted():
    vf = VisualFormat(title=TitleFormat(text="T", font_name="Arial Black"))
    _, container = build_format_objects(vf, "columnChart")
    assert container["title"][0]["properties"]["fontFamily"] == _lit("'''Arial Black'''")


def test_empty_title_text_still_emits_font_properties():
    """text="" suppresses show/text but font properties are still emitted."""
    vf = VisualFormat(title=TitleFormat(text="", font_name="Verdana", bold=True))
    _, container = build_format_objects(vf, "columnChart")
    title_props = container["title"][0]["properties"]
    assert "show" not in title_props
    assert "text" not in title_props
    assert title_props["fontFamily"]["expr"]["Literal"]["Value"] == "'Verdana'"
    assert title_props["bold"]["expr"]["Literal"]["Value"] == "true"
