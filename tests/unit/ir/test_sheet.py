from __future__ import annotations

from tableau2pbir.ir.common import FieldRef
from tableau2pbir.ir.sheet import Encoding, Filter, Sheet


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
        format=None,
        uses_calculations=(),
    )
    assert s.mark_type == "bar"
    assert s.encoding.color is None


def test_sheet_with_categorical_filter():
    f = Filter(
        id="f1", kind="categorical", field=FieldRef(table_id="t1", column_id="region"),
        include=("West", "East"), exclude=(), expr=None,
    )
    s = Sheet(
        id="sheet2", name="Regional",
        datasource_refs=("ds1",),
        mark_type="bar",
        encoding=Encoding(rows=(), columns=()),
        filters=(f,),
        sort=(), dual_axis=False, reference_lines=(),
        format=None, uses_calculations=("calc1",),
    )
    assert s.filters[0].include == ("West", "East")
    assert s.uses_calculations == ("calc1",)
