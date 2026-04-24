"""Parameter IR — enriched per §5.7 with intent classification."""
from __future__ import annotations

from enum import Enum

from tableau2pbir.ir.common import IRBase


class ParameterIntent(str, Enum):
    NUMERIC_WHAT_IF = "numeric_what_if"
    CATEGORICAL_SELECTOR = "categorical_selector"
    INTERNAL_CONSTANT = "internal_constant"
    FORMATTING_CONTROL = "formatting_control"
    UNSUPPORTED = "unsupported"


class ParameterExposure(str, Enum):
    CARD = "card"           # has a parameter card on a dashboard
    SHELF = "shelf"         # used on a viz shelf
    CALC_ONLY = "calc_only" # referenced only in calc bodies


class ParameterBindingTarget(IRBase):
    """Present only when intent == FORMATTING_CONTROL."""
    measure_ids: tuple[str, ...]
    format_pattern: str | None = None


class Parameter(IRBase):
    id: str
    name: str
    datatype: str
    default: str
    allowed_values: tuple[str, ...]
    intent: ParameterIntent
    exposure: ParameterExposure
    binding_target: ParameterBindingTarget | None = None
