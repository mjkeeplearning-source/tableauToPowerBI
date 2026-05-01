"""Raw datasource extraction. Output is a list of JSON-serializable dicts
mirroring the XML structure; no classification or IR mapping here — that
lives in stage 2 (`classify/` + `s02_canonicalize.py`).

Structure per datasource:
{
  "name": str,
  "caption": str | None,
  "connection": {"class": str, **attrs},         # the outer <connection>
  "named_connections": [                         # preserves §5.8 upstream
      {"name": str, "caption": str | None,
       "connection": {"class": str, **attrs}},
      ...
  ],
  "extract": {"connection": {...}} | None,       # the <extract><connection/> if any
  "columns": [ {"name": str, "datatype": str, "role": str, "type": str | None} ],
  "calculations": [ {"host_column_name", "tableau_expr", "datatype", "role"} ],
}
"""
from __future__ import annotations

from typing import Any

from lxml import etree

from tableau2pbir.util.xml import attr, optional_attr


_RESERVED_DS_NAME = "Parameters"     # §5.7 — handled separately by extract/parameters.py


def _strip_brackets(s: str) -> str:
    if s.startswith("[") and s.endswith("]"):
        return s[1:-1]
    return s


def _connection_to_dict(conn: etree._Element) -> dict[str, Any]:
    out: dict[str, Any] = {"class": attr(conn, "class", default="unknown")}
    for k, v in conn.attrib.items():
        if k != "class":
            out[str(k)] = v
    return out


def _extract_block(conn: etree._Element) -> dict[str, Any] | None:
    ex = conn.find("extract")
    if ex is None:
        return None
    inner = ex.find("connection")
    if inner is None:
        return {"connection": None}
    return {"connection": _connection_to_dict(inner)}


def _parse_bracket_pair(val: str) -> tuple[str, str]:
    """Parse '[schema].[table]' or '[table]' → (schema, table) or ('', table)."""
    parts = [p.strip("[]") for p in val.split("].") if p]
    if len(parts) == 2:
        return parts[0], parts[1]
    return "", parts[0] if parts else val


def _relations(conn: etree._Element) -> list[dict[str, Any]]:
    """Extract <relation type='table'> children from a <relation type='collection'>."""
    coll = conn.find("relation[@type='collection']")
    if coll is None:
        return []
    out: list[dict[str, Any]] = []
    for rel in coll.findall("relation[@type='table']"):
        out.append({
            "name": attr(rel, "name"),
            "table": attr(rel, "table", default=""),
            "connection": optional_attr(rel, "connection") or "",
        })
    return out


def _col_map(conn: etree._Element) -> dict[str, tuple[str, str]]:
    """Extract <cols><map> elements → {col_name: (table_name, physical_col_name)}.

    Map key is like '[category]', value is like '[orders].[category]'.
    """
    out: dict[str, tuple[str, str]] = {}
    for m in conn.findall("cols/map"):
        key = optional_attr(m, "key") or ""
        val = optional_attr(m, "value") or ""
        col_name = key.strip("[]")
        if not col_name or not val:
            continue
        table_name, physical_col = _parse_bracket_pair(val)
        out[col_name] = (table_name, physical_col)
    return out


def _named_connections(conn: etree._Element) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for nc in conn.findall("named-connections/named-connection"):
        inner = nc.find("connection")
        out.append({
            "name": attr(nc, "name"),
            "caption": optional_attr(nc, "caption"),
            "connection": _connection_to_dict(inner) if inner is not None else None,
        })
    return out


def _columns_and_calculations(
    ds_elem: etree._Element,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cols: list[dict[str, Any]] = []
    calcs: list[dict[str, Any]] = []
    for col in ds_elem.findall("column"):
        name = _strip_brackets(attr(col, "name"))
        datatype = attr(col, "datatype", default="string")
        role = attr(col, "role", default="dimension")
        type_ = optional_attr(col, "type")
        cols.append({"name": name, "datatype": datatype, "role": role, "type": type_})
        calc = col.find("calculation")
        if calc is not None:
            calcs.append({
                "host_column_name": name,
                "tableau_expr": attr(calc, "formula"),
                "datatype": datatype,
                "role": role,
            })
    return cols, calcs


def extract_object_graph_relationships(root: etree._Element) -> list[dict[str, Any]]:
    """Extract <object-graph><relationships> — Tableau join predicates.

    Returns list of {"left_col": str, "right_col": str} dicts whose column
    names can be resolved to physical (table, column) pairs via the datasource
    col_map in Stage 2.
    """
    out: list[dict[str, Any]] = []
    for og in root.iter("object-graph"):
        for rel in og.findall("relationships/relationship"):
            expr = rel.find("expression[@op='=']")
            if expr is None:
                continue
            children = expr.findall("expression")
            if len(children) != 2:
                continue
            left_col = children[0].get("op", "").strip("[]")
            right_col = children[1].get("op", "").strip("[]")
            if left_col and right_col:
                out.append({"left_col": left_col, "right_col": right_col})
    return out


def extract_datasources(root: etree._Element) -> list[dict[str, Any]]:
    """Extract every `<datasource>` in the workbook except the reserved
    `Parameters` datasource (handled by extract/parameters.py)."""
    out: list[dict[str, Any]] = []
    for ds in root.findall("datasources/datasource"):
        name = attr(ds, "name")
        if name == _RESERVED_DS_NAME:
            continue
        conn = ds.find("connection")
        if conn is None:
            conn_dict: dict[str, Any] = {"class": "unknown"}
            named: list[dict[str, Any]] = []
            extract: dict[str, Any] | None = None
            rels: list[dict[str, Any]] = []
            cmap: dict[str, tuple[str, str]] = {}
        else:
            conn_dict = _connection_to_dict(conn)
            named = _named_connections(conn)
            extract = _extract_block(conn)
            rels = _relations(conn)
            cmap = _col_map(conn)
        cols, calcs = _columns_and_calculations(ds)
        out.append({
            "name": name,
            "caption": optional_attr(ds, "caption"),
            "connection": conn_dict,
            "named_connections": named,
            "extract": extract,
            "relations": rels,
            "col_map": cmap,
            "columns": cols,
            "calculations": calcs,
        })
    return out
