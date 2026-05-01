"""Result dataclasses shared by Stage 8 validators. See spec §6 Stage 8."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ValidatorOutcome(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class ValidatorResult:
    outcome: ValidatorOutcome
    reason: str | None
    log_path: str | None


@dataclass(frozen=True)
class StructuralFinding:
    code: str
    severity: str          # 'info' | 'warn' | 'error'
    message: str
    location: str


@dataclass(frozen=True)
class StructuralResult:
    outcome: ValidatorOutcome
    findings: tuple[StructuralFinding, ...] = ()
    log_path: str | None = None


@dataclass(frozen=True)
class TraceEvent:
    name: str              # canonical (ReportLoaded / ModelLoaded / ...)
    timestamp_ms: int
    raw: str               # original event line for debugging


@dataclass(frozen=True)
class DesktopOpenResult:
    outcome: ValidatorOutcome
    reason: str | None
    events: tuple[TraceEvent, ...] = ()
    expected_credential_prompts: tuple[TraceEvent, ...] = ()
    log_path: str | None = None


@dataclass(frozen=True)
class RubricItemResult:
    name: str
    required: bool
    outcome: ValidatorOutcome
    observed: str | None = None


@dataclass(frozen=True)
class RubricResult:
    outcome: ValidatorOutcome
    reason: str | None
    items: tuple[RubricItemResult, ...] = ()
    log_path: str | None = None
