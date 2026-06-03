"""Render visuals/<vid>/visual.json."""
from __future__ import annotations

import json

from tableau2pbir.ir.dashboard import Position
from tableau2pbir.ir.sheet import PbirVisual
from tableau2pbir.visualmap.format_map import build_format_objects


def render_visual(
    visual_id: str,
    pbir_visual: PbirVisual,
    position: Position,
    z_order: int,
    field_lookup: dict[str, dict] | None = None,
) -> str:
    fl = field_lookup or {}

    if pbir_visual.visual_format is not None:
        objects, container_objects = build_format_objects(
            pbir_visual.visual_format, pbir_visual.visual_type
        )
        number_formats = pbir_visual.visual_format.number_formats
    else:
        objects = pbir_visual.format or {}
        container_objects = {}
        number_formats = {}

    query_state: dict[str, dict] = {}
    for b in pbir_visual.encoding_bindings:
        query_state.setdefault(b.channel, {"projections": []})
        query_state[b.channel]["projections"].append(
            _make_projection(b.source_field_id, fl, number_formats)
        )

    query: dict = {"queryState": query_state}
    if pbir_visual.sort_by:
        query["sortDefinition"] = {
            "sort": [_make_sort_entry(s, fl) for s in pbir_visual.sort_by],
            "isDefaultSort": False,
        }

    visual_block: dict = {
        "visualType": pbir_visual.visual_type,
        "query": query,
        "objects": objects,
    }
    if container_objects:
        visual_block["visualContainerObjects"] = container_objects

    obj = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/1.0.0/schema.json",
        "name": visual_id,
        "position": {"x": position.x, "y": position.y,
                     "width": position.w, "height": position.h, "z": z_order},
        "visual": visual_block,
    }
    return json.dumps(obj, indent=2)


def _make_sort_entry(s, field_lookup: dict) -> dict:
    info = field_lookup.get(s.field_id, {})
    if info:
        table_name = info.get("table_name", "Model")
        prop_name = info.get("measure_name") or info.get("col_name", s.field_id)
        is_measure = info.get("is_measure", True)
    elif "." in s.field_id:
        table_name, prop_name = s.field_id.split(".", 1)
        is_measure = False
    else:
        table_name = "Model"
        prop_name = s.field_id
        is_measure = True
    field_type = "Measure" if is_measure else "Column"
    direction = "Descending" if s.direction.lower() in ("desc", "descending") else "Ascending"
    return {
        "direction": direction,
        "field": {
            field_type: {
                "Expression": {"SourceRef": {"Entity": table_name}},
                "Property": prop_name,
            }
        },
    }


def _make_projection(
    field_id: str,
    field_lookup: dict,
    number_formats: dict[str, str] | None = None,
) -> dict:
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
    proj: dict = {
        "field": {
            field_type: {
                "Expression": {"SourceRef": {"Entity": table_name}},
                "Property": prop_name,
            }
        },
        "queryRef": f"{table_name}.{prop_name}",
        "active": True,
    }
    if number_formats:
        dax_fmt = number_formats.get(field_id)
        if dax_fmt:
            proj["format"] = dax_fmt
    return proj
