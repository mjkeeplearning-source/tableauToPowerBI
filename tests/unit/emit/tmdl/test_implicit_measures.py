"""Unit tests for collect_implicit_measures — RED phase."""
from __future__ import annotations

import pytest

from tableau2pbir.emit.tmdl.implicit_measures import collect_implicit_measures
from tableau2pbir.ir.calculation import (
    Calculation, CalculationKind, CalculationPhase, CalculationScope,
)
from tableau2pbir.ir.common import FieldRef
from tableau2pbir.ir.datasource import ConnectorTier, Datasource
from tableau2pbir.ir.model import Column, ColumnKind, ColumnRole, Table
from tableau2pbir.ir.sheet import Encoding, EncodingBinding, PbirVisual, Sheet
from tableau2pbir.ir.workbook import DataModel, Workbook


def _ds() -> Datasource:
    return Datasource(
        id="d1", name="orders", tableau_kind="postgres",
        connector_tier=ConnectorTier.TIER_2,
        pbi_m_connector="PostgreSQL.Database",
        connection_params={"server": "srv", "dbname": "db"},
        user_action_required=(), table_ids=("t1",), extract_ignored=False,
    )


def _col(cid: str, name: str, role: ColumnRole = ColumnRole.MEASURE) -> Column:
    return Column(
        id=cid, name=name, datatype="real", role=role,
        kind=ColumnKind.RAW, source_column=name,
    )


def _sheet(sid: str, pill_slugs: list[str], table_id: str) -> Sheet:
    """Build a Sheet whose pbir_visual bindings reference the given pill slugs."""
    bindings = tuple(
        EncodingBinding(channel="Y", source_field_id=slug)
        for slug in pill_slugs
    )
    row_refs = tuple(
        FieldRef(table_id=table_id, column_id=slug) for slug in pill_slugs
    )
    return Sheet(
        id=sid, name=sid, mark_type="bar",
        datasource_refs=(table_id,),
        encoding=Encoding(rows=row_refs),
        filters=(), sort=(), dual_axis=False, reference_lines=(),
        uses_calculations=(),
        pbir_visual=PbirVisual(
            visual_type="columnChart",
            encoding_bindings=bindings,
        ),
    )


def _wb(
    cols: list[Column],
    pill_slugs: list[str],
    calcs: list[Calculation] = (),
) -> Workbook:
    table = Table(id="t1", name="orders", datasource_id="d1",
                  column_ids=tuple(c.id for c in cols))
    sheet = _sheet("s1", pill_slugs, table_id="t1")
    dm = DataModel(
        datasources=(_ds(),),
        tables=(table,),
        columns=tuple(cols),
        calculations=tuple(calcs),
    )
    return Workbook(
        ir_schema_version="1.1.0", source_path="x.twb", source_hash="a",
        tableau_version="2024.1", config={},
        data_model=dm, sheets=(sheet,), dashboards=(), unsupported=(),
    )


# ── Tests ────────────────────────────────────────────────────────────────────

def test_sum_pill_produces_sum_measure():
    wb = _wb(
        cols=[_col("c1", "profit")],
        pill_slugs=["sum_profit_qk"],
    )
    result = collect_implicit_measures(wb)
    assert "orders" in result
    entries = dict(result["orders"])
    # Measure name must be prefixed ("Sum profit"), not the raw column name ("profit")
    assert "Sum profit" in entries, f"Expected 'Sum profit' key, got: {list(entries)}"
    assert entries["Sum profit"] == "SUM('orders'[profit])"


def test_avg_pill_produces_average_measure():
    wb = _wb(
        cols=[_col("c1", "sales")],
        pill_slugs=["avg_sales_qk"],
    )
    result = collect_implicit_measures(wb)
    entries = dict(result["orders"])
    assert entries["Avg sales"] == "AVERAGE('orders'[sales])"


def test_min_max_cnt_cntd_pills():
    wb = _wb(
        cols=[
            _col("c1", "quantity"),
            _col("c2", "order_id"),
        ],
        pill_slugs=["min_quantity_qk", "max_quantity_qk", "cnt_order_id_qk", "cntd_order_id_qk"],
    )
    result = collect_implicit_measures(wb)
    entries = dict(result["orders"])
    assert "Min quantity" in entries or "Max quantity" in entries
    assert "Count order_id" in entries or "Count Distinct order_id" in entries


def test_dimension_pill_nk_suffix_is_skipped():
    """none_region_nk has suffix 'nk' — not quantitative, must not emit a measure."""
    wb = _wb(
        cols=[_col("c1", "region", role=ColumnRole.DIMENSION)],
        pill_slugs=["none_region_nk"],
    )
    result = collect_implicit_measures(wb)
    assert result == {}


def test_ordinal_pill_ok_suffix_is_skipped():
    """yr_order_date_ok has suffix 'ok' — ordinal date, must not emit a measure."""
    wb = _wb(
        cols=[_col("c1", "order_date", role=ColumnRole.DIMENSION)],
        pill_slugs=["yr_order_date_ok"],
    )
    result = collect_implicit_measures(wb)
    assert result == {}


def test_duplicate_pill_across_bindings_emits_one_measure():
    """Same base column referenced twice in same sheet should produce one measure."""
    wb = _wb(
        cols=[_col("c1", "sales")],
        pill_slugs=["sum_sales_qk", "sum_sales_qk"],
    )
    result = collect_implicit_measures(wb)
    assert len(result["orders"]) == 1
    assert result["orders"][0][0] == "Sum sales"


def test_skips_if_explicit_calc_name_matches_prefixed_name():
    """If a Calculation named 'Sum profit' already exists, no implicit measure emitted."""
    calc = Calculation(
        id="calc__sum_profit", name="Sum profit",
        scope=CalculationScope.MEASURE,
        tableau_expr="SUM([profit])",
        dax_expr="SUM('orders'[profit])",
        kind=CalculationKind.AGGREGATE,
        phase=CalculationPhase.AGGREGATE,
    )
    wb = _wb(
        cols=[_col("c1", "profit")],
        pill_slugs=["sum_profit_qk"],
        calcs=[calc],
    )
    result = collect_implicit_measures(wb)
    assert result == {}


def test_returns_empty_when_no_visual_bindings():
    table = Table(id="t1", name="orders", datasource_id="d1", column_ids=("c1",))
    sheet = Sheet(
        id="s1", name="s1", mark_type="bar",
        datasource_refs=("t1",),
        encoding=Encoding(),
        filters=(), sort=(), dual_axis=False, reference_lines=(),
        uses_calculations=(),
        pbir_visual=None,
    )
    dm = DataModel(
        datasources=(_ds(),),
        tables=(table,),
        columns=(_col("c1", "profit"),),
    )
    wb = Workbook(
        ir_schema_version="1.1.0", source_path="x.twb", source_hash="a",
        tableau_version="2024.1", config={},
        data_model=dm, sheets=(sheet,), dashboards=(), unsupported=(),
    )
    result = collect_implicit_measures(wb)
    assert result == {}
