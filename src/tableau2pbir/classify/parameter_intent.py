"""§5.7 parameter-intent classification."""
from __future__ import annotations

from typing import Literal


Intent = Literal[
    "numeric_what_if", "categorical_selector",
    "internal_constant", "formatting_control", "unsupported",
]
DomainType = Literal["range", "list", "any"]
Exposure = Literal["card", "shelf", "calc_only"]


def classify_parameter_intent(
    *,
    domain_type: str,
    exposure: str,
    drives_format_switch: bool = False,
) -> Intent:
    if drives_format_switch:
        return "formatting_control"
    if exposure == "calc_only":
        return "internal_constant"
    if domain_type == "range" and exposure == "card":
        return "numeric_what_if"
    if domain_type == "list" and exposure == "card":
        return "categorical_selector"
    return "unsupported"
