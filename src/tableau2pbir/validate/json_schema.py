"""JSON schema validation against official Microsoft PBIR schemas. See spec §5."""
from __future__ import annotations

import json
import os
from pathlib import Path

import jsonschema

from tableau2pbir.validate.results import (
    SchemaFinding,
    SchemaValidationResult,
    ValidatorOutcome,
)

_BUNDLED_DIR = Path(__file__).parent / "_schemas"
_SKIP_DIRS = frozenset({"validation", "stages"})


def _load_manifest(bundled_dir: Path) -> dict[str, str]:
    """Return {url: filename} from manifest.json in bundled_dir."""
    data = json.loads((bundled_dir / "manifest.json").read_text(encoding="utf-8"))
    return {entry["url"]: entry["file"] for entry in data["schemas"]}


def _resolve_schema(url: str, cache_dir: Path, bundled_dir: Path) -> dict[str, object] | None:
    """Return schema dict from user cache or bundled fallback. None if unavailable."""
    manifest = _load_manifest(bundled_dir)
    filename = manifest.get(url)
    if filename is None:
        return None
    for search_dir in (cache_dir, bundled_dir):
        candidate = search_dir / filename
        if candidate.is_file():
            return json.loads(candidate.read_text(encoding="utf-8"))  # type: ignore[return-value]
    return None


def _default_cache_dir() -> Path:
    env = os.environ.get("T2P_SCHEMA_CACHE")
    return Path(env) if env else Path.home() / ".cache" / "tableau2pbir" / "schemas"


def run_json_schema(
    out_dir: Path,
    cache_dir: Path | None = None,
    _bundled_dir: Path = _BUNDLED_DIR,
) -> SchemaValidationResult:
    """Walk all *.json under out_dir and validate files that declare $schema."""
    if cache_dir is None:
        cache_dir = _default_cache_dir()
    manifest = _load_manifest(_bundled_dir)
    findings: list[SchemaFinding] = []

    for json_file in sorted(out_dir.rglob("*.json")):
        rel_parts = json_file.relative_to(out_dir).parts
        if rel_parts[0] in _SKIP_DIRS:
            continue
        try:
            data: dict[str, object] = json.loads(json_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(data, dict):
            continue
        url = data.get("$schema")
        if not isinstance(url, str):
            continue
        if url not in manifest:
            findings.append(SchemaFinding(
                code="schema.not_cached",
                severity="warn",
                message=f"$schema URL not in bundled manifest: {url!r}",
                location=str(json_file.relative_to(out_dir)),
            ))
            continue
        schema = _resolve_schema(url, cache_dir, _bundled_dir)
        if schema is None:
            continue  # in manifest but files missing — packaging error, skip silently
        # Strip $schema from instance data before validation — it is a meta-keyword
        # and should not be treated as a data property (would trigger additionalProperties errors).
        instance = {k: v for k, v in data.items() if k != "$schema"}
        validator = jsonschema.Draft7Validator(schema)
        for error in validator.iter_errors(instance):
            path_str = " > ".join(str(p) for p in error.absolute_path) or "(root)"
            findings.append(SchemaFinding(
                code="schema.violation",
                severity="warn",
                message=f"{error.message} (at {path_str})",
                location=str(json_file.relative_to(out_dir)),
            ))

    outcome = ValidatorOutcome.FAILED if findings else ValidatorOutcome.PASSED
    return SchemaValidationResult(
        outcome=outcome,
        findings=tuple(findings),
        log_path="validation/json_schema.json",
    )
