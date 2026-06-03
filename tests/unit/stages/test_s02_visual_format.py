from tableau2pbir.stages._build_sheets import _build_visual_format
from tableau2pbir.ir.sheet import VisualFormat, TitleFormat, AxisTitleFormat, TableFormat


def test_none_raw_returns_none():
    assert _build_visual_format(None) is None


def test_mark_color_and_labels_show():
    vf = _build_visual_format({"mark_color": "#f28e2b", "labels_show": True,
                                "title": None, "axis_font_name": None, "axis_font_size": None,
                                "cell_font_name": None, "cell_font_size": None,
                                "header_font_name": None, "header_font_size": None,
                                "number_formats": {}})
    assert isinstance(vf, VisualFormat)
    assert vf.mark_color == "#f28e2b"
    assert vf.labels_show is True
    assert vf.title is None
    assert vf.axis is None


def test_title_fields_populated():
    raw = {
        "mark_color": None, "labels_show": False,
        "axis_font_name": None, "axis_font_size": None,
        "cell_font_name": None, "cell_font_size": None,
        "header_font_name": None, "header_font_size": None,
        "number_formats": {},
        "title": {
            "text": "Category Based  Profit",
            "font_name": "Verdana",
            "font_size": 20,
            "bold": True,
            "italic": True,
            "underline": False,
            "font_color": None,
        },
    }
    vf = _build_visual_format(raw)
    assert isinstance(vf.title, TitleFormat)
    assert vf.title.text == "Category Based  Profit"
    assert vf.title.font_name == "Verdana"
    assert vf.title.font_size == 20
    assert vf.title.bold is True


def test_axis_format_populated():
    raw = {
        "mark_color": None, "labels_show": False, "title": None,
        "axis_font_name": "Verdana", "axis_font_size": 16,
        "cell_font_name": None, "cell_font_size": None,
        "header_font_name": None, "header_font_size": None,
        "number_formats": {},
    }
    vf = _build_visual_format(raw)
    assert isinstance(vf.axis, AxisTitleFormat)
    assert vf.axis.font_name == "Verdana"
    assert vf.axis.font_size == 16


def test_number_formats_translated_to_stable_id():
    raw = {
        "mark_color": None, "labels_show": False, "title": None,
        "axis_font_name": None, "axis_font_size": None,
        "cell_font_name": None, "cell_font_size": None,
        "header_font_name": None, "header_font_size": None,
        "number_formats": {"sum:profit:qk": "C1033%"},
    }
    vf = _build_visual_format(raw)
    # stable_id("", "sum:profit:qk") → "sum_profit_qk"
    assert "sum_profit_qk" in vf.number_formats
    assert vf.number_formats["sum_profit_qk"] == r"\$#,0.00;(\$#,0.00);\$#,0.00"


def test_unknown_format_code_returns_none():
    """Unknown format codes translate to empty number_formats dict, so return None."""
    raw = {
        "mark_color": None, "labels_show": False, "title": None,
        "axis_font_name": None, "axis_font_size": None,
        "cell_font_name": None, "cell_font_size": None,
        "header_font_name": None, "header_font_size": None,
        "number_formats": {"some:field:qk": "UNKNOWN"},
    }
    vf = _build_visual_format(raw)
    assert vf is None


def test_all_defaults_returns_none():
    raw = {
        "mark_color": None, "labels_show": False, "title": None,
        "axis_font_name": None, "axis_font_size": None,
        "cell_font_name": None, "cell_font_size": None,
        "header_font_name": None, "header_font_size": None,
        "number_formats": {},
    }
    assert _build_visual_format(raw) is None
