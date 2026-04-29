"""LeafKind → PBI object-kind mapping. §6 Stage 5 step 4."""
from __future__ import annotations

from enum import Enum

from tableau2pbir.ir.dashboard import LeafKind


class PbiObjectKind(str, Enum):
    VISUAL = "visual"
    SLICER_FILTER = "slicer_filter"
    SLICER_PARAMETER = "slicer_parameter"
    LEGEND_SUPPRESS = "legend_suppress"
    TEXTBOX = "textbox"
    IMAGE = "image"
    NAV_BUTTON = "nav_button"
    PLACEHOLDER = "placeholder"
    DROP = "drop"


_TABLE: dict[LeafKind, PbiObjectKind] = {
    LeafKind.SHEET:          PbiObjectKind.VISUAL,
    LeafKind.FILTER_CARD:    PbiObjectKind.SLICER_FILTER,
    LeafKind.PARAMETER_CARD: PbiObjectKind.SLICER_PARAMETER,
    LeafKind.LEGEND:         PbiObjectKind.LEGEND_SUPPRESS,
    LeafKind.TEXT:           PbiObjectKind.TEXTBOX,
    LeafKind.IMAGE:          PbiObjectKind.IMAGE,
    LeafKind.NAVIGATION:     PbiObjectKind.NAV_BUTTON,
    LeafKind.WEB_PAGE:       PbiObjectKind.PLACEHOLDER,
    LeafKind.BLANK:          PbiObjectKind.DROP,
}


def map_leaf_kind(kind: LeafKind) -> PbiObjectKind:
    return _TABLE[kind]
