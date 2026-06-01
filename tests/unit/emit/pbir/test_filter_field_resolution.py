"""collect_page_filters must resolve filter column_id → TMDL name via field_lookup."""
from __future__ import annotations

from tableau2pbir.emit.pbir.filters import collect_page_filters
from tableau2pbir.ir.common import FieldRef
from tableau2pbir.ir.sheet import CategoricalFilter, RangeFilter


def _make_field_lookup(col_id: str, table_name: str, col_name: str) -> dict:
    return {col_id: {"table_name": table_name, "col_name": col_name,
                     "is_measure": False, "measure_name": col_name}}


def test_collect_page_filters_resolves_entity_and_property_via_field_lookup():
    """Pill slug 'none_sub_category_nk' → Entity='orders', Property='sub_category'."""
    f = CategoricalFilter(
        id="filter__s1_0",
        field=FieldRef(table_id="tbl__orders", column_id="none_sub_category_nk"),
        include=("Accessories",),
        exclude=(),
    )
    lookup = _make_field_lookup("none_sub_category_nk", "orders", "sub_category")
    result = collect_page_filters([(("s1",), [f])], lookup)
    assert len(result) == 1
    container = result[0]
    assert container["field"]["Column"]["Expression"]["SourceRef"]["Entity"] == "orders"
    assert container["field"]["Column"]["Property"] == "sub_category"
    where_col = container["filter"]["Where"][0]["Condition"]["In"]["Expressions"][0]
    assert where_col["Column"]["Property"] == "sub_category"


def test_collect_page_filters_resolves_range_filter_via_field_lookup():
    """Range filter also resolves Entity and Property via field_lookup."""
    f = RangeFilter(
        id="filter__s1_0",
        field=FieldRef(table_id="tbl__orders", column_id="none_sales_qk"),
        min_val="100",
        max_val=None,
        agg_prefix=None,
    )
    lookup = _make_field_lookup("none_sales_qk", "orders", "sales")
    result = collect_page_filters([(("s1",), [f])], lookup)
    assert len(result) == 1
    container = result[0]
    assert container["field"]["Column"]["Expression"]["SourceRef"]["Entity"] == "orders"
    assert container["field"]["Column"]["Property"] == "sales"


def test_collect_page_filters_without_lookup_uses_column_id_as_is():
    """Without field_lookup, column_id is used unchanged (plain TMDL column names)."""
    f = CategoricalFilter(
        id="f1",
        field=FieldRef(table_id="tbl__orders", column_id="sub_category"),
        include=("Accessories",),
        exclude=(),
    )
    result = collect_page_filters([(("s1",), [f])])
    assert len(result) == 1
    assert result[0]["field"]["Column"]["Property"] == "sub_category"


def test_collect_page_filters_lookup_miss_falls_back_to_column_id():
    """If field_lookup provided but column_id not in it, fall back to column_id."""
    f = CategoricalFilter(
        id="f1",
        field=FieldRef(table_id="tbl__orders", column_id="unknown_col"),
        include=("X",),
        exclude=(),
    )
    lookup = _make_field_lookup("other_col", "orders", "other")
    result = collect_page_filters([(("s1",), [f])], lookup)
    assert len(result) == 1
    # Falls back to the raw column_id and table_id
    assert result[0]["field"]["Column"]["Property"] == "unknown_col"
