"""Compute blocked_visuals[] per §A.4-3."""
from __future__ import annotations

from tableau2pbir.ir.common import UnsupportedItem


def compute_blocked_visuals(
    rendered: list[dict],
    unsupported: tuple[UnsupportedItem, ...],
    datasource_tier_by_field: dict[str, int],
) -> list[dict]:
    deferred_ids = {
        u.object_id for u in unsupported
        if (u.code or "").startswith("deferred_feature_")
    }
    out: list[dict] = []
    for v in rendered:
        blockers: list[str] = []
        for fid in v.get("field_ids", ()):
            if fid in deferred_ids:
                blockers.append(fid)
            elif datasource_tier_by_field.get(fid) == 4:
                blockers.append("tier4_datasource")
        if blockers:
            out.append({
                "page_id": v["page_id"], "visual_id": v["visual_id"],
                "blocked_by": blockers,
            })
    return out
