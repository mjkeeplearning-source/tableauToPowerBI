from tableau2pbir.emit.tmdl.column import render_column
from tableau2pbir.ir.model import Column, ColumnKind, ColumnRole


def test_raw_column():
    col = Column(id="c1", name="Region", datatype="string", role=ColumnRole.DIMENSION, kind=ColumnKind.RAW)
    out = render_column(col)
    assert "column Region" in out
    assert "dataType: string" in out
    assert "expression" not in out


def test_calculated_column():
    col = Column(
        id="c2", name="Region Upper", datatype="string",
        role=ColumnRole.DIMENSION, kind=ColumnKind.CALCULATED,
        tableau_expr="UPPER([Region])",
        dax_expr="UPPER('Sales'[Region])",
    )
    out = render_column(col)
    assert "column 'Region Upper'" in out
    assert "expression: UPPER('Sales'[Region])" in out


def test_calculated_column_without_dax_emits_nothing():
    col = Column(
        id="c3", name="Skip Me", datatype="string",
        role=ColumnRole.DIMENSION, kind=ColumnKind.CALCULATED,
        tableau_expr="some_unsupported", dax_expr=None,
    )
    assert render_column(col) == ""


# ── datatype mapping ───────────────────────────────────────────────────────
def test_datatype_integer_maps_to_int64():
    col = Column(id="c4", name="row_id", datatype="integer", role=ColumnRole.DIMENSION, kind=ColumnKind.RAW)
    assert "dataType: int64" in render_column(col)


def test_datatype_real_maps_to_double():
    col = Column(id="c5", name="sales", datatype="real", role=ColumnRole.MEASURE, kind=ColumnKind.RAW)
    assert "dataType: double" in render_column(col)


def test_datatype_datetime_maps_to_dateTime():
    col = Column(id="c6", name="order_date", datatype="datetime", role=ColumnRole.DIMENSION, kind=ColumnKind.RAW)
    assert "dataType: dateTime" in render_column(col)


def test_datatype_date_maps_to_dateTime():
    col = Column(id="c11", name="ship_date", datatype="date", role=ColumnRole.DIMENSION, kind=ColumnKind.RAW)
    assert "dataType: dateTime" in render_column(col), "TMDL has no 'date' type; date must map to dateTime"


# ── sourceColumn ────────────────────────────────────────────────────────────
def test_raw_column_emits_source_column():
    col = Column(id="c7", name="order_id", datatype="string", role=ColumnRole.DIMENSION,
                 kind=ColumnKind.RAW, source_column="order_id")
    out = render_column(col)
    assert "sourceColumn: order_id" in out


def test_raw_column_falls_back_to_name_when_source_column_none():
    col = Column(id="c8", name="region", datatype="string", role=ColumnRole.DIMENSION,
                 kind=ColumnKind.RAW, source_column=None)
    assert "sourceColumn: region" in render_column(col)


# ── column name uses physical (source_column) name, not Tableau alias ───────
def test_raw_column_name_is_source_column_not_alias():
    col = Column(id="c_alias", name="order_id (returns)", datatype="string",
                 role=ColumnRole.DIMENSION, kind=ColumnKind.RAW, source_column="order_id")
    out = render_column(col)
    assert "\tcolumn order_id\n" in out, "TMDL column name must be physical source_column, not Tableau alias"
    assert "order_id (returns)" not in out, "Tableau alias must not appear as TMDL column name"


# ── indentation ─────────────────────────────────────────────────────────────
def test_column_properties_indented_two_tabs():
    col = Column(id="c10", name="region", datatype="string", role=ColumnRole.DIMENSION,
                 kind=ColumnKind.RAW, source_column="region")
    out = render_column(col)
    assert "\t\tdataType: string" in out, "dataType must be indented 2 tabs under column header"
    assert "\t\tsourceColumn: region" in out, "sourceColumn must be indented 2 tabs under column header"


# ── internal column filter ──────────────────────────────────────────────────
def test_internal_table_datatype_column_returns_empty():
    col = Column(id="c9", name="__tableau_internal_object_id__", datatype="table",
                 role=ColumnRole.DIMENSION, kind=ColumnKind.RAW)
    assert render_column(col) == ""
