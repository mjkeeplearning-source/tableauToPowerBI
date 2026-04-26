from __future__ import annotations

from tableau2pbir.ir.calculation import (
    Calculation, CalculationKind, CalculationPhase, CalculationScope,
)
from tableau2pbir.ir.common import UnsupportedItem
from tableau2pbir.ir.datasource import ConnectorTier, Datasource
from tableau2pbir.ir.parameter import Parameter, ParameterExposure, ParameterIntent
from tableau2pbir.stages._summary import render_stage2_summary


def _ds(name: str, tier: ConnectorTier) -> Datasource:
    return Datasource(
        id=f"ds__{name}", name=name, tableau_kind="csv",
        connector_tier=tier, pbi_m_connector="Csv.Document" if tier != ConnectorTier.TIER_4 else None,
        connection_params={}, user_action_required=(), table_ids=(),
        extract_ignored=False,
    )


def _calc(kind: CalculationKind) -> Calculation:
    return Calculation(
        id=f"calc__{kind.value}", name=kind.value, scope=CalculationScope.MEASURE,
        tableau_expr="x", kind=kind, phase=CalculationPhase.AGGREGATE, depends_on=(),
    )


def _param(intent: ParameterIntent) -> Parameter:
    return Parameter(
        id=f"param__{intent.value}", name=intent.value, datatype="string",
        default="", allowed_values=(), intent=intent, exposure=ParameterExposure.CARD,
    )


def test_summary_includes_tier_histogram():
    md = render_stage2_summary(
        datasources=(_ds("a", ConnectorTier.TIER_1), _ds("b", ConnectorTier.TIER_2)),
        calculations=(),
        parameters=(),
        sheets_count=0, dashboards_count=0,
        unsupported=(),
    )
    assert "datasource tier histogram" in md.lower()
    assert "tier 1: 1" in md.lower()
    assert "tier 2: 1" in md.lower()


def test_summary_includes_calc_histogram():
    md = render_stage2_summary(
        datasources=(),
        calculations=(_calc(CalculationKind.ROW), _calc(CalculationKind.AGGREGATE),
                      _calc(CalculationKind.LOD_FIXED)),
        parameters=(), sheets_count=0, dashboards_count=0, unsupported=(),
    )
    assert "row: 1" in md.lower()
    assert "aggregate: 1" in md.lower()
    assert "lod_fixed: 1" in md.lower()


def test_summary_includes_parameter_intent_histogram():
    md = render_stage2_summary(
        datasources=(), calculations=(),
        parameters=(_param(ParameterIntent.NUMERIC_WHAT_IF),
                    _param(ParameterIntent.CATEGORICAL_SELECTOR)),
        sheets_count=0, dashboards_count=0, unsupported=(),
    )
    assert "numeric_what_if: 1" in md.lower()
    assert "categorical_selector: 1" in md.lower()


def test_summary_includes_unsupported_breakdown():
    md = render_stage2_summary(
        datasources=(), calculations=(), parameters=(),
        sheets_count=0, dashboards_count=0,
        unsupported=(UnsupportedItem(
            object_kind="calc", object_id="x",
            source_excerpt="", reason="", code="deferred_feature_table_calcs",
        ),),
    )
    assert "deferred_feature_table_calcs: 1" in md.lower()
