"""Validator: every binding's source_field_id resolves to an IR column or
calc; every binding.channel is in the visual's slot set."""
from __future__ import annotations

from tableau2pbir.ir.sheet import EncodingBinding, PbirVisual
from tableau2pbir.visualmap.validator import validate_visual


def test_valid_visual_passes():
    pv = PbirVisual(
        visual_type="clusteredBarChart",
        encoding_bindings=(
            EncodingBinding(channel="category", source_field_id="t__col__region"),
            EncodingBinding(channel="value", source_field_id="t__col__sales"),
        ),
        format={},
    )
    known_field_ids = frozenset({"t__col__region", "t__col__sales"})
    errors = validate_visual(pv, known_field_ids=known_field_ids)
    assert errors == ()


def test_unknown_source_field_reported():
    pv = PbirVisual(
        visual_type="clusteredBarChart",
        encoding_bindings=(
            EncodingBinding(channel="value", source_field_id="t__col__missing"),
        ),
        format={},
    )
    errors = validate_visual(pv, known_field_ids=frozenset())
    assert any("missing" in e for e in errors)


def test_invalid_slot_reported():
    pv = PbirVisual(
        visual_type="clusteredBarChart",
        encoding_bindings=(
            EncodingBinding(channel="bogus", source_field_id="t__col__sales"),
        ),
        format={},
    )
    errors = validate_visual(
        pv, known_field_ids=frozenset({"t__col__sales"}),
    )
    assert any("bogus" in e for e in errors)


def test_unknown_visual_type_reported():
    pv = PbirVisual(
        visual_type="madeUp",
        encoding_bindings=(),
        format={},
    )
    errors = validate_visual(pv, known_field_ids=frozenset())
    assert any("madeUp" in e for e in errors)
