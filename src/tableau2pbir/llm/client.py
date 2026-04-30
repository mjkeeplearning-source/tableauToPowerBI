"""LLMClient — single AI entry point per spec §7.

Three modes per spec §7 step 4 + §9 layer vi:
1. Cache hit (content-hash) — zero network.
2. Snapshot replay (`PYTEST_SNAPSHOT=replay`) — zero network, read from
   `tests/llm_snapshots/<method>/<payload['fixture']>.json`.
3. Live — calls Anthropic SDK with tool-use; result validated against
   the prompt-pack tool schema; cached on success.

Validator: the response must be a valid tool-use block whose input keys
match the tool_schema.input_schema.required set; otherwise we drop it
(callers treat None / KeyError as a miss and route to unsupported[])."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from tableau2pbir.llm.cache import OnDiskCache, make_cache_key
from tableau2pbir.llm.prompt_loader import PromptPack, load_prompt_pack
from tableau2pbir.llm.snapshots import SnapshotStore, is_replay_mode

_METHODS = ("translate_calc", "map_visual", "cleanup_name")
_DEFAULT_MODEL = "claude-haiku-4-5"  #"claude-sonnet-4-6"
_SNAPSHOT_ROOT = Path(__file__).resolve().parents[3] / "tests" / "llm_snapshots"


class LLMClient:
    def __init__(
        self,
        *,
        cache_dir: Path,
        model_by_method: dict[str, str] | None = None,
        snapshot_root: Path | None = None,
    ) -> None:
        self.cache = OnDiskCache(cache_dir)
        self.packs: dict[str, PromptPack] = {m: load_prompt_pack(m) for m in _METHODS}
        self.model_by_method = {m: _DEFAULT_MODEL for m in _METHODS}
        if model_by_method:
            self.model_by_method.update(model_by_method)
        self.snapshots = SnapshotStore(snapshot_root or _SNAPSHOT_ROOT)

    # --- public entry points ---

    def translate_calc(self, calc_subset: dict[str, Any]) -> dict[str, Any]:
        return self._call("translate_calc", calc_subset)

    def map_visual(self, sheet_subset: dict[str, Any]) -> dict[str, Any]:
        return self._call("map_visual", sheet_subset)

    def cleanup_name(self, *, raw_name: str, kind: str) -> dict[str, Any]:
        return self._call("cleanup_name", {"raw_name": raw_name, "kind": kind})

    # --- shared dispatch ---

    def _call(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        pack = self.packs[method]
        model = self.model_by_method[method]
        cache_payload = {k: v for k, v in payload.items() if k != "fixture"}

        if is_replay_mode():
            fixture = payload.get("fixture")
            if not fixture:
                raise RuntimeError(
                    f"PYTEST_SNAPSHOT=replay set but no 'fixture' in payload "
                    f"for {method}: {payload!r}"
                )
            return self.snapshots.load(method, fixture)

        key = make_cache_key(
            model=model,
            prompt_hash=pack.system_prompt_hash,
            schema_hash=pack.tool_schema_hash,
            payload=cache_payload,
        )
        cached = self.cache.get(key)
        if cached is not None:
            return cached

        # Live path — strict env check up front.
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError(
                "ANTHROPIC_API_KEY not set — cannot run live LLM call. "
                "Set the env var, populate the cache, or use PYTEST_SNAPSHOT=replay."
            )
        result = self._call_anthropic(pack, model, payload)
        self._validate(pack, result)
        self.cache.put(key, result)
        return result

    def _call_anthropic(
        self, pack: PromptPack, model: str, payload: dict[str, Any],
    ) -> dict[str, Any]:
        # Lazy import so unit tests don't pay for the SDK on cache/replay paths.
        import anthropic

        client = anthropic.Anthropic()
        message = client.messages.create(
            model=model,
            max_tokens=1024,
            system=pack.system_text,
            tools=[pack.tool_schema],
            tool_choice={"type": "tool", "name": pack.tool_schema["name"]},
            messages=[
                {"role": "user", "content": json.dumps(payload, sort_keys=True)},
            ],
        )
        for block in message.content:
            if getattr(block, "type", None) == "tool_use":
                # Anthropic SDK returns dict for tool_use.input.
                return dict(block.input)  # type: ignore[arg-type]
        raise RuntimeError(f"no tool_use block in response for {pack.method}")

    def _validate(self, pack: PromptPack, result: dict[str, Any]) -> None:
        required = pack.tool_schema["input_schema"].get("required", [])
        missing = [k for k in required if k not in result]
        if missing:
            raise RuntimeError(
                f"{pack.method} response missing required keys: {missing}"
            )
