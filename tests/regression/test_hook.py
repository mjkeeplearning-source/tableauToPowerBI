from __future__ import annotations
import stat
import sys
from pathlib import Path
import pytest
from tableau2pbir.regression.hook import install_hook, HookInstallError


@pytest.mark.regression
def test_creates_hook_when_none_exists(tmp_path: Path):
    hooks_dir = tmp_path / ".git" / "hooks"
    hooks_dir.mkdir(parents=True)
    hook_path = hooks_dir / "pre-commit"
    install_hook(hook_path=hook_path)
    content = hook_path.read_text(encoding="utf-8")
    assert "regression-check" in content
    if sys.platform != "win32":
        assert hook_path.stat().st_mode & stat.S_IXUSR, "hook must be executable"


@pytest.mark.regression
def test_appends_when_hook_already_exists(tmp_path: Path):
    hooks_dir = tmp_path / ".git" / "hooks"
    hooks_dir.mkdir(parents=True)
    hook_path = hooks_dir / "pre-commit"
    hook_path.write_text("#!/bin/sh\necho 'existing'\n", encoding="utf-8")
    install_hook(hook_path=hook_path)
    content = hook_path.read_text(encoding="utf-8")
    assert "existing" in content
    assert "regression-check" in content


@pytest.mark.regression
def test_idempotent_when_already_installed(tmp_path: Path):
    hooks_dir = tmp_path / ".git" / "hooks"
    hooks_dir.mkdir(parents=True)
    hook_path = hooks_dir / "pre-commit"
    install_hook(hook_path=hook_path)
    install_hook(hook_path=hook_path)
    content = hook_path.read_text(encoding="utf-8")
    assert content.count("regression-check") == 1, "must not add duplicate entry"


@pytest.mark.regression
def test_raises_when_hooks_dir_missing(tmp_path: Path):
    hook_path = tmp_path / ".git" / "hooks" / "pre-commit"
    with pytest.raises(HookInstallError, match="hooks directory"):
        install_hook(hook_path=hook_path)
