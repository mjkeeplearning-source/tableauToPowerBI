from tableau2pbir.emit.pbir.filters import collect_page_filters
from tableau2pbir.ir.common import FieldRef
from tableau2pbir.ir.sheet import Filter


def test_dedupes_filters_across_sheets_of_same_page():
    f1 = Filter(id="f1", kind="categorical", field=FieldRef(table_id="Sales", column_id="Region"),
                include=("West", "East"))
    f2 = Filter(id="f2", kind="categorical", field=FieldRef(table_id="Sales", column_id="Region"),
                include=("West", "East"))
    out = collect_page_filters([(("s1",), [f1]), (("s2",), [f2])])
    assert len(out) == 1


def test_unique_filters_kept():
    f1 = Filter(id="f1", kind="categorical", field=FieldRef(table_id="Sales", column_id="Region"),
                include=("West",))
    f2 = Filter(id="f2", kind="range", field=FieldRef(table_id="Sales", column_id="Year"))
    out = collect_page_filters([(("s1",), [f1]), (("s2",), [f2])])
    assert len(out) == 2
