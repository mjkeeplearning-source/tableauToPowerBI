"""Stage-3 DAX syntax gate. We use sqlglot's tsql dialect as a pragmatic
DAX parser — it accepts the SQL-Server-flavored function calls and bracketed
identifiers DAX shares with T-SQL. Goal is to catch unbalanced parens, bare
identifiers without context, etc.; not to fully validate DAX semantics."""
from __future__ import annotations

from tableau2pbir.translate.syntax_gate import is_valid_dax


def test_valid_simple_arithmetic():
    assert is_valid_dax("[Sales] + [Tax]") is True


def test_valid_calculate():
    assert is_valid_dax(
        "CALCULATE(SUM('Orders'[Amount]), REMOVEFILTERS('Orders'[Region]))"
    ) is True


def test_invalid_unbalanced_parens():
    assert is_valid_dax("CALCULATE(SUM('Orders'[Amount])") is False


def test_invalid_empty_string():
    assert is_valid_dax("") is False


def test_invalid_garbage():
    assert is_valid_dax("@@@##$$$ broken") is False
