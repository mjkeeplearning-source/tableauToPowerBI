"""AI fallback for stage 3. Invokes LLMClient.translate_calc, validates
the resulting DAX through the syntax gate, and returns None on validator
fail (caller routes the calc to unsupported[])."""
from __future__ import annotations

from typing import Any

from tableau2pbir.ir.calculation import Calculation
from tableau2pbir.llm.client import LLMClient
from tableau2pbir.translate.syntax_gate import is_valid_dax


def _calc_subset(
    calc: Calculation,
    fixture: str | None,
    *,
    columns_by_table: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    """Stable, content-hashable subset for cache keying."""
    payload: dict[str, Any] = {
        "id": calc.id,
        "name": calc.name,
        "kind": calc.kind.value,
        "phase": calc.phase.value,
        "tableau_expr": calc.tableau_expr,
        "depends_on": list(calc.depends_on),
    }
    if calc.lod_fixed is not None:
        payload["lod_fixed"] = {
            "dimensions": [
                {"table_id": d.table_id, "column_id": d.column_id}
                for d in calc.lod_fixed.dimensions
            ],
        }
    if columns_by_table:
        payload["columns_by_table"] = columns_by_table
    if fixture is not None:
        payload["fixture"] = fixture
    return payload


def translate_via_ai(
    calc: Calculation,
    *,
    fixture: str | None,
    client: LLMClient,
    columns_by_table: dict[str, list[str]] | None = None,
) -> dict[str, Any] | None:
    """Returns the validated AI response, or None if the gate fails."""
    response = client.translate_calc(
        _calc_subset(calc, fixture, columns_by_table=columns_by_table)
    )
    if not is_valid_dax(response.get("dax_expr", "")):
        return None
    return response
