"""Common IR types shared across IR modules. See spec §5."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class IRBase(BaseModel):
    """Base class for all IR pydantic models. Frozen so IR objects are hashable
    after canonicalization, and extra fields are rejected so drift is caught
    by the stage 2 contract test."""
    model_config = ConfigDict(frozen=True, extra="forbid")


class FieldRef(IRBase):
    """Reference to a column inside a table. Used by encodings, table_calc
    addressing/partitioning/sort, lod_fixed.dimensions, etc."""
    table_id: str
    column_id: str


class UnsupportedItem(IRBase):
    """One entry in Workbook.unsupported[] (§5.1) or workbook-level
    unsupported.json (§4.4). Must carry enough context for the
    workbook-report.md renderer to produce a human-readable entry."""
    object_kind: str            # "mark" | "calc" | "datasource" | "parameter" | "action" | ...
    object_id: str              # IR id of the affected object
    source_excerpt: str         # short XML/expr excerpt for debugging
    reason: str                 # human-readable reason
    code: str = Field(          # stable code for status-rule matching (§8.1)
        description="Stable identifier, e.g. 'unsupported_mark_polygon', "
                    "'deferred_feature_table_calcs', 'datasource_tier_4'.",
    )
