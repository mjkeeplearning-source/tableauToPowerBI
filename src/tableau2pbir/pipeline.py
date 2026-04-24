"""Pipeline runner and stage contract — §4.3 + §8.2.

Only the contract types are defined in this task. Registry and runner
are added in Task 13/14."""
from __future__ import annotations

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
