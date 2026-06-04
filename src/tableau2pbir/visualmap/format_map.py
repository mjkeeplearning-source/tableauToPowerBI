"""Translate VisualFormat IR → PBI PBIR visual.objects and visual.visualContainerObjects.

All card names and property names confirmed from:
- out/simple_join_sorted_test_format_manul.Report PBIR JSON files (PBI Desktop output)
- report-visualContainer-1.0.0.json schema (bundled)
"""
from __future__ import annotations

from tableau2pbir.ir.sheet import VisualFormat

_CHART_TYPES = frozenset({"columnChart", "barChart", "lineChart", "areaChart", "scatterChart"})
_TABLE_TYPES = frozenset({"tableEx"})


def _lit(value: str) -> dict:
    return {"expr": {"Literal": {"Value": value}}}


def _color(hex_color: str) -> dict:
    return {"solid": {"color": _lit(f"'{hex_color}'")}}


def _font_name_lit(name: str) -> dict:
    """Triple-quote font names that contain spaces (confirmed from manual PBIR visual_1)."""
    if " " in name:
        return _lit(f"'''{name}'''")
    return _lit(f"'{name}'")


def _font_size_lit(pt: int) -> dict:
    """PBI stores font sizes as decimal literals with 'D' suffix (confirmed from manual PBIR)."""
    return _lit(f"{pt}D")


def build_format_objects(
    vf: VisualFormat | None,
    visual_type: str,
    per_series_colors: list[tuple[str, str]] | None = None,
) -> tuple[dict[str, list[dict]], dict[str, list[dict]]]:
    """Return (visual_objects, visual_container_objects) for PBIR emission.

    visual_objects        → visual.visual.objects
    visual_container_objects → visual.visual.visualContainerObjects
    """
    if vf is None:
        return {}, {}

    objects: dict[str, list[dict]] = {}
    container: dict[str, list[dict]] = {}

    # ---------- visual.objects ----------

    if vf.labels_show:
        objects["labels"] = [{"properties": {"show": _lit("true")}}]

    if per_series_colors:
        objects["dataPoint"] = [
            {"properties": {"fill": _color(hex_val)}, "selector": {"metadata": qr}}
            for qr, hex_val in per_series_colors
        ]
    elif vf.mark_color:
        objects["dataPoint"] = [
            {"properties": {"fill": _color(vf.mark_color)}}
        ]

    if visual_type in _CHART_TYPES and vf.axis:
        ax = vf.axis
        cat_props: dict = {}
        val_props: dict = {}
        if ax.font_name:
            cat_props["titleFontFamily"] = _font_name_lit(ax.font_name)
            val_props["titleFontFamily"] = _font_name_lit(ax.font_name)
        if ax.font_size:
            cat_props["titleFontSize"] = _font_size_lit(ax.font_size)
            val_props["titleFontSize"] = _font_size_lit(ax.font_size)
        if cat_props:
            objects["categoryAxis"] = [{"properties": cat_props}]
        if val_props:
            objects["valueAxis"] = [{"properties": val_props}]

    if visual_type in _TABLE_TYPES and vf.table:
        t = vf.table
        val_props = {}
        hdr_props = {}
        if t.cell_font_name:
            val_props["fontFamily"] = _font_name_lit(t.cell_font_name)
        if t.cell_font_size:
            val_props["fontSize"] = _font_size_lit(t.cell_font_size)
        if t.header_font_name:
            hdr_props["fontFamily"] = _font_name_lit(t.header_font_name)
        if t.header_font_size:
            hdr_props["fontSize"] = _font_size_lit(t.header_font_size)
        if val_props:
            objects["values"] = [{"properties": val_props}]
        if hdr_props:
            objects["columnHeaders"] = [{"properties": hdr_props}]

    # ---------- visual.visualContainerObjects ----------

    if vf.title:
        tit = vf.title
        title_props: dict = {}
        if tit.text:  # Only emit show/text when text is non-empty
            title_props["show"] = _lit("true")
            title_props["text"] = _lit(f"'{tit.text}'")
        if tit.font_name:
            title_props["fontFamily"] = _font_name_lit(tit.font_name)
        if tit.font_size:
            title_props["fontSize"] = _font_size_lit(tit.font_size)
        if tit.bold:
            title_props["bold"] = _lit("true")
        if tit.italic:
            title_props["italic"] = _lit("true")
        if tit.underline:
            title_props["underline"] = _lit("true")
        if tit.font_color:
            title_props["fontColor"] = _color(tit.font_color)
        if title_props:
            container["title"] = [{"properties": title_props}]

    return objects, container
