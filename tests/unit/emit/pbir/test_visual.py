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


def test_projection_uses_measure_name_not_col_name_for_aggregated_field():
    """When field_lookup contains measure_name, Property and queryRef must use it."""
    pv = PbirVisual(
        visual_type="columnChart",
        encoding_bindings=(
            EncodingBinding(channel="Y", source_field_id="sum_profit_qk"),
        ),
        format={},
    )
    lookup = {
        "sum_profit_qk": {
            "table_name": "orders",
            "col_name": "profit",
            "measure_name": "Sum profit",
            "is_measure": True,
        }
    }
    pos = Position(x=0, y=0, w=400, h=300)
    obj = json.loads(render_visual("v1", pv, pos, 0, field_lookup=lookup))
    proj = obj["visual"]["query"]["queryState"]["Y"]["projections"][0]
    assert proj["field"]["Measure"]["Property"] == "Sum profit"
    assert proj["queryRef"] == "orders.Sum profit"


def test_visual_json_has_position_and_query():
    pos = Position(x=10, y=20, w=400, h=300)
    out = render_visual(visual_id="v1", pbir_visual=_bar_visual(), position=pos, z_order=0)
    obj = json.loads(out)
    assert obj["name"] == "v1"
    assert obj["position"]["x"] == 10
    assert obj["position"]["width"] == 400
    assert obj["visual"]["visualType"] == "clusteredBarChart"
    assert any("Region" in str(p) for p in obj["visual"]["query"]["queryState"]["Category"]["projections"])


def test_render_visual_emits_sort_definition_when_present():
    """When PbirVisual.sort_by is set, visual.query.sortDefinition must be emitted."""
    import json
    from tableau2pbir.ir.dashboard import Position
    from tableau2pbir.emit.pbir.visual import render_visual
    from tableau2pbir.ir.sheet import EncodingBinding, PbirVisual, VisualSortEntry

    pv = PbirVisual(
        visual_type="tableEx",
        encoding_bindings=(
            EncodingBinding(channel="Values", source_field_id="category_nk"),
            EncodingBinding(channel="Values", source_field_id="profit_qk"),
        ),
        sort_by=(
            VisualSortEntry(field_id="profit_qk", direction="desc"),
        ),
    )
    pos = Position(x=0, y=0, w=800, h=600)
    field_lookup = {
        "category_nk": {"table_name": "orders", "col_name": "category", "is_measure": False},
        "profit_qk": {"table_name": "orders", "col_name": "profit", "is_measure": True,
                      "measure_name": "Sum profit"},
    }
    obj = json.loads(render_visual("v1", pv, pos, 0, field_lookup))
    sort_def = obj["visual"]["query"].get("sortDefinition")
    assert sort_def is not None, "sortDefinition must be present in query"
    assert sort_def["isDefaultSort"] is False
    sort = sort_def["sort"]
    assert len(sort) == 1
    entry = sort[0]
    assert entry["direction"] == "Descending"
    assert entry["field"]["Measure"]["Property"] == "Sum profit"
    assert entry["field"]["Measure"]["Expression"]["SourceRef"]["Entity"] == "orders"


def test_render_visual_no_sort_definition_when_empty():
    """When PbirVisual.sort_by is empty, sortDefinition must not appear in query."""
    import json
    from tableau2pbir.ir.dashboard import Position
    from tableau2pbir.emit.pbir.visual import render_visual
    from tableau2pbir.ir.sheet import EncodingBinding, PbirVisual

    pv = PbirVisual(
        visual_type="columnChart",
        encoding_bindings=(
            EncodingBinding(channel="Category", source_field_id="region_nk"),
            EncodingBinding(channel="Y", source_field_id="sales_qk"),
        ),
    )
    pos = Position(x=0, y=0, w=800, h=600)
    obj = json.loads(render_visual("v1", pv, pos, 0, {}))
    assert "sortDefinition" not in obj["visual"]["query"]


def test_visual_container_objects_emitted_when_title_set():
    from tableau2pbir.ir.sheet import AxisTitleFormat, TableFormat, TitleFormat, VisualFormat

    vf = VisualFormat(title=TitleFormat(
        text="Category Based  Profit",
        font_name="Verdana",
        font_size=20,
    ))
    pv = PbirVisual(
        visual_type="tableEx",
        encoding_bindings=(EncodingBinding(channel="Values", source_field_id="orders.category"),),
        visual_format=vf,
    )
    pos = Position(x=0, y=0, w=400, h=300)
    obj = json.loads(render_visual("v1", pv, pos, 0))
    vco = obj["visual"]["visualContainerObjects"]
    assert vco["title"][0]["properties"]["text"]["expr"]["Literal"]["Value"] == "'Category Based  Profit'"
    assert vco["title"][0]["properties"]["fontSize"]["expr"]["Literal"]["Value"] == "20D"


def test_visual_container_objects_absent_when_no_title():
    from tableau2pbir.ir.sheet import VisualFormat

    pv = PbirVisual(
        visual_type="columnChart",
        encoding_bindings=(EncodingBinding(channel="Category", source_field_id="orders.category"),),
        visual_format=None,
    )
    pos = Position(x=0, y=0, w=400, h=300)
    obj = json.loads(render_visual("v1", pv, pos, 0))
    assert "visualContainerObjects" not in obj["visual"]


def test_projection_format_added_when_number_format_present():
    from tableau2pbir.ir.sheet import VisualFormat

    vf = VisualFormat(number_formats={"orders_profit_qk": r"\$#,0.00;(\$#,0.00);\$#,0.00"})
    pv = PbirVisual(
        visual_type="tableEx",
        encoding_bindings=(EncodingBinding(channel="Values", source_field_id="orders_profit_qk"),),
        visual_format=vf,
    )
    lookup = {"orders_profit_qk": {"table_name": "orders", "col_name": "profit", "is_measure": True}}
    pos = Position(x=0, y=0, w=400, h=300)
    obj = json.loads(render_visual("v1", pv, pos, 0, field_lookup=lookup))
    proj = obj["visual"]["query"]["queryState"]["Values"]["projections"][0]
    assert proj["format"] == r"\$#,0.00;(\$#,0.00);\$#,0.00"


def test_projection_format_absent_when_no_number_format():
    pv = PbirVisual(
        visual_type="columnChart",
        encoding_bindings=(EncodingBinding(channel="Y", source_field_id="orders.revenue"),),
        visual_format=None,
    )
    pos = Position(x=0, y=0, w=400, h=300)
    obj = json.loads(render_visual("v1", pv, pos, 0))
    proj = obj["visual"]["query"]["queryState"]["Y"]["projections"][0]
    assert "format" not in proj


def test_category_axis_objects_emitted_for_chart():
    from tableau2pbir.ir.sheet import AxisTitleFormat, VisualFormat

    vf = VisualFormat(axis=AxisTitleFormat(font_name="Verdana", font_size=16))
    pv = PbirVisual(
        visual_type="columnChart",
        encoding_bindings=(EncodingBinding(channel="Category", source_field_id="orders.category"),),
        visual_format=vf,
    )
    pos = Position(x=0, y=0, w=400, h=300)
    obj = json.loads(render_visual("v1", pv, pos, 0))
    objects = obj["visual"]["objects"]
    assert "categoryAxis" in objects
    assert "valueAxis" in objects


def test_table_column_headers_emitted_for_tableex():
    from tableau2pbir.ir.sheet import TableFormat, VisualFormat

    vf = VisualFormat(table=TableFormat(header_font_name="Arial Black", header_font_size=13))
    pv = PbirVisual(
        visual_type="tableEx",
        encoding_bindings=(EncodingBinding(channel="Values", source_field_id="orders.category"),),
        visual_format=vf,
    )
    pos = Position(x=0, y=0, w=400, h=300)
    obj = json.loads(render_visual("v1", pv, pos, 0))
    assert "columnHeaders" in obj["visual"]["objects"]


def test_existing_format_dict_still_works():
    """Backward compat: PbirVisual.format={...} still emitted when visual_format is None."""
    pv = PbirVisual(
        visual_type="clusteredBarChart",
        encoding_bindings=(EncodingBinding(channel="Category", source_field_id="orders.region"),),
        format={"labels": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}]},
        visual_format=None,
    )
    pos = Position(x=0, y=0, w=400, h=300)
    obj = json.loads(render_visual("v1", pv, pos, 0))
    assert obj["visual"]["objects"]["labels"][0]["properties"]["show"]["expr"]["Literal"]["Value"] == "true"


def test_visual_objects_populated_from_format():
    """When PbirVisual.format is non-empty, render_visual must emit it under 'objects'."""
    pv = PbirVisual(
        visual_type="barChart",
        encoding_bindings=(EncodingBinding(channel="Y", source_field_id="sales"),),
        format={
            "labels": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}],
            "dataPoint": [{"properties": {"fill": {"solid": {"color": {"expr": {"Literal": {"Value": "'#e15759'"}}}}}}}],
        },
    )
    pos = Position(x=0, y=0, w=400, h=300)
    obj = json.loads(render_visual("v1", pv, pos, 0))
    objects = obj["visual"]["objects"]
    assert "labels" in objects
    assert "dataPoint" in objects
    assert objects["labels"][0]["properties"]["show"]["expr"]["Literal"]["Value"] == "true"
    assert objects["dataPoint"][0]["properties"]["fill"]["solid"]["color"]["expr"]["Literal"]["Value"] == "'#e15759'"
