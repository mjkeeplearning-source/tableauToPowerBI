"""Raw dashboard extraction. Emits a flat list of leaves with position
info; stage 5 (Plan 4) walks and builds the container tree. Plan 2
stores leaves in document order; container inference is deferred.

Output per dashboard:
{
  "name": str,
  "size": {"w": int, "h": int, "kind": 'exact'|'automatic'|'range'},
  "leaves": [
      {"leaf_kind": 'sheet'|'text'|'image'|'filter_card'|'parameter_card'|
                    'legend'|'navigation'|'blank'|'web_page',
       "payload": dict,
       "position": {"x","y","w","h"},
       "floating": bool}
  ],
}

Tableau zone formats:
  Synthetic fixtures:  <zone type='worksheet'|'filter'|...>
  Real Tableau:        <zone> with no 'type'; uses 'type-v2' for non-worksheet
                       leaves ('color'=legend, 'filter', 'text', 'paramctrl',
                       'title', 'empty') and no type-v2 for worksheet zones.
                       Container zones have type-v2='layout-flow'|'layout-basic'
                       and contain child <zone> elements.
                       Real workbooks duplicate each zone (once clean, once with
                       is-fixed='true' + zone-style child); deduplicated by id.
"""
from __future__ import annotations

from typing import Any

from lxml import etree

from tableau2pbir.util.xml import attr, optional_attr


_ZONE_KIND_MAP = {
    "worksheet":   "sheet",
    "text":        "text",
    "bitmap":      "image",
    "image":       "image",
    "filter":      "filter_card",
    "parameter":   "parameter_card",
    "legend":      "legend",
    "navigation":  "navigation",
    "blank":       "blank",
    "webpage":     "web_page",
    "web-page":    "web_page",
}

# type-v2 values used in real Tableau (non-container leaf types)
_ZONE_KIND_MAP_V2 = {
    "color":       "legend",
    "text":        "text",
    "title":       "text",
    "filter":      "filter_card",
    "paramctrl":   "parameter_card",
    "empty":       "blank",
}

_CONTAINER_TYPES_V2 = {"layout-flow", "layout-basic"}


def _unbracket(s: str) -> str:
    if s.startswith("[") and s.endswith("]") and "].[" not in s:
        return s[1:-1]
    return s


def _size(dashboard: etree._Element) -> dict[str, Any]:
    size = dashboard.find("size")
    if size is None:
        return {"w": 1200, "h": 800, "kind": "automatic"}
    minw = optional_attr(size, "minwidth")
    maxw = optional_attr(size, "maxwidth")
    minh = optional_attr(size, "minheight")
    maxh = optional_attr(size, "maxheight")
    if minw == maxw and minh == maxh and minw is not None:
        return {"w": int(minw), "h": int(minh), "kind": "exact"}
    if minw is not None and maxw is not None and minw != maxw:
        return {"w": int(maxw), "h": int(maxh or 768), "kind": "range"}
    return {"w": int(maxw or 1200), "h": int(maxh or 800), "kind": "automatic"}


def _payload_for_kind(kind: str, zone: etree._Element) -> dict[str, Any]:
    name = optional_attr(zone, "name")
    param = optional_attr(zone, "param")
    if kind == "sheet":
        return {"sheet_name": name or ""}
    if kind == "filter_card":
        return {"field": _unbracket(param) if param else ""}
    if kind == "parameter_card":
        return {"parameter_name": _unbracket(param) if param else ""}
    if kind == "legend":
        return {"host_sheet_name": param or name or ""}
    if kind == "text":
        return {"text": param or ""}
    if kind == "image":
        return {"path": optional_attr(zone, "param") or ""}
    if kind == "navigation":
        return {"target": param or ""}
    return {}   # blank, web_page — no structured payload


def _leaves(dashboard: etree._Element) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for zone in dashboard.findall(".//zones//zone"):
        # Deduplicate: real Tableau repeats each zone twice (clean + is-fixed copy).
        zone_id = optional_attr(zone, "id")
        if zone_id is not None:
            if zone_id in seen_ids:
                continue
            seen_ids.add(zone_id)

        # Skip containers — they hold child <zone> elements.
        if zone.find("zone") is not None:
            continue

        z_type = optional_attr(zone, "type")
        z_type_v2 = optional_attr(zone, "type-v2")

        if z_type is not None:
            # Synthetic fixture format
            leaf_kind = _ZONE_KIND_MAP.get(z_type, "blank")
        elif z_type_v2 is not None:
            # Real Tableau: container types are already skipped above; map the rest
            if z_type_v2 in _CONTAINER_TYPES_V2:
                continue
            leaf_kind = _ZONE_KIND_MAP_V2.get(z_type_v2, "blank")
        else:
            # Real Tableau worksheet zone: identified by presence of name attribute
            if optional_attr(zone, "name") is None:
                continue
            leaf_kind = "sheet"

        try:
            pos = {
                "x": int(attr(zone, "x", default="0")),
                "y": int(attr(zone, "y", default="0")),
                "w": int(attr(zone, "w", default="0")),
                "h": int(attr(zone, "h", default="0")),
            }
        except ValueError:
            pos = {"x": 0, "y": 0, "w": 0, "h": 0}
        out.append({
            "leaf_kind": leaf_kind,
            "payload": _payload_for_kind(leaf_kind, zone),
            "position": pos,
            "floating": attr(zone, "floating", default="false").lower() == "true",
        })
    return out


def extract_dashboards(root: etree._Element) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for db in root.findall("dashboards/dashboard"):
        out.append({
            "name": attr(db, "name"),
            "size": _size(db),
            "leaves": _leaves(db),
        })
    return out
