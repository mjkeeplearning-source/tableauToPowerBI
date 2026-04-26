"""Rule dispatch — pick row/aggregate/lod_fixed by Calculation.kind. v1
deferred kinds (table_calc / lod_include / lod_exclude) return (None, None)
without trying any rule, since stage 2 has already routed them to
unsupported[]."""
from __future__ import annotations

from tableau2pbir.ir.calculation import Calculation, CalculationKind
from tableau2pbir.ir.parameter import Parameter
from tableau2pbir.translate.parameters import rewrite_parameter_refs
from tableau2pbir.translate.rules.aggregate import translate_aggregate
from tableau2pbir.translate.rules.lod_fixed import translate_lod_fixed
from tableau2pbir.translate.rules.row import translate_row


def dispatch_rule(
    calc: Calculation, *, parameters: tuple[Parameter, ...],
) -> tuple[str | None, str | None]:
    """Return (dax_expr, rule_name).
    `rule_name` records which rule was *attempted* — useful for the stage-3
    summary even on miss. Returns (None, None) for v1-deferred kinds."""
    if calc.kind in (
        CalculationKind.TABLE_CALC,
        CalculationKind.LOD_INCLUDE,
        CalculationKind.LOD_EXCLUDE,
    ):
        return None, None

    expr = rewrite_parameter_refs(calc.tableau_expr, parameters)

    if calc.kind is CalculationKind.ROW:
        return translate_row(expr), "row"
    if calc.kind is CalculationKind.AGGREGATE:
        return translate_aggregate(expr), "aggregate"
    if calc.kind is CalculationKind.LOD_FIXED:
        # Inject the rewritten expr back into the calc for the lod rule
        # which re-parses {FIXED ... : ...}.
        rebuilt = calc.model_copy(update={"tableau_expr": expr})
        return translate_lod_fixed(rebuilt), "lod_fixed"

    return None, None
