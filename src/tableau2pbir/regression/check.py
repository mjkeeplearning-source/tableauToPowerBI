"""Regression check orchestrator."""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from tableau2pbir.regression.compare.json_diff import diff_json
from tableau2pbir.regression.compare.result import (
    EntityDiff, FileDiff, RegressionResult, WorkbookResult,
)
from tableau2pbir.regression.compare.tmdl_diff import diff_model_tmdl, diff_tmdl_table
from tableau2pbir.regression.corpus import load_corpus

_LLM_SKIP_MARKERS = (
    "ANTHROPIC_API_KEY not set",
    "authentication_error",
    "invalid x-api-key",
)


def run_regression_check(
    corpus_path: Path,
    snapshots_root: Path,
    name_filter: str | None = None,
) -> RegressionResult:
    entries = load_corpus(corpus_path)
    if name_filter:
        entries = [e for e in entries if e.name == name_filter]

    workbook_results: list[WorkbookResult] = []
    for entry in entries:
        workbook_results.append(
            _check_one(entry.name, Path(entry.path), snapshots_root / entry.name)
        )
    return RegressionResult(workbook_results=workbook_results)


def _check_one(name: str, workbook_path: Path, snap_dir: Path) -> WorkbookResult:
    with tempfile.TemporaryDirectory() as td:
        out_dir = Path(td) / "out"
        result = subprocess.run(
            [sys.executable, "-m", "tableau2pbir.cli", "convert",
             str(workbook_path.resolve()), "--out", str(out_dir)],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            if any(m in result.stderr for m in _LLM_SKIP_MARKERS):
                return WorkbookResult(name=name, status="SKIP", skip_reason="no API key")
            return WorkbookResult(
                name=name, status="FAIL",
                file_diffs=[FileDiff(
                    relative_path="<pipeline>",
                    diffs=[EntityDiff("pipeline", name, "exit_code", "0", str(result.returncode))],
                )],
            )

        wb_out = out_dir / name
        file_diffs = _compare_snapshots(snap_dir, wb_out)

    if any(fd.has_changes for fd in file_diffs):
        return WorkbookResult(name=name, status="FAIL", file_diffs=file_diffs)
    return WorkbookResult(name=name, status="PASS", file_diffs=file_diffs)


def _compare_snapshots(snap_dir: Path, wb_out: Path) -> list[FileDiff]:
    file_diffs: list[FileDiff] = []
    for snap_file in sorted(snap_dir.rglob("*")):
        if not snap_file.is_file():
            continue
        rel = snap_file.relative_to(snap_dir)
        new_file = wb_out / rel
        if not new_file.exists():
            file_diffs.append(FileDiff(relative_path=str(rel).replace("\\", "/"), missing=True))
            continue
        diffs = _compare_file(snap_file, new_file)
        if diffs:
            file_diffs.append(FileDiff(relative_path=str(rel).replace("\\", "/"), diffs=diffs))
    return file_diffs


def _compare_file(snap_file: Path, new_file: Path) -> list[EntityDiff]:
    snap_text = snap_file.read_text(encoding="utf-8")
    new_text = new_file.read_text(encoding="utf-8")
    if snap_file.suffix == ".json":
        raw_diffs = diff_json(snap_text, new_text)
        return [
            EntityDiff("json", path, "value", old_v, new_v)
            for path, old_v, new_v in raw_diffs
        ]
    if snap_file.suffix == ".tmdl":
        if snap_file.name == "model.tmdl":
            return diff_model_tmdl(snap_text, new_text)
        return diff_tmdl_table(snap_text, new_text)
    return []
