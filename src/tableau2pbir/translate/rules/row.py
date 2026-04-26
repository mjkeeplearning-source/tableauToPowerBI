"""Row-calc translation rules (v1). Each rule is a regex-based or string-
substitution pattern. `translate_row(expr)` tries every rule in order and
returns the first transform that fires; returns None on no-match so the
caller can hand off to AI fallback.

The rule list is intentionally small and conservative — anything not
covered is treated as a candidate for `LLMClient.translate_calc`."""
from __future__ import annotations

import re

# Each rule is (compiled_regex, replacement_template | callable).
_RULES: list[tuple[re.Pattern[str], object]] = [
    # IIF(cond, then, else) → IF(cond, then, else)
    (re.compile(r"\bIIF\s*\("), "IF("),
    # ZN(x) → COALESCE(x, 0)
    (re.compile(r"\bZN\s*\(\s*(?P<x>[^()]+?)\s*\)"),
     lambda m: f"COALESCE({m.group('x')}, 0)"),
    # IFNULL(a, b) → COALESCE(a, b)
    (re.compile(r"\bIFNULL\s*\(\s*(?P<a>[^,()]+?)\s*,\s*(?P<b>[^()]+?)\s*\)"),
     lambda m: f"COALESCE({m.group('a')}, {m.group('b')})"),
    # DATEDIFF('unit', start, end) → DATEDIFF(start, end, UNIT)
    (re.compile(
        r"\bDATEDIFF\s*\(\s*'(?P<u>day|month|year|hour|minute|second)'\s*,\s*"
        r"(?P<a>[^,()]+?)\s*,\s*(?P<b>[^()]+?)\s*\)",
    ), lambda m: f"DATEDIFF({m.group('a')}, {m.group('b')}, {m.group('u').upper()})"),
    # DATETRUNC('month', x) → STARTOFMONTH(x)
    (re.compile(r"\bDATETRUNC\s*\(\s*'month'\s*,\s*(?P<x>[^()]+?)\s*\)"),
     lambda m: f"STARTOFMONTH({m.group('x')})"),
    # DATETRUNC('year', x) → STARTOFYEAR(x)
    (re.compile(r"\bDATETRUNC\s*\(\s*'year'\s*,\s*(?P<x>[^()]+?)\s*\)"),
     lambda m: f"STARTOFYEAR({m.group('x')})"),
    # DATETRUNC('quarter', x) → STARTOFQUARTER(x)
    (re.compile(r"\bDATETRUNC\s*\(\s*'quarter'\s*,\s*(?P<x>[^()]+?)\s*\)"),
     lambda m: f"STARTOFQUARTER({m.group('x')})"),
]

# Patterns that are valid DAX as-is (passthrough). Used to short-circuit
# AI fallback on plain arithmetic / boolean / string-concat expressions.
# Includes ':' to cover string literals like "Region: ".
_PASSTHROUGH = re.compile(
    r"^[\s\[\]\w\d\+\-\*\/\=\<\>\!\,\.\(\)\"\'%:]+$"
)


def translate_row(tableau_expr: str) -> str | None:
    """Return DAX expression, or None if no rule matched."""
    expr = tableau_expr
    fired = False
    for pattern, replacement in _RULES:
        if isinstance(replacement, str):
            new_expr, n = pattern.subn(replacement, expr)
        else:
            new_expr, n = pattern.subn(replacement, expr)
        if n:
            fired = True
            expr = new_expr
    if fired:
        return expr
    if _PASSTHROUGH.match(expr) and not re.search(r"[A-Z_][A-Z_]+\s*\(", expr):
        # Pure operators/identifiers/literals — no unknown function calls.
        return expr
    return None
