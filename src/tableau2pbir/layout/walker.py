"""Container-tree walker — §6 Stage 5 step 1 + step 4 + step 5 + step 6."""
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
    clamped: bool = False
    dropped: bool = False


def walk_layout(root: Container | Leaf, canvas_w: int, canvas_h: int, scale: float) -> list[ResolvedLeaf]:
    out: list[ResolvedLeaf] = []
    counter = [0]
    _walk(root, x=0, y=0, w=canvas_w, h=canvas_h, scale=scale,
          canvas_w=canvas_w, canvas_h=canvas_h, out=out, counter=counter)
    return out


def _clamp(pos: Position, canvas_w: int, canvas_h: int) -> tuple[Position, bool, bool]:
    x, y = pos.x, pos.y
    if x >= canvas_w or y >= canvas_h:
        return Position(x=x, y=y, w=0, h=0), False, True
    new_right = min(pos.x + pos.w, canvas_w)
    new_bottom = min(pos.y + pos.h, canvas_h)
    new_w = max(0, new_right - x)
    new_h = max(0, new_bottom - y)
    if new_w <= 0 or new_h <= 0:
        return Position(x=x, y=y, w=0, h=0), False, True
    clamped = (new_w != pos.w) or (new_h != pos.h)
    return Position(x=x, y=y, w=new_w, h=new_h), clamped, False


def _walk(node, x: int, y: int, w: int, h: int, scale: float,
          canvas_w: int, canvas_h: int,
          out: list[ResolvedLeaf], counter: list[int]) -> None:
    if isinstance(node, Leaf):
        if node.position is not None:
            scaled = Position(
                x=int(node.position.x * scale),
                y=int(node.position.y * scale),
                w=int(node.position.w * scale),
                h=int(node.position.h * scale),
            )
            pos, clamped, dropped = _clamp(scaled, canvas_w, canvas_h)
        else:
            pos, clamped, dropped = Position(x=x, y=y, w=w, h=h), False, False
        out.append(ResolvedLeaf(
            kind=node.kind, payload=node.payload, position=pos,
            z_order=counter[0], clamped=clamped, dropped=dropped,
        ))
        counter[0] += 1
        return

    pad = node.padding
    inner_x, inner_y = x + pad, y + pad
    inner_w, inner_h = max(0, w - 2 * pad), max(0, h - 2 * pad)

    if node.kind == ContainerKind.FLOATING:
        for child in node.children:
            _walk(child, inner_x, inner_y, inner_w, inner_h, scale,
                  canvas_w, canvas_h, out, counter)
        return

    n = len(node.children) or 1
    if node.kind == ContainerKind.H:
        seg = inner_w // n
        for i, child in enumerate(node.children):
            child_w = inner_w - seg * (n - 1) if i == n - 1 else seg
            _walk(child, inner_x + seg * i, inner_y, child_w, inner_h, scale,
                  canvas_w, canvas_h, out, counter)
    else:  # V
        seg = inner_h // n
        for i, child in enumerate(node.children):
            child_h = inner_h - seg * (n - 1) if i == n - 1 else seg
            _walk(child, inner_x, inner_y + seg * i, inner_w, child_h, scale,
                  canvas_w, canvas_h, out, counter)
