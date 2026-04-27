"""Stage 3 summary.md — counts by translation source, rule hit histogram,
AI confidence histogram, cache hit rate, validator failures."""
from __future__ import annotations

from tableau2pbir.translate.summary import TranslationStats, render_stage3_summary


def test_summary_renders_counts_and_histograms():
    stats = TranslationStats(
        total=10, by_source={"rule": 6, "ai": 3, "skip": 1},
        rule_hits={"row": 3, "aggregate": 2, "lod_fixed": 1},
        ai_confidence={"high": 1, "medium": 2, "low": 0},
        ai_cache_hits=2, ai_cache_misses=1,
        validator_failed=1,
    )
    md = render_stage3_summary(stats)
    assert "# Stage 3" in md
    assert "rule: 6" in md
    assert "ai: 3" in md
    assert "row: 3" in md
    assert "high: 1" in md
    assert "cache hit rate: 67%" in md
    assert "validator-failed: 1" in md


def test_summary_handles_zero_calcs():
    stats = TranslationStats(
        total=0, by_source={}, rule_hits={}, ai_confidence={},
        ai_cache_hits=0, ai_cache_misses=0, validator_failed=0,
    )
    md = render_stage3_summary(stats)
    assert "total calculations: 0" in md
    assert "cache hit rate: n/a" in md
