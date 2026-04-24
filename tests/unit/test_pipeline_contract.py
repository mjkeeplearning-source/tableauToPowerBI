from __future__ import annotations

from pathlib import Path

import pytest

from tableau2pbir.pipeline import StageContext, StageError, StageResult


def test_stage_error_severity_levels():
    err = StageError(
        severity="warn", code="test.code", object_id="obj1",
        message="x", fix_hint=None,
    )
    assert err.severity == "warn"


def test_stage_error_rejects_unknown_severity():
    with pytest.raises(Exception):
        StageError(severity="bogus", code="c", object_id="o", message="m", fix_hint=None)


def test_stage_result_defaults():
    r = StageResult()
    assert r.output == {}
    assert r.summary_md == ""
    assert r.errors == ()


def test_stage_context_fields(tmp_path: Path):
    ctx = StageContext(
        workbook_id="wb1",
        output_dir=tmp_path,
        config={},
        stage_number=1,
    )
    assert ctx.stage_number == 1
