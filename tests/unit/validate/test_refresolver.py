"""Tests that run_json_schema resolves nested $ref links via RefResolver."""
from __future__ import annotations

import json
from pathlib import Path

from tableau2pbir.validate.json_schema import run_json_schema
from tableau2pbir.validate.results import ValidatorOutcome

# Minimal schema that references a sibling definition via $ref
_OUTER_URL = "https://example.com/outer/1.0.0/schema.json"
_INNER_URL = "https://example.com/inner/1.0.0/schema.json"

_INNER_SCHEMA = {
    "$id": _INNER_URL,
    "$schema": "http://json-schema.org/draft-07/schema#",
    "definitions": {
        "Name": {
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
            "additionalProperties": False,
        }
    },
}

_OUTER_SCHEMA = {
    "$id": _OUTER_URL,
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "$schema": {"type": "string"},
        "name": {"$ref": f"{_INNER_URL}#/definitions/Name"},
    },
    "required": ["$schema", "name"],
    "additionalProperties": False,
}


def _setup(tmp_path: Path) -> tuple[Path, Path, Path]:
    out_dir = tmp_path / "output"
    out_dir.mkdir()
    bundled = tmp_path / "bundled"
    bundled.mkdir()
    manifest = {
        "schemas": [
            {"url": _OUTER_URL, "file": "outer-1.0.0.json", "description": "outer"},
            {"url": _INNER_URL, "file": "inner-1.0.0.json", "description": "inner"},
        ]
    }
    (bundled / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (bundled / "outer-1.0.0.json").write_text(json.dumps(_OUTER_SCHEMA), encoding="utf-8")
    (bundled / "inner-1.0.0.json").write_text(json.dumps(_INNER_SCHEMA), encoding="utf-8")
    user_cache = tmp_path / "cache"
    user_cache.mkdir()
    return out_dir, bundled, user_cache


def test_ref_resolved_valid_passes(tmp_path: Path) -> None:
    out_dir, bundled, user_cache = _setup(tmp_path)
    (out_dir / "good.json").write_text(
        json.dumps({"$schema": _OUTER_URL, "name": {"value": "hello"}}),
        encoding="utf-8",
    )
    result = run_json_schema(out_dir, cache_dir=user_cache, _bundled_dir=bundled)
    assert result.outcome == ValidatorOutcome.PASSED


def test_ref_resolved_invalid_fails(tmp_path: Path) -> None:
    out_dir, bundled, user_cache = _setup(tmp_path)
    # name.value must be a string but we pass an int — caught only if $ref resolves
    (out_dir / "bad.json").write_text(
        json.dumps({"$schema": _OUTER_URL, "name": {"value": 42}}),
        encoding="utf-8",
    )
    result = run_json_schema(out_dir, cache_dir=user_cache, _bundled_dir=bundled)
    assert result.outcome == ValidatorOutcome.FAILED
    assert any("value" in f.message for f in result.findings)
