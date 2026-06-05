from __future__ import annotations

from tableau2pbir.ir.common import FieldRef
from tableau2pbir.ir.sheet import (
    AxisTitle, CategoricalFilter, Encoding, EncodingBinding, Filter,
    PbirVisual, RangeFilter, Sheet, TopNFilter, ContextFilter, ConditionalFilter,
    VisualFormat,
)


def test_sheet_minimal():
    s = Sheet(
        id="sheet1", name="Revenue",
        datasource_refs=("ds1",),
        mark_type="bar",
        encoding=Encoding(
            rows=(FieldRef(table_id="t1", column_id="month"),),
            columns=(FieldRef(table_id="t1", column_id="revenue"),),
        ),
        filters=(),
        sort=(),
        dual_axis=False,
        reference_lines=(),
        uses_calculations=(),
    )
    assert s.mark_type == "bar"
    assert s.encoding.color is None


def test_sheet_with_categorical_filter():
    f = CategoricalFilter(
        id="f1", field=FieldRef(table_id="t1", column_id="region"),
        include=("West", "East"),
    )
    s = Sheet(
        id="sheet2", name="Regional",
        datasource_refs=("ds1",),
        mark_type="bar",
        encoding=Encoding(rows=(), columns=()),
        filters=(f,),
        sort=(), dual_axis=False, reference_lines=(),
        uses_calculations=("calc1",),
    )
    assert s.filters[0].include == ("West", "East")
    assert s.uses_calculations == ("calc1",)


def test_categorical_filter_roundtrip():
    f = CategoricalFilter(
        id="f1", field=FieldRef(table_id="Sales", column_id="Region"),
        include=("East", "West"), exclude=(),
    )
    assert f.kind == "categorical"
    assert f.include == ("East", "West")
    # Pydantic round-trip: serialize → deserialize via the union
    import json
    from pydantic import TypeAdapter
    ta = TypeAdapter(Filter)
    restored = ta.validate_python(json.loads(f.model_dump_json()))
    assert isinstance(restored, CategoricalFilter)
    assert restored.include == ("East", "West")


def test_range_filter_roundtrip():
    f = RangeFilter(
        id="f2", field=FieldRef(table_id="Sales", column_id="Amount"),
        min_val="100", max_val="9999",
    )
    assert f.kind == "range"
    from pydantic import TypeAdapter
    ta = TypeAdapter(Filter)
    restored = ta.validate_python(f.model_dump())
    assert isinstance(restored, RangeFilter)
    assert restored.min_val == "100"


def test_topn_filter_fields():
    f = TopNFilter(
        id="f3", field=FieldRef(table_id="Sales", column_id="Customer"),
        n=10, direction="Top",
        by_field=FieldRef(table_id="Sales", column_id="Revenue"),
        by_agg="SUM",
    )
    assert f.kind == "top_n"
    assert f.n == 10
    assert f.by_agg == "SUM"


def test_context_filter_is_categorical_shaped():
    f = ContextFilter(
        id="f4", field=FieldRef(table_id="Sales", column_id="Year"),
        include=("2023",), exclude=(),
    )
    assert f.kind == "context"


def test_conditional_filter_fields():
    f = ConditionalFilter(
        id="f5", field=FieldRef(table_id="Sales", column_id="Profit"),
        expr="[Profit] > 0",
    )
    assert f.kind == "conditional"
    assert f.expr == "[Profit] > 0"


def test_sheet_accepts_new_filter_subtypes():
    from tableau2pbir.ir.sheet import Sheet, Encoding
    f = RangeFilter(
        id="f6", field=FieldRef(table_id="t1", column_id="price"),
        min_val="10",
    )
    s = Sheet(
        id="sheet3", name="Priced",
        datasource_refs=("ds1",),
        mark_type="bar",
        encoding=Encoding(rows=(), columns=()),
        filters=(f,),
        sort=(), dual_axis=False, reference_lines=(),
        uses_calculations=(),
    )
    assert isinstance(s.filters[0], RangeFilter)


def test_visual_format_defaults():
    vf = VisualFormat()
    assert vf.mark_color is None
    assert vf.labels_show is False


def test_visual_format_with_values():
    vf = VisualFormat(mark_color="#ffaa7f", labels_show=True)
    assert vf.mark_color == "#ffaa7f"
    assert vf.labels_show is True


def test_sheet_visual_format_defaults_to_none():
    s = Sheet(
        id="s1", name="T", datasource_refs=("ds",), mark_type="bar",
        encoding=Encoding(), filters=(), sort=(), dual_axis=False,
        reference_lines=(), uses_calculations=(),
    )
    assert s.visual_format is None


def test_pbir_visual_format_accepts_objects_structure():
    """PbirVisual.format must accept the PBIR DataViewObjectDefinitions shape."""
    pv = PbirVisual(
        visual_type="barChart",
        encoding_bindings=(EncodingBinding(channel="Y", source_field_id="sales"),),
        format={
            "labels": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}],
            "dataPoint": [{"properties": {"fill": {"solid": {"color": {"expr": {"Literal": {"Value": "'#ffaa7f'"}}}}}}}],
        },
    )
    assert "labels" in pv.format
    assert "dataPoint" in pv.format


def test_axis_title_model_fields():
    at = AxisTitle(field_id="sum_profit_qk", scope="rows", title="#  Profit")
    assert at.field_id == "sum_profit_qk"
    assert at.scope == "rows"
    assert at.title == "#  Profit"


def test_visual_format_axis_titles_defaults_empty():
    vf = VisualFormat()
    assert vf.axis_titles == ()


def test_visual_format_axis_titles_accepts_tuple():
    at = AxisTitle(field_id="sum_sales_qk", scope="rows", title="#  Revenue")
    vf = VisualFormat(axis_titles=(at,))
    assert len(vf.axis_titles) == 1
    assert vf.axis_titles[0].title == "#  Revenue"
