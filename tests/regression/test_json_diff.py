from __future__ import annotations
import json
import pytest
from tableau2pbir.regression.compare.json_diff import diff_json


def _j(obj) -> str:
    return json.dumps(obj)


def test_identical_objects_produce_no_diffs():
    a = _j({"name": "foo", "value": 42})
    assert diff_json(a, a) == []


def test_changed_leaf_value_detected():
    old = _j({"dataType": "int64"})
    new = _j({"dataType": "string"})
    diffs = diff_json(old, new)
    assert len(diffs) == 1
    path, old_v, new_v = diffs[0]
    assert "dataType" in path
    assert old_v == "int64"
    assert new_v == "string"


def test_key_ordering_ignored():
    a = _j({"b": 2, "a": 1})
    b = _j({"a": 1, "b": 2})
    assert diff_json(a, b) == []


def test_array_of_dicts_sorted_by_name():
    old = _j([{"name": "z", "v": 1}, {"name": "a", "v": 2}])
    new = _j([{"name": "a", "v": 2}, {"name": "z", "v": 1}])
    assert diff_json(old, new) == []


def test_array_of_dicts_sorted_by_id_fallback():
    old = _j([{"id": "z", "v": 1}, {"id": "a", "v": 2}])
    new = _j([{"id": "a", "v": 2}, {"id": "z", "v": 1}])
    assert diff_json(old, new) == []


def test_changed_array_element_detected():
    old = _j([{"name": "col", "dataType": "int64"}])
    new = _j([{"name": "col", "dataType": "string"}])
    diffs = diff_json(old, new)
    assert len(diffs) == 1
    assert "int64" in diffs[0][1]
    assert "string" in diffs[0][2]


def test_missing_key_detected():
    old = _j({"a": 1, "b": 2})
    new = _j({"a": 1})
    diffs = diff_json(old, new)
    assert len(diffs) == 1
    assert "b" in diffs[0][0]


def test_nested_diff_detected():
    old = _j({"visual": {"encoding": {"x": {"field": "Sales"}}}})
    new = _j({"visual": {"encoding": {"x": {"field": "Profit"}}}})
    diffs = diff_json(old, new)
    assert len(diffs) == 1
    assert "Sales" in diffs[0][1]
    assert "Profit" in diffs[0][2]


def test_whitespace_in_string_values_ignored():
    old = _j({"dax": "  SUM([Sales])  "})
    new = _j({"dax": "SUM([Sales])"})
    assert diff_json(old, new) == []
