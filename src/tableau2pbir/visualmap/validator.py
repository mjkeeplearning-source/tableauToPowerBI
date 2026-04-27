"""Stage-4 validator: returns a tuple of human-readable error strings.
Empty tuple means valid."""
from __future__ import annotations

from tableau2pbir.ir.sheet import PbirVisual
from tableau2pbir.visualmap.catalog import VISUAL_TYPES, slots_for


def validate_visual(
    pv: PbirVisual, *, known_field_ids: frozenset[str],
) -> tuple[str, ...]:
    errors: list[str] = []
    if pv.visual_type not in VISUAL_TYPES:
        errors.append(f"unknown visual_type: {pv.visual_type!r}")
        return tuple(errors)
    allowed = slots_for(pv.visual_type)
    for b in pv.encoding_bindings:
        if b.channel not in allowed:
            errors.append(
                f"channel {b.channel!r} not allowed for {pv.visual_type}"
            )
        if b.source_field_id not in known_field_ids:
            errors.append(f"unknown source_field_id: {b.source_field_id!r}")
    return tuple(errors)
