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


def test_visual_json_has_position_and_query():
    pos = Position(x=10, y=20, w=400, h=300)
    out = render_visual(visual_id="v1", pbir_visual=_bar_visual(), position=pos, z_order=0)
    obj = json.loads(out)
    assert obj["name"] == "v1"
    assert obj["position"]["x"] == 10
    assert obj["position"]["width"] == 400
    assert obj["visual"]["visualType"] == "clusteredBarChart"
    assert any("Region" in str(p) for p in obj["visual"]["query"]["queryState"]["Category"]["projections"])
