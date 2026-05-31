"""refresh-schemas command logic — downloads schemas to user cache. See spec §8."""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

_BUNDLED_DIR = Path(__file__).parent / "_schemas"


def _get_cache_dir(cli_override: str | None = None) -> Path:
    """Resolve cache dir: CLI flag → T2P_SCHEMA_CACHE env var → default."""
    val = cli_override or os.environ.get("T2P_SCHEMA_CACHE")
    return Path(val) if val else Path.home() / ".cache" / "tableau2pbir" / "schemas"


def refresh_schemas(cache_dir: Path, bundled_dir: Path = _BUNDLED_DIR) -> bool:
    """Download all schemas from manifest into cache_dir. Returns True if all succeeded."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    data = json.loads((bundled_dir / "manifest.json").read_text(encoding="utf-8"))
    all_ok = True
    for entry in data["schemas"]:
        url: str = entry["url"]
        filename: str = entry["file"]
        dest = cache_dir / filename
        try:
            with urllib.request.urlopen(url) as resp:
                content: bytes = resp.read()
        except Exception as exc:
            print(f"FAILED   {filename} ({exc})")
            all_ok = False
            continue
        existing = dest.read_bytes() if dest.is_file() else None
        if existing == content:
            print(f"unchanged  {filename}")
        else:
            dest.write_bytes(content)
            print(f"updated  {filename}")
    return all_ok
