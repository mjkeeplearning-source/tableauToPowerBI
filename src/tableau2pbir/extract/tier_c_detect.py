"""Detect tier-C (hard-unsupported) objects during stage 1. Stage 2
lifts these into `Workbook.unsupported[]` as `UnsupportedItem`s.

Each detection emits a dict:
{
  "object_kind": 'story'|'calc'|'mark'|'annotation'|'forecast'|'webpage'|'shape',
  "object_id": str,                # stable per-object identifier
  "source_excerpt": str,           # XML snippet for debugging
  "reason": str,                   # human-readable one-liner
  "code": str,                     # §8.1-stable code (unsupported_<subcategory>)
}
"""
from __future__ import annotations

import re
from typing import Any

from lxml import etree

from tableau2pbir.util.xml import attr


_POLYGON_DENSITY_GANTT = {"Polygon", "Density", "Gantt"}

_R_PYTHON_PREFIX = re.compile(r"SCRIPT_(REAL|STR|INT|BOOL)\s*\(", re.IGNORECASE)


def _excerpt(elem: etree._Element) -> str:
    s = etree.tostring(elem, encoding="unicode")
    return s[:200].strip()


def _stories(root: etree._Element) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for story in root.findall("stories/story"):
        out.append({
            "object_kind": "story",
            "object_id": f"story__{attr(story, 'name', default='unnamed')}",
            "source_excerpt": _excerpt(story),
            "reason": "Tableau story points have no PBI equivalent (§14).",
            "code": "unsupported_story_points",
        })
    return out


def _r_python_calcs(root: etree._Element) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for col in root.findall(".//datasources/datasource/column"):
        calc = col.find("calculation")
        if calc is None:
            continue
        formula = attr(calc, "formula", default="")
        if _R_PYTHON_PREFIX.search(formula):
            name = attr(col, "name", default="unnamed")
            out.append({
                "object_kind": "calc",
                "object_id": f"calc__{name}",
                "source_excerpt": formula[:200],
                "reason": "R/Python script calculations are not mapped.",
                "code": "unsupported_r_python_script",
            })
    return out


def _polygon_density_gantt(root: etree._Element) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for ws in root.findall("worksheets/worksheet"):
        name = attr(ws, "name", default="unnamed")
        for mark in ws.findall(".//pane/mark"):
            kls = attr(mark, "class", default="")
            if kls in _POLYGON_DENSITY_GANTT:
                out.append({
                    "object_kind": "mark",
                    "object_id": f"mark__{name}__{kls.lower()}",
                    "source_excerpt": _excerpt(mark),
                    "reason": f"{kls} marks have no first-class PBIR equivalent.",
                    "code": f"unsupported_mark_{kls.lower()}",
                })
    return out


def _annotations(root: etree._Element) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for ws in root.findall("worksheets/worksheet"):
        name = attr(ws, "name", default="unnamed")
        for ann in ws.findall(".//annotations/annotation"):
            out.append({
                "object_kind": "annotation",
                "object_id": f"annotation__{name}__{attr(ann, 'type', default='')}",
                "source_excerpt": _excerpt(ann),
                "reason": "Annotations have no PBI equivalent (§14).",
                "code": "unsupported_annotation",
            })
    return out


def _forecast(root: etree._Element) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for fc in root.findall(".//worksheets/worksheet//forecast"):
        out.append({
            "object_kind": "forecast",
            "object_id": f"forecast__{id(fc)}",
            "source_excerpt": _excerpt(fc),
            "reason": "Forecast/trend lines have no PBI equivalent (§14).",
            "code": "unsupported_forecast",
        })
    return out


def detect_tier_c(root: etree._Element) -> list[dict[str, Any]]:
    return (
        _stories(root)
        + _r_python_calcs(root)
        + _polygon_density_gantt(root)
        + _annotations(root)
        + _forecast(root)
    )
