from tableau2pbir.visualmap.number_format import tableau_format_to_dax

def test_c1033_percent_maps_to_usd():
    """C1033% is Tableau's internal code for US Dollar currency (confirmed from TWB + Tableau Desktop UI)."""
    result = tableau_format_to_dax("C1033%")
    assert result == r"\$#,0.00;(\$#,0.00);\$#,0.00"

def test_none_returns_none():
    assert tableau_format_to_dax(None) is None

def test_empty_returns_none():
    assert tableau_format_to_dax("") is None

def test_unknown_format_returns_none():
    # Unknown codes are not guessed — return None so PBI uses its model default.
    assert tableau_format_to_dax("UNKNOWN") is None

def test_c2057_maps_to_gbp():
    """C2057 = en-GB locale = British Pound."""
    result = tableau_format_to_dax("C2057")
    assert result == "£#,0.00;(£#,0.00);£0.00"

def test_c1036_maps_to_eur():
    """C1036 = fr-FR locale = Euro."""
    result = tableau_format_to_dax("C1036")
    assert result == "€#,0.00;(€#,0.00);€0.00"
