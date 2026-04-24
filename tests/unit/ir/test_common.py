"""Unit tests for IR common types."""
from __future__ import annotations

import pytest

from tableau2pbir.ir.common import FieldRef, UnsupportedItem
from tableau2pbir.ir.version import IR_SCHEMA_VERSION


def test_ir_schema_version_is_semver_1_0_0():
    assert IR_SCHEMA_VERSION == "1.0.0"


def test_field_ref_accepts_table_and_column():
    ref = FieldRef(table_id="orders", column_id="customer_id")
    assert ref.table_id == "orders"
    assert ref.column_id == "customer_id"


def test_unsupported_item_captures_source_excerpt():
    item = UnsupportedItem(
        object_kind="mark",
        object_id="sheet_42::polygon",
        source_excerpt="<mark class='Polygon'/>",
        reason="polygon marks not mapped",
        code="unsupported_mark_polygon",
    )
    assert item.object_kind == "mark"
    assert item.code == "unsupported_mark_polygon"


def test_unsupported_item_rejects_missing_fields():
    with pytest.raises(Exception):
        UnsupportedItem()  # type: ignore[call-arg]
