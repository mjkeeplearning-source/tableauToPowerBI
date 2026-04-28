"""Stage-4 summary: visual-type histogram, rule-vs-AI rate, low-confidence
flags, unsupported mark types."""
from __future__ import annotations

from tableau2pbir.visualmap.summary import VisualMapStats, render_stage4_summary


def test_summary_includes_required_sections():
    stats = VisualMapStats(
        total_sheets=5,
        by_source={"rule": 3, "ai": 1, "skip": 1},
        visual_type_hist={"clusteredBarChart": 2, "lineChart": 1, "tableEx": 1},
        ai_low_confidence_sheet_ids=("s_low_conf",),
        unsupported_mark_types={"polygon": 1},
    )
    md = render_stage4_summary(stats)
    assert "# Stage 4" in md
    assert "rule: 3" in md
    assert "clusteredBarChart: 2" in md
    assert "s_low_conf" in md
    assert "polygon: 1" in md
