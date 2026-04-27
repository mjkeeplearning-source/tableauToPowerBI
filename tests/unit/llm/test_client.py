"""LLMClient.translate_calc — three modes:
1. Cache hit  → returns cached value, no network, no snapshot read.
2. Replay     → PYTEST_SNAPSHOT=replay env: reads from llm_snapshots/.
3. Live       → calls Anthropic SDK; not exercised in unit tests."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from tableau2pbir.llm.client import LLMClient


_FIXTURE_SUBSET = {"id": "calc1", "name": "C1", "kind": "row",
                   "tableau_expr": "WEIRDFN([x])"}


def test_cache_hit_returns_value(tmp_path: Path):
    cache_dir = tmp_path / "cache"
    client = LLMClient(cache_dir=cache_dir)
    # Pre-populate the cache by computing the key the same way the client does.
    pack = client.packs["translate_calc"]
    from tableau2pbir.llm.cache import make_cache_key
    key = make_cache_key(
        model=client.model_by_method["translate_calc"],
        prompt_hash=pack.system_prompt_hash,
        schema_hash=pack.tool_schema_hash,
        payload=_FIXTURE_SUBSET,
    )
    client.cache.put(key, {"dax_expr": "FROM_CACHE",
                           "confidence": "high", "notes": ""})

    out = client.translate_calc(_FIXTURE_SUBSET)
    assert out["dax_expr"] == "FROM_CACHE"


def test_replay_mode_reads_snapshot(tmp_path: Path, monkeypatch):
    """In replay mode we ignore cache and read from the on-disk snapshot
    keyed by the `fixture` name in the payload."""
    monkeypatch.setenv("PYTEST_SNAPSHOT", "replay")
    cache_dir = tmp_path / "cache"
    client = LLMClient(cache_dir=cache_dir)
    payload = {**_FIXTURE_SUBSET, "fixture": "ai_only_compose"}
    out = client.translate_calc(payload)
    # Whatever is in tests/llm_snapshots/translate_calc/ai_only_compose.json
    assert out["confidence"] in ("high", "medium", "low")
    assert isinstance(out["dax_expr"], str)


def test_live_mode_without_api_key_raises(tmp_path: Path, monkeypatch):
    """Without ANTHROPIC_API_KEY, the live path raises a clear error rather
    than silently swallowing the SDK exception."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("PYTEST_SNAPSHOT", raising=False)
    cache_dir = tmp_path / "cache"
    client = LLMClient(cache_dir=cache_dir)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        client.translate_calc({"id": "x", "name": "x",
                               "kind": "row", "tableau_expr": "y"})
