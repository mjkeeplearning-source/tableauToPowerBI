"""Raw actions extraction — workbook-level and dashboard-level.

Output per action:
{
  "name": str,
  "caption": str | None,
  "kind": 'filter'|'highlight'|'url'|'parameter',
  "trigger": 'select'|'hover'|'menu',
  "source_sheets": tuple[str, ...],
  "target_sheets": tuple[str, ...],
  "clearing_behavior": str,               # 'keep_filter'|'show_all'|'exclude'
  "url": str | None,                      # only for url actions
}

Tableau action formats:
  Synthetic fixtures:  <filter-action trigger='select' clearing-behavior='...'/>
                       with <source><worksheet>Name</worksheet></source> text children
  Real Tableau:        <action name='[...]'> with:
                       - <activation type='on-select|on-hover|on-menu'/>
                       - <source worksheet='Name' dashboard='...'/>  (attr, not text)
                       - <command command='tsc:tsl-filter|tsc:brush|...'/> for kind
"""
from __future__ import annotations

from typing import Any

from lxml import etree

from tableau2pbir.util.xml import attr, optional_attr


_KIND_BY_TAG = {
    "filter-action":    "filter",
    "highlight-action": "highlight",
    "url-action":       "url",
    "parameter-action": "parameter",
}

# Real Tableau <command command='...'> → kind
_KIND_BY_COMMAND = {
    "tsc:tsl-filter":    "filter",
    "tsc:brush":         "highlight",
    "tsc:navigate":      "url",
    "tsc:set-parameter": "parameter",
}


def _unbracket(s: str) -> str:
    if s.startswith("[") and s.endswith("]") and "].[" not in s:
        return s[1:-1]
    return s


def _sheets_under(elem: etree._Element | None) -> tuple[str, ...]:
    """Collect sheet names from synthetic <source>/<target> text children."""
    if elem is None:
        return ()
    return tuple(
        (w.text or "")
        for w in elem.findall("worksheet")
        if w.text
    )


def _normalize_clearing(raw: str | None) -> str:
    if raw is None:
        return "keep_filter"
    return raw.replace("-", "_")


def _one_action(elem: etree._Element) -> dict[str, Any]:
    """Parse synthetic-format action element (<filter-action>, etc.)."""
    return {
        "name": attr(elem, "name"),
        "caption": optional_attr(elem, "caption"),
        "kind": _KIND_BY_TAG[elem.tag],
        "trigger": attr(elem, "trigger", default="select"),
        "source_sheets": _sheets_under(elem.find("source")),
        "target_sheets": _sheets_under(elem.find("target")),
        "clearing_behavior": _normalize_clearing(optional_attr(elem, "clearing-behavior")),
        "url": optional_attr(elem, "url"),
    }


def _one_real_action(elem: etree._Element) -> dict[str, Any] | None:
    """Parse real-Tableau <action> element."""
    cmd = elem.find("command")
    if cmd is None:
        return None
    kind = _KIND_BY_COMMAND.get(cmd.get("command", ""))
    if kind is None:
        return None

    activation = elem.find("activation")
    trigger_raw = activation.get("type", "on-select") if activation is not None else "on-select"
    trigger = trigger_raw[len("on-"):] if trigger_raw.startswith("on-") else trigger_raw

    src = elem.find("source")
    src_ws = src.get("worksheet") if src is not None else None
    source_sheets = (src_ws,) if src_ws else ()

    # auto-clear=true → clear on deselect (show_all); false → keep_filter
    auto_clear = activation.get("auto-clear", "true") if activation is not None else "true"
    clearing = "show_all" if auto_clear.lower() == "true" else "keep_filter"

    return {
        "name": _unbracket(attr(elem, "name")),
        "caption": optional_attr(elem, "caption"),
        "kind": kind,
        "trigger": trigger,
        "source_sheets": source_sheets,
        "target_sheets": (),
        "clearing_behavior": clearing,
        "url": None,
    }


def extract_actions(root: etree._Element) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    # Synthetic format: typed tags (<filter-action>, etc.)
    for tag in _KIND_BY_TAG:
        for elem in root.findall(f".//actions/{tag}"):
            out.append(_one_action(elem))
    # Real Tableau format: generic <action> with <command> child
    for elem in root.findall(".//actions/action"):
        record = _one_real_action(elem)
        if record is not None:
            out.append(record)
    return out
