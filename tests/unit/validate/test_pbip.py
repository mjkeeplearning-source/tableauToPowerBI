import json
from pathlib import Path
from tableau2pbir.validate.pbip import write_pbip_root


def test_writes_pbip_pointer(tmp_path: Path):
    (tmp_path / "Report" / "definition").mkdir(parents=True)
    (tmp_path / "SemanticModel").mkdir()

    pbip = write_pbip_root(tmp_path, "Superstore")

    assert pbip == tmp_path / "Superstore.pbip"
    assert pbip.is_file()
    data = json.loads(pbip.read_text(encoding="utf-8"))
    assert data["version"] == "1.0"
    assert data["settings"]["enableAutoRecovery"] is True


def test_pbip_artifacts_includes_both_report_and_dataset(tmp_path: Path):
    """Both report and dataset artifacts are required for PBI Desktop to open the project."""
    (tmp_path / "Report" / "definition").mkdir(parents=True)
    (tmp_path / "SemanticModel").mkdir()

    pbip = write_pbip_root(tmp_path, "Superstore")
    data = json.loads(pbip.read_text(encoding="utf-8"))

    artifact_types = {list(a.keys())[0] for a in data["artifacts"]}
    assert "report" in artifact_types, "artifacts must include report entry"
    assert "dataset" in artifact_types, "artifacts must include dataset (SemanticModel) entry"
    report_artifact = next(a for a in data["artifacts"] if "report" in a)
    dataset_artifact = next(a for a in data["artifacts"] if "dataset" in a)
    assert report_artifact["report"]["path"] == "Report"
    assert dataset_artifact["dataset"]["path"] == "SemanticModel"


def test_overwrites_existing_placeholder(tmp_path: Path):
    (tmp_path / "Report" / "definition").mkdir(parents=True)
    (tmp_path / "Foo.pbip").write_text("", encoding="utf-8")    # 0-byte stub
    pbip = write_pbip_root(tmp_path, "Foo")
    assert pbip.read_text(encoding="utf-8") != ""
    assert json.loads(pbip.read_text(encoding="utf-8"))["version"] == "1.0"


def test_raises_when_report_dir_missing(tmp_path: Path):
    import pytest
    with pytest.raises(FileNotFoundError, match="Report"):
        write_pbip_root(tmp_path, "NoReport")


def test_writes_definition_pbir(tmp_path: Path):
    (tmp_path / "Report" / "definition").mkdir(parents=True)
    (tmp_path / "SemanticModel").mkdir()

    write_pbip_root(tmp_path, "Superstore")

    definition_pbir = tmp_path / "Report" / "definition.pbir"
    assert definition_pbir.is_file(), "Report/definition.pbir must be written"
    data = json.loads(definition_pbir.read_text(encoding="utf-8"))
    assert data["version"] == "4.0"
    assert data["datasetReference"]["byPath"]["path"] == "../SemanticModel"
    assert data["datasetReference"]["byConnection"] is None


def test_definition_pbir_schema_key_present(tmp_path: Path):
    (tmp_path / "Report" / "definition").mkdir(parents=True)
    (tmp_path / "SemanticModel").mkdir()

    write_pbip_root(tmp_path, "Superstore")

    data = json.loads((tmp_path / "Report" / "definition.pbir").read_text(encoding="utf-8"))
    assert "$schema" in data
