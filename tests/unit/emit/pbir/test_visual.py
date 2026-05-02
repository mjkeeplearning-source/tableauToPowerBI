import json

from tableau2pbir.emit.pbir.visual import render_visual
from tableau2pbir.ir.dashboard import Position
from tableau2pbir.ir.sheet import EncodingBinding, PbirVisual


def _bar_visual() -> PbirVisual:
    return PbirVisual(
        visual_type="clusteredBarChart",
        encoding_bindings=(
            EncodingBinding(channel="Category", source_field_id="Sales.Region"),
            EncodingBinding(channel="Y", source_field_id="Total Sales"),
        ),
        format={},
    )


def test_visual_json_schema_is_1_0_0():
    pos = Position(x=0, y=0, w=400, h=300)
    out = render_visual(visual_id="v1", pbir_visual=_bar_visual(), position=pos, z_order=0)
    obj = json.loads(out)
    assert "/1.0.0/" in obj["$schema"], f"Expected schema 1.0.0, got: {obj['$schema']}"


def test_projection_uses_entity_not_source():
    """SourceRef must use 'Entity' (semantic model table), not 'Source' (query alias)."""
    pv = PbirVisual(
        visual_type="clusteredBarChart",
        encoding_bindings=(
            EncodingBinding(channel="Category", source_field_id="none_category_nk"),
        ),
        format={},
    )
    lookup = {"none_category_nk": {"table_name": "orders", "col_name": "category", "is_measure": False}}
    pos = Position(x=0, y=0, w=400, h=300)
    obj = json.loads(render_visual("v1", pv, pos, 0, field_lookup=lookup))
    proj = obj["visual"]["query"]["queryState"]["Category"]["projections"][0]
    field_def = proj["field"]
    assert "Column" in field_def, "dimension must use Column not Measure"
    src_ref = field_def["Column"]["Expression"]["SourceRef"]
    assert src_ref.get("Entity") == "orders", "must use Entity key"
    assert "Source" not in src_ref, "must not use Source key"
    assert field_def["Column"]["Property"] == "category"


def test_projection_has_query_ref_and_active():
    pv = PbirVisual(
        visual_type="clusteredBarChart",
        encoding_bindings=(
            EncodingBinding(channel="Y", source_field_id="usr_calc_01_qk"),
        ),
        format={},
    )
    lookup = {"usr_calc_01_qk": {"table_name": "orders", "col_name": "DeltaOrder", "is_measure": True}}
    pos = Position(x=0, y=0, w=400, h=300)
    obj = json.loads(render_visual("v1", pv, pos, 0, field_lookup=lookup))
    proj = obj["visual"]["query"]["queryState"]["Y"]["projections"][0]
    assert proj.get("queryRef") == "orders.DeltaOrder"
    assert proj.get("active") is True
    assert "Measure" in proj["field"]
    assert proj["field"]["Measure"]["Expression"]["SourceRef"]["Entity"] == "orders"
    assert proj["field"]["Measure"]["Property"] == "DeltaOrder"


def test_visual_json_has_position_and_query():
    pos = Position(x=10, y=20, w=400, h=300)
    out = render_visual(visual_id="v1", pbir_visual=_bar_visual(), position=pos, z_order=0)
    obj = json.loads(out)
    assert obj["name"] == "v1"
    assert obj["position"]["x"] == 10
    assert obj["position"]["width"] == 400
    assert obj["visual"]["visualType"] == "clusteredBarChart"
    assert any("Region" in str(p) for p in obj["visual"]["query"]["queryState"]["Category"]["projections"])
