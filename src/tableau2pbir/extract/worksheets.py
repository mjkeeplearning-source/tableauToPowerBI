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
      # categorical / context / conditional:
      {"kind": "categorical"|"context"|"conditional", "column": str,
       "include": tuple, "exclude": tuple, "expr": str | None},
      # range:
      {"kind": "range", "column": str, "min_val": str | None,
       "max_val": str | None, "agg_prefix": None},
      # top_n:
      {"kind": "top_n", "column": str, "n": int, "direction": str,
       "by_column": str | None, "by_agg": str | None},
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


_USER_NS = "http://www.tableausoftware.com/xml/user"


def _strip_member_quotes(value: str) -> str:
    """Strip surrounding double-quotes Tableau embeds in member values (&quot;Value&quot;)."""
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1]
    return value


def _filter_members(filter_elem: etree._Element) -> tuple[tuple[str, ...], tuple[str, ...]]:
    include: list[str] = []
    exclude: list[str] = []
    for gf in filter_elem.findall("groupfilter"):
        func = attr(gf, "function", default="member")
        member = optional_attr(gf, "member")

        if func == "union":
            # Real Tableau XML: members nested inside a <groupfilter function="union"> wrapper.
            # user:ui-enumeration tells us whether nested members are included or excluded.
            enumeration = gf.get(f"{{{_USER_NS}}}ui-enumeration") or "inclusive"
            target = exclude if enumeration == "exclusive" else include
            for child in gf.findall("groupfilter"):
                child_member = optional_attr(child, "member")
                if child_member is not None:
                    target.append(_strip_member_quotes(child_member))
        elif member is not None:
            val = _strip_member_quotes(member)
            if func == "except":
                exclude.append(val)
            else:
                include.append(val)
    return tuple(include), tuple(exclude)


_TABLEAU_CLASS_TO_KIND: dict[str, str] = {
    "categorical": "categorical",
    "quantitative": "range",
    "top": "top_n",
    "context": "context",
    "condition": "conditional",
}


def _parse_filter_column(column_attr: str) -> str:
    """Extract the column-instance name from a potentially qualified Tableau column ref.

    Real workbooks use '[datasource].[none:col:nk]' fully-qualified form.
    _parse_shelf splits this into individual bracket tokens; we drop the
    datasource-marker token (contains '.' but not ':') and keep the instance token.
    Simple refs like '[region]' pass through unchanged.
    """
    tokens = _parse_shelf(column_attr)
    non_markers = [t for t in tokens if not ("." in t and ":" not in t)]
    if non_markers:
        return non_markers[-1]
    return _unbracket(column_attr)


def _extract_shared_view_filters(root: etree._Element) -> dict[str, dict[str, Any]]:
    """Parse workbook-level <shared-views>/<shared-view>/<filter> elements.

    Returns a dict keyed by the raw column attribute string (e.g.
    '[federated.xxx].[none:region:nk]') so worksheet <slices>/<column> text
    can look them up directly.
    """
    out: dict[str, dict[str, Any]] = {}
    for sv in root.findall("shared-views/shared-view"):
        for f in sv.findall("filter"):
            col_attr = attr(f, "column")
            tableau_class = attr(f, "class", default="categorical")
            kind = _TABLEAU_CLASS_TO_KIND.get(tableau_class, "categorical")
            col = _parse_filter_column(col_attr)
            include, exclude = _filter_members(f)
            out[col_attr] = {
                "kind": kind,
                "column": col,
                "include": include,
                "exclude": exclude,
                "expr": optional_attr(f, "formula"),
            }
    return out


def _filters(
    view: etree._Element,
    shared_view_filters: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    inline_col_attrs: set[str] = set()
    for f in view.findall("filter"):
        tableau_class = attr(f, "class", default="categorical")
        kind = _TABLEAU_CLASS_TO_KIND.get(tableau_class, "categorical")
        col_attr = attr(f, "column")
        column = _parse_filter_column(col_attr)
        inline_col_attrs.add(col_attr)

        if kind == "range":
            out.append({
                "kind": "range",
                "column": column,
                "min_val": f.findtext("min"),
                "max_val": f.findtext("max"),
                "agg_prefix": None,
            })
        elif kind == "top_n":
            spec = f.find("top-spec-field")
            out.append({
                "kind": "top_n",
                "column": column,
                "n": int(f.findtext("top-spec-count") or 10),
                "direction": f.findtext("top-spec-direction") or "Top",
                "by_column": (_unbracket(attr(spec, "column", default="")) or None) if spec is not None else None,
                "by_agg": optional_attr(spec, "aggregation") if spec is not None else None,
            })
        else:
            include, exclude = _filter_members(f)
            out.append({
                "kind": kind,
                "column": column,
                "include": include,
                "exclude": exclude,
                "expr": optional_attr(f, "formula"),
            })

    # Merge shared-view filters referenced by this worksheet's <slices>.
    if shared_view_filters:
        for slice_col in view.findall("slices/column"):
            col_ref = (slice_col.text or "").strip()
            if col_ref in shared_view_filters and col_ref not in inline_col_attrs:
                out.append(shared_view_filters[col_ref])

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


def _mark_style(pane_parent: etree._Element) -> dict[str, Any]:
    """Read <style-rule element='mark'>/<format> across all panes; last write wins."""
    style: dict[str, Any] = {"mark_color": None, "labels_show": False}
    panes = pane_parent.findall("panes/pane") or pane_parent.findall("pane")
    for pane in panes:
        for fmt in pane.findall("style/style-rule[@element='mark']/format"):
            attr_name = optional_attr(fmt, "attr")
            value = optional_attr(fmt, "value")
            if attr_name == "mark-color":
                style["mark_color"] = value
            elif attr_name == "mark-labels-show":
                style["labels_show"] = (value == "true")
    return style


def extract_worksheets(root: etree._Element) -> list[dict[str, Any]]:
    shared_view_filters = _extract_shared_view_filters(root)
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
        mark_type = (attr(mark, "class", default="automatic") if mark is not None else "automatic").lower()

        out.append({
            "name": attr(ws, "name"),
            "datasource_refs": _datasource_refs(view),
            "mark_type": mark_type,
            "encodings": _encodings(shelf_elem, pane_parent),
            "filters": _filters(view, shared_view_filters),
            "sort": _sort(view),
            "dual_axis": _dual_axis(search_root),
            "reference_lines": _reference_lines(search_root),
            "quick_table_calcs": _quick_table_calcs(search_root),
            "mark_style": _mark_style(pane_parent),
        })
    return out
