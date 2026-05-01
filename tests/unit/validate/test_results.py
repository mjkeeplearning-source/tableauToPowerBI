from tableau2pbir.validate.results import (
    ValidatorOutcome, ValidatorResult, StructuralFinding, StructuralResult,
    TraceEvent, DesktopOpenResult, RubricItemResult, RubricResult,
)


def test_validator_result_passed_minimal():
    r = ValidatorResult(outcome=ValidatorOutcome.PASSED, reason=None, log_path="validation/foo.log")
    assert r.outcome.value == "passed"
    assert r.reason is None


def test_validator_result_skipped_requires_reason():
    r = ValidatorResult(outcome=ValidatorOutcome.SKIPPED, reason="te2_unavailable", log_path=None)
    assert r.outcome.value == "skipped"
    assert r.reason == "te2_unavailable"


def test_structural_finding_fields():
    f = StructuralFinding(code="visual.missing_field", severity="error",
                          message="visual v1 references unknown field colX",
                          location="pages/p1/visuals/v1/visual.json")
    assert f.severity == "error"


def test_desktop_open_result_collects_events():
    e1 = TraceEvent(name="ReportLoaded", timestamp_ms=1000, raw="...")
    r = DesktopOpenResult(outcome=ValidatorOutcome.PASSED, reason=None, events=(e1,),
                          expected_credential_prompts=(), log_path="validation/desktop_open.log")
    assert r.events[0].name == "ReportLoaded"


def test_rubric_item_pass_records_observed():
    item = RubricItemResult(name="all_pages_load", required=True,
                            outcome=ValidatorOutcome.PASSED, observed="2/2 pages")
    assert item.required is True


def test_dataclasses_are_frozen():
    r = ValidatorResult(outcome=ValidatorOutcome.PASSED, reason=None, log_path=None)
    import dataclasses
    assert dataclasses.is_dataclass(r)
    try:
        r.reason = "x"     # type: ignore[misc]
    except dataclasses.FrozenInstanceError:
        return
    raise AssertionError("ValidatorResult should be frozen")
