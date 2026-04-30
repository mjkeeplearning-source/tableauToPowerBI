from tableau2pbir.emit.pbir.blocked import compute_blocked_visuals
from tableau2pbir.ir.common import UnsupportedItem


def test_visual_backed_by_deferred_calc_is_blocked():
    rendered = [{
        "page_id": "p1", "visual_id": "v1", "sheet_id": "s1",
        "field_ids": ("calc_table_calc_42",),
    }]
    unsupported = (
        UnsupportedItem(
            object_kind="calculation", object_id="calc_table_calc_42",
            source_excerpt="WINDOW_SUM", reason="deferred to v1.1",
            code="deferred_feature_table_calcs",
        ),
    )
    out = compute_blocked_visuals(rendered, unsupported, datasource_tier_by_field={})
    assert out == [{"page_id": "p1", "visual_id": "v1", "blocked_by": ["calc_table_calc_42"]}]


def test_visual_backed_by_tier4_is_blocked():
    rendered = [{
        "page_id": "p1", "visual_id": "v1", "sheet_id": "s1",
        "field_ids": ("col_xyz",),
    }]
    out = compute_blocked_visuals(rendered, (), datasource_tier_by_field={"col_xyz": 4})
    assert out == [{"page_id": "p1", "visual_id": "v1", "blocked_by": ["tier4_datasource"]}]


def test_clean_visual_not_blocked():
    rendered = [{"page_id": "p1", "visual_id": "v1", "sheet_id": "s1", "field_ids": ("col_a",)}]
    out = compute_blocked_visuals(rendered, (), datasource_tier_by_field={"col_a": 1})
    assert out == []
