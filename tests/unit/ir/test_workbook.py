from __future__ import annotations

from tableau2pbir.ir.version import IR_SCHEMA_VERSION
from tableau2pbir.ir.workbook import DataModel, Workbook


def test_empty_workbook_stamps_schema_version():
    wb = Workbook(
        ir_schema_version=IR_SCHEMA_VERSION,
        source_path="fixtures/trivial.twb",
        source_hash="abc123",
        tableau_version="2024.1",
        config={},
        data_model=DataModel(),
        sheets=(), dashboards=(), unsupported=(),
    )
    assert wb.ir_schema_version == "1.0.0"
    assert wb.data_model.datasources == ()


def test_workbook_round_trip_json():
    wb = Workbook(
        ir_schema_version=IR_SCHEMA_VERSION,
        source_path="fixtures/trivial.twb",
        source_hash="abc123",
        tableau_version="2024.1",
        config={},
        data_model=DataModel(),
        sheets=(), dashboards=(), unsupported=(),
    )
    as_json = wb.model_dump_json()
    wb2 = Workbook.model_validate_json(as_json)
    assert wb2 == wb
