"""Dispatch maps Tableau (mark_type, shelf_signature) to PBIR visual_type
+ channel bindings. shelf_signature is a tuple summarizing which shelves
are bound: ('rows', 'cols', 'color'?, ...)."""
from __future__ import annotations

from tableau2pbir.ir.common import FieldRef
from tableau2pbir.ir.sheet import Encoding, VisualFormat, Sheet
from tableau2pbir.visualmap.dispatch import dispatch_visual


def _sheet(mark: str, *, rows=(), cols=(), color=None) -> Sheet:
    return Sheet(
        id="s1", name="S", datasource_refs=("ds1",),
        mark_type=mark,
        encoding=Encoding(rows=rows, columns=cols, color=color),
        filters=(), sort=(), dual_axis=False, reference_lines=(),
        uses_calculations=(),
    )


def _fr(col: str) -> FieldRef:
    return FieldRef(table_id="t", column_id=col)


def test_bar_with_ambiguous_roles_emits_column_chart():
    """Without _qk/_nk suffixes the dispatch defaults to columnChart (vertical bar)."""
    sh = _sheet("bar", rows=(_fr("sales"),), cols=(_fr("region"),))
    pv = dispatch_visual(sh)
    assert pv is not None
    assert pv.visual_type == "columnChart"
    channels = {b.channel for b in pv.encoding_bindings}
    assert "Category" in channels and "Y" in channels


def test_bar_emits_pbi_channel_names():
    sh = _sheet("bar", rows=(_fr("sales"),), cols=(_fr("region"),))
    pv = dispatch_visual(sh)
    assert pv is not None
    channels = {b.channel for b in pv.encoding_bindings}
    assert "Category" in channels and "Y" in channels
    assert "category" not in channels and "value" not in channels


def test_bar_assigns_cols_to_category_and_rows_to_y():
    """Tableau vertical bar: COLUMNS=dimension→Category, ROWS=measure→Y."""
    sh = _sheet("bar", rows=(_fr("sales"),), cols=(_fr("region"),))
    pv = dispatch_visual(sh)
    cat = next(b.source_field_id for b in pv.encoding_bindings if b.channel == "Category")
    y_val = next(b.source_field_id for b in pv.encoding_bindings if b.channel == "Y")
    assert cat == "region"
    assert y_val == "sales"


# --- Bug 1: correct visual types based on pill role suffixes ---

def test_vertical_bar_dim_on_cols_measure_on_rows_emits_column_chart():
    """COLUMNS=dimension(_nk), ROWS=measure(_qk) → columnChart (vertical bars)."""
    sh = _sheet("automatic", rows=(_fr("sales_qk"),), cols=(_fr("region_nk"),))
    pv = dispatch_visual(sh)
    assert pv is not None
    assert pv.visual_type == "columnChart"


def test_horizontal_bar_measure_on_cols_dim_on_rows_emits_bar_chart():
    """COLUMNS=measure(_qk), ROWS=dimension(_nk) → barChart (horizontal bars)."""
    sh = _sheet("automatic", rows=(_fr("region_nk"),), cols=(_fr("sales_qk"),))
    pv = dispatch_visual(sh)
    assert pv is not None
    assert pv.visual_type == "barChart"


# --- Bug 2: correct channel assignment for horizontal bar ---

def test_horizontal_bar_category_is_rows_field_not_cols():
    """For barChart: dimension from ROWS shelf → Category; measure from COLS → Y."""
    sh = _sheet("automatic", rows=(_fr("region_nk"),), cols=(_fr("sales_qk"),))
    pv = dispatch_visual(sh)
    assert pv is not None
    cat = next(b.source_field_id for b in pv.encoding_bindings if b.channel == "Category")
    y_val = next(b.source_field_id for b in pv.encoding_bindings if b.channel == "Y")
    assert cat == "region_nk"   # dimension from ROWS
    assert y_val == "sales_qk"  # measure from COLS


def test_line_emits_pbi_channel_names():
    sh = _sheet("line", rows=(_fr("sales"),), cols=(_fr("date"),))
    pv = dispatch_visual(sh)
    assert pv is not None
    channels = {b.channel for b in pv.encoding_bindings}
    assert "Category" in channels and "Y" in channels


def test_scatter_emits_pbi_channel_names():
    sh = _sheet("circle", rows=(_fr("profit"),), cols=(_fr("sales"),))
    pv = dispatch_visual(sh)
    assert pv is not None
    channels = {b.channel for b in pv.encoding_bindings}
    assert "X" in channels and "Y" in channels


def test_line_chart():
    sh = _sheet("line", rows=(_fr("sales"),), cols=(_fr("date"),))
    pv = dispatch_visual(sh)
    assert pv is not None and pv.visual_type == "lineChart"


def test_pie_with_color_dim_and_measure_size():
    sh = _sheet("pie", rows=(_fr("sales"),), color=_fr("region"))
    pv = dispatch_visual(sh)
    assert pv is not None and pv.visual_type == "pieChart"


def test_text_mark_to_table():
    sh = _sheet("text", rows=(_fr("sales"),), cols=(_fr("region"),))
    pv = dispatch_visual(sh)
    assert pv is not None and pv.visual_type == "tableEx"


def test_unsupported_mark_returns_none():
    sh = _sheet("polygon", rows=(_fr("x"),))
    assert dispatch_visual(sh) is None


def test_column_chart_multi_measure_rows_all_bound_to_y():
    """Two measures on ROWS shelf must both appear in Y channel — not just the first."""
    sh = _sheet("automatic", rows=(_fr("sum_profit_qk"), _fr("sum_sales_qk")), cols=(_fr("region_nk"),))
    pv = dispatch_visual(sh)
    assert pv is not None
    assert pv.visual_type == "columnChart"
    y_fields = [b.source_field_id for b in pv.encoding_bindings if b.channel == "Y"]
    assert "sum_profit_qk" in y_fields
    assert "sum_sales_qk" in y_fields
    assert len(y_fields) == 2


def test_line_chart_multi_measure_rows_all_bound_to_y():
    """Two measures on ROWS shelf of a line chart must both appear in Y channel."""
    sh = _sheet("line", rows=(_fr("sum_sales_qk"), _fr("sum_profit_qk")), cols=(_fr("date_nk"),))
    pv = dispatch_visual(sh)
    assert pv is not None
    assert pv.visual_type == "lineChart"
    y_fields = [b.source_field_id for b in pv.encoding_bindings if b.channel == "Y"]
    assert "sum_sales_qk" in y_fields
    assert "sum_profit_qk" in y_fields
    assert len(y_fields) == 2


def test_horizontal_bar_multi_measure_cols_all_bound_to_y():
    """Two measures on COLS shelf of a horizontal bar chart must both appear in Y channel."""
    sh = _sheet("automatic", rows=(_fr("region_nk"),), cols=(_fr("sum_sales_qk"), _fr("sum_profit_qk")))
    pv = dispatch_visual(sh)
    assert pv is not None
    assert pv.visual_type == "barChart"
    y_fields = [b.source_field_id for b in pv.encoding_bindings if b.channel == "Y"]
    assert "sum_sales_qk" in y_fields
    assert "sum_profit_qk" in y_fields
    assert len(y_fields) == 2


# --- VisualFormat / format objects ---

def _sheet_with_style(mark: str, *, rows=(), cols=(), color=None,
                      visual_format: VisualFormat | None = None) -> Sheet:
    return Sheet(
        id="s1", name="S", datasource_refs=("ds1",),
        mark_type=mark,
        encoding=Encoding(rows=rows, columns=cols, color=color),
        filters=(), sort=(), dual_axis=False, reference_lines=(),
        uses_calculations=(), visual_format=visual_format,
    )


def test_dispatch_no_mark_style_produces_none_visual_format():
    sh = _sheet_with_style("bar", rows=(_fr("sales"),), cols=(_fr("region"),))
    pv = dispatch_visual(sh)
    assert pv is not None
    assert pv.visual_format is None


def test_dispatch_labels_show_passes_visual_format_through():
    vf = VisualFormat(labels_show=True)
    sh = _sheet_with_style("bar", rows=(_fr("sales"),), cols=(_fr("region"),),
                           visual_format=vf)
    pv = dispatch_visual(sh)
    assert pv is not None
    assert pv.visual_format is vf
    assert pv.visual_format.labels_show is True


def test_dispatch_mark_color_passes_visual_format_through():
    vf = VisualFormat(mark_color="#e15759")
    sh = _sheet_with_style("bar", rows=(_fr("sales"),), cols=(_fr("region"),),
                           visual_format=vf)
    pv = dispatch_visual(sh)
    assert pv is not None
    assert pv.visual_format is vf
    assert pv.visual_format.mark_color == "#e15759"


def test_dispatch_both_labels_and_color_passes_visual_format_through():
    vf = VisualFormat(mark_color="#ffaa7f", labels_show=True)
    sh = _sheet_with_style("automatic", rows=(_fr("sales_qk"),), cols=(_fr("region_nk"),),
                           visual_format=vf)
    pv = dispatch_visual(sh)
    assert pv is not None
    assert pv.visual_format is vf
    assert pv.visual_format.labels_show is True
    assert pv.visual_format.mark_color == "#ffaa7f"


def test_dispatch_labels_false_passes_visual_format_through():
    vf = VisualFormat(labels_show=False, mark_color=None)
    sh = _sheet_with_style("bar", rows=(_fr("sales"),), cols=(_fr("region"),),
                           visual_format=vf)
    pv = dispatch_visual(sh)
    assert pv is not None
    assert pv.visual_format is vf
    assert pv.visual_format.labels_show is False


def test_dispatch_color_none_passes_visual_format_through():
    vf = VisualFormat(labels_show=False, mark_color=None)
    sh = _sheet_with_style("bar", rows=(_fr("sales"),), cols=(_fr("region"),),
                           visual_format=vf)
    pv = dispatch_visual(sh)
    assert pv is not None
    assert pv.visual_format is vf
    assert pv.visual_format.mark_color is None


def test_automatic_dims_only_on_rows_emits_table():
    """Nested-header layout: N dims on rows, no cols → tableEx with Values bindings."""
    sh = _sheet("automatic", rows=(_fr("category_nk"), _fr("sub_category_nk")))
    pv = dispatch_visual(sh)
    assert pv is not None
    assert pv.visual_type == "tableEx"
    channels = [b.channel for b in pv.encoding_bindings]
    assert channels.count("Values") == 2


def test_single_dim_on_rows_no_cols_emits_table():
    """Single dimension with no cols also maps to tableEx."""
    sh = _sheet("automatic", rows=(_fr("product_name_nk"),))
    pv = dispatch_visual(sh)
    assert pv is not None
    assert pv.visual_type == "tableEx"


def test_text_mark_with_text_encoding_includes_text_field_in_values():
    """Text mark with <text> encoding: the text-encoded field must appear in Values."""
    sh = Sheet(
        id="s1", name="S", datasource_refs=("ds1",),
        mark_type="text",
        encoding=Encoding(
            rows=(_fr("category_nk"),),
            text=_fr("profit_qk"),
        ),
        filters=(), sort=(), dual_axis=False, reference_lines=(),
        uses_calculations=(),
    )
    pv = dispatch_visual(sh)
    assert pv is not None
    assert pv.visual_type == "tableEx"
    field_ids = {b.source_field_id for b in pv.encoding_bindings}
    assert "profit_qk" in field_ids, "Text encoding field must appear in Values"
    assert "category_nk" in field_ids


def test_text_mark_computed_sort_wires_sort_into_pbir_visual():
    """dispatch_visual must populate sort_by and add sort-by measure as Values binding."""
    from tableau2pbir.ir.sheet import SortSpec
    sh = Sheet(
        id="s1", name="S", datasource_refs=("ds1",),
        mark_type="text",
        encoding=Encoding(rows=(_fr("category_nk"),), text=_fr("profit_qk")),
        filters=(),
        sort=(SortSpec(field=_fr("category_nk"), direction="desc",
                       sort_by_field=_fr("profit_qk")),),
        dual_axis=False, reference_lines=(), uses_calculations=(),
    )
    pv = dispatch_visual(sh)
    assert pv is not None
    assert len(pv.sort_by) == 1
    assert pv.sort_by[0].field_id == "profit_qk"
    assert pv.sort_by[0].direction == "desc"
    # profit_qk already in Values via enc.text — must not be duplicated
    values_ids = [b.source_field_id for b in pv.encoding_bindings if b.channel == "Values"]
    assert values_ids.count("profit_qk") == 1


def test_text_mark_sort_by_new_measure_added_to_values():
    """When sort_by_field is not in enc.text/rows/cols, it must be added as a Values binding."""
    from tableau2pbir.ir.sheet import SortSpec
    sh = Sheet(
        id="s1", name="S", datasource_refs=("ds1",),
        mark_type="text",
        encoding=Encoding(rows=(_fr("category_nk"),)),  # no enc.text
        filters=(),
        sort=(SortSpec(field=_fr("category_nk"), direction="desc",
                       sort_by_field=_fr("sales_qk")),),
        dual_axis=False, reference_lines=(), uses_calculations=(),
    )
    pv = dispatch_visual(sh)
    assert pv is not None
    values_ids = [b.source_field_id for b in pv.encoding_bindings if b.channel == "Values"]
    assert "sales_qk" in values_ids, "sort-by measure must be added as Values binding"
    assert len(pv.sort_by) == 1
    assert pv.sort_by[0].field_id == "sales_qk"


def test_column_chart_with_computed_sort_emits_sort_by():
    """Sheet with ROWS=measure, COLS=dimension, automatic mark and a computed-sort
    must emit a PbirVisual with sort_by populated."""
    from tableau2pbir.ir.sheet import SortSpec

    sh = Sheet(
        id="s1", name="S1", datasource_refs=("ds1",),
        mark_type="automatic",
        encoding=Encoding(
            rows=(_fr("delta_order_qk"),),
            columns=(_fr("none_category_nk"),),
        ),
        filters=(),
        sort=(
            SortSpec(
                field=_fr("none_category_nk"),
                direction="desc",
                sort_by_field=_fr("delta_order_qk"),
            ),
        ),
        dual_axis=False, reference_lines=(), uses_calculations=(),
    )
    pv = dispatch_visual(sh)
    assert pv is not None
    assert pv.visual_type == "columnChart"
    assert pv.sort_by, "sort_by must not be empty for a computed-sort column chart"
    assert len(pv.sort_by) == 1
    entry = pv.sort_by[0]
    assert entry.field_id == "delta_order_qk"
    assert entry.direction == "desc"
    # The sort field is already in Y — no duplicate binding added
    field_ids = [b.source_field_id for b in pv.encoding_bindings]
    assert field_ids.count("delta_order_qk") == 1, "sort field must not appear twice"
