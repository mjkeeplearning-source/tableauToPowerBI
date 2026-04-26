from __future__ import annotations

from tableau2pbir.ir.calculation import (
    Calculation, CalculationKind, CalculationPhase, CalculationScope,
    LodRelative, TableCalc, TableCalcFrame, TableCalcFrameType,
)
from tableau2pbir.ir.common import FieldRef, UnsupportedItem
from tableau2pbir.ir.parameter import (
    Parameter, ParameterExposure, ParameterIntent,
)
from tableau2pbir.stages._deferred_routing import (
    lift_tier_c_detections, route_deferred_calcs, route_deferred_parameters,
)


def _tc_calc() -> Calculation:
    return Calculation(
        id="c_tc", name="Running", scope=CalculationScope.MEASURE,
        tableau_expr="RUNNING_SUM(SUM([Sales]))",
        kind=CalculationKind.TABLE_CALC, phase=CalculationPhase.VIZ,
        depends_on=(),
        table_calc=TableCalc(
            partitioning=(), addressing=(), sort=(),
            frame=TableCalcFrame(type=TableCalcFrameType.CUMULATIVE),
            restart_every=None,
        ),
    )


def _lod_include_calc() -> Calculation:
    return Calculation(
        id="c_li", name="Per Customer", scope=CalculationScope.MEASURE,
        tableau_expr="{INCLUDE [Customer]: SUM([Sales])}",
        kind=CalculationKind.LOD_INCLUDE, phase=CalculationPhase.AGGREGATE,
        depends_on=(),
        lod_relative=LodRelative(extra_dims=(FieldRef(table_id="t", column_id="customer"),)),
    )


def test_table_calc_routed_to_deferred():
    items = route_deferred_calcs((_tc_calc(),))
    assert len(items) == 1
    assert items[0].code == "deferred_feature_table_calcs"
    assert items[0].object_id == "c_tc"


def test_lod_include_routed_to_deferred():
    items = route_deferred_calcs((_lod_include_calc(),))
    assert items[0].code == "deferred_feature_lod_relative"


def test_v1_kinds_not_routed():
    ok = Calculation(
        id="c_ok", name="Sum", scope=CalculationScope.MEASURE,
        tableau_expr="SUM([Sales])", kind=CalculationKind.AGGREGATE,
        phase=CalculationPhase.AGGREGATE, depends_on=(),
    )
    assert route_deferred_calcs((ok,)) == ()


def _param(name: str, intent: ParameterIntent) -> Parameter:
    return Parameter(
        id=f"param__{name}", name=name, datatype="string", default="",
        allowed_values=(), intent=intent, exposure=ParameterExposure.CARD,
    )


def test_formatting_control_param_routes_to_format_switch_flag():
    p = _param("fmt", ParameterIntent.FORMATTING_CONTROL)
    items = route_deferred_parameters((p,))
    assert items[0].code == "deferred_feature_format_switch"


def test_unsupported_intent_routes_to_unsupported_parameter():
    p = _param("ghost", ParameterIntent.UNSUPPORTED)
    items = route_deferred_parameters((p,))
    assert items[0].code == "unsupported_parameter"


def test_v1_intents_not_routed():
    params = (
        _param("p1", ParameterIntent.NUMERIC_WHAT_IF),
        _param("p2", ParameterIntent.CATEGORICAL_SELECTOR),
        _param("p3", ParameterIntent.INTERNAL_CONSTANT),
    )
    assert route_deferred_parameters(params) == ()


def test_lift_tier_c_preserves_stage1_detections():
    raw_unsupported = [
        {"object_kind": "story", "object_id": "story__tour",
         "source_excerpt": "<story/>", "reason": "Story points have no PBI equivalent.",
         "code": "unsupported_story_points"},
    ]
    lifted = lift_tier_c_detections(raw_unsupported)
    assert len(lifted) == 1
    assert isinstance(lifted[0], UnsupportedItem)
    assert lifted[0].code == "unsupported_story_points"
