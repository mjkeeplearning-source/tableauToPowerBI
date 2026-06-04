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


def _full_pipeline(wb: Path, out: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "tableau2pbir.cli", "convert",
         str(wb), "--out", str(out)],
        capture_output=True, text=True, env=os.environ,
    )


@pytest.mark.integration
def test_tmdl_orders_has_year_calculated_column(tmp_path: Path):
    """orders.tmdl must contain the YEAR() calculated column block."""
    if not _WB.exists():
        pytest.skip(f"{_WB.name} not present")
    out = tmp_path / "out"
    result = _full_pipeline(_WB, out)
    if result.returncode != 0 and any(
        x in result.stderr for x in ("ANTHROPIC_API_KEY not set", "authentication_error", "invalid x-api-key")
    ):
        pytest.skip("ANTHROPIC_API_KEY needed for Stage 3 (unexpected — workbook has no calcs)")
    assert result.returncode == 0, result.stderr

    orders_tmdl = (
        out / "simple_join_calculated_line" /
        "SemanticModel" / "definition" / "tables" / "orders.tmdl"
    )
    assert orders_tmdl.is_file(), "orders.tmdl not generated"
    text = orders_tmdl.read_text(encoding="utf-8")

    assert "Year order_date" in text, (
        "Calculated column 'Year order_date' not found in orders.tmdl"
    )
    assert "YEAR(orders[order_date])" in text, (
        "DAX expression YEAR(orders[order_date]) not found in orders.tmdl"
    )
    assert "dataType: int64" in text, "int64 dataType not found in orders.tmdl"


@pytest.mark.integration
def test_visual_json_sheet2_category_uses_year_column(tmp_path: Path):
    """Sheet 2 visual.json Category projection must bind to Year order_date, not order_date."""
    if not _WB.exists():
        pytest.skip(f"{_WB.name} not present")
    out = tmp_path / "out"
    result = _full_pipeline(_WB, out)
    if result.returncode != 0 and any(
        x in result.stderr for x in ("ANTHROPIC_API_KEY not set", "authentication_error", "invalid x-api-key")
    ):
        pytest.skip("ANTHROPIC_API_KEY needed for Stage 3")
    assert result.returncode == 0, result.stderr

    visual_path = (
        out / "simple_join_calculated_line" / "Report" / "definition" /
        "pages" / "ReportSection2" / "visuals" / "visual_2" / "visual.json"
    )
    assert visual_path.is_file(), "visual_2/visual.json not generated for Sheet 2"
    visual = json.loads(visual_path.read_text(encoding="utf-8"))

    projections = visual["visual"]["query"]["queryState"]["Category"]["projections"]
    assert len(projections) == 1
    field = projections[0]["field"]
    assert "Column" in field, (
        f"Expected Column binding for Category, got: {list(field.keys())}"
    )
    prop = field["Column"]["Property"]
    assert prop == "Year order_date", (
        f"Expected 'Year order_date' but got {prop!r} — date truncation is still lost"
    )
    assert projections[0]["queryRef"] == "orders.Year order_date"


@pytest.mark.integration
def test_visual_json_sheet2_raw_order_date_not_used(tmp_path: Path):
    """Regression guard: the raw 'order_date' property must NOT appear in Sheet 2 Category."""
    if not _WB.exists():
        pytest.skip(f"{_WB.name} not present")
    out = tmp_path / "out"
    result = _full_pipeline(_WB, out)
    if result.returncode != 0 and any(
        x in result.stderr for x in ("ANTHROPIC_API_KEY not set", "authentication_error", "invalid x-api-key")
    ):
        pytest.skip("ANTHROPIC_API_KEY needed for Stage 3")
    assert result.returncode == 0, result.stderr

    visual_path = (
        out / "simple_join_calculated_line" / "Report" / "definition" /
        "pages" / "ReportSection2" / "visuals" / "visual_2" / "visual.json"
    )
    visual = json.loads(visual_path.read_text(encoding="utf-8"))
    projections = visual["visual"]["query"]["queryState"]["Category"]["projections"]
    field = projections[0]["field"]
    if "Column" not in field:
        pytest.skip(f"Binding is not Column type: {list(field.keys())} — check other test")
    prop = field["Column"]["Property"]
    assert prop != "order_date", (
        "BUG STILL PRESENT: Category binding is 'order_date' (raw daily) not 'Year order_date'"
    )
