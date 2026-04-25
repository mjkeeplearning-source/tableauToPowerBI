"""Raw worksheet extraction — mark type, encodings, filters, sort,
dual-axis, reference lines, quick-table-calc detection.

Real Tableau structure:  <worksheet>/<table>/<view>  with <rows>/<cols>/<panes>
                         as siblings of <view> inside <table>.
Synthetic test structure: <worksheet>/<view> with everything nested inside.
Both are handled via the `table` detection in `extract_worksheets`.

Output per worksheet:
{
  "name": str,
  "datasource_refs": tuple[str, ...],
  "mark_type": str,                       # Bar, Line, Circle, Square, ...
  "encodings": {
      "rows": tuple[str, ...],             # bracket-token tuples from shelf text
      "columns": tuple[str, ...],
      "color": str | None,                 # raw column ref (may be qualified)
      "size": str | None,
      "label": str | None,
      "tooltip": str | None,
      "detail": tuple[str, ...],
      "shape": str | None,
      "angle": str | None,
  },
  "filters": [
      {"kind": 'categorical'|'range'|'top_n'|'context'|'conditional',
       "column": str,
       "include": tuple[str, ...],
       "exclude": tuple[str, ...],
       "expr": str | None}
  ],
  "sort": [ {"column": str, "direction": 'asc'|'desc'} ],
  "dual_axis": bool,
  "reference_lines": [ {"kind": str, "scope_column": str, "value": str | None} ],
  "quick_table_calcs": [ {"column": str, "type": str, "compute_using": str | None} ],
}
"""
from __future__ import annotations

from typing import Any

from lxml import etree

from tableau2pbir.util.xml import attr, optional_attr


def _unbracket(s: str) -> str:
    """Strip brackets from a simple ref like [field].
    Qualified refs like [datasource].[field:type] are returned as-is."""
    if s.startswith("[") and s.endswith("]") and "].[" not in s:
        return s[1:-1]
    return s


def _parse_shelf(text: str | None) -> tuple[str, ...]:
    """Extract each bracketed token from a shelf text string.
    e.g. '([a]+[b])' -> ('a', 'b'); '[ds].[f:t]' -> ('[ds].[f:t]' kept as-is)."""
    if text is None:
        return ()
    tokens: list[str] = []
    buf = ""
    depth = 0
    for ch in text:
        if ch == "[":
            depth += 1
            buf += ch
        elif ch == "]":
            depth -= 1
            buf += ch
            if depth == 0:
                tokens.append(_unbracket(buf.strip()))
                buf = ""
        elif depth > 0:
            buf += ch
    return tuple(tokens)


def _datasource_refs(view: etree._Element) -> tuple[str, ...]:
    return tuple(attr(d, "name") for d in view.findall("datasources/datasource"))


def _encodings(shelf_elem: etree._Element, pane_parent: etree._Element) -> dict[str, Any]:
    """Extract encoding channels.

    shelf_elem: element holding <rows> and <cols>/<columns> text.
    pane_parent: element holding <panes>/<pane> (real) or <pane> (synthetic).
    """
    rows = shelf_elem.findtext("rows")
    # Real Tableau uses <cols>; synthetic fixtures may use <columns>.
    cols = shelf_elem.findtext("cols") or shelf_elem.findtext("columns")
    enc: dict[str, Any] = {
        "rows": _parse_shelf(rows),
        "columns": _parse_shelf(cols),
        "color": None, "size": None, "label": None, "tooltip": None,
        "detail": (), "shape": None, "angle": None,
    }
    panes = pane_parent.findall("panes/pane") or pane_parent.findall("pane")
    for pane in panes:
        for ch in pane.findall("encodings/*"):
            col = optional_attr(ch, "column")
            if col is None:
                continue
            col = _unbracket(col)
            if ch.tag == "detail":
                enc["detail"] = (*enc["detail"], col)
            elif ch.tag in {"color", "size", "label", "tooltip", "shape", "angle"}:
                enc[ch.tag] = col
    return enc


def _filter_members(filter_elem: etree._Element) -> tuple[tuple[str, ...], tuple[str, ...]]:
    include: list[str] = []
    exclude: list[str] = []
    for gf in filter_elem.findall("groupfilter"):
        func = attr(gf, "function", default="member")
        member = optional_attr(gf, "member")
        if member is None:
            continue
        if func == "except":
            exclude.append(member)
        else:
            include.append(member)
    return tuple(include), tuple(exclude)


def _filters(view: etree._Element) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for f in view.findall("filter"):
        kind = attr(f, "class", default="categorical")
        column = _unbracket(attr(f, "column"))
        include, exclude = _filter_members(f)
        out.append({
            "kind": kind,
            "column": column,
            "include": include,
            "exclude": exclude,
            "expr": optional_attr(f, "formula"),
        })
    return out


def _sort(view: etree._Element) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for s in view.findall("sort"):
        col = optional_attr(s, "column")
        if col is None:
            continue
        out.append({
            "column": _unbracket(col),
            "direction": attr(s, "direction", default="asc"),
        })
    return out


def _reference_lines(search_root: etree._Element) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for rl in search_root.findall(".//formatted-text/reference-line"):
        out.append({
            "kind": attr(rl, "class", default="constant"),
            "scope_column": _unbracket(attr(rl, "column", default="")),
            "value": optional_attr(rl, "value"),
        })
    for rl in search_root.findall(".//reference-lines/reference-line"):
        out.append({
            "kind": attr(rl, "class", default="constant"),
            "scope_column": _unbracket(attr(rl, "column", default="")),
            "value": optional_attr(rl, "value"),
        })
    return out


def _dual_axis(search_root: etree._Element) -> bool:
    return (
        search_root.find(".//pane[@dual-axis='true']") is not None
        or search_root.find(".//dual-axis") is not None
    )


def _quick_table_calcs(search_root: etree._Element) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for tc in search_root.findall(".//table-calculations/table-calculation"):
        out.append({
            "column": _unbracket(attr(tc, "column", default="")),
            "type": attr(tc, "type", default="unknown"),
            "compute_using": optional_attr(tc, "compute-using"),
        })
    return out


def extract_worksheets(root: etree._Element) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for ws in root.findall("worksheets/worksheet"):
        # Real Tableau: <worksheet>/<table>/<view>, rows/cols/panes inside <table>
        # Synthetic:    <worksheet>/<view>, everything inside <view>
        table = ws.find("table")
        if table is not None:
            view = table.find("view")
            shelf_elem: etree._Element = table
            pane_parent: etree._Element = table
            search_root: etree._Element = table
        else:
            view = ws.find("view")
            shelf_elem = view  # type: ignore[assignment]
            pane_parent = view  # type: ignore[assignment]
            search_root = view  # type: ignore[assignment]

        if view is None:
            continue

        panes = pane_parent.findall("panes/pane") or pane_parent.findall("pane")
        mark = next(
            (p.find("mark") for p in panes if p.find("mark") is not None), None
        )
        mark_type = attr(mark, "class", default="Automatic") if mark is not None else "Automatic"

        out.append({
            "name": attr(ws, "name"),
            "datasource_refs": _datasource_refs(view),
            "mark_type": mark_type,
            "encodings": _encodings(shelf_elem, pane_parent),
            "filters": _filters(view),
            "sort": _sort(view),
            "dual_axis": _dual_axis(search_root),
            "reference_lines": _reference_lines(search_root),
            "quick_table_calcs": _quick_table_calcs(search_root),
        })
    return out
