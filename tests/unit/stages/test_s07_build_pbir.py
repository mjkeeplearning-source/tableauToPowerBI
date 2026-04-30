from pathlib import Path

from tests.unit.emit.pbir.test_render import _wb_one_page_one_visual  # type: ignore
from tableau2pbir.pipeline import StageContext
from tableau2pbir.stages import s07_build_pbir


def test_stage7_runner_writes_files_and_returns_manifest(tmp_path: Path):
    wb = _wb_one_page_one_visual()
    ctx = StageContext(workbook_id="wb", output_dir=tmp_path, config={}, stage_number=7)
    result = s07_build_pbir.run(wb.model_dump(mode="json"), ctx)
    assert (tmp_path / "Report" / "definition" / "report.json").is_file()
    assert result.output["counts"]["pages"] == 1
    assert "Stage 7" in result.summary_md
    assert "blocked_visuals" in result.output
