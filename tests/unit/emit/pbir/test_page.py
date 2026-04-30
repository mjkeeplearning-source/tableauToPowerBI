import json

from tableau2pbir.emit.pbir.page import render_page


def test_page_json_basic():
    out = render_page(page_id="p1", display_name="Revenue", ordinal=0, width=1280, height=720)
    obj = json.loads(out)
    assert obj["name"] == "p1"
    assert obj["displayName"] == "Revenue"
    assert obj["ordinal"] == 0
    assert obj["width"] == 1280
    assert obj["height"] == 720
