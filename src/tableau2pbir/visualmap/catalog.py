"""PBIR visual-type catalog (v1). Maps each supported visual_type to its
allowed encoding-channel slots. The set is what stage 4 emits; the AI
fallback's tool schema enumerates the same set so the model cannot invent
a non-existent visual."""
from __future__ import annotations

_SLOTS: dict[str, frozenset[str]] = {
    "clusteredBarChart": frozenset({"Category", "Y", "Series", "Tooltips"}),
    "stackedBarChart":   frozenset({"Category", "Y", "Series", "Tooltips"}),
    "lineChart":         frozenset({"Category", "Y", "Series", "Tooltips"}),
    "areaChart":         frozenset({"Category", "Y", "Series", "Tooltips"}),
    "scatterChart":      frozenset({"X", "Y", "Size", "Color", "Details", "Tooltips"}),
    "tableEx":           frozenset({"Values", "Tooltips"}),
    "pieChart":          frozenset({"Category", "Y", "Tooltips"}),
    "filledMap":         frozenset({"Location", "Y", "Color", "Tooltips"}),
}

VISUAL_TYPES: frozenset[str] = frozenset(_SLOTS)


def slots_for(visual_type: str) -> frozenset[str]:
    return _SLOTS[visual_type]
