from tableau2pbir.emit.tmdl.relationship import render_relationship
from tableau2pbir.ir.common import FieldRef
from tableau2pbir.ir.model import Relationship, RelationshipSource


def test_one_to_many_single_filter():
    rel = Relationship(
        id="r1",
        from_ref=FieldRef(table_id="Orders", column_id="CustomerKey"),
        to_ref=FieldRef(table_id="Customers", column_id="CustomerKey"),
        cardinality="many_to_one", cross_filter="single",
        source=RelationshipSource.TABLEAU_JOIN,
    )
    out = render_relationship(rel, from_table_name="Orders", to_table_name="Customers")
    assert "relationship r1" in out
    assert "fromColumn: Orders.CustomerKey" in out
    assert "toColumn: Customers.CustomerKey" in out
    assert "fromCardinality: many" in out
    assert "toCardinality: one" in out
