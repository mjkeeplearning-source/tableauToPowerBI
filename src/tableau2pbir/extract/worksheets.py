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
      "text": str | None,
  },
  "filters": [
      # categorical / context / conditional:
      {"kind": "categorical"|"context"|"conditional", "column": str,
       "include": tuple, "exclude": tuple, "expr": str | None},
      # range:
      {"kind": "range", "column": str, "min_val": str | None,
       "max_val": str | None, "agg_prefix": str | None},
      # top_n:
      {"kind": "top_n", "column": str, "n": int, "direction": str,
       "by_column": str | None, "by_agg": str | None},
  ],
  "sort": [ {"column": str, "direction": 'asc'|'desc', "sort_by": str | None} ],
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
        "detail": (), "shape": None, "angle": None, "text": None,
    }
    panes = pane_parent.findall("panes/pane") or pane_parent.findall("pane")
    for pane in panes:
        for ch in pane.findall("encodings/*"):
            col = optional_attr(ch, "column")
            if col is None:
                continue
            col = _parse_filter_column(col)
            if ch.tag == "detail":
                enc["detail"] = (*enc["detail"], col)
            elif ch.tag in {"color", "size", "label", "tooltip", "shape", "angle", "text"}:
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


_KNOWN_AGGS: frozenset[str] = frozenset({
    "sum", "avg", "average", "min", "max",
    "cntd", "ctd", "countd", "cnt", "count", "median",
})

_DATE_DERIVATIONS: frozenset[str] = frozenset({
    "Year", "Quarter", "Month", "Week", "Day", "Hour", "Minute", "Second",
})


def _column_instances(view: etree._Element) -> list[dict[str, Any]]:
    """Collect date-part <column-instance> elements from <datasource-dependencies>.

    Only derivations in _DATE_DERIVATIONS are returned. Aggregation derivations
    (Sum, Count, CountD, etc.) and None are handled elsewhere in the pipeline.
    """
    out: list[dict[str, Any]] = []
    for dep in view.findall("datasource-dependencies"):
        for ci in dep.findall("column-instance"):
            derivation = optional_attr(ci, "derivation") or "None"
            if derivation not in _DATE_DERIVATIONS:
                continue
            slug = _parse_filter_column(optional_attr(ci, "name") or "")
            base_col = _parse_filter_column(optional_attr(ci, "column") or "")
            if not slug or not base_col:
                continue
            out.append({
                "slug": slug,             # "yr:order_date:ok"
                "base_column": base_col,  # "order_date"
                "derivation": derivation, # "Year"
            })
    return out


def _parse_agg_prefix(column_instance: str) -> str | None:
    """Extract the aggregation prefix from a Tableau column-instance name.

    Format: 'aggregation:field:type'  e.g. 'max:profit:qk' → 'max'.
    Returns None for 'none' prefix or unrecognised tokens (treats as row-level).
    """
    parts = column_instance.split(":")
    if len(parts) < 2:
        return None
    prefix = parts[0].lower()
    if prefix == "none":
        return None
    return prefix if prefix in _KNOWN_AGGS else None


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
                "agg_prefix": _parse_agg_prefix(column),
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


def _sort(view: etree._Element) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for s in view.findall("sort"):
        col = optional_attr(s, "column")
        if col is None:
            continue
        out.append({
            "column": _unbracket(col),
            "direction": attr(s, "direction", default="asc").lower(),
            "sort_by": None,
        })
    for s in view.findall("computed-sort"):
        col = optional_attr(s, "column")
        if col is None:
            continue
        using = optional_attr(s, "using")
        out.append({
            "column": _parse_filter_column(col),
            "direction": attr(s, "direction", default="asc").lower(),
            "sort_by": _parse_filter_column(using) if using else None,
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


def _sheet_style(
    ws: etree._Element,
    table: etree._Element | None,
    pane_parent: etree._Element,
) -> dict[str, Any]:
    """Extract all visual formatting from a worksheet element.

    Reads title font, axis/cell/header fonts, number formats per field,
    and pane-level mark color/labels.
    """
    style: dict[str, Any] = {
        "title": None,
        "mark_color": None,
        "labels_show": False,
        "axis_font_name": None,
        "axis_font_size": None,
        "cell_font_name": None,
        "cell_font_size": None,
        "header_font_name": None,
        "header_font_size": None,
        "number_formats": {},
    }

    # --- Title ---
    runs = ws.findall("layout-options/title/formatted-text/run")
    if runs:
        run = runs[0]
        fs_str = optional_attr(run, "fontsize")
        fs_int: int | None = None
        if fs_str is not None:
            try:
                fs_int = int(fs_str)
            except ValueError:
                pass
        style["title"] = {
            "text": "".join(r.text or "" for r in runs),
            "font_name": optional_attr(run, "fontname"),
            "font_size": fs_int,
            "bold": optional_attr(run, "bold") == "true",
            "italic": optional_attr(run, "italic") == "true",
            "underline": optional_attr(run, "underline") == "true",
            "font_color": optional_attr(run, "fontcolor"),
        }

    # --- Table-level style rules ---
    if table is not None:
        for rule in table.findall("style/style-rule"):
            element = optional_attr(rule, "element")
            field = optional_attr(rule, "field")
            for fmt in rule.findall("format"):
                a = optional_attr(fmt, "attr")
                v = optional_attr(fmt, "value")
                if not a or v is None:
                    continue
                if element == "field-labels" and field is None:
                    if a == "font-family":
                        style["axis_font_name"] = v
                    elif a == "font-size":
                        try:
                            style["axis_font_size"] = int(v)
                        except ValueError:
                            pass
                elif element == "cell":
                    fmt_field = optional_attr(fmt, "field")
                    if a == "text-format" and fmt_field is not None:
                        style["number_formats"][fmt_field] = v
                    elif a == "font-family" and field is None:
                        style["cell_font_name"] = v
                    elif a == "font-size" and field is None:
                        try:
                            style["cell_font_size"] = int(v)
                        except ValueError:
                            pass
                elif element == "header" and field is None:
                    if a == "font-family":
                        style["header_font_name"] = v
                    elif a == "font-size":
                        try:
                            style["header_font_size"] = int(v)
                        except ValueError:
                            pass

    # --- Pane-level mark styles ---
    panes = pane_parent.findall("panes/pane") or pane_parent.findall("pane")
    for pane in panes:
        for fmt in pane.findall("style/style-rule[@element='mark']/format"):
            a = optional_attr(fmt, "attr")
            v = optional_attr(fmt, "value")
            if a == "mark-color":
                style["mark_color"] = v
            elif a == "mark-labels-show":
                style["labels_show"] = (v == "true")

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
            "sheet_style": _sheet_style(ws, table, pane_parent),
            "column_instances": _column_instances(view),
        })
    return out
