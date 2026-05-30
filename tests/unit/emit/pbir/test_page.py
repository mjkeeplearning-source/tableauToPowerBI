import json

from tableau2pbir.emit.pbir.page import render_page


def test_page_json_basic():
    out = render_page(page_id="p1", display_name="Revenue", width=1280, height=720)
    obj = json.loads(out)
    assert obj["name"] == "p1"
    assert obj["displayName"] == "Revenue"
    assert obj["width"] == 1280
    assert obj["height"] == 720


def test_page_json_has_no_ordinal():
    # ordinal is not in page/2.1.0 schema; ordering is handled by pagesMetadata/pageOrder
    out = render_page(page_id="p1", display_name="Revenue", width=1280, height=720)
    obj = json.loads(out)
    assert "ordinal" not in obj, f"page.json must not contain 'ordinal', got: {list(obj.keys())}"


def test_page_json_schema_is_2_1_0():
    out = render_page(page_id="p1", display_name="Revenue", width=1280, height=720)
    obj = json.loads(out)
    assert "/2.1.0/" in obj["$schema"], f"Expected schema 2.1.0, got: {obj['$schema']}"


def test_page_json_no_filter_config_when_no_filters():
    out = render_page(page_id="p1", display_name="Revenue", width=1280, height=720)
    obj = json.loads(out)
    assert "filterConfig" not in obj, (
        f"filterConfig must be omitted when there are no filters, got keys: {list(obj.keys())}"
    )


def test_page_json_filter_config_present_when_filters_given():
    filters = [{"type": "Categorical"}]
    out = render_page(page_id="p1", display_name="Revenue", width=1280, height=720, filters=filters)
    obj = json.loads(out)
    assert "filterConfig" in obj
    assert obj["filterConfig"]["filters"] == filters
