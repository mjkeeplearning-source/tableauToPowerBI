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
