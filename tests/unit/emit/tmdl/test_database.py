from tableau2pbir.emit.tmdl.database import render_database


def test_database_tmdl_basic():
    out = render_database(name="MyWorkbook", compatibility_level=1567)
    assert "database 'MyWorkbook'" in out
    assert "compatibilityLevel: 1567" in out


def test_database_tmdl_simple_name_quoted():
    out = render_database(name="Sales", compatibility_level=1567)
    assert "database 'Sales'" in out
