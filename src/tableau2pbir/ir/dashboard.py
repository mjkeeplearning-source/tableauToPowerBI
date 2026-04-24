"""Dashboard IR, layout tree, and Action — §5.1, §5.2, §5.3."""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import Field

from tableau2pbir.ir.common import IRBase


class ContainerKind(str, Enum):
    H = "h"
    V = "v"
    FLOATING = "floating"


class LeafKind(str, Enum):
    SHEET = "sheet"
    TEXT = "text"
    IMAGE = "image"
    FILTER_CARD = "filter_card"
    PARAMETER_CARD = "parameter_card"
    LEGEND = "legend"
    NAVIGATION = "navigation"
    BLANK = "blank"
    WEB_PAGE = "web_page"


class Position(IRBase):
    x: int
    y: int
    w: int
    h: int


class Leaf(IRBase):
    kind: LeafKind
    payload: dict[str, Any]                   # shape depends on kind (§5.2)
    position: Position | None = None          # None at extract; filled by stage 5


class Container(IRBase):
    kind: ContainerKind
    children: tuple["Container | Leaf", ...]
    padding: int = 0
    background: str | None = None


# Let pydantic resolve the recursive ref
Container.model_rebuild()


class DashboardSize(IRBase):
    w: int
    h: int
    kind: str                                 # "exact" | "automatic" | "range"


class ActionKind(str, Enum):
    FILTER = "filter"
    HIGHLIGHT = "highlight"
    URL = "url"
    PARAMETER = "parameter"


class ActionTrigger(str, Enum):
    SELECT = "select"
    HOVER = "hover"
    MENU = "menu"


class Action(IRBase):
    id: str
    name: str
    kind: ActionKind
    trigger: ActionTrigger
    source_sheet_ids: tuple[str, ...]
    target_sheet_ids: tuple[str, ...]
    source_fields: tuple[str, ...] = ()
    target_fields: tuple[str, ...] = ()
    clearing_behavior: str = "keep_filter"    # "keep_filter" | "show_all" | "exclude"


class Dashboard(IRBase):
    id: str
    name: str
    size: DashboardSize
    layout_tree: Container | Leaf = Field(discriminator=None)   # root is usually a Container
    actions: tuple[Action, ...] = ()
