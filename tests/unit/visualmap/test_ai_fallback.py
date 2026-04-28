"""map_visual AI fallback — snapshot replay returns a PbirVisual; if
visual_type is not in the catalog, the validator drops the response."""
from __future__ import annotations

from pathlib import Path

from tableau2pbir.ir.common import FieldRef
from tableau2pbir.ir.sheet import Encoding, Sheet
from tableau2pbir.llm.client import LLMClient
from tableau2pbir.visualmap.ai_fallback import map_visual_via_ai


def _sheet() -> Sheet:
    return Sheet(
        id="s1", name="Combo", datasource_refs=("ds1",),
        mark_type="bar",
        encoding=Encoding(
            rows=(FieldRef(table_id="t", column_id="t__col__sales"),),
            columns=(FieldRef(table_id="t", column_id="t__col__region"),),
        ),
        filters=(), sort=(), dual_axis=True,
        reference_lines=(), uses_calculations=(),
    )


def test_replay_returns_visual_passing_validation(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PYTEST_SNAPSHOT", "replay")
    client = LLMClient(cache_dir=tmp_path / "cache")
    pv = map_visual_via_ai(
        _sheet(), fixture="ai_only_combo_chart", client=client,
        known_field_ids=frozenset({"t__col__sales", "t__col__region"}),
    )
    assert pv is not None
    assert pv.visual_type in ("clusteredBarChart", "lineChart")


def test_replay_drops_unknown_visual_type(tmp_path: Path, monkeypatch):
    snaps = tmp_path / "snaps"
    (snaps / "map_visual").mkdir(parents=True)
    (snaps / "map_visual" / "broken.json").write_text(
        '{"visual_type": "madeUp", "encoding_bindings": [], '
        '"confidence": "low", "notes": ""}',
        encoding="utf-8",
    )
    monkeypatch.setenv("PYTEST_SNAPSHOT", "replay")
    client = LLMClient(cache_dir=tmp_path / "cache", snapshot_root=snaps)
    pv = map_visual_via_ai(
        _sheet(), fixture="broken", client=client,
        known_field_ids=frozenset(),
    )
    assert pv is None
