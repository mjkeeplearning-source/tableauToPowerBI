from __future__ import annotations
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from tableau2pbir.regression.corpus import CorpusEntry, save_corpus
from tableau2pbir.regression.check import run_regression_check
from tableau2pbir.regression.report import format_report


_TMDL_ORDERS = """\
table orders

\tcolumn order_id
\t\tdataType: int64
\t\tsourceColumn: order_id

\tmeasure 'Total Sales' = SUM([Sales])

\tpartition orders = m
\t\tmode: directQuery
\t\tsource =
\t\t\tlet Source = Sql.Database() in Source
"""

_REPORT_JSON = json.dumps({"$schema": "x", "id": "r1", "name": "Report"})


def _write_snapshot(snap_dir: Path, tmdl: str, rjson: str) -> None:
    sm = snap_dir / "SemanticModel" / "definition" / "tables"
    sm.mkdir(parents=True)
    (sm / "orders.tmdl").write_text(tmdl, encoding="utf-8")
    rd = snap_dir / "Report" / "definition"
    rd.mkdir(parents=True)
    (rd / "report.json").write_text(rjson, encoding="utf-8")


def _make_fake_pipeline_output(out_dir: Path, wb_name: str, tmdl: str, rjson: str) -> None:
    sm = out_dir / wb_name / "SemanticModel" / "definition" / "tables"
    sm.mkdir(parents=True)
    (sm / "orders.tmdl").write_text(tmdl, encoding="utf-8")
    rd = out_dir / wb_name / "Report" / "definition"
    rd.mkdir(parents=True)
    (rd / "report.json").write_text(rjson, encoding="utf-8")


@pytest.mark.regression
def test_check_pass_when_output_matches(tmp_path: Path):
    corpus_path = tmp_path / "corpus.yaml"
    snap_root = tmp_path / "snapshots"
    entry = CorpusEntry("wb", str(tmp_path / "wb.twb"), "me", "2026-01-01")
    save_corpus([entry], corpus_path)
    _write_snapshot(snap_root / "wb", _TMDL_ORDERS, _REPORT_JSON)

    def fake_run(cmd, **kwargs):
        out_dir = Path(cmd[cmd.index("--out") + 1])
        _make_fake_pipeline_output(out_dir, "wb", _TMDL_ORDERS, _REPORT_JSON)
        return MagicMock(returncode=0, stderr="", stdout="")

    with patch("subprocess.run", side_effect=fake_run):
        result = run_regression_check(corpus_path=corpus_path, snapshots_root=snap_root)

    assert result.all_passed
    assert result.exit_code == 0
    assert result.workbook_results[0].status == "PASS"


@pytest.mark.regression
def test_check_fail_when_tmdl_changes(tmp_path: Path):
    corpus_path = tmp_path / "corpus.yaml"
    snap_root = tmp_path / "snapshots"
    entry = CorpusEntry("wb", str(tmp_path / "wb.twb"), "me", "2026-01-01")
    save_corpus([entry], corpus_path)
    _write_snapshot(snap_root / "wb", _TMDL_ORDERS, _REPORT_JSON)

    modified_tmdl = _TMDL_ORDERS.replace("int64", "string")

    def fake_run(cmd, **kwargs):
        out_dir = Path(cmd[cmd.index("--out") + 1])
        _make_fake_pipeline_output(out_dir, "wb", modified_tmdl, _REPORT_JSON)
        return MagicMock(returncode=0, stderr="", stdout="")

    with patch("subprocess.run", side_effect=fake_run):
        result = run_regression_check(corpus_path=corpus_path, snapshots_root=snap_root)

    assert not result.all_passed
    assert result.exit_code == 1
    assert result.workbook_results[0].status == "FAIL"
    all_diffs = [d for fd in result.workbook_results[0].file_diffs for d in fd.diffs]
    assert any(d.attribute == "dataType" for d in all_diffs)


@pytest.mark.regression
def test_check_fail_when_json_changes(tmp_path: Path):
    corpus_path = tmp_path / "corpus.yaml"
    snap_root = tmp_path / "snapshots"
    entry = CorpusEntry("wb", str(tmp_path / "wb.twb"), "me", "2026-01-01")
    save_corpus([entry], corpus_path)
    _write_snapshot(snap_root / "wb", _TMDL_ORDERS, _REPORT_JSON)

    modified_json = json.dumps({"$schema": "x", "id": "r1", "name": "Changed"})

    def fake_run(cmd, **kwargs):
        out_dir = Path(cmd[cmd.index("--out") + 1])
        _make_fake_pipeline_output(out_dir, "wb", _TMDL_ORDERS, modified_json)
        return MagicMock(returncode=0, stderr="", stdout="")

    with patch("subprocess.run", side_effect=fake_run):
        result = run_regression_check(corpus_path=corpus_path, snapshots_root=snap_root)

    assert not result.all_passed
    assert result.workbook_results[0].status == "FAIL"


@pytest.mark.regression
def test_check_fail_when_snapshot_file_missing_from_output(tmp_path: Path):
    corpus_path = tmp_path / "corpus.yaml"
    snap_root = tmp_path / "snapshots"
    entry = CorpusEntry("wb", str(tmp_path / "wb.twb"), "me", "2026-01-01")
    save_corpus([entry], corpus_path)
    _write_snapshot(snap_root / "wb", _TMDL_ORDERS, _REPORT_JSON)

    def fake_run(cmd, **kwargs):
        out_dir = Path(cmd[cmd.index("--out") + 1])
        # Only emit the JSON, skip the TMDL (simulates deleted table)
        rd = out_dir / "wb" / "Report" / "definition"
        rd.mkdir(parents=True)
        (rd / "report.json").write_text(_REPORT_JSON, encoding="utf-8")
        return MagicMock(returncode=0, stderr="", stdout="")

    with patch("subprocess.run", side_effect=fake_run):
        result = run_regression_check(corpus_path=corpus_path, snapshots_root=snap_root)

    assert not result.all_passed
    file_diffs = result.workbook_results[0].file_diffs
    assert any(fd.missing for fd in file_diffs)


@pytest.mark.regression
def test_check_skip_when_no_api_key(tmp_path: Path):
    corpus_path = tmp_path / "corpus.yaml"
    snap_root = tmp_path / "snapshots"
    entry = CorpusEntry("wb", str(tmp_path / "wb.twb"), "me", "2026-01-01")
    save_corpus([entry], corpus_path)
    _write_snapshot(snap_root / "wb", _TMDL_ORDERS, _REPORT_JSON)

    with patch("subprocess.run", return_value=MagicMock(
        returncode=1, stderr="ANTHROPIC_API_KEY not set", stdout=""
    )):
        result = run_regression_check(corpus_path=corpus_path, snapshots_root=snap_root)

    assert result.all_passed  # SKIP counts as passed
    assert result.workbook_results[0].status == "SKIP"


@pytest.mark.regression
def test_check_single_workbook_by_name(tmp_path: Path):
    corpus_path = tmp_path / "corpus.yaml"
    snap_root = tmp_path / "snapshots"
    e1 = CorpusEntry("wb1", str(tmp_path / "wb1.twb"), "me", "2026-01-01")
    e2 = CorpusEntry("wb2", str(tmp_path / "wb2.twb"), "me", "2026-01-01")
    save_corpus([e1, e2], corpus_path)
    _write_snapshot(snap_root / "wb1", _TMDL_ORDERS, _REPORT_JSON)

    def fake_run(cmd, **kwargs):
        out_dir = Path(cmd[cmd.index("--out") + 1])
        _make_fake_pipeline_output(out_dir, "wb1", _TMDL_ORDERS, _REPORT_JSON)
        return MagicMock(returncode=0, stderr="", stdout="")

    with patch("subprocess.run", side_effect=fake_run):
        result = run_regression_check(corpus_path=corpus_path, snapshots_root=snap_root, name_filter="wb1")

    assert len(result.workbook_results) == 1
    assert result.workbook_results[0].name == "wb1"


@pytest.mark.regression
def test_format_report_pass(tmp_path: Path):
    from tableau2pbir.regression.compare.result import WorkbookResult, RegressionResult
    r = RegressionResult([WorkbookResult("wb", "PASS")])
    output = format_report(r)
    assert "PASS" in output
    assert "wb" in output


@pytest.mark.regression
def test_format_report_fail_shows_diffs(tmp_path: Path):
    from tableau2pbir.regression.compare.result import (
        WorkbookResult, RegressionResult, FileDiff, EntityDiff
    )
    fd = FileDiff(
        relative_path="SemanticModel/definition/tables/orders.tmdl",
        diffs=[EntityDiff("measure", "Profit Ratio", "DAX",
                          "SUM([Profit]) / SUM([Sales])",
                          "DIVIDE(SUM([Profit]), SUM([Sales]))")],
    )
    r = RegressionResult([WorkbookResult("wb", "FAIL", file_diffs=[fd])])
    output = format_report(r)
    assert "FAIL" in output
    assert "orders.tmdl" in output
    assert "Profit Ratio" in output
    assert "SUM([Profit])" in output
