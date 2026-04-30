from tableau2pbir.emit.tmdl.escape import tmdl_ident, tmdl_string


def test_simple_ident_unquoted():
    assert tmdl_ident("Sales") == "Sales"


def test_ident_with_space_quoted():
    assert tmdl_ident("Total Revenue") == "'Total Revenue'"


def test_ident_with_apostrophe_doubled():
    assert tmdl_ident("Bob's KPIs") == "'Bob''s KPIs'"


def test_string_literal_quotes_doubled():
    assert tmdl_string('a "b" c') == '"a ""b"" c"'


def test_empty_ident_quoted():
    assert tmdl_ident("") == "''"
