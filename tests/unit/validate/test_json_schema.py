"""Tests for run_json_schema auto-discovery validator."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tableau2pbir.validate.json_schema import run_json_schema
from tableau2pbir.validate.results import ValidatorOutcome

FAKE_URL = "https://example.com/fake/1.0.0/schema.json"

FAKE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["name"],
    "properties": {"name": {"type": "string"}},
    "additionalProperties": False,
}

STRICT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["name", "extra"],
    "properties": {
        "name": {"type": "string"},
        "extra": {"type": "string"},
    },
}


def _setup(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Returns (out_dir, bundled_dir, user_cache)."""
    out_dir = tmp_path / "output"
    out_dir.mkdir()
    bundled = tmp_path / "bundled"
    bundled.mkdir()
    manifest = {
        "schemas": [{"url": FAKE_URL, "file": "fake-1.0.0.json", "description": "test"}]
    }
    (bundled / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (bundled / "fake-1.0.0.json").write_text(json.dumps(FAKE_SCHEMA), encoding="utf-8")
    user_cache = tmp_path / "user_cache"
    user_cache.mkdir()
    return out_dir, bundled, user_cache


def test_valid_file_passes(tmp_path: Path) -> None:
    out_dir, bundled, user_cache = _setup(tmp_path)
    (out_dir / "test.json").write_text(
        json.dumps({"$schema": FAKE_URL, "name": "foo"}), encoding="utf-8"
    )
    result = run_json_schema(out_dir, cache_dir=user_cache, _bundled_dir=bundled)
    assert result.outcome == ValidatorOutcome.PASSED
    assert result.findings == ()


def test_invalid_file_produces_finding(tmp_path: Path) -> None:
    out_dir, bundled, user_cache = _setup(tmp_path)
    (out_dir / "bad.json").write_text(
        json.dumps({"$schema": FAKE_URL}),  # missing required "name"
        encoding="utf-8",
    )
    result = run_json_schema(out_dir, cache_dir=user_cache, _bundled_dir=bundled)
    assert result.outcome == ValidatorOutcome.FAILED
    assert len(result.findings) == 1
    assert result.findings[0].code == "schema.violation"
    assert "name" in result.findings[0].message


def test_file_without_schema_key_skipped(tmp_path: Path) -> None:
    out_dir, bundled, user_cache = _setup(tmp_path)
    (out_dir / "no_schema.json").write_text(
        json.dumps({"version": "4.0", "x": 1}), encoding="utf-8"
    )
    result = run_json_schema(out_dir, cache_dir=user_cache, _bundled_dir=bundled)
    assert result.outcome == ValidatorOutcome.PASSED
    assert result.findings == ()


def test_unknown_schema_url_produces_not_cached_finding(tmp_path: Path) -> None:
    out_dir, bundled, user_cache = _setup(tmp_path)
    (out_dir / "unknown.json").write_text(
        json.dumps({"$schema": "https://unknown.example.com/schema.json", "x": 1}),
        encoding="utf-8",
    )
    result = run_json_schema(out_dir, cache_dir=user_cache, _bundled_dir=bundled)
    assert result.outcome == ValidatorOutcome.FAILED
    assert result.findings[0].code == "schema.not_cached"
    assert "unknown.example.com" in result.findings[0].message


def test_stages_dir_excluded(tmp_path: Path) -> None:
    out_dir, bundled, user_cache = _setup(tmp_path)
    stages = out_dir / "stages"
    stages.mkdir()
    (stages / "01_extract.json").write_text(
        json.dumps({"$schema": "https://unknown.example.com/bad.json"}), encoding="utf-8"
    )
    result = run_json_schema(out_dir, cache_dir=user_cache, _bundled_dir=bundled)
    assert result.outcome == ValidatorOutcome.PASSED
    assert result.findings == ()


def test_validation_dir_excluded(tmp_path: Path) -> None:
    out_dir, bundled, user_cache = _setup(tmp_path)
    validation = out_dir / "validation"
    validation.mkdir()
    (validation / "structural.json").write_text(
        json.dumps({"$schema": "https://unknown.example.com/bad.json"}), encoding="utf-8"
    )
    result = run_json_schema(out_dir, cache_dir=user_cache, _bundled_dir=bundled)
    assert result.outcome == ValidatorOutcome.PASSED
    assert result.findings == ()


def test_user_cache_takes_precedence_over_bundled(tmp_path: Path) -> None:
    out_dir, bundled, user_cache = _setup(tmp_path)
    # Place a stricter schema in user cache (requires both "name" AND "extra")
    (user_cache / "fake-1.0.0.json").write_text(json.dumps(STRICT_SCHEMA), encoding="utf-8")
    # File that satisfies bundled (just "name") but fails strict (missing "extra")
    (out_dir / "test.json").write_text(
        json.dumps({"$schema": FAKE_URL, "name": "foo"}), encoding="utf-8"
    )
    result = run_json_schema(out_dir, cache_dir=user_cache, _bundled_dir=bundled)
    # If user cache is used → FAILED (missing "extra"); if bundled used → PASSED
    assert result.outcome == ValidatorOutcome.FAILED


def test_bundled_fallback_used_when_user_cache_empty(tmp_path: Path) -> None:
    out_dir, bundled, user_cache = _setup(tmp_path)
    # user_cache is empty — bundled has the schema
    (out_dir / "test.json").write_text(
        json.dumps({"$schema": FAKE_URL, "name": "foo"}), encoding="utf-8"
    )
    result = run_json_schema(out_dir, cache_dir=user_cache, _bundled_dir=bundled)
    assert result.outcome == ValidatorOutcome.PASSED
