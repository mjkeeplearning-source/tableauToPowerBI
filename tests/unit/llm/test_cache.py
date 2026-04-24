from __future__ import annotations

from pathlib import Path

from tableau2pbir.llm.cache import OnDiskCache, make_cache_key


def test_make_cache_key_is_stable():
    k1 = make_cache_key(model="m", prompt_hash="p", schema_hash="s", payload={"x": 1})
    k2 = make_cache_key(model="m", prompt_hash="p", schema_hash="s", payload={"x": 1})
    assert k1 == k2
    assert len(k1) == 64                 # sha256 hex


def test_cache_roundtrip(tmp_path: Path):
    c = OnDiskCache(tmp_path)
    assert c.get("missing_key") is None
    c.put("k1", {"dax": "SUM([x])"})
    assert c.get("k1") == {"dax": "SUM([x])"}


def test_cache_key_changes_on_payload_change():
    k1 = make_cache_key(model="m", prompt_hash="p", schema_hash="s", payload={"x": 1})
    k2 = make_cache_key(model="m", prompt_hash="p", schema_hash="s", payload={"x": 2})
    assert k1 != k2
