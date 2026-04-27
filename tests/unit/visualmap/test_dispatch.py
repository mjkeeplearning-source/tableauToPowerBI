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


def test_bar_with_dim_on_rows_and_measure_on_cols():
    sh = _sheet("bar", rows=(_fr("region"),), cols=(_fr("sales"),))
    pv = dispatch_visual(sh)
    assert pv is not None
    assert pv.visual_type == "clusteredBarChart"
    channels = {b.channel for b in pv.encoding_bindings}
    assert "category" in channels and "value" in channels


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
