"""Row-calc rule. v1 row library: arithmetic, string concat, IF/CASE,
date functions DATEDIFF/DATETRUNC, ISNULL/ZN. Each rule returns the
rewritten DAX expression; on no-match, returns None."""
from __future__ import annotations

from tableau2pbir.translate.rules.row import translate_row


def test_arithmetic_passthrough():
    assert translate_row("[Sales] + [Tax]") == "[Sales] + [Tax]"


def test_iif_to_if():
    assert translate_row("IIF([x] > 0, 1, 0)") == "IF([x] > 0, 1, 0)"


def test_zn_to_coalesce_zero():
    assert translate_row("ZN([Sales])") == "COALESCE([Sales], 0)"


def test_ifnull_to_coalesce():
    assert translate_row("IFNULL([Sales], 0)") == "COALESCE([Sales], 0)"


def test_string_concat_plus_passthrough():
    assert translate_row('"Region: " + [Region]') == '"Region: " + [Region]'


def test_datediff_to_dax_datediff():
    assert translate_row("DATEDIFF('day', [Start], [End])") == \
        "DATEDIFF([Start], [End], DAY)"


def test_datetrunc_month_to_startofmonth():
    assert translate_row("DATETRUNC('month', [OrderDate])") == \
        "STARTOFMONTH([OrderDate])"


def test_unmatched_returns_none():
    assert translate_row("WEIRDFN([x])") is None
