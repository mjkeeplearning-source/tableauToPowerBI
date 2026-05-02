"""PBIR visual catalog. v1 scope: bar (clustered + stacked), line, area,
scatter, table, pie, filledMap. Each visual type has a fixed set of
encoding slots (channel names) the validator enforces."""
from __future__ import annotations

from tableau2pbir.visualmap.catalog import VISUAL_TYPES, slots_for


def test_v1_visuals_present():
    expected = {
        "clusteredBarChart", "stackedBarChart",
        "lineChart", "areaChart", "scatterChart",
        "tableEx", "pieChart", "filledMap",
    }
    assert expected.issubset(VISUAL_TYPES)


def test_slots_for_clustered_bar():
    s = slots_for("clusteredBarChart")
    assert "Category" in s
    assert "Y" in s
    assert "category" not in s   # old lowercase name must be gone
    assert "value" not in s      # old lowercase name must be gone


def test_slots_for_unknown_visual_raises():
    import pytest
    with pytest.raises(KeyError):
        slots_for("doesNotExist")
