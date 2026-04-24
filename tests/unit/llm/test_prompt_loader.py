from __future__ import annotations

from tableau2pbir.llm.prompt_loader import PromptPack, load_prompt_pack


def test_load_translate_calc_pack():
    pack = load_prompt_pack("translate_calc")
    assert isinstance(pack, PromptPack)
    assert pack.method == "translate_calc"
    assert pack.version
    assert pack.system_text
    assert "name" in pack.tool_schema
    assert pack.system_prompt_hash
    assert pack.tool_schema_hash


def test_load_map_visual_pack():
    pack = load_prompt_pack("map_visual")
    assert pack.method == "map_visual"
    assert pack.tool_schema.get("name")


def test_load_cleanup_name_pack():
    pack = load_prompt_pack("cleanup_name")
    assert pack.method == "cleanup_name"


def test_version_change_changes_hash():
    pack = load_prompt_pack("translate_calc")
    assert pack.version in pack.system_prompt_hash                 # version folded into hash
