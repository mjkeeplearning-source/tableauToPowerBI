"""v1 deferred-feature routing. Stage 2 classifies every object per §5.6 /
§5.7 / §5.8; this module emits the corresponding UnsupportedItem records
with stable `deferred_feature_*` codes so §8.1 (Plan 4) can key off them."""
from __future__ import annotations

from typing import Any

from tableau2pbir.ir.calculation import Calculation, CalculationKind
from tableau2pbir.ir.common import UnsupportedItem
from tableau2pbir.ir.parameter import Parameter, ParameterIntent


_DEFERRED_CALC_KINDS: dict[CalculationKind, str] = {
    CalculationKind.TABLE_CALC:  "deferred_feature_table_calcs",
    CalculationKind.LOD_INCLUDE: "deferred_feature_lod_relative",
    CalculationKind.LOD_EXCLUDE: "deferred_feature_lod_relative",
}


def route_deferred_calcs(calcs: tuple[Calculation, ...]) -> tuple[UnsupportedItem, ...]:
    out: list[UnsupportedItem] = []
    for c in calcs:
        code = _DEFERRED_CALC_KINDS.get(c.kind)
        if code is None:
            continue
        out.append(UnsupportedItem(
            object_kind="calc",
            object_id=c.id,
            source_excerpt=c.tableau_expr[:200],
            reason=f"Calculation {c.name!r} uses v1-deferred kind {c.kind.value!r}.",
            code=code,
        ))
    return tuple(out)


def route_deferred_parameters(params: tuple[Parameter, ...]) -> tuple[UnsupportedItem, ...]:
    out: list[UnsupportedItem] = []
    for p in params:
        if p.intent == ParameterIntent.FORMATTING_CONTROL:
            out.append(UnsupportedItem(
                object_kind="parameter",
                object_id=p.id,
                source_excerpt=f"parameter={p.name!r} intent=formatting_control",
                reason="Formatting-control parameters are deferred behind --with-format-switch.",
                code="deferred_feature_format_switch",
            ))
        elif p.intent == ParameterIntent.UNSUPPORTED:
            out.append(UnsupportedItem(
                object_kind="parameter",
                object_id=p.id,
                source_excerpt=f"parameter={p.name!r} default={p.default!r}",
                reason="Parameter shape has no PBI equivalent (§5.7 fallthrough).",
                code="unsupported_parameter",
            ))
    return tuple(out)


def lift_tier_c_detections(
    raw_unsupported: list[dict[str, Any]],
) -> tuple[UnsupportedItem, ...]:
    """Convert stage-1 tier-C raw dicts into IR UnsupportedItems."""
    return tuple(
        UnsupportedItem(
            object_kind=raw["object_kind"],
            object_id=raw["object_id"],
            source_excerpt=raw["source_excerpt"],
            reason=raw["reason"],
            code=raw["code"],
        )
        for raw in raw_unsupported
    )
