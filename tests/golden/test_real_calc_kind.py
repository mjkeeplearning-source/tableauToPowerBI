"""Real-workbook regression tests for classify/calc_kind.

Locks in the expected kind distribution for every calculation found
in the real workbook set."""
from __future__ import annotations

import pathlib
from collections import Counter

import pytest

from tableau2pbir.classify.calc_kind import classify_calc_kind
from tableau2pbir.extract.datasources import extract_datasources
from tableau2pbir.util.xml import parse_workbook_xml
from tableau2pbir.util.zip import read_workbook

_REAL_DIR = pathlib.Path(__file__).parent / "real"


def _kind_counts(name: str) -> Counter:
    path = _REAL_DIR / name
    if not path.exists():
        pytest.skip(f"{name} not present")
    wb = read_workbook(path)
    root = parse_workbook_xml(wb.xml_bytes)
    counts: Counter = Counter()
    for ds in extract_datasources(root):
        for c in ds["calculations"]:
            r = classify_calc_kind(c["tableau_expr"])
            counts[r.kind] += 1
    return counts


def test_join_custom_rds_calcs():
    counts = _kind_counts("join_custom_rds.twb")
    assert counts["row"] == 1
    assert counts["aggregate"] == 0


def test_rds_complex_cal_calcs():
    counts = _kind_counts("rds_compllex_cal.twb")
    assert counts["row"] == 1
    assert counts["table_calc"] == 2


def test_sales_insights_calcs():
    counts = _kind_counts("Sales Insights - Data Analysis Project using Tableau.twbx")
    assert counts["row"] == 2
    assert counts["aggregate"] == 1


def test_simple_join_calcs():
    counts = _kind_counts("simple_join.twb")
    assert counts["aggregate"] == 2
    assert counts["row"] == 0


def test_superstore_calcs():
    counts = _kind_counts("Superstore.twbx")
    assert counts["row"] == 12
    assert counts["aggregate"] == 7
    assert counts["table_calc"] == 1
    assert counts["lod_fixed"] == 1
