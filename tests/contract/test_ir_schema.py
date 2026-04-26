"""Contract tests — the committed IR JSON Schema must match the pydantic-generated
schema. Bumping IR_SCHEMA_VERSION without regenerating the artifact fails CI."""
from __future__ import annotations

import json
from pathlib import Path

from tableau2pbir.ir.schema import generate_ir_schema
from tableau2pbir.ir.sheet import EncodingBinding, PbirVisual, Sheet
from tableau2pbir.ir.version import IR_SCHEMA_VERSION


def test_committed_schema_matches_generated(repo_root: Path):
    artifact_path = repo_root / "schemas" / f"ir-v{IR_SCHEMA_VERSION}.schema.json"
    assert artifact_path.exists(), \
        "committed schema missing; run `make schema` to regenerate."

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


def test_ir_schema_version_is_1_1_0():
    assert IR_SCHEMA_VERSION == "1.1.0"


def test_sheet_pbir_visual_default_is_none():
    s = Sheet(
        id="s1", name="Sales", datasource_refs=("ds1",),
        mark_type="bar", encoding={"rows": (), "columns": ()},
        filters=(), sort=(), dual_axis=False,
        reference_lines=(), uses_calculations=(),
    )
    assert s.pbir_visual is None


def test_pbir_visual_round_trip():
    binding = EncodingBinding(channel="value", source_field_id="t1__col__amount")
    pv = PbirVisual(
        visual_type="clusteredBarChart",
        encoding_bindings=(binding,),
        format={"title": "Sales"},
    )
    assert pv.visual_type == "clusteredBarChart"
    assert pv.encoding_bindings[0].channel == "value"
    assert pv.format["title"] == "Sales"
