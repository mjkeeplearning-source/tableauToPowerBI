"""Render Report/definition/report.json."""
from __future__ import annotations

import json


def render_report(report_name: str, page_order: list[str]) -> str:
    obj = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/2.0.0/schema.json",
        "themeCollection": {"baseTheme": {"name": "CY24SU10"}},
        "pages": {
            "pageOrder": list(page_order),
            "activePageName": page_order[0] if page_order else "",
        },
    }
    return json.dumps(obj, indent=2)
