"""Render Report/definition/report.json and pages/pages.json."""
from __future__ import annotations

import json

_SCHEMA_BASE = "https://developer.microsoft.com/json-schemas/fabric/item/report"


def render_report() -> str:
    """Render Report/definition/report.json (schema 3.2.0).

    Page order is NOT embedded here — it lives in pages/pages.json (render_pages_manifest).
    """
    obj = {
        "$schema": f"{_SCHEMA_BASE}/definition/report/3.2.0/schema.json",
        "themeCollection": {
            "baseTheme": {
                "name": "CY26SU02",
                "reportVersionAtImport": {
                    "visual": "2.6.0",
                    "report": "3.1.0",
                    "page": "2.3.0",
                },
                "type": "SharedResources",
            }
        },
        "objects": {
            "section": [
                {
                    "properties": {
                        "verticalAlignment": {
                            "expr": {"Literal": {"Value": "'Top'"}}
                        }
                    }
                }
            ]
        },
        "settings": {
            "useStylableVisualContainerHeader": True,
            "exportDataMode": "AllowSummarized",
            "defaultDrillFilterOtherVisuals": True,
            "allowChangeFilterTypes": True,
            "useEnhancedTooltips": True,
            "useDefaultAggregateDisplayName": True,
        },
    }
    return json.dumps(obj, indent=2)


def render_pages_manifest(page_order: list[str]) -> str:
    """Render pages/pages.json — the pagesMetadata manifest required by schema 3.2.0."""
    obj = {
        "$schema": f"{_SCHEMA_BASE}/definition/pagesMetadata/1.0.0/schema.json",
        "pageOrder": list(page_order),
        "activePageName": page_order[0] if page_order else "",
    }
    return json.dumps(obj, indent=2)
