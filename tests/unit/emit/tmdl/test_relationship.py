"""Unit tests for render_relationship()."""
from __future__ import annotations

from tableau2pbir.emit.tmdl.relationship import render_relationship
from tableau2pbir.ir.common import FieldRef
from tableau2pbir.ir.model import Relationship, RelationshipSource


def _rel(cardinality: str, cross_filter: str) -> Relationship:
    return Relationship(
        id="rel__a__b",
        from_ref=FieldRef(table_id="tbl__a", column_id="fk_col"),
        to_ref=FieldRef(table_id="tbl__b", column_id="pk_col"),
        cardinality=cardinality,
        cross_filter=cross_filter,
        source=RelationshipSource.TABLEAU_JOIN,
    )


def test_many_to_one_renders_one_direction():
    out = render_relationship(_rel("many_to_one", "single"), "factA", "dimB")
    assert "fromCardinality: many" in out
    assert "toCardinality: one" in out
    assert "crossFilteringBehavior: oneDirection" in out


def test_many_to_many_renders_both_directions():
    out = render_relationship(_rel("many_to_many", "both"), "tableA", "tableB")
    assert "fromCardinality: many" in out
    assert "toCardinality: many" in out
    assert "crossFilteringBehavior: bothDirections" in out


def test_one_to_one_renders_both_directions():
    out = render_relationship(_rel("one_to_one", "both"), "tableA", "tableB")
    assert "fromCardinality: one" in out
    assert "toCardinality: one" in out
    assert "crossFilteringBehavior: bothDirections" in out


def test_from_and_to_column_names_appear_in_output():
    out = render_relationship(_rel("many_to_one", "single"), "orders", "people")
    assert "fromColumn: orders.fk_col" in out
    assert "toColumn: people.pk_col" in out
