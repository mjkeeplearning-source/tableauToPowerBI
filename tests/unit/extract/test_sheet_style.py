from lxml import etree
from tableau2pbir.extract.worksheets import _sheet_style


def _ws(xml: str) -> tuple:
    """Parse a minimal worksheet XML and return (ws_elem, table_elem, pane_parent)."""
    root = etree.fromstring(xml.encode())
    table = root.find("table")
    return root, table, table if table is not None else root


def test_title_text_and_font_extracted():
    ws, table, pp = _ws("""
    <worksheet name="Sheet 4">
      <layout-options>
        <title>
          <formatted-text>
            <run bold='true' fontname='Verdana' fontsize='20' italic='true'>Category Based  Profit</run>
          </formatted-text>
        </title>
      </layout-options>
      <table><panes><pane><style></style></pane></panes></table>
    </worksheet>
    """)
    result = _sheet_style(ws, table, pp)
    t = result["title"]
    assert t["text"] == "Category Based  Profit"
    assert t["font_name"] == "Verdana"
    assert t["font_size"] == 20
    assert t["bold"] is True
    assert t["italic"] is True
    assert t["underline"] is False
    assert t["font_color"] is None


def test_title_font_color_extracted():
    ws, table, pp = _ws("""
    <worksheet name="Sheet 3">
      <layout-options>
        <title>
          <formatted-text>
            <run fontcolor='#e15759'>Category Details</run>
          </formatted-text>
        </title>
      </layout-options>
      <table><panes><pane><style></style></pane></panes></table>
    </worksheet>
    """)
    result = _sheet_style(ws, table, pp)
    assert result["title"]["font_color"] == "#e15759"


def test_field_labels_font_extracted():
    ws, table, pp = _ws("""
    <worksheet name="S">
      <table>
        <style>
          <style-rule element='field-labels'>
            <format attr='font-family' value='Verdana' />
            <format attr='font-size' value='16' />
          </style-rule>
        </style>
        <panes><pane><style></style></pane></panes>
      </table>
    </worksheet>
    """)
    result = _sheet_style(ws, table, pp)
    assert result["axis_font_name"] == "Verdana"
    assert result["axis_font_size"] == 16


def test_cell_global_font_extracted():
    ws, table, pp = _ws("""
    <worksheet name="S">
      <table>
        <style>
          <style-rule element='cell'>
            <format attr='font-family' value='Verdana' />
            <format attr='font-size' value='9' />
          </style-rule>
        </style>
        <panes><pane><style></style></pane></panes>
      </table>
    </worksheet>
    """)
    result = _sheet_style(ws, table, pp)
    assert result["cell_font_name"] == "Verdana"
    assert result["cell_font_size"] == 9


def test_cell_text_format_field_scoped():
    ws, table, pp = _ws("""
    <worksheet name="S">
      <table>
        <style>
          <style-rule element='cell' field='sum:profit:qk'>
            <format attr='text-format' value='C1033%' />
          </style-rule>
        </style>
        <panes><pane><style></style></pane></panes>
      </table>
    </worksheet>
    """)
    result = _sheet_style(ws, table, pp)
    assert result["number_formats"] == {"sum:profit:qk": "C1033%"}


def test_header_font_extracted():
    ws, table, pp = _ws("""
    <worksheet name="S">
      <table>
        <style>
          <style-rule element='header'>
            <format attr='font-family' value='Arial Black' />
            <format attr='font-size' value='13' />
          </style-rule>
        </style>
        <panes><pane><style></style></pane></panes>
      </table>
    </worksheet>
    """)
    result = _sheet_style(ws, table, pp)
    assert result["header_font_name"] == "Arial Black"
    assert result["header_font_size"] == 13


def test_pane_mark_color_extracted():
    ws, table, pp = _ws("""
    <worksheet name="S">
      <table>
        <panes>
          <pane>
            <style>
              <style-rule element='mark'>
                <format attr='mark-color' value='#f28e2b' />
                <format attr='mark-labels-show' value='true' />
              </style-rule>
            </style>
          </pane>
        </panes>
      </table>
    </worksheet>
    """)
    result = _sheet_style(ws, table, pp)
    assert result["mark_color"] == "#f28e2b"
    assert result["labels_show"] is True


def test_no_style_returns_empty_defaults():
    ws, table, pp = _ws("""
    <worksheet name="S">
      <table><panes><pane><style></style></pane></panes></table>
    </worksheet>
    """)
    result = _sheet_style(ws, table, pp)
    assert result["title"] is None
    assert result["mark_color"] is None
    assert result["labels_show"] is False
    assert result["axis_font_name"] is None
    assert result["number_formats"] == {}
