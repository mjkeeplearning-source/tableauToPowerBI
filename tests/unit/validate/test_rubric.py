from pathlib import Path
import textwrap

from tableau2pbir.validate.rubric import load_rubric, evaluate_rubric, write_acceptance_json
from tableau2pbir.validate.results import ValidatorOutcome


def _write(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "wb.rubric.yaml"
    p.write_text(textwrap.dedent(body), encoding="utf-8")
    return p


def test_load_rubric_minimal(tmp_path):
    p = _write(tmp_path, """
        workbook: Foo.twbx
        pages: []
        measures: []
        datasources: []
        pass_criteria:
          all_pages_load: true
    """)
    r = load_rubric(p)
    assert r.workbook == "Foo.twbx"
    assert r.pass_criteria["all_pages_load"] is True


def test_evaluate_passes_when_observation_matches(tmp_path):
    p = _write(tmp_path, """
        workbook: Foo.twbx
        pages:
          - name: Overview
            must_render_visuals: [bar_by_region]
            must_have_slicers: [region]
            known_degradations: []
        measures: []
        datasources: []
        pass_criteria:
          all_pages_load: true
          all_must_render_visuals_present: true
          all_must_have_slicers_present: true
          no_unexpected_placeholders: true
          desktop_open_gate: passed
    """)
    rubric = load_rubric(p)

    observation = {
        "rendered_pages": ["Overview"],
        "rendered_visuals_by_page": {"Overview": ["bar_by_region"]},
        "rendered_slicers_by_page": {"Overview": ["region"]},
        "placeholder_visuals_by_page": {"Overview": []},
        "desktop_open_outcome": "passed",
    }
    result = evaluate_rubric(rubric, observation)
    assert result.outcome == ValidatorOutcome.PASSED
    names = [item.name for item in result.items]
    assert "all_pages_load" in names
    assert "desktop_open_gate" in names


def test_evaluate_fails_when_must_render_visual_missing(tmp_path):
    p = _write(tmp_path, """
        workbook: Foo.twbx
        pages:
          - name: Overview
            must_render_visuals: [bar_by_region]
            must_have_slicers: []
            known_degradations: []
        measures: []
        datasources: []
        pass_criteria:
          all_must_render_visuals_present: true
    """)
    rubric = load_rubric(p)
    observation = {
        "rendered_pages": ["Overview"],
        "rendered_visuals_by_page": {"Overview": []},
        "rendered_slicers_by_page": {"Overview": []},
        "placeholder_visuals_by_page": {"Overview": []},
        "desktop_open_outcome": "skipped",
    }
    r = evaluate_rubric(rubric, observation)
    assert r.outcome == ValidatorOutcome.FAILED
    bad = next(i for i in r.items if i.name == "all_must_render_visuals_present")
    assert bad.outcome == ValidatorOutcome.FAILED


def test_measure_tolerance_is_skipped_in_v1(tmp_path):
    p = _write(tmp_path, """
        workbook: Foo.twbx
        pages: []
        measures:
          - name: Total Revenue
            must_match_tableau_value_within: 0.0001
        datasources: []
        pass_criteria:
          all_measure_values_within_tolerance: true
    """)
    rubric = load_rubric(p)
    r = evaluate_rubric(rubric, {})
    item = next(i for i in r.items if i.name == "all_measure_values_within_tolerance")
    assert item.outcome == ValidatorOutcome.SKIPPED


def test_write_acceptance_json_emits_per_item(tmp_path):
    from tableau2pbir.validate.results import RubricItemResult, RubricResult
    rr = RubricResult(outcome=ValidatorOutcome.PASSED, reason=None, items=(
        RubricItemResult(name="all_pages_load", required=True,
                         outcome=ValidatorOutcome.PASSED, observed="2/2"),
    ))
    out = tmp_path / "acceptance.json"
    write_acceptance_json(out, rr)
    import json
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["overall"] == "passed"
    assert data["items"][0] == {
        "name": "all_pages_load", "required": True,
        "outcome": "passed", "observed": "2/2",
    }
