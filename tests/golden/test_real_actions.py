"""Real-workbook smoke test for extract_actions.

Validates that the extractor handles real Tableau <action> elements
(which use <command command='tsc:...'> for kind and <activation type='...'> for
trigger — not the <filter-action> tag style used in synthetic fixtures).
"""
from __future__ import annotations

import pathlib
import zipfile

import pytest
from lxml import etree

from tableau2pbir.extract.actions import extract_actions

_REAL_DIR = pathlib.Path(__file__).parent / "real"

_VALID_KINDS = {"filter", "highlight", "url", "parameter"}
_VALID_TRIGGERS = {"select", "hover", "menu"}
_REQUIRED_KEYS = {"name", "caption", "kind", "trigger", "source_sheets",
                  "target_sheets", "clearing_behavior", "url"}


def _load_root(path: pathlib.Path) -> etree._Element:
    if path.suffix == ".twbx":
        with zipfile.ZipFile(path) as z:
            twb = next(n for n in z.namelist() if n.endswith(".twb"))
            return etree.fromstring(z.read(twb))
    return etree.fromstring(path.read_bytes())


# ── Sales Insights ─────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def sales_insights_actions():
    path = _REAL_DIR / "Sales Insights - Data Analysis Project using Tableau.twbx"
    if not path.exists():
        pytest.skip("Sales Insights workbook not present")
    return extract_actions(_load_root(path))


def test_sales_insights_action_count(sales_insights_actions):
    assert len(sales_insights_actions) == 18


def test_sales_insights_all_filter_actions(sales_insights_actions):
    assert all(a["kind"] == "filter" for a in sales_insights_actions)


def test_sales_insights_action_structure(sales_insights_actions):
    for a in sales_insights_actions:
        assert _REQUIRED_KEYS <= a.keys()
        assert a["kind"] in _VALID_KINDS
        assert a["trigger"] in _VALID_TRIGGERS
        assert isinstance(a["source_sheets"], tuple)
        assert isinstance(a["target_sheets"], tuple)
        # name should have brackets stripped
        assert not a["name"].startswith("["), f"name still bracketed: {a['name']!r}"


def test_sales_insights_source_sheets_populated(sales_insights_actions):
    # Every filter action here has a specific source worksheet
    assert all(len(a["source_sheets"]) > 0 for a in sales_insights_actions)
    src_names = {a["source_sheets"][0] for a in sales_insights_actions}
    assert "Year" in src_names
    assert "Revenue" in src_names


# ── Superstore ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def superstore_actions():
    path = _REAL_DIR / "Superstore.twbx"
    if not path.exists():
        pytest.skip("Superstore workbook not present")
    return extract_actions(_load_root(path))


def test_superstore_action_count(superstore_actions):
    assert len(superstore_actions) == 10


def test_superstore_mixed_kinds(superstore_actions):
    kinds = {a["kind"] for a in superstore_actions}
    assert "filter" in kinds
    assert "highlight" in kinds


def test_superstore_action_structure(superstore_actions):
    for a in superstore_actions:
        assert _REQUIRED_KEYS <= a.keys()
        assert a["kind"] in _VALID_KINDS
        assert a["trigger"] in _VALID_TRIGGERS
        assert not a["name"].startswith("["), f"name still bracketed: {a['name']!r}"
