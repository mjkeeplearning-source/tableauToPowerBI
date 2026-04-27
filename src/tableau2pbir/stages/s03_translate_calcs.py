"""Stage 3 — translate calcs. See spec §6 Stage 3 + §16 v1 scope.

For every Calculation: parameter-rewrite, dispatch to row/aggregate/lod_fixed
rule, fall back to LLM on miss, syntax-gate the resulting DAX. Calcs already
in unsupported[] (with `deferred_feature_*` code from stage 2) are skipped."""
from __future__ import annotations

from typing import Any

from tableau2pbir.ir.common import UnsupportedItem
from tableau2pbir.ir.parameter import Parameter
from tableau2pbir.ir.workbook import Workbook
from tableau2pbir.llm.client import LLMClient
from tableau2pbir.pipeline import StageContext, StageResult
from tableau2pbir.translate.ai_fallback import translate_via_ai
from tableau2pbir.translate.rules.dispatch import dispatch_rule
from tableau2pbir.translate.summary import TranslationStats, render_stage3_summary
from tableau2pbir.translate.syntax_gate import is_valid_dax
from tableau2pbir.translate.topo import partition_lanes, topo_sort


def _make_client(ctx: StageContext) -> LLMClient:
    cache_dir = ctx.output_dir / ".llm-cache"
    return LLMClient(cache_dir=cache_dir)


def run(input_json: dict[str, Any], ctx: StageContext) -> StageResult:
    wb = Workbook.model_validate(input_json)
    deferred_ids = {
        u.object_id for u in wb.unsupported
        if u.code.startswith("deferred_feature_") or u.code == "calc_cycle"
    }
    parameters: tuple[Parameter, ...] = wb.data_model.parameters

    global_lane, per_sheet_lane = partition_lanes(wb.data_model.calculations)
    ordered = (*topo_sort(global_lane), *topo_sort(per_sheet_lane))

    by_source: dict[str, int] = {}
    rule_hits: dict[str, int] = {}
    ai_confidence: dict[str, int] = {}
    ai_cache_hits = 0
    ai_cache_misses = 0
    validator_failed = 0
    new_unsupported: list[UnsupportedItem] = list(wb.unsupported)
    new_calcs_by_id: dict[str, Any] = {}

    client: LLMClient | None = None
    for calc in ordered:
        if calc.id in deferred_ids:
            by_source["skip"] = by_source.get("skip", 0) + 1
            new_calcs_by_id[calc.id] = calc
            continue

        dax, rule_name = dispatch_rule(calc, parameters=parameters)
        if dax is not None and is_valid_dax(dax):
            by_source["rule"] = by_source.get("rule", 0) + 1
            if rule_name:
                rule_hits[rule_name] = rule_hits.get(rule_name, 0) + 1
            new_calcs_by_id[calc.id] = calc.model_copy(update={"dax_expr": dax})
            continue

        # AI fallback.
        if client is None:
            client = _make_client(ctx)
        cache_before = sum(
            1 for _ in client.cache.root.iterdir()
        ) if client.cache.root.exists() else 0
        ai = translate_via_ai(calc, fixture=None, client=client)
        cache_after = sum(
            1 for _ in client.cache.root.iterdir()
        ) if client.cache.root.exists() else 0
        if cache_after > cache_before:
            ai_cache_misses += 1
        else:
            ai_cache_hits += 1

        if ai is None:
            validator_failed += 1
            new_unsupported.append(UnsupportedItem(
                object_kind="calc", object_id=calc.id,
                source_excerpt=calc.tableau_expr[:200],
                reason=f"DAX syntax gate rejected output for {calc.name!r}",
                code="calc_dax_syntax_failed",
            ))
            new_calcs_by_id[calc.id] = calc
            continue

        by_source["ai"] = by_source.get("ai", 0) + 1
        conf = ai.get("confidence", "low")
        ai_confidence[conf] = ai_confidence.get(conf, 0) + 1
        new_calcs_by_id[calc.id] = calc.model_copy(
            update={"dax_expr": ai["dax_expr"]},
        )

    new_calcs = tuple(
        new_calcs_by_id[c.id] for c in wb.data_model.calculations
    )
    new_data_model = wb.data_model.model_copy(update={"calculations": new_calcs})
    new_wb = wb.model_copy(update={
        "data_model": new_data_model,
        "unsupported": tuple(new_unsupported),
    })

    stats = TranslationStats(
        total=len(wb.data_model.calculations),
        by_source=by_source, rule_hits=rule_hits,
        ai_confidence=ai_confidence,
        ai_cache_hits=ai_cache_hits, ai_cache_misses=ai_cache_misses,
        validator_failed=validator_failed,
    )
    return StageResult(
        output=new_wb.model_dump(mode="json"),
        summary_md=render_stage3_summary(stats),
        errors=(),
    )
