"""Tests for _filter_to_pbir per-kind emit."""
from __future__ import annotations

import pytest

from tableau2pbir.emit.pbir.filters import _filter_to_pbir
from tableau2pbir.ir.common import FieldRef
from tableau2pbir.ir.sheet import (
    CategoricalFilter, ConditionalFilter, ContextFilter,
    RangeFilter, TopNFilter,
)

_FIELD = FieldRef(table_id="Sales", column_id="Region")


def _cat(include=(), exclude=()):
    return CategoricalFilter(id="f1", field=_FIELD, include=include, exclude=exclude)


class TestCategoricalEmit:
    def test_include_only(self):
        result = _filter_to_pbir(_cat(include=("East", "West")))
        assert result is not None
        assert result["type"] == "Categorical"
        assert result["name"] == "f1"
        # top-level field uses Entity (StandaloneSourceRef)
        assert result["field"]["Column"]["Expression"]["SourceRef"]["Entity"] == "Sales"
        assert result["field"]["Column"]["Property"] == "Region"
        # filter body
        fd = result["filter"]
        assert fd["Version"] == 2
        assert fd["From"][0] == {"Name": "f", "Entity": "Sales", "Type": 0}
        condition = fd["Where"][0]["Condition"]
        assert "In" in condition
        in_expr = condition["In"]
        # alias-ref inside Where uses Source key
        assert in_expr["Expressions"][0]["Column"]["Expression"]["SourceRef"]["Source"] == "f"
        values = [v[0]["Literal"]["Value"] for v in in_expr["Values"]]
        assert "'East'" in values
        assert "'West'" in values
        assert result["howCreated"] == "User"
        assert result["isHiddenInViewMode"] is False

    def test_exclude_only(self):
        result = _filter_to_pbir(_cat(exclude=("North",)))
        assert result is not None
        condition = result["filter"]["Where"][0]["Condition"]
        assert "Not" in condition
        assert "In" in condition["Not"]["Expression"]

    def test_include_and_exclude(self):
        result = _filter_to_pbir(_cat(include=("East",), exclude=("North",)))
        assert result is not None
        condition = result["filter"]["Where"][0]["Condition"]
        assert "And" in condition
        assert "In" in condition["And"]["Left"]
        assert "Not" in condition["And"]["Right"]

    def test_empty_returns_none(self):
        assert _filter_to_pbir(_cat()) is None

    def test_howcreated_and_hidden(self):
        result = _filter_to_pbir(_cat(include=("East",)))
        assert result["howCreated"] == "User"
        assert result["isHiddenInViewMode"] is False


class TestContextEmit:
    def test_context_same_structure_as_categorical(self):
        f = ContextFilter(id="f2", field=_FIELD, include=("West",))
        result = _filter_to_pbir(f)
        assert result is not None
        assert result["name"] == "f2"
        assert result["type"] == "Categorical"
        condition = result["filter"]["Where"][0]["Condition"]
        assert "In" in condition

    def test_context_empty_returns_none(self):
        f = ContextFilter(id="f3", field=_FIELD)
        assert _filter_to_pbir(f) is None
