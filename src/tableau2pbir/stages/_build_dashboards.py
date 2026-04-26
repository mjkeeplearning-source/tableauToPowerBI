"""Stage 2 dashboard + action builders."""
from __future__ import annotations

from typing import Any

from tableau2pbir.ir.dashboard import (
    Action, ActionKind, ActionTrigger,
    Container, ContainerKind, Dashboard, DashboardSize,
    Leaf, LeafKind, Position,
)
from tableau2pbir.util.ids import stable_id


def _payload_for_leaf(
    leaf_kind: str,
    raw_payload: dict[str, Any],
    sheet_id_for_name: dict[str, str],
    param_id_for_name: dict[str, str],
    field_id_for_name: dict[str, str],
) -> dict[str, Any]:
    if leaf_kind == "sheet":
        name = raw_payload.get("sheet_name", "")
        return {"sheet_id": sheet_id_for_name.get(name, stable_id("sheet", name))}
    if leaf_kind == "text":
        return {"text": raw_payload.get("text", ""), "format": {}}
    if leaf_kind == "image":
        return {"path": raw_payload.get("path", "")}
    if leaf_kind == "filter_card":
        name = raw_payload.get("field", "")
        return {"field_id": field_id_for_name.get(name, "")}
    if leaf_kind == "parameter_card":
        name = raw_payload.get("parameter_name", "")
        return {"parameter_id": param_id_for_name.get(name, stable_id("param", name))}
    if leaf_kind == "legend":
        name = raw_payload.get("host_sheet_name", "")
        return {"host_sheet_id": sheet_id_for_name.get(name, stable_id("sheet", name))}
    if leaf_kind == "navigation":
        return {"target": raw_payload.get("target", "")}
    return {}


def _leaf_from_raw(
    raw_leaf: dict[str, Any],
    sheet_id_for_name: dict[str, str],
    param_id_for_name: dict[str, str],
    field_id_for_name: dict[str, str],
) -> Leaf:
    pos = raw_leaf["position"]
    return Leaf(
        kind=LeafKind(raw_leaf["leaf_kind"]),
        payload=_payload_for_leaf(
            raw_leaf["leaf_kind"], raw_leaf["payload"],
            sheet_id_for_name, param_id_for_name, field_id_for_name,
        ),
        position=Position(x=pos["x"], y=pos["y"], w=pos["w"], h=pos["h"]),
    )


def build_dashboards(
    raw_dashboards: list[dict[str, Any]],
    sheet_id_for_name: dict[str, str],
    param_id_for_name: dict[str, str],
    field_id_for_name: dict[str, str],
) -> tuple[Dashboard, ...]:
    out: list[Dashboard] = []
    for raw in raw_dashboards:
        leaves = tuple(
            _leaf_from_raw(rl, sheet_id_for_name, param_id_for_name, field_id_for_name)
            for rl in raw["leaves"]
        )
        root = Container(kind=ContainerKind.FLOATING, children=leaves, padding=0, background=None)
        size = raw["size"]
        out.append(Dashboard(
            id=stable_id("dashboard", raw["name"]),
            name=raw["name"],
            size=DashboardSize(w=size["w"], h=size["h"], kind=size["kind"]),
            layout_tree=root,
            actions=(),
        ))
    return tuple(out)


_ACTION_KIND_MAP = {
    "filter":    ActionKind.FILTER,
    "highlight": ActionKind.HIGHLIGHT,
    "url":       ActionKind.URL,
    "parameter": ActionKind.PARAMETER,
}


def _trigger(raw: str) -> ActionTrigger:
    if raw == "hover":
        return ActionTrigger.HOVER
    if raw == "menu":
        return ActionTrigger.MENU
    return ActionTrigger.SELECT


def build_actions(
    raw_actions: list[dict[str, Any]],
    sheet_id_for_name: dict[str, str],
) -> tuple[Action, ...]:
    def resolve(names: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(
            sheet_id_for_name[n]
            for n in names
            if n in sheet_id_for_name
        )

    out: list[Action] = []
    for raw in raw_actions:
        out.append(Action(
            id=stable_id("action", raw["name"]),
            name=raw.get("caption") or raw["name"],
            kind=_ACTION_KIND_MAP[raw["kind"]],
            trigger=_trigger(raw["trigger"]),
            source_sheet_ids=resolve(raw["source_sheets"]),
            target_sheet_ids=resolve(raw["target_sheets"]),
            source_fields=(),
            target_fields=(),
            clearing_behavior=raw["clearing_behavior"],
        ))
    return tuple(out)
