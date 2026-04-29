from tableau2pbir.ir.dashboard import (
    Container, ContainerKind, Leaf, LeafKind, Position,
)
from tableau2pbir.layout.walker import walk_layout, ResolvedLeaf


def _leaf(kind: LeafKind, payload: dict, position: Position | None = None) -> Leaf:
    return Leaf(kind=kind, payload=payload, position=position)


def test_single_leaf_fills_canvas():
    leaf = _leaf(LeafKind.SHEET, {"sheet_id": "s1"})
    container = Container(kind=ContainerKind.H, children=(leaf,))
    out = walk_layout(container, canvas_w=1000, canvas_h=600, scale=1.0)
    assert len(out) == 1
    assert out[0].position == Position(x=0, y=0, w=1000, h=600)
    assert out[0].payload == {"sheet_id": "s1"}


def test_horizontal_split_two_equal():
    a = _leaf(LeafKind.SHEET, {"sheet_id": "a"})
    b = _leaf(LeafKind.SHEET, {"sheet_id": "b"})
    container = Container(kind=ContainerKind.H, children=(a, b))
    out = walk_layout(container, canvas_w=1000, canvas_h=600, scale=1.0)
    assert [r.position for r in out] == [
        Position(x=0, y=0, w=500, h=600),
        Position(x=500, y=0, w=500, h=600),
    ]


def test_vertical_split_three_equal():
    children = tuple(_leaf(LeafKind.SHEET, {"sheet_id": f"s{i}"}) for i in range(3))
    container = Container(kind=ContainerKind.V, children=children)
    out = walk_layout(container, canvas_w=900, canvas_h=600, scale=1.0)
    assert [r.position for r in out] == [
        Position(x=0, y=0,   w=900, h=200),
        Position(x=0, y=200, w=900, h=200),
        Position(x=0, y=400, w=900, h=200),
    ]


def test_floating_leaf_keeps_explicit_position_scaled():
    leaf = _leaf(LeafKind.SHEET, {"sheet_id": "f"}, position=Position(x=100, y=50, w=200, h=150))
    container = Container(kind=ContainerKind.FLOATING, children=(leaf,))
    out = walk_layout(container, canvas_w=1280, canvas_h=720, scale=2.0)
    assert out[0].position == Position(x=200, y=100, w=400, h=300)


def test_z_order_reflects_document_order():
    a = _leaf(LeafKind.SHEET, {"sheet_id": "a"})
    b = _leaf(LeafKind.SHEET, {"sheet_id": "b"})
    container = Container(kind=ContainerKind.FLOATING, children=(a, b))
    out = walk_layout(container, canvas_w=1000, canvas_h=600, scale=1.0)
    assert [r.z_order for r in out] == [0, 1]


def test_padding_shrinks_child_rect():
    leaf = _leaf(LeafKind.SHEET, {"sheet_id": "p"})
    container = Container(kind=ContainerKind.H, children=(leaf,), padding=10)
    out = walk_layout(container, canvas_w=1000, canvas_h=600, scale=1.0)
    assert out[0].position == Position(x=10, y=10, w=980, h=580)
