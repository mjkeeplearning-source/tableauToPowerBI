from tableau2pbir.emit.tmdl.model import render_model


def test_model_tmdl_includes_culture_and_default_table():
    out = render_model(culture="en-US")
    assert "model Model" in out
    assert "culture: en-US" in out
    assert "defaultPowerBIDataSourceVersion" in out


def test_model_tmdl_custom_culture():
    out = render_model(culture="fr-FR")
    assert "culture: fr-FR" in out
    assert "sourceQueryCulture: fr-FR" in out
