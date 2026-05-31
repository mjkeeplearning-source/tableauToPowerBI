"""Tests for _format_literal and field-building helpers."""
from __future__ import annotations

from tableau2pbir.emit.pbir.filters import _alias_col_expr, _entity_field, _format_literal


class TestFormatLiteral:
    def test_none_returns_null(self):
        assert _format_literal(None) == "null"

    def test_empty_string_returns_null(self):
        assert _format_literal("") == "null"

    def test_date_only(self):
        assert _format_literal("#2023-01-03#") == "datetime'2023-01-03T00:00:00'"

    def test_datetime_with_time(self):
        assert _format_literal("#2023-01-03 12:30:00#") == "datetime'2023-01-03T12:30:00'"

    def test_integer_string(self):
        assert _format_literal("42") == "42L"

    def test_negative_integer(self):
        assert _format_literal("-7") == "-7L"

    def test_float_string(self):
        assert _format_literal("3.14") == "3.14D"

    def test_plain_string(self):
        assert _format_literal("East") == "'East'"

    def test_string_with_apostrophe_escaped(self):
        # Single quotes inside strings are doubled per DAX convention
        result = _format_literal("O'Brien")
        assert result == "'O''Brien'"

    def test_zero_integer(self):
        assert _format_literal("0") == "0L"


class TestEntityField:
    def test_column_entity_field(self):
        result = _entity_field("Sales", "Region", "Column")
        assert result == {
            "Column": {
                "Expression": {"SourceRef": {"Entity": "Sales"}},
                "Property": "Region",
            }
        }

    def test_measure_entity_field(self):
        result = _entity_field("Sales", "Total", "Measure")
        assert "Measure" in result
        assert result["Measure"]["Expression"]["SourceRef"]["Entity"] == "Sales"


class TestAliasColExpr:
    def test_alias_col_expression(self):
        result = _alias_col_expr("f", "Region")
        assert result == {
            "Column": {
                "Expression": {"SourceRef": {"Source": "f"}},
                "Property": "Region",
            }
        }
