"""Shared pytest fixtures for the tableau2pbir test suite."""
from __future__ import annotations

from pathlib import Path

import pytest
from dotenv import load_dotenv

load_dotenv()  # loads .env so ANTHROPIC_API_KEY is available in tests

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def synthetic_fixtures_dir() -> Path:
    return REPO_ROOT / "tests" / "golden" / "synthetic"


@pytest.fixture
def snapshot_replay_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Turn on LLM snapshot replay mode (§7 step 4 of LLMClient)."""
    monkeypatch.setenv("PYTEST_SNAPSHOT", "replay")
