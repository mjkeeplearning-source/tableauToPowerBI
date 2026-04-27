"""PBIR visual-type catalog (v1). Maps each supported visual_type to its
allowed encoding-channel slots. The set is what stage 4 emits; the AI
fallback's tool schema enumerates the same set so the model cannot invent
a non-existent visual."""
from __future__ import annotations

_SLOTS: dict[str, frozenset[str]] = {
    "clusteredBarChart": frozenset({"category", "value", "series", "tooltip"}),
    "stackedBarChart":   frozenset({"category", "value", "series", "tooltip"}),
    "lineChart":         frozenset({"category", "value", "series", "tooltip"}),
    "areaChart":         frozenset({"category", "value", "series", "tooltip"}),
    "scatterChart":      frozenset({"x", "y", "size", "color", "details", "tooltip"}),
    "tableEx":           frozenset({"values", "tooltip"}),  # matrix-like text-table
    "pieChart":          frozenset({"category", "value", "tooltip"}),
    "filledMap":         frozenset({"location", "value", "color", "tooltip"}),
}

VISUAL_TYPES: frozenset[str] = frozenset(_SLOTS)


def slots_for(visual_type: str) -> frozenset[str]:
    return _SLOTS[visual_type]
