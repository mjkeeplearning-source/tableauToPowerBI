import json

from tableau2pbir.emit.pbir.report import render_report


def test_report_json_minimal():
    out = render_report(report_name="Wb", page_order=["pageA", "pageB"])
    obj = json.loads(out)
    assert obj["$schema"].startswith("https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/")
    assert obj["pages"]["pageOrder"] == ["pageA", "pageB"]
    assert obj["pages"]["activePageName"] == "pageA"
