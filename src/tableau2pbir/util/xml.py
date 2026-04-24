"""lxml helpers. All extract modules funnel through these so attribute-missing
errors raise uniformly and tests can monkey-patch parsing behavior once."""
from __future__ import annotations

from collections.abc import Iterator

from lxml import etree


def parse_workbook_xml(xml_bytes: bytes) -> etree._Element:
    """Parse workbook XML. Raises `etree.XMLSyntaxError` on malformed input."""
    parser = etree.XMLParser(remove_blank_text=False, recover=False)
    return etree.fromstring(xml_bytes, parser=parser)


def attr(elem: etree._Element, name: str, default: str = "") -> str:
    value = elem.get(name)
    return value if value is not None else default


def optional_attr(elem: etree._Element, name: str) -> str | None:
    return elem.get(name)


def require_attr(elem: etree._Element, name: str) -> str:
    value = elem.get(name)
    if value is None:
        raise ValueError(f"<{elem.tag}> missing attribute {name!r}")
    return value


def child_text(elem: etree._Element, tag: str) -> str | None:
    child = elem.find(tag)
    return child.text if child is not None else None


def iter_children(elem: etree._Element, tag: str) -> Iterator[etree._Element]:
    return iter(elem.findall(tag))
