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
from tableau2pbir.ir.model import Column, ColumnKind, ColumnRole, Relationship, RelationshipSource, Table
from tableau2pbir.util.ids import stable_id


def _connection_params(raw_ds: dict[str, Any]) -> dict[str, str]:
    conn = raw_ds.get("connection") or {}
    # For federated datasources the top-level connection has no real params;
    # use the first named-connection's connection instead.
    if conn.get("class") == "federated":
        named = raw_ds.get("named_connections") or []
        if named and named[0].get("connection"):
            conn = named[0]["connection"]
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


def _parse_physical(table_attr: str) -> tuple[str, str]:
    """Parse '[schema].[table]' → (schema, table). Falls back to ('', name) for bare names."""
    parts = [p.strip("[]") for p in table_attr.split("].") if p]
    if len(parts) == 2:
        return parts[0], parts[1]
    return "", parts[0] if parts else table_attr


def _build_column(col: dict[str, Any], col_id: str,
                  calc_by_host: dict[str, Any],
                  source_column: str | None = None) -> Column:
    calc = calc_by_host.get(col["name"])
    if calc is not None:
        return Column(
            id=col_id, name=col["name"],
            datatype=col["datatype"], role=_column_role(col["role"]),
            kind=ColumnKind.CALCULATED,
            tableau_expr=calc["tableau_expr"],
            dax_expr=None,
        )
    return Column(
        id=col_id, name=col["name"],
        datatype=col["datatype"], role=_column_role(col["role"]),
        kind=ColumnKind.RAW,
        source_column=source_column if source_column is not None else col["name"],
    )


def build_tables(
    raw_datasources: list[dict[str, Any]],
) -> tuple[tuple[Table, ...], tuple[Column, ...]]:
    """Emit IR Tables with their columns.

    For plain datasources: one Table per datasource.
    For federated joins (raw["relations"] non-empty): one Table per relation,
    with columns assigned to tables via col_map.  Columns not in col_map go to
    the first (primary) relation table."""
    tables: list[Table] = []
    columns: list[Column] = []

    for raw in raw_datasources:
        ds_id = stable_id("ds", raw["name"])
        calc_by_host = {c["host_column_name"]: c for c in raw.get("calculations", [])}
        relations = raw.get("relations") or []
        col_map: dict[str, tuple[str, str]] = raw.get("col_map") or {}

        if relations:
            # Federated join: emit one Table per physical relation.
            # Build column lists keyed by relation name, then assign remainder to primary.
            primary_rel_name = relations[0]["name"]
            cols_by_table: dict[str, list[str]] = {r["name"]: [] for r in relations}
            for col in raw.get("columns", []):
                # Use a shared prefix derived from ds name so col IDs stay stable.
                col_prefix = stable_id("tbl", raw["name"])
                col_id = f"{col_prefix}__{stable_id('col', col['name'])}"
                owner_entry = col_map.get(col["name"], (primary_rel_name, col["name"]))
                owner_table = owner_entry[0]
                phys_col    = owner_entry[1]
                if owner_table not in cols_by_table:
                    owner_table = primary_rel_name
                cols_by_table[owner_table].append(col_id)
                columns.append(_build_column(col, col_id, calc_by_host, source_column=phys_col))

            for rel in relations:
                schema, phys_table = _parse_physical(rel["table"])
                table_id = stable_id("tbl", rel["name"])
                tables.append(Table(
                    id=table_id,
                    name=rel["name"],
                    datasource_id=ds_id,
                    column_ids=tuple(cols_by_table[rel["name"]]),
                    physical_schema=schema or None,
                    physical_table=phys_table or None,
                ))
        else:
            # Plain datasource: one Table.
            table_id = stable_id("tbl", raw["name"])
            col_ids: list[str] = []
            for col in raw.get("columns", []):
                col_id = f"{table_id}__{stable_id('col', col['name'])}"
                col_ids.append(col_id)
                columns.append(_build_column(col, col_id, calc_by_host, source_column=col["name"]))
            tables.append(Table(
                id=table_id,
                name=raw["name"],
                datasource_id=ds_id,
                column_ids=tuple(col_ids),
            ))

    return tuple(tables), tuple(columns)


def build_relationships(
    raw_rels: list[dict[str, Any]],
    raw_datasources: list[dict[str, Any]],
    tables: tuple[Table, ...],
) -> tuple[tuple[Relationship, ...], tuple[UnsupportedItem, ...]]:
    """Build Relationship IR from raw Stage-1 join predicates.

    Applies the four-case algorithm driven by Tableau's official unique-key
    XSD attribute. See research_relationship_cardinality.md for full rationale.

    Returns (relationships, unsupported_warnings).
    """
    if not raw_rels:
        return (), ()

    merged_col_map: dict[str, tuple[str, str]] = {}
    for raw_ds in raw_datasources:
        merged_col_map.update(raw_ds.get("col_map") or {})

    table_by_name: dict[str, Table] = {t.name: t for t in tables}

    out: list[Relationship] = []
    warnings: list[UnsupportedItem] = []

    for raw in raw_rels:
        left_col  = raw.get("left_col", "")
        right_col = raw.get("right_col", "")

        left_resolved  = merged_col_map.get(left_col)
        right_resolved = merged_col_map.get(right_col)
        if not left_resolved or not right_resolved:
            continue

        left_table_name,  left_phys_col  = left_resolved
        right_table_name, right_phys_col = right_resolved

        left_table  = table_by_name.get(left_table_name)
        right_table = table_by_name.get(right_table_name)
        if not left_table or not right_table:
            continue

        first_unique  = raw.get("first_unique_key",  False)
        second_unique = raw.get("second_unique_key", False)

        if first_unique and second_unique:
            # Case 4 — 1:1: both sides unique; PBI mandates bothDirections for 1:1.
            cardinality  = "one_to_one"
            cross_filter = "both"
            from_table, from_col = left_table,  left_phys_col
            to_table,   to_col   = right_table, right_phys_col
            warnings.append(UnsupportedItem(
                object_kind="relationship",
                object_id=stable_id("rel", f"{left_table_name}__{right_table_name}"),
                source_excerpt=f"{left_table_name}.{left_phys_col} = {right_table_name}.{right_phys_col}",
                reason=(
                    f"One-to-one relationship detected between {left_table_name!r} and "
                    f"{right_table_name!r}. Microsoft recommends merging these tables in "
                    "Power Query instead."
                ),
                code="relationship_cardinality_one_to_one",
            ))
        elif first_unique:
            # Case 3 — first endpoint is ONE side.
            # Swap so PBI TMDL invariant holds: fromColumn = MANY side.
            cardinality  = "many_to_one"
            cross_filter = "single"
            from_table, from_col = right_table, right_phys_col   # MANY side
            to_table,   to_col   = left_table,  left_phys_col    # ONE side
        elif second_unique:
            # Case 2 — second endpoint is ONE side; current order is already correct.
            cardinality  = "many_to_one"
            cross_filter = "single"
            from_table, from_col = left_table,  left_phys_col    # MANY side
            to_table,   to_col   = right_table, right_phys_col   # ONE side
        else:
            # Case 1 — No unique-key: Tableau M:M default → bothDirections.
            cardinality  = "many_to_many"
            cross_filter = "both"
            from_table, from_col = left_table,  left_phys_col
            to_table,   to_col   = right_table, right_phys_col
            warnings.append(UnsupportedItem(
                object_kind="relationship",
                object_id=stable_id("rel", f"{left_table_name}__{right_table_name}"),
                source_excerpt=f"{left_table_name}.{left_phys_col} = {right_table_name}.{right_phys_col}",
                reason=(
                    f"Relationship {left_table_name!r}.{left_phys_col} ↔ "
                    f"{right_table_name!r}.{right_phys_col}: no unique-key set in Tableau "
                    "source — defaulted to M:M bidirectional cross-filter. Verify "
                    "intended cardinality in PBI Desktop Model View."
                ),
                code="relationship_cardinality_mm_default",
            ))

        rel_id = stable_id("rel", f"{from_table.name}__{to_table.name}")
        out.append(Relationship(
            id=rel_id,
            from_ref=FieldRef(table_id=from_table.id, column_id=from_col),
            to_ref=FieldRef(table_id=to_table.id,   column_id=to_col),
            cardinality=cardinality,
            cross_filter=cross_filter,
            source=RelationshipSource.TABLEAU_JOIN,
        ))

    return tuple(out), tuple(warnings)


_DERIVATION_TO_DAX: dict[str, str] = {
    "Year":    "YEAR",
    "Quarter": "QUARTER",
    "Month":   "MONTH",
    "Week":    "WEEKNUM",
    "Day":     "DAY",
    "Hour":    "HOUR",
    "Minute":  "MINUTE",
    "Second":  "SECOND",
}


def build_date_part_columns(
    raw_worksheets: list[dict[str, Any]],
    raw_datasources: list[dict[str, Any]],
    tables: tuple[Table, ...],
    columns: tuple[Column, ...],
) -> tuple[tuple[Column, ...], tuple[Table, ...]]:
    """Synthesize DAX calculated columns for Tableau date-part pills.

    For each unique (base_column, derivation) pair referenced in worksheet
    column_instances, creates a Column(kind=CALCULATED) with the appropriate
    DAX YEAR/MONTH/… expression and appends its ID to the owning Table.

    Returns (new_columns, updated_tables). The caller merges new_columns into
    DataModel.columns and replaces the tables tuple with updated_tables.
    """
    col_by_id: dict[str, Column] = {c.id: c for c in columns}
    table_by_name: dict[str, Table] = {t.name: t for t in tables}

    # Merge col_map entries from all raw datasources.
    # col_map: logical_col_name → [physical_table_name, physical_col_name]
    merged_col_map: dict[str, tuple[str, str]] = {}
    for raw_ds in raw_datasources:
        for k, v in (raw_ds.get("col_map") or {}).items():
            merged_col_map[k] = (v[0], v[1])

    seen: set[tuple[str, str]] = set()
    new_columns: list[Column] = []
    extra_col_ids: dict[str, list[str]] = {t.name: [] for t in tables}

    for raw_ws in raw_worksheets:
        for ci in raw_ws.get("column_instances", []):
            base_col_name: str = ci["base_column"]   # "order_date"
            derivation: str = ci["derivation"]        # "Year"
            key = (base_col_name, derivation)
            if key in seen:
                continue

            dax_fn = _DERIVATION_TO_DAX.get(derivation)
            if dax_fn is None:
                continue

            # Locate owning physical table.
            # For federated joins col_map has the answer directly.
            # For plain single-table datasources col_map is empty — scan tables.
            phys: tuple[str, str] | None = merged_col_map.get(base_col_name)
            if phys is None:
                for t in tables:
                    for cid in t.column_ids:
                        c = col_by_id.get(cid)
                        if c and c.name == base_col_name:
                            phys = (t.name, c.source_column or c.name)
                            break
                    if phys:
                        break
            if phys is None:
                continue
            phys_table_name, phys_col_name = phys

            table = table_by_name.get(phys_table_name)
            if table is None:
                continue

            # Guard: only synthesize for date/datetime columns.
            base_col_ir = next(
                (col_by_id[cid] for cid in table.column_ids
                 if cid in col_by_id and col_by_id[cid].name == base_col_name),
                None,
            )
            if base_col_ir is None or base_col_ir.datatype not in ("date", "datetime"):
                continue

            seen.add(key)

            # Derive the column ID prefix from existing column IDs in this table
            # (consistent with how build_tables() constructs them).
            existing_ids = [cid for cid in table.column_ids if "__col__" in cid]
            col_prefix = (
                existing_ids[0].rsplit("__col__", 1)[0]
                if existing_ids else stable_id("tbl", table.name)
            )

            derived_name = f"{derivation} {base_col_name}"          # "Year order_date"
            dax_expr = f"{dax_fn}({phys_table_name}[{phys_col_name}])"  # "YEAR(orders[order_date])"
            derived_col_id = f"{col_prefix}__{stable_id('col', derived_name)}"

            new_columns.append(Column(
                id=derived_col_id,
                name=derived_name,
                datatype="integer",
                role=ColumnRole.DIMENSION,
                kind=ColumnKind.CALCULATED,
                dax_expr=dax_expr,
            ))
            extra_col_ids[phys_table_name].append(derived_col_id)

    # Return immutable updated tables (pydantic model_copy preserves immutability).
    updated_tables = tuple(
        t.model_copy(update={"column_ids": t.column_ids + tuple(extra_col_ids[t.name])})
        for t in tables
    )
    return tuple(new_columns), updated_tables


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
            name=raw_calc.get("caption") or raw_calc["host_column_name"],
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
