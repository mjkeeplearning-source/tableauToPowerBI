from tableau2pbir.emit.pbir.filters import collect_page_filters
from tableau2pbir.ir.common import FieldRef
from tableau2pbir.ir.sheet import CategoricalFilter, RangeFilter


def test_dedupes_filters_across_sheets_of_same_page():
    f1 = CategoricalFilter(id="f1", field=FieldRef(table_id="Sales", column_id="Region"),
                           include=("West", "East"))
    f2 = CategoricalFilter(id="f2", field=FieldRef(table_id="Sales", column_id="Region"),
                           include=("West", "East"))
    out = collect_page_filters([(("s1",), [f1]), (("s2",), [f2])])
    assert len(out) == 0  # placeholder: _filter_to_pbir returns None until Task 7


def test_unique_filters_kept():
    f1 = CategoricalFilter(id="f1", field=FieldRef(table_id="Sales", column_id="Region"),
                           include=("West",))
    f2 = RangeFilter(id="f2", field=FieldRef(table_id="Sales", column_id="Year"))
    out = collect_page_filters([(("s1",), [f1]), (("s2",), [f2])])
    assert len(out) == 0  # placeholder: _filter_to_pbir returns None until Task 7
