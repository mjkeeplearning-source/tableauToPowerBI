"""ai_fallback.translate_via_ai — invokes LLMClient and validates the
response: dax_expr must pass the syntax gate, else returns None so the
caller routes the calc to unsupported[]."""
from __future__ import annotations

from pathlib import Path

import pytest

from tableau2pbir.ir.calculation import (
    Calculation, CalculationKind, CalculationPhase,
)
from tableau2pbir.llm.client import LLMClient
from tableau2pbir.translate.ai_fallback import translate_via_ai


def _calc(expr: str) -> Calculation:
    return Calculation(
        id="c1", name="Conditional", scope="measure", tableau_expr=expr,
        depends_on=(), kind=CalculationKind.AGGREGATE,
        phase=CalculationPhase.AGGREGATE,
    )


def test_replay_returns_dax_when_syntax_passes(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PYTEST_SNAPSHOT", "replay")
    client = LLMClient(cache_dir=tmp_path / "cache")
    c = _calc("SUM(IF [r] = 'x' THEN [s] END)")
    out = translate_via_ai(c, fixture="ai_only_aggregate_conditional",
                           client=client)
    assert out is not None
    assert out["dax_expr"]


def test_replay_drops_when_syntax_fails(tmp_path: Path, monkeypatch):
    """A snapshot whose dax_expr is intentionally malformed must be
    rejected by the gate and return None."""
    snapshots_root = tmp_path / "snaps"
    (snapshots_root / "translate_calc").mkdir(parents=True)
    (snapshots_root / "translate_calc" / "broken.json").write_text(
        '{"dax_expr": "@@@ broken", "confidence": "low", "notes": ""}',
        encoding="utf-8",
    )
    monkeypatch.setenv("PYTEST_SNAPSHOT", "replay")
    client = LLMClient(cache_dir=tmp_path / "cache",
                       snapshot_root=snapshots_root)
    c = _calc("SUM([s])")
    out = translate_via_ai(c, fixture="broken", client=client)
    assert out is None
