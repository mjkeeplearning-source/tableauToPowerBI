from __future__ import annotations

from tableau2pbir.ir.dashboard import (
    ActionKind, ActionTrigger, ContainerKind, Leaf, LeafKind, Position,
)
from tableau2pbir.stages._build_dashboards import build_actions, build_dashboards


def test_single_sheet_dashboard():
    raw = [{
        "name": "Main",
        "size": {"w": 1200, "h": 800, "kind": "exact"},
        "leaves": [{
            "leaf_kind": "sheet",
            "payload": {"sheet_name": "Revenue"},
            "position": {"x": 0, "y": 0, "w": 1200, "h": 800},
            "floating": False,
        }],
    }]
    sheet_id_for_name = {"Revenue": "sheet__revenue"}
    param_id_for_name: dict[str, str] = {}
    field_id_for_name: dict[str, str] = {}
    dashboards = build_dashboards(raw, sheet_id_for_name, param_id_for_name, field_id_for_name)
    assert len(dashboards) == 1
    d = dashboards[0]
    assert d.size.w == 1200
    assert d.size.kind == "exact"
    # Root is a floating container with one sheet leaf.
    assert d.layout_tree.kind == ContainerKind.FLOATING
    assert len(d.layout_tree.children) == 1
    leaf = d.layout_tree.children[0]
    assert isinstance(leaf, Leaf)
    assert leaf.kind == LeafKind.SHEET
    assert leaf.payload["sheet_id"] == "sheet__revenue"
    assert leaf.position == Position(x=0, y=0, w=1200, h=800)


def test_filter_card_resolves_field():
    raw = [{
        "name": "D",
        "size": {"w": 800, "h": 600, "kind": "exact"},
        "leaves": [{
            "leaf_kind": "filter_card",
            "payload": {"field": "region"},
            "position": {"x": 0, "y": 0, "w": 200, "h": 100},
            "floating": False,
        }],
    }]
    dashboards = build_dashboards(
        raw, sheet_id_for_name={}, param_id_for_name={},
        field_id_for_name={"region": "tbl__ds__col__region"},
    )
    leaf = dashboards[0].layout_tree.children[0]
    assert leaf.kind == LeafKind.FILTER_CARD
    assert leaf.payload["field_id"] == "tbl__ds__col__region"


def test_action_resolves_sheet_ids():
    raw = [{
        "name": "a1", "caption": "Filter",
        "kind": "filter", "trigger": "select",
        "source_sheets": ("Revenue",),
        "target_sheets": ("Detail",),
        "clearing_behavior": "keep_filter", "url": None,
    }]
    actions = build_actions(raw, sheet_id_for_name={
        "Revenue": "sheet__revenue", "Detail": "sheet__detail",
    })
    assert len(actions) == 1
    a = actions[0]
    assert a.kind == ActionKind.FILTER
    assert a.trigger == ActionTrigger.SELECT
    assert a.source_sheet_ids == ("sheet__revenue",)
    assert a.target_sheet_ids == ("sheet__detail",)


def test_action_ignores_unknown_sheet_names():
    raw = [{
        "name": "a1", "caption": None, "kind": "highlight", "trigger": "hover",
        "source_sheets": ("Ghost",), "target_sheets": ("Detail",),
        "clearing_behavior": "keep_filter", "url": None,
    }]
    actions = build_actions(raw, sheet_id_for_name={"Detail": "sheet__detail"})
    assert actions[0].source_sheet_ids == ()
    assert actions[0].target_sheet_ids == ("sheet__detail",)
