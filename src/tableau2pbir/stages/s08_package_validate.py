"""Stage 8 — package + validate (pure python). See spec §6 Stage 8."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tableau2pbir.pipeline import StageContext, StageResult
from tableau2pbir.validate import (
    desktop_open as _do, pbir_compile as _pbir, pbip as _pbip,
    report as _report, rubric as _rubric, status as _status,
    structural as _struct, tmdl_schema as _tmdl,
)
from tableau2pbir.validate.results import ValidatorOutcome


def _read_json(p: Path, default):
    if not p.is_file():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def _is_real_workbook(workbook_id: str, config: dict) -> tuple[bool, Path | None]:
    """Real-workbook detection: explicit config override OR a <id>.rubric.yaml
    file alongside tests/golden/real/."""
    if "is_real_workbook" in config:
        is_real = bool(config["is_real_workbook"])
        rubric_path = Path(config["rubric_path"]) if config.get("rubric_path") else None
        return is_real, rubric_path
    repo_root = Path(__file__).resolve().parents[3]
    candidate = repo_root / "tests" / "golden" / "real" / f"{workbook_id}.rubric.yaml"
    if candidate.is_file():
        return True, candidate
    return False, None


def run(input_json: dict[str, Any], ctx: StageContext) -> StageResult:
    out_dir = ctx.output_dir
    stages_dir = out_dir / "stages"

    # 1. Package — write the .pbip pointer.
    pbip_path = _pbip.write_pbip_root(out_dir, ctx.workbook_id)

    # 2. TMDL validity.
    tmdl_res = _tmdl.run_tmdl_validity(out_dir)
    # 3. PBIR compile.
    pbir_res = _pbir.run_pbir_compile(out_dir)
    # 4. Structural checks.
    struct_res = _struct.run_structural(out_dir)
    (out_dir / "validation").mkdir(exist_ok=True)
    (out_dir / "validation" / "structural.json").write_text(
        json.dumps({
            "outcome": struct_res.outcome.value,
            "findings": [
                {"code": f.code, "severity": f.severity,
                 "message": f.message, "location": f.location}
                for f in struct_res.findings
            ],
        }, indent=2), encoding="utf-8")

    # Load IR + manifests for downstream steps.
    ir = _read_json(stages_dir / "02_canonicalize.json", {})
    s07 = _read_json(stages_dir / "07_build_pbir.json", {"blocked_visuals": [], "counts": {}})
    unsupported = _read_json(out_dir / "unsupported.json", [])

    datasources = ir.get("data_model", {}).get("datasources", [])
    tiers = tuple(int(d.get("connector_tier", 1)) for d in datasources)
    is_real, rubric_path = _is_real_workbook(ctx.workbook_id, ctx.config)

    # 5. Desktop-open gate (real-workbook subset only).
    if is_real and 4 not in tiers:
        traces_dir = Path(ctx.config.get("pbi_traces_dir") or
                          (Path.home() / "AppData" / "Local" / "Microsoft" /
                           "Power BI Desktop" / "Traces"))
        desktop_res = _do.run_desktop_open(
            pbip_path, datasource_tiers=tiers, traces_dir=traces_dir,
            desktop_version=str(ctx.config.get("pbi_desktop_version", "2.130")),
        )
    else:
        desktop_res = _do.DesktopOpenResult(
            outcome=ValidatorOutcome.SKIPPED,
            reason="synthetic" if not is_real else "tier_4_short_circuit",
        )

    # 6. Rubric evaluation.
    if is_real and rubric_path is not None:
        rubric = _rubric.load_rubric(rubric_path)
        observation = _build_observation(ir, s07, desktop_res.outcome.value)
        rubric_res = _rubric.evaluate_rubric(rubric, observation)
        _rubric.write_acceptance_json(out_dir / "acceptance.json", rubric_res)
        rubric_outcome = rubric_res.outcome.value
        rubric_reason = rubric_res.reason
        rubric_items = [
            {"name": i.name, "required": i.required,
             "outcome": i.outcome.value, "observed": i.observed}
            for i in rubric_res.items
        ]
        acceptance_failed = rubric_res.outcome == ValidatorOutcome.FAILED
    else:
        rubric_outcome = "skipped"
        rubric_reason = ("synthetic" if "is_real_workbook" in ctx.config and not ctx.config["is_real_workbook"]
                         else "no_rubric" if not is_real else "rubric_missing")
        rubric_items = []
        acceptance_failed = False

    # 7. Status rule.
    obs_bundle = _status.ObservationBundle(
        datasource_tiers=tiers,
        unsupported=unsupported,
        measures_total=sum(
            1 for c in ir.get("data_model", {}).get("calculations", [])
            if c.get("scope") == "measure"
        ) or 1,
        placeholder_leaf_ratios=[],
        blocked_visuals=s07.get("blocked_visuals", []),
        tmdl_outcome=tmdl_res.outcome.value,
        pbir_compile_outcome=pbir_res.outcome.value,
        desktop_open_outcome=desktop_res.outcome.value,
        rubric_acceptance_failed=acceptance_failed,
        any_calc_low_confidence=any(
            (c.get("confidence") or "high") != "high"
            for c in ir.get("data_model", {}).get("calculations", [])
        ),
        any_clamped_or_dropped_layout=False,
        param_intents=[
            (p.get("intent") or {}).get("value") if isinstance(p.get("intent"), dict)
            else (p.get("intent") or "")
            for p in ir.get("data_model", {}).get("parameters", [])
        ],
        user_actions=[
            ua for d in datasources for ua in (d.get("user_action_required") or [])
        ],
    )
    final_status, triggers = _status.compute_status(obs_bundle)

    # 8. Reporting.
    validators = {
        "tmdl":         {"result": tmdl_res.outcome.value, "reason": tmdl_res.reason,
                         "log_path": tmdl_res.log_path},
        "pbir_compile": {"result": pbir_res.outcome.value, "reason": pbir_res.reason,
                         "log_path": pbir_res.log_path},
        "structural":   {"result": struct_res.outcome.value,
                         "findings": [
                             {"code": f.code, "severity": f.severity,
                              "message": f.message, "location": f.location}
                             for f in struct_res.findings
                         ],
                         "log_path": "validation/structural.json"},
        "desktop_open": {"result": desktop_res.outcome.value, "reason": desktop_res.reason,
                         "events": [{"name": e.name, "ts": e.timestamp_ms}
                                    for e in desktop_res.events],
                         "log_path": desktop_res.log_path},
        "rubric":       {"result": rubric_outcome, "reason": rubric_reason,
                         "items": rubric_items, "log_path": "acceptance.json"},
    }

    workbook_md = _report.render_workbook_report(
        workbook_id=ctx.workbook_id, status=final_status, triggers=triggers,
        validators={
            k: {"outcome": v["result"], "reason": v.get("reason"),
                "findings": v.get("findings")}
            for k, v in validators.items()
        },
        datasources=[{"name": d.get("name"),
                      "tier": int(d.get("connector_tier", 1)),
                      "user_action_required": d.get("user_action_required") or []}
                     for d in datasources],
        placeholders_per_page={d.get("name", d.get("id", "?")): 0
                               for d in ir.get("dashboards", [])},
    )
    (out_dir / "workbook-report.md").write_text(workbook_md, encoding="utf-8")

    artifact_size = sum(p.stat().st_size for p in out_dir.rglob("*") if p.is_file())
    summary_md = _report.render_summary_md(
        validators={k: {"outcome": v["result"], "reason": v.get("reason")}
                    for k, v in validators.items()},
        artifact_size_bytes=artifact_size,
        status=final_status,
    )

    manifest = {
        "pbip_path": str(pbip_path.relative_to(out_dir)),
        "validators": validators,
        "status": final_status,
        "trigger_reasons": triggers,
    }
    return StageResult(output=manifest, summary_md=summary_md, errors=())


def _build_observation(ir: dict, s07: dict, desktop_outcome: str) -> dict:
    rendered_pages = [d.get("name", d.get("id", "?")) for d in ir.get("dashboards", [])]
    rendered_visuals_by_page: dict[str, list[str]] = {}
    rendered_slicers_by_page: dict[str, list[str]] = {}
    placeholder_visuals_by_page: dict[str, list[str]] = {}
    for d in ir.get("dashboards", []):
        key = d.get("name", d.get("id", "?"))
        rendered_visuals_by_page[key] = []
        rendered_slicers_by_page[key] = []
        placeholder_visuals_by_page[key] = []
    return {
        "rendered_pages": rendered_pages,
        "rendered_visuals_by_page": rendered_visuals_by_page,
        "rendered_slicers_by_page": rendered_slicers_by_page,
        "placeholder_visuals_by_page": placeholder_visuals_by_page,
        "desktop_open_outcome": desktop_outcome,
    }
