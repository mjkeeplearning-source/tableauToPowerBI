"""Register a workbook: run pipeline, copy TMDL/JSON snapshots, append corpus."""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from tableau2pbir.regression.corpus import CorpusEntry, load_corpus, save_corpus


class RegistrationError(Exception):
    pass


def register_workbook(
    workbook_path: Path,
    corpus_path: Path,
    snapshots_root: Path,
    notes: str = "",
    added_by: str = "",
    added_on: str = "",
) -> tuple[int, int]:
    """Run pipeline, snapshot TMDL+JSON output, append corpus entry.

    Returns (tmdl_count, json_count).
    Raises RegistrationError on duplicate, pipeline failure.
    """
    name = workbook_path.stem
    entries = load_corpus(corpus_path)
    if any(e.name == name for e in entries):
        raise RegistrationError(f"{name!r} already registered in corpus")

    with tempfile.TemporaryDirectory() as td:
        out_dir = Path(td) / "out"
        result = subprocess.run(
            [sys.executable, "-m", "tableau2pbir.cli", "convert",
             str(workbook_path.resolve()), "--out", str(out_dir)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RegistrationError(
                f"pipeline failed for {name!r}:\n{result.stderr}"
            )

        wb_out = out_dir / name
        snap_dir = snapshots_root / name
        tmdl_count, json_count = _copy_snapshots(wb_out, snap_dir)

    entry = CorpusEntry(
        name=name,
        path=str(workbook_path),
        added_by=added_by,
        added_on=added_on,
        notes=notes,
    )
    entries.append(entry)
    save_corpus(entries, corpus_path)
    return tmdl_count, json_count


def _copy_snapshots(wb_out: Path, snap_dir: Path) -> tuple[int, int]:
    tmdl_count = 0
    json_count = 0
    sm_src = wb_out / "SemanticModel"
    rd_src = wb_out / "Report" / "definition"
    for src_root in (sm_src, rd_src):
        if not src_root.exists():
            continue
        for src_file in src_root.rglob("*"):
            if not src_file.is_file():
                continue
            if src_file.suffix == ".tmdl":
                rel = src_file.relative_to(wb_out)
                dst = snap_dir / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dst)
                tmdl_count += 1
            elif src_file.suffix == ".json":
                rel = src_file.relative_to(wb_out)
                dst = snap_dir / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dst)
                json_count += 1
    return tmdl_count, json_count
