from tableau2pbir.emit.tmdl.model import render_model


def test_model_tmdl_includes_culture_and_default_version():
    out = render_model(culture="en-US")
    assert "model Model" in out
    assert "culture: en-US" in out
    assert "defaultPowerBIDataSourceVersion: powerBI_V3" in out


def test_model_tmdl_custom_culture():
    out = render_model(culture="fr-FR")
    assert "culture: fr-FR" in out


def test_model_tmdl_no_extra_properties():
    out = render_model()
    assert "sourceQueryCulture" not in out, "sourceQueryCulture must not be emitted"
    assert "dataAccessOptions" not in out, "dataAccessOptions block must not be emitted"
    assert "legacyRedirects" not in out
    assert "returnErrorValuesAsNull" not in out
