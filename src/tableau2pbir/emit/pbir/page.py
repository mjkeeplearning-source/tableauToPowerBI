"""Render pages/<page>/page.json."""
from __future__ import annotations

import json


def render_page(page_id: str, display_name: str, width: int, height: int,
                filters: list | None = None) -> str:
    obj = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json",
        "name": page_id,
        "displayName": display_name,
        "displayOption": "FitToPage",
        "width": width,
        "height": height,
    }
    if filters:  # omit key for empty or None — PBI schema 2.1.0 rejects empty filterConfig
        obj["filterConfig"] = {"filters": filters}
    return json.dumps(obj, indent=2)
