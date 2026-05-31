"""Tests for refresh_schemas command logic."""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

FAKE_CONTENT_A = b'{"$schema":"http://json-schema.org/draft-07/schema#","type":"object"}'
FAKE_CONTENT_B = b'{"$schema":"http://json-schema.org/draft-07/schema#","type":"string"}'


def _make_bundled(tmp_path: Path) -> Path:
    bundled = tmp_path / "bundled"
    bundled.mkdir()
    manifest = {
        "schemas": [
            {
                "url": "https://example.com/schema-a/1.0.0/schema.json",
                "file": "schema-a-1.0.0.json",
                "description": "A",
            },
            {
                "url": "https://example.com/schema-b/1.0.0/schema.json",
                "file": "schema-b-1.0.0.json",
                "description": "B",
            },
        ]
    }
    (bundled / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return bundled


def _mock_urlopen(responses: dict[str, bytes] | None = None) -> MagicMock:
    """Returns a mock for urllib.request.urlopen that serves bytes by URL."""
    default_content = FAKE_CONTENT_A
    if responses is None:
        responses = {}

    def fake_open(url: str) -> MagicMock:
        content = responses.get(url, default_content)
        cm = MagicMock()
        cm.__enter__ = lambda s: s
        cm.__exit__ = MagicMock(return_value=False)
        cm.read.return_value = content
        return cm

    return MagicMock(side_effect=fake_open)


def test_refresh_downloads_all_schemas(tmp_path: Path) -> None:
    bundled = _make_bundled(tmp_path)
    cache = tmp_path / "cache"
    with patch("urllib.request.urlopen", _mock_urlopen()):
        from tableau2pbir.validate.refresh_schemas import refresh_schemas
        ok = refresh_schemas(cache_dir=cache, bundled_dir=bundled)
    assert ok is True
    assert (cache / "schema-a-1.0.0.json").read_bytes() == FAKE_CONTENT_A
    assert (cache / "schema-b-1.0.0.json").read_bytes() == FAKE_CONTENT_A


def test_refresh_skips_unchanged(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bundled = _make_bundled(tmp_path)
    cache = tmp_path / "cache"
    cache.mkdir()
    # Pre-populate cache with same content the mock will return
    (cache / "schema-a-1.0.0.json").write_bytes(FAKE_CONTENT_A)
    (cache / "schema-b-1.0.0.json").write_bytes(FAKE_CONTENT_A)
    with patch("urllib.request.urlopen", _mock_urlopen()):
        from tableau2pbir.validate.refresh_schemas import refresh_schemas
        refresh_schemas(cache_dir=cache, bundled_dir=bundled)
    captured = capsys.readouterr()
    assert "unchanged" in captured.out
    assert "updated" not in captured.out


def test_refresh_returns_false_on_network_failure(tmp_path: Path) -> None:
    bundled = _make_bundled(tmp_path)
    cache = tmp_path / "cache"
    with patch("urllib.request.urlopen", side_effect=OSError("network error")):
        from tableau2pbir.validate.refresh_schemas import refresh_schemas
        ok = refresh_schemas(cache_dir=cache, bundled_dir=bundled)
    assert ok is False


def test_refresh_custom_cache_dir_creates_dir(tmp_path: Path) -> None:
    bundled = _make_bundled(tmp_path)
    custom_cache = tmp_path / "deeply" / "nested" / "cache"
    assert not custom_cache.exists()
    with patch("urllib.request.urlopen", _mock_urlopen()):
        from tableau2pbir.validate.refresh_schemas import refresh_schemas
        refresh_schemas(cache_dir=custom_cache, bundled_dir=bundled)
    assert (custom_cache / "schema-a-1.0.0.json").exists()


def test_get_cache_dir_uses_env_var(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_path = tmp_path / "env_cache"
    monkeypatch.setenv("T2P_SCHEMA_CACHE", str(env_path))
    from tableau2pbir.validate.refresh_schemas import _get_cache_dir
    assert _get_cache_dir() == env_path
