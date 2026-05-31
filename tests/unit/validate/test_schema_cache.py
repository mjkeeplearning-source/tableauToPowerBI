"""Tests for _resolve_schema two-tier cache lookup."""
import json
import pytest
from pathlib import Path

FAKE_URL = "https://example.com/fake/1.0.0/schema.json"
FAKE_SCHEMA = {"$schema": "http://json-schema.org/draft-07/schema#", "type": "object"}
ALT_SCHEMA = {"$schema": "http://json-schema.org/draft-07/schema#", "type": "string"}


def _make_bundled(tmp_path: Path, include_schema: bool = True) -> Path:
    bundled = tmp_path / "bundled"
    bundled.mkdir()
    manifest = {"schemas": [{"url": FAKE_URL, "file": "fake-1.0.0.json", "description": "test"}]}
    (bundled / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    if include_schema:
        (bundled / "fake-1.0.0.json").write_text(json.dumps(FAKE_SCHEMA), encoding="utf-8")
    return bundled


def test_resolve_user_cache_hit(tmp_path):
    bundled = _make_bundled(tmp_path, include_schema=True)
    user_cache = tmp_path / "user_cache"
    user_cache.mkdir()
    # Put a different schema in user cache to prove it wins over bundled
    (user_cache / "fake-1.0.0.json").write_text(json.dumps(ALT_SCHEMA), encoding="utf-8")

    from tableau2pbir.validate.json_schema import _resolve_schema
    result = _resolve_schema(FAKE_URL, user_cache, bundled)
    assert result == ALT_SCHEMA


def test_resolve_bundled_fallback(tmp_path):
    bundled = _make_bundled(tmp_path, include_schema=True)
    user_cache = tmp_path / "empty_cache"
    user_cache.mkdir()  # empty — no files

    from tableau2pbir.validate.json_schema import _resolve_schema
    result = _resolve_schema(FAKE_URL, user_cache, bundled)
    assert result == FAKE_SCHEMA


def test_resolve_returns_none_when_files_missing(tmp_path):
    bundled = _make_bundled(tmp_path, include_schema=False)  # manifest exists, schema file does not
    user_cache = tmp_path / "empty_cache"
    user_cache.mkdir()

    from tableau2pbir.validate.json_schema import _resolve_schema
    result = _resolve_schema(FAKE_URL, user_cache, bundled)
    assert result is None
