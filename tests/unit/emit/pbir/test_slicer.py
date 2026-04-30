import json

from tableau2pbir.emit.pbir.slicer import render_filter_slicer, render_parameter_slicer
from tableau2pbir.ir.dashboard import Position


def test_filter_slicer_minimal():
    pos = Position(x=0, y=0, w=200, h=80)
    out = render_filter_slicer(visual_id="s1", source_field_id="Sales.Region", position=pos, z_order=0)
    obj = json.loads(out)
    assert obj["visual"]["visualType"] == "slicer"
    assert "Region" in json.dumps(obj)


def test_parameter_slicer_minimal():
    pos = Position(x=0, y=0, w=200, h=80)
    out = render_parameter_slicer(
        visual_id="ps1", parameter_name="Discount Rate", parameter_intent="numeric_what_if",
        position=pos, z_order=0,
    )
    obj = json.loads(out)
    assert obj["visual"]["visualType"] == "slicer"
    assert "Discount Rate" in json.dumps(obj)
