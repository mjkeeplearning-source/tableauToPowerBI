"""Contract tests — the committed IR JSON Schema must match the pydantic-generated
schema. Bumping IR_SCHEMA_VERSION without regenerating the artifact fails CI."""
from __future__ import annotations

import json
from pathlib import Path

from tableau2pbir.ir.schema import generate_ir_schema
from tableau2pbir.ir.version import IR_SCHEMA_VERSION


def test_committed_schema_matches_generated(repo_root: Path):
    artifact_path = repo_root / "schemas" / f"ir-v{IR_SCHEMA_VERSION}.schema.json"
    assert artifact_path.exists(), \
        f"committed schema missing; run `make schema` to regenerate."

    committed = json.loads(artifact_path.read_text(encoding="utf-8"))
    generated = generate_ir_schema()
    assert committed == generated, (
        "committed IR JSON Schema is out of date; run `make schema` and commit."
    )


def test_generated_schema_has_expected_top_level_keys():
    schema = generate_ir_schema()
    assert schema.get("title") == "Workbook"
    assert "properties" in schema
    assert "ir_schema_version" in schema["properties"]
