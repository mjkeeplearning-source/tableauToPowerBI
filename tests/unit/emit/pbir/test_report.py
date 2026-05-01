import json

from tableau2pbir.emit.pbir.report import render_report


def test_report_json_minimal():
    out = render_report(report_name="Wb", page_order=["pageA", "pageB"])
    obj = json.loads(out)
    assert obj["$schema"].startswith("https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/")
    assert obj["pages"]["pageOrder"] == ["pageA", "pageB"]
    assert obj["pages"]["activePageName"] == "pageA"


def test_report_json_schema_is_v1():
    """report.json must use the 1.0.0 schema — v2.0.0 is rejected by Desktop."""
    out = render_report(report_name="Wb", page_order=[])
    obj = json.loads(out)
    assert "/1.0.0/" in obj["$schema"], f"Expected v1.0.0 schema, got: {obj['$schema']}"
