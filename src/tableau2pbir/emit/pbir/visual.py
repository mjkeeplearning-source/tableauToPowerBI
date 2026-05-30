"""Render visuals/<vid>/visual.json."""
from __future__ import annotations

import json

from tableau2pbir.ir.dashboard import Position
from tableau2pbir.ir.sheet import PbirVisual


def render_visual(
    visual_id: str,
    pbir_visual: PbirVisual,
    position: Position,
    z_order: int,
    field_lookup: dict[str, dict] | None = None,
) -> str:
    fl = field_lookup or {}
    query_state: dict[str, dict] = {}
    for b in pbir_visual.encoding_bindings:
        query_state.setdefault(b.channel, {"projections": []})
        query_state[b.channel]["projections"].append(_make_projection(b.source_field_id, fl))

    obj = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/1.0.0/schema.json",
        "name": visual_id,
        "position": {"x": position.x, "y": position.y,
                     "width": position.w, "height": position.h, "z": z_order},
        "visual": {
            "visualType": pbir_visual.visual_type,
            "query": {"queryState": query_state},
            "objects": pbir_visual.format or {},
        },
    }
    return json.dumps(obj, indent=2)


def _make_projection(field_id: str, field_lookup: dict) -> dict:
    info = field_lookup.get(field_id)
    if info:
        table_name = info["table_name"]
        is_measure = info["is_measure"]
        # measure_name is the PBI display name (e.g. "Sum profit"); fall back to col_name
        prop_name = info.get("measure_name") or info["col_name"]
    elif "." in field_id:
        # Fallback for dot-qualified test fixtures like "Sales.Region"
        table_name, prop_name = field_id.split(".", 1)
        is_measure = False
    else:
        table_name = "Model"
        prop_name = field_id
        is_measure = True
    field_type = "Measure" if is_measure else "Column"
    return {
        "field": {
            field_type: {
                "Expression": {"SourceRef": {"Entity": table_name}},
                "Property": prop_name,
            }
        },
        "queryRef": f"{table_name}.{prop_name}",
        "active": True,
    }
