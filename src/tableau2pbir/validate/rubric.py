"""Rubric loader + evaluator. See spec §15."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from tableau2pbir.validate.results import (
    RubricItemResult, RubricResult, ValidatorOutcome,
)


@dataclass(frozen=True)
class RubricPage:
    name: str
    must_render_visuals: tuple[str, ...]
    must_have_slicers: tuple[str, ...]
    known_degradations: tuple[str, ...]


@dataclass(frozen=True)
class Rubric:
    workbook: str
    pages: tuple[RubricPage, ...]
    measures: tuple[dict, ...]
    datasources: tuple[dict, ...]
    pass_criteria: dict[str, Any]


def load_rubric(path: Path) -> Rubric:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    pages = tuple(
        RubricPage(
            name=p.get("name", ""),
            must_render_visuals=tuple(p.get("must_render_visuals") or ()),
            must_have_slicers=tuple(p.get("must_have_slicers") or ()),
            known_degradations=tuple(p.get("known_degradations") or ()),
        )
        for p in (data.get("pages") or ())
    )
    return Rubric(
        workbook=data.get("workbook", ""),
        pages=pages,
        measures=tuple(data.get("measures") or ()),
        datasources=tuple(data.get("datasources") or ()),
        pass_criteria=dict(data.get("pass_criteria") or {}),
    )


def evaluate_rubric(rubric: Rubric, observation: dict[str, Any]) -> RubricResult:
    items: list[RubricItemResult] = []
    pc = rubric.pass_criteria

    if "all_pages_load" in pc:
        rendered = set(observation.get("rendered_pages") or ())
        expected = {p.name for p in rubric.pages}
        ok = expected.issubset(rendered) if expected else True
        items.append(RubricItemResult(
            name="all_pages_load", required=bool(pc["all_pages_load"]),
            outcome=ValidatorOutcome.PASSED if ok else ValidatorOutcome.FAILED,
            observed=f"{len(rendered & expected)}/{len(expected)} pages",
        ))

    if "all_must_render_visuals_present" in pc:
        ok, observed = _check_must_lists(
            rubric, observation.get("rendered_visuals_by_page") or {},
            attr="must_render_visuals",
        )
        items.append(RubricItemResult(
            name="all_must_render_visuals_present",
            required=bool(pc["all_must_render_visuals_present"]),
            outcome=ValidatorOutcome.PASSED if ok else ValidatorOutcome.FAILED,
            observed=observed,
        ))

    if "all_must_have_slicers_present" in pc:
        ok, observed = _check_must_lists(
            rubric, observation.get("rendered_slicers_by_page") or {},
            attr="must_have_slicers",
        )
        items.append(RubricItemResult(
            name="all_must_have_slicers_present",
            required=bool(pc["all_must_have_slicers_present"]),
            outcome=ValidatorOutcome.PASSED if ok else ValidatorOutcome.FAILED,
            observed=observed,
        ))

    if "no_unexpected_placeholders" in pc:
        bad: list[str] = []
        for page in rubric.pages:
            placeholders = set(
                (observation.get("placeholder_visuals_by_page") or {}).get(page.name, ())
            )
            unexpected = placeholders - set(page.known_degradations)
            for u in unexpected:
                bad.append(f"{page.name}/{u}")
        ok = not bad
        items.append(RubricItemResult(
            name="no_unexpected_placeholders",
            required=bool(pc["no_unexpected_placeholders"]),
            outcome=ValidatorOutcome.PASSED if ok else ValidatorOutcome.FAILED,
            observed=", ".join(bad) if bad else "none",
        ))

    if "desktop_open_gate" in pc:
        target = pc["desktop_open_gate"]
        actual = observation.get("desktop_open_outcome", "skipped")
        ok = (actual == target)
        items.append(RubricItemResult(
            name="desktop_open_gate", required=True,
            outcome=ValidatorOutcome.PASSED if ok else ValidatorOutcome.FAILED,
            observed=str(actual),
        ))

    if "all_measure_values_within_tolerance" in pc:
        items.append(RubricItemResult(
            name="all_measure_values_within_tolerance",
            required=bool(pc["all_measure_values_within_tolerance"]),
            outcome=ValidatorOutcome.SKIPPED,
            observed="dax_probe_runner_unavailable",
        ))

    failed_required = any(
        i.required and i.outcome == ValidatorOutcome.FAILED for i in items
    )
    overall = ValidatorOutcome.FAILED if failed_required else ValidatorOutcome.PASSED
    return RubricResult(outcome=overall, reason=None, items=tuple(items))


def _check_must_lists(rubric: Rubric, observed_by_page: dict[str, list[str]],
                      *, attr: str) -> tuple[bool, str]:
    missing: list[str] = []
    total = 0
    for page in rubric.pages:
        wanted = set(getattr(page, attr))
        total += len(wanted)
        actual = set(observed_by_page.get(page.name, ()))
        for w in wanted:
            if w not in actual:
                missing.append(f"{page.name}/{w}")
    return (not missing, f"missing={missing}" if missing else f"all {total} present")


def write_acceptance_json(path: Path, result: RubricResult) -> None:
    payload = {
        "overall": result.outcome.value,
        "items": [
            {"name": i.name, "required": i.required,
             "outcome": i.outcome.value, "observed": i.observed}
            for i in result.items
        ],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
