"""Render visuals/<vid>/visual.json."""
from __future__ import annotations

import json

from tableau2pbir.ir.dashboard import Position
from tableau2pbir.ir.sheet import PbirVisual


def render_visual(visual_id: str, pbir_visual: PbirVisual, position: Position, z_order: int) -> str:
    query_state: dict[str, dict] = {}
    for b in pbir_visual.encoding_bindings:
        query_state.setdefault(b.channel, {"projections": []})
        query_state[b.channel]["projections"].append({"field": _field_obj(b.source_field_id)})

    obj = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.0.0/schema.json",
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


def _field_obj(source_field_id: str) -> dict:
    if "." in source_field_id:
        table, col = source_field_id.split(".", 1)
        return {"Column": {"Expression": {"SourceRef": {"Source": table}}, "Property": col}}
    return {"Measure": {"Expression": {"SourceRef": {"Source": "Sales"}}, "Property": source_field_id}}
