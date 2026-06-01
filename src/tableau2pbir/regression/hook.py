"""Install regression-check as a git pre-commit hook."""
from __future__ import annotations
import stat
from pathlib import Path

_HOOK_LINE = "python -m tableau2pbir.cli regression-check\n"
_SHEBANG = "#!/bin/sh\n"


class HookInstallError(Exception):
    pass


def install_hook(hook_path: Path) -> bool:
    """Write or append regression-check to the pre-commit hook.

    Returns True if newly written, False if already present (idempotent).
    Raises HookInstallError if the hooks directory does not exist.
    """
    if not hook_path.parent.exists():
        raise HookInstallError(
            f"hooks directory {hook_path.parent} does not exist. "
            "Run this command from the root of a git repository."
        )

    if hook_path.exists():
        content = hook_path.read_text(encoding="utf-8")
        if _HOOK_LINE.strip() in content:
            return False  # already installed
        hook_path.write_text(content.rstrip("\n") + "\n" + _HOOK_LINE, encoding="utf-8")
    else:
        hook_path.write_text(_SHEBANG + _HOOK_LINE, encoding="utf-8")

    # Set executable bit (owner + group + other)
    current = hook_path.stat().st_mode
    hook_path.chmod(current | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return True
