"""Canvas size selection — §6 Stage 5 step 2 + step 3."""
from __future__ import annotations

from tableau2pbir.ir.dashboard import DashboardSize

_DEFAULT_W = 1280
_DEFAULT_H = 720


def select_canvas(size: DashboardSize, config: dict) -> tuple[int, int, float]:
    """Return (canvas_w, canvas_h, scale). Scale is applied to all leaf rects."""
    layout_cfg = (config or {}).get("layout", {}) or {}
    override_w = layout_cfg.get("canvas_w")
    override_h = layout_cfg.get("canvas_h")

    if size.kind == "automatic" or (size.w == 0 or size.h == 0):
        nominal_w, nominal_h = _DEFAULT_W, _DEFAULT_H
    else:
        nominal_w, nominal_h = size.w, size.h

    if override_w and override_h:
        scale = min(override_w / nominal_w, override_h / nominal_h)
        return (override_w, override_h, scale)
    return (nominal_w, nominal_h, 1.0)
