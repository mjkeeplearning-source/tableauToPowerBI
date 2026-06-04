import json

from tableau2pbir.emit.pbir.slicer import render_filter_slicer, render_parameter_slicer
from tableau2pbir.ir.dashboard import Position


def test_filter_slicer_minimal():
    """Backward-compat: no field_lookup still produces a slicer (fallback binding)."""
    pos = Position(x=0, y=0, w=200, h=80)
    out = render_filter_slicer(visual_id="s1", source_field_id="Sales.Region", position=pos, z_order=0)
    obj = json.loads(out)
    assert obj["visual"]["visualType"] == "slicer"
    assert "Region" in json.dumps(obj)


def test_filter_slicer_with_lookup_uses_column_type():
    """With field_lookup, a dimension field must use Column (not Measure) type."""
    pos = Position(x=0, y=0, w=200, h=150)
    lookup = {"people__col__region": {
        "table_name": "people", "col_name": "region", "is_measure": False,
    }}
    out = render_filter_slicer(
        visual_id="s1",
        source_field_id="people__col__region",
        position=pos,
        z_order=2,
        field_lookup=lookup,
    )
    obj = json.loads(out)
    proj = obj["visual"]["query"]["queryState"]["Values"]["projections"][0]
    field = proj["field"]
    assert "Column" in field, "dimension must bind as Column, not Measure"
    assert field["Column"]["Expression"]["SourceRef"]["Entity"] == "people"
    assert field["Column"]["Property"] == "region"
    assert proj["queryRef"] == "people.region"


def test_filter_slicer_drills_other_visuals():
    """drillFilterOtherVisuals must be True — this is what makes the slicer filter the page."""
    pos = Position(x=0, y=0, w=200, h=150)
    out = render_filter_slicer(visual_id="s1", source_field_id="x", position=pos, z_order=0)
    obj = json.loads(out)
    assert obj["visual"].get("drillFilterOtherVisuals") is True


def test_filter_slicer_has_basic_mode_object():
    """Slicer objects must include data.mode = 'Basic'."""
    pos = Position(x=0, y=0, w=200, h=150)
    out = render_filter_slicer(visual_id="s1", source_field_id="x", position=pos, z_order=0)
    obj = json.loads(out)
    data_obj = obj["visual"]["objects"]["data"]
    mode = data_obj[0]["properties"]["mode"]["expr"]["Literal"]["Value"]
    assert mode == "'Basic'"


def test_filter_slicer_has_selection_multiselect_enabled():
    """Slicer selection must allow multi-select with Select All checkbox."""
    pos = Position(x=0, y=0, w=200, h=150)
    out = render_filter_slicer(visual_id="s1", source_field_id="x", position=pos, z_order=0)
    obj = json.loads(out)
    sel = obj["visual"]["objects"]["selection"][0]["properties"]
    assert sel["singleSelect"]["expr"]["Literal"]["Value"] == "false"
    assert sel["strictSingleSelect"]["expr"]["Literal"]["Value"] == "false"
    assert sel["selectAllCheckboxEnabled"]["expr"]["Literal"]["Value"] == "true"


def test_parameter_slicer_minimal():
    pos = Position(x=0, y=0, w=200, h=80)
    out = render_parameter_slicer(
        visual_id="ps1", parameter_name="Discount Rate", parameter_intent="numeric_what_if",
        position=pos, z_order=0,
    )
    obj = json.loads(out)
    assert obj["visual"]["visualType"] == "slicer"
    assert "Discount Rate" in json.dumps(obj)
