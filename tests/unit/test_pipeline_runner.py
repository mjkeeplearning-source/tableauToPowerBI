from __future__ import annotations

from pathlib import Path

import pytest

from tableau2pbir.pipeline import (
    STAGE_SEQUENCE, PipelineResult, run_pipeline,
)


def test_stage_sequence_has_8_stages():
    assert len(STAGE_SEQUENCE) == 8
    names = [s[0] for s in STAGE_SEQUENCE]
    assert names == ["extract", "canonicalize", "translate_calcs", "map_visuals",
                     "compute_layout", "build_tmdl", "build_pbir", "package_validate"]


def test_run_pipeline_full_run(tmp_path: Path):
    out = tmp_path / "wb"
    result = run_pipeline(
        workbook_id="wb",
        source_path=Path("dummy.twb"),
        output_dir=out,
        config={},
        gate=None,
        resume_from=None,
    )
    assert isinstance(result, PipelineResult)
    assert result.stages_run == 8
    # Per-stage artifacts
    for i, (name, _mod) in enumerate(STAGE_SEQUENCE, start=1):
        assert (out / "stages" / f"{i:02d}_{name}.json").exists()
        assert (out / "stages" / f"{i:02d}_{name}.summary.md").exists()
    # Stage 8 placeholder
    assert (out / "wb.pbip").exists()
    # Cumulative unsupported file exists
    assert (out / "unsupported.json").exists()


def test_run_pipeline_gate_stops_after_named_stage(tmp_path: Path):
    out = tmp_path / "wb"
    result = run_pipeline(
        workbook_id="wb", source_path=Path("d.twb"), output_dir=out,
        config={}, gate="canonicalize", resume_from=None,
    )
    assert result.stages_run == 2                          # extract + canonicalize
    assert (out / "stages" / "02_canonicalize.json").exists()
    assert not (out / "stages" / "03_translate_calcs.json").exists()


def test_run_pipeline_resume_from_reads_prior_output(tmp_path: Path):
    out = tmp_path / "wb"
    # First: gated run stops after stage 2
    run_pipeline(workbook_id="wb", source_path=Path("d.twb"), output_dir=out,
                 config={}, gate="canonicalize", resume_from=None)
    assert (out / "stages" / "02_canonicalize.json").exists()
    assert not (out / "stages" / "08_package_validate.json").exists()
    # Resume: picks up from stage 3
    result = run_pipeline(workbook_id="wb", source_path=Path("d.twb"), output_dir=out,
                          config={}, gate=None, resume_from="translate_calcs")
    assert result.stages_run == 6                          # stages 3..8
    assert (out / "stages" / "08_package_validate.json").exists()


def test_run_pipeline_resume_from_unknown_stage_errors(tmp_path: Path):
    with pytest.raises(ValueError, match="unknown stage"):
        run_pipeline(workbook_id="wb", source_path=Path("d.twb"),
                     output_dir=tmp_path, config={}, gate=None, resume_from="nonsense")
