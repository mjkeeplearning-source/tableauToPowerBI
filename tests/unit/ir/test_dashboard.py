from __future__ import annotations

from tableau2pbir.ir.dashboard import (
    Action, ActionKind, ActionTrigger,
    Container, ContainerKind, Dashboard, DashboardSize, Leaf, LeafKind, Position,
)


def test_leaf_sheet_position_none_at_extract_time():
    leaf = Leaf(kind=LeafKind.SHEET, payload={"sheet_id": "sheet1"}, position=None)
    assert leaf.position is None


def test_container_with_children():
    child = Leaf(kind=LeafKind.TEXT, payload={"text": "Hello"}, position=None)
    c = Container(kind=ContainerKind.H, children=(child,), padding=4, background=None)
    assert len(c.children) == 1


def test_dashboard_minimal():
    root = Container(kind=ContainerKind.V, children=(), padding=0, background=None)
    d = Dashboard(
        id="d1", name="Main",
        size=DashboardSize(w=1200, h=800, kind="exact"),
        layout_tree=root,
        actions=(),
    )
    assert d.size.w == 1200


def test_action_filter_kind():
    a = Action(
        id="a1", name="Filter By Region",
        kind=ActionKind.FILTER, trigger=ActionTrigger.SELECT,
        source_sheet_ids=("sheet1",), target_sheet_ids=("sheet2",),
        source_fields=(), target_fields=(),
        clearing_behavior="keep_filter",
    )
    assert a.kind == ActionKind.FILTER


def test_position_fields():
    p = Position(x=10, y=20, w=300, h=200)
    assert p.w == 300
