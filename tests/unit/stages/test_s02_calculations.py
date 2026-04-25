from __future__ import annotations

from tableau2pbir.ir.calculation import CalculationKind, CalculationPhase, CalculationScope
from tableau2pbir.stages._build_data_model import build_calculations


def _raw_ds_with_calcs(ds_name: str, calcs: list[dict]) -> dict:
    return {
        "name": ds_name, "caption": None,
        "connection": {"class": "textscan"}, "named_connections": [],
        "extract": None,
        "columns": [{"name": c["host_column_name"], "datatype": c["datatype"],
                     "role": c["role"], "type": None} for c in calcs],
        "calculations": calcs,
    }


def test_row_calc_gets_kind_row():
    raw = [_raw_ds_with_calcs("ds", [
        {"host_column_name": "Profit", "tableau_expr": "[Revenue] - [Cost]",
         "datatype": "real", "role": "measure"},
    ])]
    calcs = build_calculations(raw)
    assert len(calcs) == 1
    c = calcs[0]
    assert c.kind == CalculationKind.ROW
    assert c.phase == CalculationPhase.ROW
    assert c.scope == CalculationScope.MEASURE
    assert c.lod_fixed is None
    assert c.table_calc is None


def test_aggregate_calc():
    raw = [_raw_ds_with_calcs("ds", [
        {"host_column_name": "Total Sales", "tableau_expr": "SUM([Sales])",
         "datatype": "real", "role": "measure"},
    ])]
    c = build_calculations(raw)[0]
    assert c.kind == CalculationKind.AGGREGATE
    assert c.phase == CalculationPhase.AGGREGATE


def test_lod_fixed_carries_dimensions():
    raw = [_raw_ds_with_calcs("ds", [
        {"host_column_name": "Sales By Region",
         "tableau_expr": "{FIXED [Region], [Year]: SUM([Sales])}",
         "datatype": "real", "role": "measure"},
    ])]
    c = build_calculations(raw)[0]
    assert c.kind == CalculationKind.LOD_FIXED
    assert c.lod_fixed is not None
    dim_columns = [d.column_id for d in c.lod_fixed.dimensions]
    assert dim_columns == ["region", "year"]


def test_lod_fixed_grand_total_has_empty_dimensions():
    raw = [_raw_ds_with_calcs("ds", [
        {"host_column_name": "Grand Total", "tableau_expr": "{FIXED : SUM([Sales])}",
         "datatype": "real", "role": "measure"},
    ])]
    c = build_calculations(raw)[0]
    assert c.kind == CalculationKind.LOD_FIXED
    assert c.lod_fixed is not None
    assert c.lod_fixed.dimensions == ()


def test_lod_include_sets_relative_and_kind():
    raw = [_raw_ds_with_calcs("ds", [
        {"host_column_name": "Sales By Customer",
         "tableau_expr": "{INCLUDE [Customer]: SUM([Sales])}",
         "datatype": "real", "role": "measure"},
    ])]
    c = build_calculations(raw)[0]
    assert c.kind == CalculationKind.LOD_INCLUDE
    assert c.lod_relative is not None
    assert c.lod_relative.extra_dims is not None
    assert [d.column_id for d in c.lod_relative.extra_dims] == ["customer"]


def test_depends_on_detects_sibling_calcs():
    raw = [_raw_ds_with_calcs("ds", [
        {"host_column_name": "Revenue", "tableau_expr": "SUM([Sales])",
         "datatype": "real", "role": "measure"},
        {"host_column_name": "Margin", "tableau_expr": "[Revenue] - SUM([Cost])",
         "datatype": "real", "role": "measure"},
    ])]
    calcs = build_calculations(raw)
    margin = next(c for c in calcs if c.name == "Margin")
    revenue = next(c for c in calcs if c.name == "Revenue")
    assert revenue.id in margin.depends_on
