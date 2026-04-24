"""Extract the special `<datasource name='Parameters'>` into raw dicts.

Output per parameter:
{
  "name": str,                            # without brackets, e.g. 'Parameter 1'
  "caption": str | None,                  # user-visible label, e.g. 'Discount'
  "datatype": str,                        # 'real' | 'integer' | 'string' | 'date' | ...
  "domain_type": 'range' | 'list' | 'any',
  "default": str,                         # raw string literal from <calculation formula='...'> or value attr
  "allowed_values": tuple[str, ...],      # populated for list; empty otherwise
  "range": {"min", "max", "granularity"} | None,
}
"""
from __future__ import annotations

from typing import Any

from lxml import etree

from tableau2pbir.util.xml import attr, optional_attr


def _unbracket(s: str) -> str:
    return s[1:-1] if s.startswith("[") and s.endswith("]") else s


def _default_value(col: etree._Element) -> str:
    calc = col.find("calculation")
    if calc is not None and calc.get("formula") is not None:
        return attr(calc, "formula")
    return attr(col, "value", default="")


def _allowed_values(col: etree._Element) -> tuple[str, ...]:
    members = col.findall("members/member")
    return tuple(attr(m, "value") for m in members)


def _range(col: etree._Element) -> dict[str, str] | None:
    r = col.find("range")
    if r is None:
        return None
    return {
        "min": attr(r, "min"),
        "max": attr(r, "max"),
        "granularity": attr(r, "granularity"),
    }


def extract_parameters(root: etree._Element) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for ds in root.findall("datasources/datasource"):
        if attr(ds, "name") != "Parameters":
            continue
        for col in ds.findall("column"):
            out.append({
                "name": _unbracket(attr(col, "name")),
                "caption": optional_attr(col, "caption"),
                "datatype": attr(col, "datatype", default="string"),
                "domain_type": attr(col, "param-domain-type", default="any"),
                "default": _default_value(col),
                "allowed_values": _allowed_values(col),
                "range": _range(col),
            })
    return out
