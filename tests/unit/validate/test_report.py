from tableau2pbir.validate.report import (
    render_workbook_report, render_summary_md, render_run_manifest_row,
)


def test_workbook_report_lists_status_and_triggers():
    md = render_workbook_report(
        workbook_id="Foo",
        status="partial", triggers=["datasource_tier_3"],
        validators={
            "tmdl": {"outcome": "passed", "reason": None},
            "pbir_compile": {"outcome": "skipped", "reason": "pbi_tools_unavailable"},
            "structural": {"outcome": "passed", "findings": []},
            "desktop_open": {"outcome": "skipped", "reason": "synthetic"},
            "rubric": {"outcome": "skipped", "reason": "no_rubric"},
        },
        datasources=[{"name": "Sales", "tier": 3, "user_action_required": ["enter creds"]}],
        placeholders_per_page={"Overview": 0},
    )
    assert "# Workbook conversion report — Foo" in md
    assert "**Status:** partial" in md
    assert "datasource_tier_3" in md
    assert "tmdl: passed" in md
    assert "pbi_tools_unavailable" in md
    assert "Sales" in md


def test_summary_lists_validator_outcomes():
    md = render_summary_md(
        validators={"tmdl": {"outcome": "passed"},
                    "pbir_compile": {"outcome": "skipped", "reason": "x"},
                    "structural": {"outcome": "passed"},
                    "desktop_open": {"outcome": "skipped", "reason": "y"},
                    "rubric": {"outcome": "skipped", "reason": "z"}},
        artifact_size_bytes=12345,
        status="ok",
    )
    assert "Stage 8" in md
    assert "tmdl: passed" in md
    assert "12345" in md
    assert "ok" in md


def test_run_manifest_row_columns():
    row = render_run_manifest_row("Foo", "partial", ["calc_low_confidence"], "Foo/workbook-report.md")
    assert row.startswith("| Foo |")
    assert "partial" in row
    assert "calc_low_confidence" in row
    assert "Foo/workbook-report.md" in row
