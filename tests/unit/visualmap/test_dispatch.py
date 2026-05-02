"""Dispatch maps Tableau (mark_type, shelf_signature) to PBIR visual_type
+ channel bindings. shelf_signature is a tuple summarizing which shelves
are bound: ('rows', 'cols', 'color'?, ...)."""
from __future__ import annotations

from tableau2pbir.ir.common import FieldRef
from tableau2pbir.ir.sheet import Encoding, Sheet
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
