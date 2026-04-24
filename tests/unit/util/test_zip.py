"""Unit tests for util/zip — workbook reader + source hash."""
from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from tableau2pbir.util.zip import WorkbookBytes, read_workbook


def _write_twb(path: Path, xml: str) -> Path:
    path.write_text(xml, encoding="utf-8")
    return path


def _write_twbx(path: Path, xml: str, extras: dict[str, bytes] | None = None) -> Path:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("workbook.twb", xml.encode("utf-8"))
        for name, data in (extras or {}).items():
            z.writestr(name, data)
    return path


_TWB_XML = "<?xml version='1.0'?>\n<workbook version='18.1'></workbook>\n"


def test_read_workbook_twb(tmp_path: Path):
    src = _write_twb(tmp_path / "simple.twb", _TWB_XML)
    result = read_workbook(src)
    assert isinstance(result, WorkbookBytes)
    assert result.xml_bytes.startswith(b"<?xml")
    assert result.source_path == str(src.resolve())
    assert len(result.source_hash) == 64   # sha256 hex


def test_read_workbook_twbx(tmp_path: Path):
    src = _write_twbx(tmp_path / "packaged.twbx", _TWB_XML,
                      extras={"Data/sample.csv": b"id,amount\n1,10\n"})
    result = read_workbook(src)
    assert b"<workbook" in result.xml_bytes


def test_read_workbook_twbx_missing_twb(tmp_path: Path):
    src = tmp_path / "empty.twbx"
    with zipfile.ZipFile(src, "w"):
        pass
    with pytest.raises(ValueError, match="no .twb entry"):
        read_workbook(src)


def test_source_hash_is_stable_across_reads(tmp_path: Path):
    src = _write_twb(tmp_path / "stable.twb", _TWB_XML)
    first = read_workbook(src).source_hash
    second = read_workbook(src).source_hash
    assert first == second


def test_source_hash_differs_across_files(tmp_path: Path):
    a = _write_twb(tmp_path / "a.twb", _TWB_XML)
    b = _write_twb(tmp_path / "b.twb", _TWB_XML + "<!-- differ -->\n")
    assert read_workbook(a).source_hash != read_workbook(b).source_hash


def test_read_workbook_unknown_extension(tmp_path: Path):
    src = tmp_path / "bogus.xlsx"
    src.write_bytes(b"not a workbook")
    with pytest.raises(ValueError, match="extension"):
        read_workbook(src)
