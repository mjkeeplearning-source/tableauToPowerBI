"""Pipeline runner and stage contract — §4.3 + §8.2."""
from __future__ import annotations

import importlib
import json as _json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict


Severity = Literal["info", "warn", "error", "fatal"]


class _ContractBase(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class StageError(_ContractBase):
    severity: Severity
    code: str
    object_id: str
    message: str
    fix_hint: str | None


class StageResult(_ContractBase):
    output: dict = {}
    summary_md: str = ""
    errors: tuple[StageError, ...] = ()


class StageContext(_ContractBase):
    workbook_id: str
    output_dir: Path
    config: dict
    stage_number: int

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True, extra="forbid")


# ---- Stage registry + runner ----

_STAGE_NAMES = [
    "extract", "canonicalize", "translate_calcs", "map_visuals",
    "compute_layout", "build_tmdl", "build_pbir", "package_validate",
]

_MODULE_SUFFIX = {
    "extract": "s01_extract",
    "canonicalize": "s02_canonicalize",
    "translate_calcs": "s03_translate_calcs",
    "map_visuals": "s04_map_visuals",
    "compute_layout": "s05_compute_layout",
    "build_tmdl": "s06_build_tmdl",
    "build_pbir": "s07_build_pbir",
    "package_validate": "s08_package_validate",
}

STAGE_SEQUENCE: list[tuple[str, str]] = [
    (name, _MODULE_SUFFIX[name]) for name in _STAGE_NAMES
]


class PipelineResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    workbook_id: str
    stages_run: int
    errors: tuple[StageError, ...]
    stopped_at_gate: str | None = None


def _load_stage(name: str):
    if name not in _MODULE_SUFFIX:
        raise ValueError(f"unknown stage: {name!r}")
    return importlib.import_module(f"tableau2pbir.stages.{_MODULE_SUFFIX[name]}")


def run_pipeline(
    *,
    workbook_id: str,
    source_path: Path,
    output_dir: Path,
    config: dict,
    gate: str | None,
    resume_from: str | None,
) -> PipelineResult:
    """Run the 8-stage pipeline. See spec §4.3 and §4.5."""
    valid_names = {name for name, _ in STAGE_SEQUENCE}
    if gate is not None and gate not in valid_names:
        raise ValueError(f"unknown stage: {gate!r}")
    if resume_from is not None and resume_from not in valid_names:
        raise ValueError(f"unknown stage: {resume_from!r}")

    stages_dir = output_dir / "stages"
    stages_dir.mkdir(parents=True, exist_ok=True)

    resume_idx = 0
    if resume_from is not None:
        resume_idx = next(i for i, (name, _) in enumerate(STAGE_SEQUENCE) if name == resume_from)

    if resume_idx == 0:
        current_input: dict = {"source_path": str(source_path)}
    else:
        prior_name = STAGE_SEQUENCE[resume_idx - 1][0]
        prior_path = stages_dir / f"{resume_idx:02d}_{prior_name}.json"
        if not prior_path.exists():
            raise FileNotFoundError(
                f"cannot resume from {resume_from!r}: missing prior artifact {prior_path}"
            )
        current_input = _json.loads(prior_path.read_text(encoding="utf-8"))

    all_errors: list[StageError] = []
    stages_run = 0
    stopped_at_gate: str | None = None

    for idx, (name, _mod) in enumerate(STAGE_SEQUENCE[resume_idx:], start=resume_idx + 1):
        mod = _load_stage(name)
        ctx = StageContext(
            workbook_id=workbook_id,
            output_dir=output_dir,
            config=config,
            stage_number=idx,
        )
        result = mod.run(current_input, ctx)
        (stages_dir / f"{idx:02d}_{name}.json").write_text(
            _json.dumps(result.output, indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )
        (stages_dir / f"{idx:02d}_{name}.summary.md").write_text(
            result.summary_md, encoding="utf-8",
        )
        all_errors.extend(result.errors)
        current_input = result.output
        stages_run += 1
        if any(e.severity == "fatal" for e in result.errors):
            break
        if gate is not None and name == gate:
            stopped_at_gate = name
            break

    (output_dir / "unsupported.json").write_text(
        _json.dumps([], indent=2), encoding="utf-8",
    )
    return PipelineResult(
        workbook_id=workbook_id,
        stages_run=stages_run,
        errors=tuple(all_errors),
        stopped_at_gate=stopped_at_gate,
    )
