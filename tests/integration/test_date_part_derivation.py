"""Integration tests for Plan 18 — date-part derivation DAX column synthesis.

Tests run stages 1-2 (no LLM) and 1-7 (no LLM needed — no calculations in
simple_join_calculated_line.twb) against the real workbook.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_REAL_DIR = Path(__file__).resolve().parents[1] / "golden" / "real"
_WB = _REAL_DIR / "simple_join_calculated_line.twb"


def _run(args: list[str], tmp: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "tableau2pbir.cli", *args],
        capture_output=True, text=True, env=os.environ,
        cwd=str(tmp),
    )


def _stage_json(out: Path, n: int, name: str) -> dict:
    return json.loads(
        (out / "simple_join_calculated_line" / "stages" / f"{n:02d}_{name}.json")
        .read_text(encoding="utf-8")
    )


@pytest.mark.integration
def test_stage2_synthesizes_year_order_date_column(tmp_path: Path):
    """Stage 1→2 produces Year order_date column with correct DAX."""
    if not _WB.exists():
        pytest.skip(f"{_WB.name} not present")
    out = tmp_path / "out"
    result = subprocess.run(
        [sys.executable, "-m", "tableau2pbir.cli", "convert",
         str(_WB), "--out", str(out), "--gate", "canonicalize"],
        capture_output=True, text=True, env=os.environ,
    )
    assert result.returncode == 0, result.stderr

    ir2 = _stage_json(out, 2, "canonicalize")
    columns = ir2["data_model"]["columns"]

    year_col = next((c for c in columns if c["name"] == "Year order_date"), None)
    assert year_col is not None, (
        f"Year order_date not in Stage 2 columns. Got names: {[c['name'] for c in columns]}"
    )
    assert year_col["kind"] == "calculated"
    assert year_col["dax_expr"] == "YEAR(orders[order_date])"
    assert year_col["datatype"] == "integer"
    assert year_col["source_column"] is None  # not a raw physical column


@pytest.mark.integration
def test_stage2_year_column_in_orders_table_column_ids(tmp_path: Path):
    """The synthesized column ID appears in the orders table's column_ids."""
    if not _WB.exists():
        pytest.skip(f"{_WB.name} not present")
    out = tmp_path / "out"
    result = subprocess.run(
        [sys.executable, "-m", "tableau2pbir.cli", "convert",
         str(_WB), "--out", str(out), "--gate", "canonicalize"],
        capture_output=True, text=True, env=os.environ,
    )
    assert result.returncode == 0, result.stderr

    ir2 = _stage_json(out, 2, "canonicalize")
    year_col = next(c for c in ir2["data_model"]["columns"] if c["name"] == "Year order_date")
    orders_table = next(t for t in ir2["data_model"]["tables"] if t["name"] == "orders")
    assert year_col["id"] in orders_table["column_ids"], (
        f"Year order_date column id {year_col['id']!r} not in "
        f"orders table column_ids: {orders_table['column_ids']}"
    )


@pytest.mark.integration
def test_stage2_raw_order_date_still_present(tmp_path: Path):
    """The raw order_date column must remain unchanged alongside the derived one."""
    if not _WB.exists():
        pytest.skip(f"{_WB.name} not present")
    out = tmp_path / "out"
    result = subprocess.run(
        [sys.executable, "-m", "tableau2pbir.cli", "convert",
         str(_WB), "--out", str(out), "--gate", "canonicalize"],
        capture_output=True, text=True, env=os.environ,
    )
    assert result.returncode == 0, result.stderr

    ir2 = _stage_json(out, 2, "canonicalize")
    raw_col = next(
        (c for c in ir2["data_model"]["columns"]
         if c["name"] == "order_date" and c["kind"] == "raw"),
        None,
    )
    assert raw_col is not None, "Raw order_date column must still be in data_model.columns"
