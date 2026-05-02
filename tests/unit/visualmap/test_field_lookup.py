from __future__ import annotations

from tableau2pbir.ir.calculation import Calculation, CalculationKind, CalculationPhase, CalculationScope
from tableau2pbir.ir.common import FieldRef
from tableau2pbir.ir.datasource import ConnectorTier, Datasource
from tableau2pbir.ir.model import Column, ColumnKind, ColumnRole, Table
from tableau2pbir.ir.sheet import Encoding, Sheet
from tableau2pbir.ir.workbook import DataModel, Workbook
from tableau2pbir.visualmap.field_lookup import build_field_lookup


def _make_wb() -> Workbook:
    col_cat = Column(
        id="tbl__orders__col__category", name="category",
        datatype="string", role=ColumnRole.DIMENSION, kind=ColumnKind.RAW,
    )
    col_calc = Column(
        id="tbl__orders__col__calculation_01", name="Calculation_01",
        datatype="double", role=ColumnRole.MEASURE, kind=ColumnKind.CALCULATED,
    )
    table = Table(
        id="tbl__orders", name="orders", datasource_id="ds1",
        column_ids=("tbl__orders__col__category", "tbl__orders__col__calculation_01"),
    )
    calc = Calculation(
        id="calc__calculation_01", name="Revenue",
        scope=CalculationScope.MEASURE, tableau_expr="SUM([sales])",
        dax_expr="SUM('orders'[sales])",
        kind=CalculationKind.AGGREGATE, phase=CalculationPhase.AGGREGATE,
    )
    ds = Datasource(
        id="ds1", name="DS", tableau_kind="csv",
        connector_tier=ConnectorTier.TIER_1, pbi_m_connector="Csv.Document",
        connection_params={"filename": "x.csv"}, user_action_required=(),
        table_ids=("tbl__orders",), extract_ignored=False,
    )
    sheet = Sheet(
        id="s1", name="Sheet 1", datasource_refs=("ds1",), mark_type="bar",
        encoding=Encoding(
            rows=(FieldRef(table_id="tbl__orders", column_id="usr_calculation_01_qk"),),
            columns=(FieldRef(table_id="tbl__orders", column_id="none_category_nk"),),
        ),
        filters=(), sort=(), dual_axis=False, reference_lines=(), uses_calculations=(),
    )
    return Workbook(
        ir_schema_version="1.1.0", source_path="x.twb", source_hash="a",
        tableau_version="2024.1", config={},
        data_model=DataModel(
            datasources=(ds,), tables=(table,),
            columns=(col_cat, col_calc), calculations=(calc,),
        ),
        sheets=(sheet,), dashboards=(), unsupported=(),
    )


def test_dimension_resolves_to_table_and_col_name():
    lookup = build_field_lookup(_make_wb())
    assert "none_category_nk" in lookup
    info = lookup["none_category_nk"]
    assert info["table_name"] == "orders"
    assert info["col_name"] == "category"
    assert info["is_measure"] is False


def test_calculation_resolves_to_user_display_name():
    """col_name must be the user-given Calculation.name, not the internal Column.name."""
    lookup = build_field_lookup(_make_wb())
    assert "usr_calculation_01_qk" in lookup
    info = lookup["usr_calculation_01_qk"]
    assert info["table_name"] == "orders"
    assert info["col_name"] == "Revenue"   # Calculation.name, not "Calculation_01"
    assert info["is_measure"] is True


def test_datasource_marker_not_in_lookup():
    lookup = build_field_lookup(_make_wb())
    assert "federated_17kv7r10vp81pc1g60xgp0re1it8" not in lookup


def test_returns_empty_for_workbook_with_no_sheets():
    wb = _make_wb()
    wb2 = wb.model_copy(update={"sheets": ()})
    assert build_field_lookup(wb2) == {}
