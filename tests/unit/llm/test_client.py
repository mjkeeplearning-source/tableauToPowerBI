from __future__ import annotations

from pathlib import Path

import pytest

from tableau2pbir.llm.client import LLMClient


def test_client_init_loads_three_prompt_packs(tmp_path: Path):
    client = LLMClient(cache_dir=tmp_path, model_by_method={})
    assert set(client.packs.keys()) == {"translate_calc", "map_visual", "cleanup_name"}


def test_translate_calc_raises_not_implemented(tmp_path: Path):
    client = LLMClient(cache_dir=tmp_path, model_by_method={})
    with pytest.raises(NotImplementedError, match="Plan 3"):
        client.translate_calc({"tableau_expr": "SUM([x])"})


def test_map_visual_raises_not_implemented(tmp_path: Path):
    client = LLMClient(cache_dir=tmp_path, model_by_method={})
    with pytest.raises(NotImplementedError, match="Plan 3"):
        client.map_visual({"mark_type": "bar"})


def test_cleanup_name_raises_not_implemented(tmp_path: Path):
    client = LLMClient(cache_dir=tmp_path, model_by_method={})
    with pytest.raises(NotImplementedError, match="Plan 3"):
        client.cleanup_name(raw_name="SUM(Sales)", kind="measure")
