"""Container-tree walker — §6 Stage 5 step 1 + step 4 + step 5."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tableau2pbir.ir.dashboard import (
    Container, ContainerKind, Leaf, LeafKind, Position,
)


@dataclass(frozen=True)
class ResolvedLeaf:
    kind: LeafKind
    payload: dict[str, Any]
    position: Position
    z_order: int


def walk_layout(root: Container | Leaf, canvas_w: int, canvas_h: int, scale: float) -> list[ResolvedLeaf]:
    out: list[ResolvedLeaf] = []
    counter = [0]
    _walk(root, x=0, y=0, w=canvas_w, h=canvas_h, scale=scale, out=out, counter=counter)
    return out


def _walk(node, x: int, y: int, w: int, h: int, scale: float,
          out: list[ResolvedLeaf], counter: list[int]) -> None:
    if isinstance(node, Leaf):
        if node.position is not None:
            pos = Position(
                x=int(node.position.x * scale),
                y=int(node.position.y * scale),
                w=int(node.position.w * scale),
                h=int(node.position.h * scale),
            )
        else:
            pos = Position(x=x, y=y, w=w, h=h)
        out.append(ResolvedLeaf(kind=node.kind, payload=node.payload, position=pos, z_order=counter[0]))
        counter[0] += 1
        return

    pad = node.padding
    inner_x, inner_y = x + pad, y + pad
    inner_w, inner_h = max(0, w - 2 * pad), max(0, h - 2 * pad)

    if node.kind == ContainerKind.FLOATING:
        for child in node.children:
            _walk(child, inner_x, inner_y, inner_w, inner_h, scale, out, counter)
        return

    n = len(node.children) or 1
    if node.kind == ContainerKind.H:
        seg = inner_w // n
        for i, child in enumerate(node.children):
            child_w = inner_w - seg * (n - 1) if i == n - 1 else seg
            _walk(child, inner_x + seg * i, inner_y, child_w, inner_h, scale, out, counter)
    else:  # V
        seg = inner_h // n
        for i, child in enumerate(node.children):
            child_h = inner_h - seg * (n - 1) if i == n - 1 else seg
            _walk(child, inner_x, inner_y + seg * i, inner_w, child_h, scale, out, counter)
