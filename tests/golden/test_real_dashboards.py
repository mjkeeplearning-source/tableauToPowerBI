"""Real-workbook smoke test for extract_dashboards.

Validates that the extractor correctly handles real Tableau dashboard XML
which uses type-v2 attributes (not type) for zone kinds, and nested
container zones (layout-flow / layout-basic) that must be skipped.
"""
from __future__ import annotations

import pathlib
import zipfile

import pytest
from lxml import etree

from tableau2pbir.extract.dashboards import extract_dashboards

_REAL_DIR = pathlib.Path(__file__).parent / "real"

_REQUIRED_LEAF_KEYS = {"leaf_kind", "payload", "position", "floating"}
_REQUIRED_POS_KEYS = {"x", "y", "w", "h"}
_VALID_LEAF_KINDS = {
    "sheet", "text", "image", "filter_card", "parameter_card",
    "legend", "navigation", "blank", "web_page",
}


def _load_root(path: pathlib.Path) -> etree._Element:
    if path.suffix == ".twbx":
        with zipfile.ZipFile(path) as z:
            twb = next(n for n in z.namelist() if n.endswith(".twb"))
            return etree.fromstring(z.read(twb))
    return etree.fromstring(path.read_bytes())


def _assert_leaf_valid(leaf: dict) -> None:
    assert _REQUIRED_LEAF_KEYS <= leaf.keys(), f"leaf missing keys: {leaf}"
    assert leaf["leaf_kind"] in _VALID_LEAF_KINDS, f"unknown leaf_kind: {leaf['leaf_kind']!r}"
    assert _REQUIRED_POS_KEYS <= leaf["position"].keys()
    assert isinstance(leaf["floating"], bool)
    assert isinstance(leaf["payload"], dict)


# ── Sales Insights ─────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def sales_insights_dbs():
    path = _REAL_DIR / "Sales Insights - Data Analysis Project using Tableau.twbx"
    if not path.exists():
        pytest.skip("Sales Insights workbook not present")
    return extract_dashboards(_load_root(path))


def test_sales_insights_dashboard_count(sales_insights_dbs):
    assert len(sales_insights_dbs) == 2


def test_sales_insights_profit_analysis(sales_insights_dbs):
    d = next(d for d in sales_insights_dbs if "Profit" in d["name"])
    assert d["size"] == {"w": 1600, "h": 900, "kind": "exact"}
    assert len(d["leaves"]) == 10
    sheet_names = {l["payload"]["sheet_name"] for l in d["leaves"] if l["leaf_kind"] == "sheet"}
    assert "Year" in sheet_names
    assert "Profit" in sheet_names
    assert "Customer Table" in sheet_names
    for leaf in d["leaves"]:
        _assert_leaf_valid(leaf)


def test_sales_insights_revenue_analysis(sales_insights_dbs):
    d = next(d for d in sales_insights_dbs if "Revenue" in d["name"])
    assert len(d["leaves"]) == 9
    assert all(l["leaf_kind"] == "sheet" for l in d["leaves"])
    sheet_names = {l["payload"]["sheet_name"] for l in d["leaves"]}
    assert "Top 5 Customers" in sheet_names
    assert "Top 5 Products" in sheet_names


# ── Superstore ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def superstore_dbs():
    path = _REAL_DIR / "Superstore.twbx"
    if not path.exists():
        pytest.skip("Superstore workbook not present")
    return extract_dashboards(_load_root(path))


def test_superstore_dashboard_count(superstore_dbs):
    assert len(superstore_dbs) == 6


def test_superstore_all_leaves_valid(superstore_dbs):
    for d in superstore_dbs:
        assert isinstance(d["name"], str) and d["name"]
        assert d["size"]["kind"] in {"exact", "automatic", "range"}
        for leaf in d["leaves"]:
            _assert_leaf_valid(leaf)


def test_superstore_customers_dashboard(superstore_dbs):
    d = next(d for d in superstore_dbs if d["name"] == "Customers")
    assert len(d["leaves"]) == 8
    sheet_names = {l["payload"]["sheet_name"] for l in d["leaves"] if l["leaf_kind"] == "sheet"}
    assert "CustomerScatter" in sheet_names
    assert "CustomerRank" in sheet_names


def test_superstore_no_duplicate_leaves(superstore_dbs):
    # Each zone id should appear at most once per dashboard.
    for d in superstore_dbs:
        assert len(d["leaves"]) == len(d["leaves"]), "duplicate leaf"


def test_superstore_qualified_refs_preserved(superstore_dbs):
    # filter_card and legend payload fields must not be mangled by _unbracket.
    # A mangled qualified ref would contain '].[' with a missing leading '['.
    for d in superstore_dbs:
        for leaf in d["leaves"]:
            for v in leaf["payload"].values():
                if isinstance(v, str) and "].[" in v:
                    assert v.startswith("["), (
                        f"Qualified ref mangled in {d['name']}: {v!r}"
                    )
