"""LLMClient — single AI entry point per spec §7.

This Plan-1 skeleton wires cache + prompt packs but raises NotImplementedError
on the three public methods; Plan 3 (stage 3 + stage 4 implementation) fills
them in with the Anthropic SDK flow (cache -> snapshot -> API -> validator).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from tableau2pbir.llm.cache import OnDiskCache
from tableau2pbir.llm.prompt_loader import PromptPack, load_prompt_pack

_METHODS = ("translate_calc", "map_visual", "cleanup_name")
_DEFAULT_MODEL = "claude-sonnet-4-6"


class LLMClient:
    def __init__(
        self,
        *,
        cache_dir: Path,
        model_by_method: dict[str, str] | None = None,
    ) -> None:
        self.cache = OnDiskCache(cache_dir)
        self.packs: dict[str, PromptPack] = {m: load_prompt_pack(m) for m in _METHODS}
        self.model_by_method = {m: _DEFAULT_MODEL for m in _METHODS}
        if model_by_method:
            self.model_by_method.update(model_by_method)

    # --- Plan-3 targets (stub in Plan 1) ---

    def translate_calc(self, calc_subset: dict[str, Any]) -> dict[str, Any]:
        """Return {dax_expr, confidence, notes}. Implemented in Plan 3."""
        raise NotImplementedError("LLMClient.translate_calc is filled in in Plan 3")

    def map_visual(self, sheet_subset: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError("LLMClient.map_visual is filled in in Plan 3")

    def cleanup_name(self, *, raw_name: str, kind: str) -> dict[str, Any]:
        raise NotImplementedError("LLMClient.cleanup_name is filled in in Plan 3")
