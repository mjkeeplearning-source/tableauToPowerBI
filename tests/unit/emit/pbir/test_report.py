import json

from tableau2pbir.emit.pbir.report import render_pages_manifest, render_report


def test_report_json_schema_is_3_2_0():
    out = render_report()
    obj = json.loads(out)
    assert "/3.2.0/" in obj["$schema"], f"Expected schema 3.2.0, got: {obj['$schema']}"


def test_report_json_has_no_pages_key():
    """Schema 3.2.0 puts page order in pages/pages.json, not in report.json."""
    out = render_report()
    obj = json.loads(out)
    assert "pages" not in obj, "report.json must not embed page order — use pages.json instead"


def test_report_json_has_theme():
    out = render_report()
    obj = json.loads(out)
    assert obj["themeCollection"]["baseTheme"]["name"] == "CY26SU02"


def test_pages_manifest_page_order():
    out = render_pages_manifest(page_order=["pageA", "pageB"])
    obj = json.loads(out)
    assert obj["pageOrder"] == ["pageA", "pageB"]
    assert obj["activePageName"] == "pageA"


def test_pages_manifest_schema():
    out = render_pages_manifest(page_order=["p1"])
    obj = json.loads(out)
    assert "pagesMetadata/1.0.0" in obj["$schema"]


def test_pages_manifest_empty_list():
    out = render_pages_manifest(page_order=[])
    obj = json.loads(out)
    assert obj["pageOrder"] == []
    assert obj["activePageName"] == ""
