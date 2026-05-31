from __future__ import annotations
import pytest
from tableau2pbir.regression.compare.tmdl_diff import (
    parse_table_tmdl,
    parse_model_tmdl,
    diff_tmdl_table,
    diff_model_tmdl,
    TmdlTableModel,
    TmdlModelFile,
)

_TABLE_SIMPLE = """\
table orders

\tcolumn order_id
\t\tdataType: int64
\t\tsourceColumn: order_id

\tcolumn 'Customer Name'
\t\tdataType: string
\t\tsourceColumn: Customer Name

\tmeasure 'Profit Ratio' = SUM([Profit]) / SUM([Sales])

\tpartition orders = m
\t\tmode: directQuery
\t\tsource =
\t\t\tlet Source = Sql.Database() in Source
"""

_TABLE_MULTILINE_MEASURE = """\
table sales

\tmeasure 'Complex Calc' =
\t\t\tCALCULATE(
\t\t\t    SUM([Sales]),
\t\t\t    ALL(orders)
\t\t\t)

\tpartition sales = m
\t\tmode: directQuery
\t\tsource =
\t\t\tlet Source = Sql.Database() in Source
"""

_TABLE_CALC_COL = """\
table orders

\tcolumn 'Full Name' = [First] & " " & [Last]
\t\tdataType: string

\tpartition orders = m
\t\tmode: directQuery
\t\tsource =
\t\t\tlet Source = Sql.Database() in Source
"""

_MODEL_SIMPLE = """\
model Model
\tculture: en-US
\tdefaultPowerBIDataSourceVersion: powerBI_V3
"""


def test_parse_table_name():
    m = parse_table_tmdl(_TABLE_SIMPLE)
    assert m.table_name == "orders"


def test_parse_regular_columns():
    m = parse_table_tmdl(_TABLE_SIMPLE)
    assert "order_id" in m.columns
    assert m.columns["order_id"].data_type == "int64"
    assert m.columns["order_id"].source_column == "order_id"


def test_parse_quoted_column_name():
    m = parse_table_tmdl(_TABLE_SIMPLE)
    assert "Customer Name" in m.columns
    assert m.columns["Customer Name"].data_type == "string"


def test_parse_single_line_measure():
    m = parse_table_tmdl(_TABLE_SIMPLE)
    assert "Profit Ratio" in m.measures
    assert "SUM([Profit])" in m.measures["Profit Ratio"].dax_expr


def test_partition_not_in_columns_or_measures():
    m = parse_table_tmdl(_TABLE_SIMPLE)
    assert "orders" not in m.measures
    for col_name in m.columns:
        assert "partition" not in col_name.lower()


def test_parse_multiline_measure():
    m = parse_table_tmdl(_TABLE_MULTILINE_MEASURE)
    assert "Complex Calc" in m.measures
    dax = m.measures["Complex Calc"].dax_expr
    assert "CALCULATE" in dax
    assert "SUM([Sales])" in dax


def test_parse_calculated_column():
    m = parse_table_tmdl(_TABLE_CALC_COL)
    assert "Full Name" in m.columns
    assert "[First]" in m.columns["Full Name"].dax_expr
    assert m.columns["Full Name"].data_type == "string"


def test_parse_model_tmdl():
    mf = parse_model_tmdl(_MODEL_SIMPLE)
    assert mf.culture == "en-US"
    assert mf.default_pbi_ds_version == "powerBI_V3"


def test_diff_tmdl_table_identical():
    diffs = diff_tmdl_table(_TABLE_SIMPLE, _TABLE_SIMPLE)
    assert diffs == []


def test_diff_tmdl_table_measure_dax_change():
    modified = _TABLE_SIMPLE.replace(
        "SUM([Profit]) / SUM([Sales])",
        "DIVIDE(SUM([Profit]), SUM([Sales]))",
    )
    diffs = diff_tmdl_table(_TABLE_SIMPLE, modified)
    assert len(diffs) == 1
    assert diffs[0].entity_type == "measure"
    assert diffs[0].entity_name == "Profit Ratio"
    assert diffs[0].attribute == "DAX"


def test_diff_tmdl_table_column_datatype_change():
    modified = _TABLE_SIMPLE.replace("dataType: int64", "dataType: string")
    diffs = diff_tmdl_table(_TABLE_SIMPLE, modified)
    assert len(diffs) == 1
    assert diffs[0].entity_type == "column"
    assert diffs[0].entity_name == "order_id"
    assert diffs[0].attribute == "dataType"
    assert diffs[0].old_value == "int64"
    assert diffs[0].new_value == "string"


def test_diff_tmdl_table_missing_measure():
    modified = _TABLE_SIMPLE.replace(
        "\tmeasure 'Profit Ratio' = SUM([Profit]) / SUM([Sales])\n", ""
    )
    diffs = diff_tmdl_table(_TABLE_SIMPLE, modified)
    assert any(d.entity_type == "measure" and "Profit Ratio" in d.entity_name for d in diffs)


def test_diff_tmdl_table_ignores_new_columns_in_output():
    modified = _TABLE_SIMPLE + "\tcolumn extra_col\n\t\tdataType: string\n"
    diffs = diff_tmdl_table(_TABLE_SIMPLE, modified)
    assert diffs == []


def test_diff_model_tmdl_identical():
    diffs = diff_model_tmdl(_MODEL_SIMPLE, _MODEL_SIMPLE)
    assert diffs == []


def test_diff_model_tmdl_culture_change():
    modified = _MODEL_SIMPLE.replace("en-US", "fr-FR")
    diffs = diff_model_tmdl(_MODEL_SIMPLE, modified)
    assert len(diffs) == 1
    assert diffs[0].attribute == "culture"
    assert diffs[0].old_value == "en-US"
    assert diffs[0].new_value == "fr-FR"
