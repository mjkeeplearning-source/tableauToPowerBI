"""Render pages/<page>/page.json."""
from __future__ import annotations

import json


def render_page(page_id: str, display_name: str, ordinal: int,
                width: int, height: int, filters: list | None = None) -> str:
    obj = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.0.0/schema.json",
        "name": page_id,
        "displayName": display_name,
        "displayOption": "FitToPage",
        "ordinal": ordinal,
        "width": width,
        "height": height,
        "filterConfig": {"filters": filters or []},
    }
    return json.dumps(obj, indent=2)
