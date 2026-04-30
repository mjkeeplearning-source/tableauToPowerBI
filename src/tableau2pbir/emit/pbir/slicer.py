"""Slicer visuals — filter cards and parameter cards."""
from __future__ import annotations

import json

from tableau2pbir.emit.pbir.visual import _field_obj
from tableau2pbir.ir.dashboard import Position


def render_filter_slicer(visual_id: str, source_field_id: str,
                         position: Position, z_order: int) -> str:
    return _slicer_json(visual_id, source_field_id, position, z_order)


def render_parameter_slicer(visual_id: str, parameter_name: str, parameter_intent: str,
                            position: Position, z_order: int) -> str:
    if parameter_intent in ("numeric_what_if", "categorical_selector"):
        source_field_id = f"{parameter_name}.Value"
    else:
        source_field_id = parameter_name
    return _slicer_json(visual_id, source_field_id, position, z_order)


def _slicer_json(visual_id: str, source_field_id: str, position: Position, z_order: int) -> str:
    obj = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.0.0/schema.json",
        "name": visual_id,
        "position": {"x": position.x, "y": position.y,
                     "width": position.w, "height": position.h, "z": z_order},
        "visual": {
            "visualType": "slicer",
            "query": {
                "queryState": {
                    "Values": {"projections": [{"field": _field_obj(source_field_id)}]},
                },
            },
            "objects": {},
        },
    }
    return json.dumps(obj, indent=2)
