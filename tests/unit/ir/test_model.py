from __future__ import annotations

import pytest

from tableau2pbir.ir.common import FieldRef
from tableau2pbir.ir.model import Column, ColumnKind, ColumnRole, Relationship, RelationshipSource, Table


def test_column_minimal_raw():
    c = Column(id="c1", name="Amount", datatype="decimal",
               role=ColumnRole.MEASURE, kind=ColumnKind.RAW)
    assert c.tableau_expr is None
    assert c.dax_expr is None


def test_column_calculated_has_tableau_expr():
    c = Column(id="c2", name="Profit Margin", datatype="decimal",
               role=ColumnRole.MEASURE, kind=ColumnKind.CALCULATED,
               tableau_expr="SUM([Profit])/SUM([Sales])",
               dax_expr=None)
    assert c.tableau_expr.startswith("SUM")


def test_table_has_columns_and_datasource():
    tbl = Table(id="t1", name="Orders", datasource_id="ds1",
                column_ids=("c1", "c2"), primary_key=None)
    assert tbl.datasource_id == "ds1"


def test_relationship_cardinality_enum():
    rel = Relationship(
        id="r1",
        from_ref=FieldRef(table_id="t1", column_id="customer_id"),
        to_ref=FieldRef(table_id="t2", column_id="id"),
        cardinality="many_to_one",
        cross_filter="single",
        source=RelationshipSource.TABLEAU_JOIN,
    )
    assert rel.source == RelationshipSource.TABLEAU_JOIN


def test_column_rejects_invalid_role():
    with pytest.raises(Exception):
        Column(id="c3", name="X", datatype="string",
               role="wrong_role",                                  # type: ignore[arg-type]
               kind=ColumnKind.RAW)
