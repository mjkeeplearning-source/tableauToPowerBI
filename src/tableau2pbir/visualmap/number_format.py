"""Translate Tableau text-format codes to DAX format strings.

Confirmed mapping (TWB XML line 559/765 + Tableau Desktop UI + PBI Desktop manual):
  C1033%  →  \\$#,0.00;(\\$#,0.00);\\$#,0.00   (US Dollar, 2dp, thousands separator)

The C prefix means Currency; the 4-digit number is the Windows LCID.
The trailing % in C1033% is a Tableau-internal format suffix — it does NOT
mean the value is a percentage (confirmed: Tableau UI shows "$123,456.00").
"""
from __future__ import annotations
import re

# LCID → currency symbol. Covers LCIDs seen in real Tableau workbooks.
_LCID_SYMBOL: dict[int, str] = {
    1033: "$",   # en-US  (confirmed from simple_join_sorted_test_format.twb)
    2057: "£",   # en-GB
    1031: "€",   # de-DE
    1036: "€",   # fr-FR
    1041: "¥",   # ja-JP
    2052: "¥",   # zh-CN
}

_CURRENCY_RE = re.compile(r"^C(\d+)")


def tableau_format_to_dax(tableau_format: str | None) -> str | None:
    """Return a DAX format string for a Tableau text-format code, or None if unknown."""
    if not tableau_format:
        return None
    m = _CURRENCY_RE.match(tableau_format)
    if m:
        lcid = int(m.group(1))
        sym = _LCID_SYMBOL.get(lcid)
        if sym == "$":
            return r"\$#,0.00;(\$#,0.00);\$#,0.00"
        if sym:
            return f"{sym}#,0.00;({sym}#,0.00);{sym}0.00"
    return None
