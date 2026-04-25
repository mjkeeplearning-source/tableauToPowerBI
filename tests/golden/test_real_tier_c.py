"""Real-workbook smoke test for detect_tier_c.

All current real workbooks are free of tier-C objects (story points,
R/Python script calcs, polygon/density/gantt marks, annotations, forecast).
This test serves as a regression gate: if a real workbook with tier-C
features is added, the test should be updated to assert the expected items.
"""
from __future__ import annotations

import pathlib
import zipfile

import pytest
from lxml import etree

from tableau2pbir.extract.tier_c_detect import detect_tier_c

_REAL_DIR = pathlib.Path(__file__).parent / "real"

_REQUIRED_KEYS = {"object_kind", "object_id", "source_excerpt", "reason", "code"}
_VALID_CODES_PREFIX = "unsupported_"


def _load_root(path: pathlib.Path) -> etree._Element:
    if path.suffix == ".twbx":
        with zipfile.ZipFile(path) as z:
            twb = next(n for n in z.namelist() if n.endswith(".twb"))
            return etree.fromstring(z.read(twb))
    return etree.fromstring(path.read_bytes())


@pytest.mark.parametrize("name", [
    "Sales Insights - Data Analysis Project using Tableau.twbx",
    "Superstore.twbx",
    "simple_join.twb",
    "simple_join_calculated_line.twb",
])
def test_no_tier_c_in_real_workbook(name):
    path = _REAL_DIR / name
    if not path.exists():
        pytest.skip(f"{name} not present")
    items = detect_tier_c(_load_root(path))
    # All real workbooks are tier-C clean; this is the regression baseline.
    assert items == [], (
        f"{name} unexpectedly has tier-C items: "
        + ", ".join(i["code"] for i in items)
    )


def test_item_structure_when_present():
    """Validate item schema using a synthetic example through the real runner."""
    from tableau2pbir.util.xml import parse_workbook_xml
    xml = b"<workbook><stories><story name='Tour'/></stories></workbook>"
    items = detect_tier_c(parse_workbook_xml(xml))
    assert len(items) == 1
    item = items[0]
    assert _REQUIRED_KEYS <= item.keys()
    assert item["code"].startswith(_VALID_CODES_PREFIX)
    assert isinstance(item["source_excerpt"], str)
    assert isinstance(item["reason"], str)
