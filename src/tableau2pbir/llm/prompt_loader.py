"""Loads a per-prompt folder (§7) and computes its content hashes.

Each prompt method owns a folder containing:
  system.md        — system prompt text
  tool_schema.json — Anthropic tool-use JSON Schema
  VERSION          — semver; bumping invalidates cache + snapshots
  examples/*       — optional few-shot content (concatenated into system text)
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_PROMPTS_ROOT = Path(__file__).parent / "prompts"


@dataclass(frozen=True)
class PromptPack:
    method: str
    version: str
    system_text: str
    tool_schema: dict[str, Any]
    system_prompt_hash: str
    tool_schema_hash: str


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def load_prompt_pack(method: str, root: Path | None = None) -> PromptPack:
    base = (root or _PROMPTS_ROOT) / method
    if not base.is_dir():
        raise FileNotFoundError(f"no prompt folder for method: {method!r}")
    version = (base / "VERSION").read_text(encoding="utf-8").strip()
    system_text = (base / "system.md").read_text(encoding="utf-8")
    examples_dir = base / "examples"
    if examples_dir.is_dir():
        for example in sorted(examples_dir.glob("*")):
            if example.is_file() and example.name != ".gitkeep":
                system_text += "\n\n---\n\n" + example.read_text(encoding="utf-8")
    tool_schema = json.loads((base / "tool_schema.json").read_text(encoding="utf-8"))
    # Fold version into hash so a VERSION bump invalidates cache + snapshots (§A.3)
    system_hash_input = f"{version}\n---\n{system_text}"
    return PromptPack(
        method=method,
        version=version,
        system_text=system_text,
        tool_schema=tool_schema,
        system_prompt_hash=version + "-" + _hash(system_hash_input),
        tool_schema_hash=_hash(json.dumps(tool_schema, sort_keys=True)),
    )
