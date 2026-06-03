from tableau2pbir.ir.sheet import TitleFormat, AxisTitleFormat, TableFormat, VisualFormat

def test_title_format_defaults():
    t = TitleFormat()
    assert t.text is None
    assert t.bold is False
    assert t.italic is False
    assert t.underline is False
    assert t.font_color is None

def test_title_format_full():
    t = TitleFormat(
        text="Category Based Profit",
        font_name="Verdana",
        font_size=20,
        bold=True,
        italic=True,
        underline=False,
        font_color="#e15759",
    )
    assert t.text == "Category Based Profit"
    assert t.font_name == "Verdana"
    assert t.font_size == 20
    assert t.bold is True
    assert t.italic is True

def test_visual_format_defaults():
    vf = VisualFormat()
    assert vf.title is None
    assert vf.mark_color is None
    assert vf.labels_show is False
    assert vf.axis is None
    assert vf.table is None
    assert vf.number_formats == {}

def test_visual_format_with_all_fields():
    vf = VisualFormat(
        title=TitleFormat(text="My Chart", font_name="Arial", font_size=14),
        mark_color="#f28e2b",
        labels_show=True,
        axis=AxisTitleFormat(font_name="Verdana", font_size=16),
        table=TableFormat(cell_font_name="Verdana", header_font_name="Arial Black"),
        number_formats={"usr_calc_01_qk": r"\$#,0.00;(\$#,0.00);\$#,0.00"},
    )
    assert vf.title.text == "My Chart"
    assert vf.axis.font_size == 16
    assert vf.table.header_font_name == "Arial Black"
    assert "usr_calc_01_qk" in vf.number_formats
