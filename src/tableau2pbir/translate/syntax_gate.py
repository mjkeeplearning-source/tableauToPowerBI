"""DAX syntax gate — parse-only check using sqlglot's tsql dialect.

Per spec §6 Stage 3 + §A.4-2: this is the *syntax gate*, not a semantic
verifier. Semantic verification ships in §9 layer iv-c (Plan 5).

DAX uses `'Table'[Column]` qualified references which sqlglot's tsql
dialect rejects (T-SQL expects `[Table].[Column]`). We normalize the
DAX form to the tsql-compatible form before parsing — this preserves
paren/bracket balance and operator structure, which is all the gate
needs to verify."""
from __future__ import annotations

import re

import sqlglot
from sqlglot.errors import ParseError

# Matches: 'Table Name'[Column Name] — single-quoted table, bracketed column.
_DAX_QUALIFIED_REF = re.compile(r"'([^']*)'\s*\[([^\]]*)\]")


def _normalize_dax_for_tsql(expr: str) -> str:
    """Rewrite DAX `'Table'[Column]` → tsql-parseable `[Table].[Column]`."""
    return _DAX_QUALIFIED_REF.sub(r"[\1].[\2]", expr)


def is_valid_dax(expr: str) -> bool:
    """True iff `expr` parses cleanly under tsql dialect after DAX normalization.

    DAX and T-SQL share enough surface syntax (bracketed names, function
    calls, infix operators) that parse failure is a reliable signal of a
    malformed expression. We do not interpret the AST — only that one exists."""
    if not expr or not expr.strip():
        return False
    try:
        sqlglot.parse_one(_normalize_dax_for_tsql(expr), dialect="tsql")
    except ParseError:
        return False
    except Exception:
        # sqlglot occasionally raises non-ParseError on pathological input.
        return False
    return True
