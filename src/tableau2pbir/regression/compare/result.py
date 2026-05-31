"""Regression result data models."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class EntityDiff:
    entity_type: str   # "measure", "column", "property", "missing_file"
    entity_name: str
    attribute: str     # "DAX", "dataType", "sourceColumn", "value"
    old_value: str
    new_value: str


@dataclass
class FileDiff:
    relative_path: str
    missing: bool = False  # True if file in snapshot but absent from new output
    diffs: list[EntityDiff] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return self.missing or bool(self.diffs)


@dataclass
class WorkbookResult:
    name: str
    status: Literal["PASS", "FAIL", "SKIP"]
    skip_reason: str = ""
    file_diffs: list[FileDiff] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.status in ("PASS", "SKIP")


@dataclass
class RegressionResult:
    workbook_results: list[WorkbookResult] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return all(r.passed for r in self.workbook_results)

    @property
    def exit_code(self) -> int:
        return 0 if self.all_passed else 1
