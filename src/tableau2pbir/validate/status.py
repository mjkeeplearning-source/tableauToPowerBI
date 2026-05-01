"""Workbook status rule (spec §8.1)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ObservationBundle:
    datasource_tiers: tuple[int, ...]
    unsupported: list[dict]                     # raw unsupported.json items
    measures_total: int
    placeholder_leaf_ratios: list[float]
    blocked_visuals: list[dict]                 # from stage 7 manifest
    tmdl_outcome: str                           # 'passed' | 'failed' | 'skipped'
    pbir_compile_outcome: str
    desktop_open_outcome: str
    rubric_acceptance_failed: bool
    any_calc_low_confidence: bool
    any_clamped_or_dropped_layout: bool
    param_intents: list[str]                    # values like 'unsupported'
    user_actions: list[str]                     # e.g. 'install Oracle client'


def compute_status(obs: ObservationBundle) -> tuple[str, list[str]]:
    triggers: list[str] = []

    # ----- failed checks (top-to-bottom) -----
    if any(t == 4 for t in obs.datasource_tiers):
        triggers.append("datasource_tier_4")

    measure_drops = sum(
        1 for u in obs.unsupported
        if u.get("object_kind") == "calculation" and u.get("severity") in ("warn", "error", "fatal")
    )
    if obs.measures_total > 0 and measure_drops / obs.measures_total > 0.5:
        triggers.append("measures_drop_rate_over_50pct")

    if any(r >= 0.5 for r in obs.placeholder_leaf_ratios):
        triggers.append("dashboard_placeholder_ratio_over_50pct")

    if obs.tmdl_outcome == "failed":
        triggers.append("tmdl_validity_failed")
    if obs.pbir_compile_outcome == "failed":
        triggers.append("pbir_compile_failed")
    if obs.desktop_open_outcome == "failed":
        triggers.append("desktop_open_gate_failed")
    if obs.rubric_acceptance_failed:
        triggers.append("acceptance_failed")

    deferred_ds_codes = {
        u.get("code") for u in obs.unsupported
        if u.get("object_kind") == "datasource"
        and str(u.get("code", "")).startswith("deferred_feature_")
    }
    for bv in obs.blocked_visuals:
        if any(code in deferred_ds_codes for code in bv.get("blocked_by", ())):
            triggers.append("blocked_visual_with_deferred_datasource")
            break

    if triggers:
        return ("failed", triggers)

    # ----- partial checks -----
    if any(0 < r < 0.5 for r in obs.placeholder_leaf_ratios):
        triggers.append("dashboard_has_placeholders")
    if obs.any_calc_low_confidence:
        triggers.append("calc_low_confidence")
    if obs.any_clamped_or_dropped_layout:
        triggers.append("layout_clamped_or_dropped")
    if any(t == 3 for t in obs.datasource_tiers):
        triggers.append("datasource_tier_3")
    if any("install" in ua.lower() for ua in obs.user_actions):
        triggers.append("driver_install_required")
    if "unsupported" in obs.param_intents:
        triggers.append("parameter_intent_unsupported")
    if any(str(u.get("code", "")).startswith("deferred_feature_") for u in obs.unsupported):
        triggers.append("deferred_feature_present")

    if triggers:
        return ("partial", triggers)
    return ("ok", [])
