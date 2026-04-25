"""Private builders for Stage 2. One function per IR sub-tree. These are
pure: no I/O, no module-level state, fully unit-testable."""
from __future__ import annotations

import re
from typing import Any

from tableau2pbir.classify.calc_kind import classify_calc_kind
from tableau2pbir.classify.connector_tier import classify_connector
from tableau2pbir.classify.parameter_intent import classify_parameter_intent
from tableau2pbir.ir.calculation import (
    Calculation, CalculationKind, CalculationPhase, CalculationScope,
    LodFixed, LodRelative,
)
from tableau2pbir.ir.common import FieldRef, UnsupportedItem
from tableau2pbir.ir.parameter import Parameter, ParameterExposure, ParameterIntent
from tableau2pbir.ir.datasource import ConnectorTier, Datasource
from tableau2pbir.ir.model import Column, ColumnKind, ColumnRole, Table
from tableau2pbir.util.ids import stable_id


def _connection_params(raw_ds: dict[str, Any]) -> dict[str, str]:
    conn = raw_ds.get("connection") or {}
    params: dict[str, str] = {}
    for key in ("server", "dbname", "database", "warehouse", "filename",
                "directory", "host", "port", "schema", "http_path",
                "billing_project", "catalog"):
        if key in conn and conn[key]:
            params[key] = conn[key]
    return params


def _source_excerpt(raw_ds: dict[str, Any]) -> str:
    conn = raw_ds.get("connection") or {}
    return f"<datasource name={raw_ds.get('name')!r} connection.class={conn.get('class')!r}/>"


def build_datasources(
    raw_datasources: list[dict[str, Any]],
) -> tuple[tuple[Datasource, ...], tuple[UnsupportedItem, ...]]:
    """Map raw extract datasources to IR Datasources with §5.8 classification.
    Returns (datasources, unsupported_items). Tier 3/4 datasources get both
    an IR record AND an UnsupportedItem appended."""
    datasources: list[Datasource] = []
    unsupported: list[UnsupportedItem] = []

    for raw in raw_datasources:
        classification = classify_connector(raw)
        ds_id = stable_id("ds", raw["name"])
        extract_ignored = raw.get("extract") is not None and classification.tier in (1, 2)

        ds = Datasource(
            id=ds_id,
            name=raw["name"],
            tableau_kind=(raw.get("connection") or {}).get("class", "unknown"),
            connector_tier=ConnectorTier(classification.tier),
            pbi_m_connector=classification.pbi_m_connector,
            connection_params=_connection_params(raw),
            user_action_required=classification.user_action_required,
            table_ids=(),                # populated in task 16 (build_tables)
            extract_ignored=extract_ignored,
        )
        datasources.append(ds)

        if classification.tier == 4:
            unsupported.append(UnsupportedItem(
                object_kind="datasource",
                object_id=ds_id,
                source_excerpt=_source_excerpt(raw),
                reason=classification.reason or "Tier 4 datasource — no PBI mapping.",
                code="unsupported_datasource_tier_4",
            ))
        elif classification.tier == 3:
            unsupported.append(UnsupportedItem(
                object_kind="datasource",
                object_id=ds_id,
                source_excerpt=_source_excerpt(raw),
                reason=classification.reason or "Tier 3 datasource — deferred to v1.2.",
                code="deferred_feature_tier3",
            ))

    return tuple(datasources), tuple(unsupported)


def _column_role(raw_role: str) -> ColumnRole:
    return ColumnRole.MEASURE if raw_role == "measure" else ColumnRole.DIMENSION


def build_tables(
    raw_datasources: list[dict[str, Any]],
) -> tuple[tuple[Table, ...], tuple[Column, ...]]:
    """Emit one IR Table per datasource with all its columns.

    Calculated columns are recognized here: when a raw column's name matches
    a calculation's `host_column_name`, its kind becomes CALCULATED and the
    `tableau_expr` is carried through. DAX translation happens in Plan 3."""
    tables: list[Table] = []
    columns: list[Column] = []

    for raw in raw_datasources:
        ds_id = stable_id("ds", raw["name"])
        table_id = stable_id("tbl", raw["name"])
        calc_by_host = {c["host_column_name"]: c for c in raw.get("calculations", [])}
        col_ids: list[str] = []

        for col in raw.get("columns", []):
            col_id = f"{table_id}__{stable_id('col', col['name'])}"
            calc = calc_by_host.get(col["name"])
            if calc is not None:
                column = Column(
                    id=col_id, name=col["name"],
                    datatype=col["datatype"], role=_column_role(col["role"]),
                    kind=ColumnKind.CALCULATED,
                    tableau_expr=calc["tableau_expr"],
                    dax_expr=None,
                )
            else:
                column = Column(
                    id=col_id, name=col["name"],
                    datatype=col["datatype"], role=_column_role(col["role"]),
                    kind=ColumnKind.RAW,
                )
            columns.append(column)
            col_ids.append(col_id)

        tables.append(Table(
            id=table_id,
            name=raw["name"],
            datasource_id=ds_id,
            column_ids=tuple(col_ids),
            primary_key=None,
        ))

    return tuple(tables), tuple(columns)


_LOD_HEADER = re.compile(
    r"^\s*\{\s*(FIXED|INCLUDE|EXCLUDE)\s*(?P<dims>.*?)\s*:\s*.*\}\s*$",
    re.IGNORECASE | re.DOTALL,
)
_BRACKETED = re.compile(r"\[([^\[\]]+)\]")


def _parse_lod_dimensions(tableau_expr: str, table_id: str) -> tuple[FieldRef, ...]:
    m = _LOD_HEADER.match(tableau_expr)
    if not m:
        return ()
    dims_text = m.group("dims").strip()
    if not dims_text:
        return ()
    refs: list[FieldRef] = []
    for name in _BRACKETED.findall(dims_text):
        refs.append(FieldRef(table_id=table_id, column_id=stable_id("", name).lstrip("_")))
    return tuple(refs)


def _scope(raw_role: str) -> CalculationScope:
    return CalculationScope.MEASURE if raw_role == "measure" else CalculationScope.COLUMN


def _dependency_ids(expr: str, calc_name_to_id: dict[str, str]) -> tuple[str, ...]:
    deps: list[str] = []
    for name in _BRACKETED.findall(expr):
        if name in calc_name_to_id and calc_name_to_id[name] not in deps:
            deps.append(calc_name_to_id[name])
    return tuple(deps)


def build_calculations(
    raw_datasources: list[dict[str, Any]],
) -> tuple[Calculation, ...]:
    """Map raw calculations (from extract) to IR Calculations with
    classified kind/phase. Kind-specific payloads (lod_fixed, lod_relative)
    are filled in here; table_calc specifics and anonymous quick-table-calc
    records are handled in task 22 (deferred-feature routing) for v1."""
    # First pass — build name → id map for dependency resolution.
    name_to_id: dict[str, str] = {}
    per_calc: list[tuple[dict[str, Any], str, str]] = []   # (raw_calc, calc_id, table_id)
    for raw_ds in raw_datasources:
        table_id = stable_id("tbl", raw_ds["name"])
        for calc in raw_ds.get("calculations", []):
            calc_id = stable_id("calc", calc["host_column_name"])
            name_to_id[calc["host_column_name"]] = calc_id
            per_calc.append((calc, calc_id, table_id))

    out: list[Calculation] = []
    for raw_calc, calc_id, table_id in per_calc:
        expr = raw_calc["tableau_expr"]
        classification = classify_calc_kind(expr)
        kind = CalculationKind(classification.kind)
        phase = CalculationPhase(classification.phase)

        lod_fixed = None
        lod_relative = None
        if kind == CalculationKind.LOD_FIXED:
            lod_fixed = LodFixed(dimensions=_parse_lod_dimensions(expr, table_id))
        elif kind == CalculationKind.LOD_INCLUDE:
            dims = _parse_lod_dimensions(expr, table_id)
            lod_relative = LodRelative(extra_dims=dims if dims else None)
        elif kind == CalculationKind.LOD_EXCLUDE:
            dims = _parse_lod_dimensions(expr, table_id)
            lod_relative = LodRelative(excluded_dims=dims if dims else None)

        out.append(Calculation(
            id=calc_id,
            name=raw_calc["host_column_name"],
            scope=_scope(raw_calc["role"]),
            tableau_expr=expr,
            dax_expr=None,
            depends_on=_dependency_ids(expr, name_to_id),
            kind=kind,
            phase=phase,
            lod_fixed=lod_fixed,
            lod_relative=lod_relative,
            table_calc=None,                # Plan 3 populates table_calc details.
            owner_sheet_id=None,
        ))
    return tuple(out)


def _synthesize_range_values(range_dict: dict[str, str]) -> tuple[str, ...]:
    return (range_dict["min"], range_dict["max"], range_dict["granularity"])


def _exposure(raw_usage: str | None) -> ParameterExposure:
    if raw_usage == "card":
        return ParameterExposure.CARD
    if raw_usage == "shelf":
        return ParameterExposure.SHELF
    return ParameterExposure.CALC_ONLY


def build_parameters(
    raw_parameters: list[dict[str, Any]],
    usage: dict[str, str],
) -> tuple[Parameter, ...]:
    """`usage[param_name]` ∈ {'card','shelf','calc_only'} derived by the
    orchestrator from dashboards + worksheets. Defaults to 'calc_only'."""
    out: list[Parameter] = []
    for raw in raw_parameters:
        exposure_raw = usage.get(raw["name"], "calc_only")
        intent_str = classify_parameter_intent(
            domain_type=raw["domain_type"],
            exposure=exposure_raw,
        )
        exposure = _exposure(exposure_raw)
        allowed = raw["allowed_values"]
        if not allowed and raw["domain_type"] == "range" and raw["range"]:
            allowed = _synthesize_range_values(raw["range"])
        out.append(Parameter(
            id=stable_id("param", raw["name"]),
            name=raw["name"],
            datatype=raw["datatype"],
            default=raw["default"],
            allowed_values=tuple(allowed),
            intent=ParameterIntent(intent_str),
            exposure=exposure,
            binding_target=None,
        ))
    return tuple(out)
