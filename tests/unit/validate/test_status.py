from tableau2pbir.validate.status import compute_status, ObservationBundle


def _bundle(**over):
    base = dict(
        datasource_tiers=(1,),
        unsupported=[],
        measures_total=10,
        placeholder_leaf_ratios=[0.0],
        blocked_visuals=[],
        tmdl_outcome="passed",
        pbir_compile_outcome="passed",
        desktop_open_outcome="passed",
        rubric_acceptance_failed=False,
        any_calc_low_confidence=False,
        any_clamped_or_dropped_layout=False,
        param_intents=[],
        user_actions=[],
    )
    base.update(over)
    return ObservationBundle(**base)


def test_ok_all_clean():
    s, triggers = compute_status(_bundle())
    assert s == "ok"
    assert triggers == []


def test_failed_when_any_tier_4_datasource():
    s, triggers = compute_status(_bundle(datasource_tiers=(1, 4)))
    assert s == "failed"
    assert "datasource_tier_4" in triggers


def test_failed_when_more_than_50pct_measures_dropped():
    unsupported = [
        {"object_kind": "calculation", "code": "calc.invalid_dax", "severity": "warn"}
    ] * 6
    s, triggers = compute_status(_bundle(measures_total=10, unsupported=unsupported))
    assert s == "failed"
    assert "measures_drop_rate_over_50pct" in triggers


def test_failed_when_pbir_compile_fails():
    s, triggers = compute_status(_bundle(pbir_compile_outcome="failed"))
    assert s == "failed"
    assert "pbir_compile_failed" in triggers


def test_failed_when_acceptance_failed():
    s, triggers = compute_status(_bundle(rubric_acceptance_failed=True))
    assert s == "failed"
    assert "acceptance_failed" in triggers


def test_failed_when_blocked_visual_with_deferred_datasource():
    s, triggers = compute_status(_bundle(
        blocked_visuals=[{"page_id": "p1", "visual_id": "v1",
                          "blocked_by": ["deferred_feature_table_calc"]}],
        unsupported=[{"object_kind": "datasource",
                      "code": "deferred_feature_table_calc",
                      "severity": "warn"}],
    ))
    assert s == "failed"
    assert "blocked_visual_with_deferred_datasource" in triggers


def test_partial_when_dashboard_has_placeholder_leaves():
    s, triggers = compute_status(_bundle(placeholder_leaf_ratios=[0.2]))
    assert s == "partial"
    assert "dashboard_has_placeholders" in triggers


def test_partial_when_low_confidence_calc():
    s, triggers = compute_status(_bundle(any_calc_low_confidence=True))
    assert s == "partial"


def test_partial_when_tier_3_datasource():
    s, triggers = compute_status(_bundle(datasource_tiers=(1, 3)))
    assert s == "partial"
    assert "datasource_tier_3" in triggers


def test_skipped_validators_dont_affect_status():
    s, triggers = compute_status(_bundle(
        tmdl_outcome="skipped", pbir_compile_outcome="skipped",
        desktop_open_outcome="skipped",
    ))
    assert s == "ok"
    assert triggers == []


def test_failed_dominates_partial_signals():
    s, triggers = compute_status(_bundle(
        datasource_tiers=(4,),                  # → failed
        placeholder_leaf_ratios=[0.2],          # would be partial
    ))
    assert s == "failed"
