from tableau2pbir.emit.tmdl.relationship import render_relationship
from tableau2pbir.ir.common import FieldRef
from tableau2pbir.ir.model import Relationship, RelationshipSource


def _rel(cardinality="many_to_one", cross_filter="single"):
    return Relationship(
        id="r1",
        from_ref=FieldRef(table_id="tbl__orders", column_id="order_id"),
        to_ref=FieldRef(table_id="tbl__returns", column_id="order_id"),
        cardinality=cardinality,
        cross_filter=cross_filter,
        source=RelationshipSource.TABLEAU_JOIN,
    )


def test_relationship_tmdl_uses_dot_notation_for_standalone_file():
    # Standalone relationships/*.tmdl uses Table.Column dot notation —
    # fromTable:/toTable: are only valid when inline in model.tmdl.
    out = render_relationship(_rel(), from_table_name="orders", to_table_name="returns")
    assert "relationship r1" in out
    assert "\tfromColumn: orders.order_id" in out
    assert "\ttoColumn: returns.order_id" in out
    assert "fromTable:" not in out
    assert "toTable:" not in out


def test_many_to_one_single_filter_cardinality_and_direction():
    out = render_relationship(_rel("many_to_one", "single"), from_table_name="orders", to_table_name="returns")
    assert "fromCardinality: many" in out
    assert "toCardinality: one" in out
    assert "crossFilteringBehavior: oneDirection" in out


def test_both_directions_cross_filter():
    out = render_relationship(_rel("many_to_many", "both"), from_table_name="orders", to_table_name="returns")
    assert "crossFilteringBehavior: bothDirections" in out
