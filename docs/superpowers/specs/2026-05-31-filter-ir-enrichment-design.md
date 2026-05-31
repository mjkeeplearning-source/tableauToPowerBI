# Filter IR Enrichment & Schema-Compliant Emission

**Date:** 2026-05-31  
**Status:** Approved  
**Scope:** IR layer, extract layer, emit layer, schema bundle, validator resolver

---

## Problem

The current `emit/pbir/filters.py` produces invalid PBIR JSON in three ways:

1. **Type capitalization** — emits `"type": "categorical"` (lowercase); schema requires `"Categorical"`.
2. **Filter body** — emits `{"include": [...], "exclude": [...]}`, which is not a valid `FilterDefinition`. The schema requires `{"Version": 2, "From": [...], "Where": [...]}` with proper semantic query expressions.
3. **SourceRef key** — emits `{"Source": table_id}` at the top-level `FilterContainer.field`; schema requires `{"Entity": table_name}` (the `StandaloneSourceRefExpression` form).

Additionally, five schemas referenced by already-bundled schemas are missing from `validate/_schemas/`, so the validator cannot resolve `$ref` chains into `filterConfig` bodies.

---

## Goals

1. Enrich the IR `Filter` model with all data needed to emit schema-valid PBI `FilterDefinition` bodies.
2. Fix all three emit bugs, grounded in the official Microsoft semantic query schema.
3. Bundle the five missing schemas so the JSON schema validator can fully validate `filterConfig` content.
4. Wire up `RefResolver` in `json_schema.py` so nested `$ref` paths resolve to bundled files.
5. Design the IR and emit layer for extensibility — adding a new filter kind later requires only a new subclass and one new emit branch.

---

## Non-goals

- TopN filter emission (deferred — PBI `TopN` filter requires a `Subquery` structure not confirmed from schema alone).
- Conditional filter emission (deferred — requires DAX eval context not available in IR).
- Relative date / relative time / passthrough / tuple filter kinds (future, not present in Tableau XML at v1).
- Any change to TMDL emission.

---

## Official Schema Facts

### SourceRef — two distinct subtypes

| Context | Form | Required key |
|---|---|---|
| `FilterContainer.field` (top-level) | `StandaloneSourceRefExpression` | `Entity: "TableName"` |
| Inside `From`/`Where` query body | `QuerySourceRefExpression` | `Source: "alias"` (alias from `From`) |

### FilterDefinition structure

```json
{
  "Version": 2,
  "From": [{"Name": "f", "Entity": "TableName", "Type": 0}],
  "Where": [{"Condition": { ...expression... }}]
}
```

`Version` is not in `required` but is always emitted for compatibility. `From.Name` is the alias referenced inside `Where` as `SourceRef.Source`.

### Literal value formats (from `QueryLiteralExpression.Value` schema description)

| Type | Format |
|---|---|
| String | `"'some value'"` (single quotes inside JSON string) |
| Integer | `"24L"` |
| Double | `"2.4D"` |
| Decimal | `"2.4M"` |
| DateTime | `"datetime'2023-01-03T12:00:00'"` |
| Boolean | `"true"` / `"false"` |
| Null | `"null"` |

Tableau date-only literals (`#2023-01-03#`) map to `datetime'2023-01-03T00:00:00'`. The `date'...'` short form is absent from the official schema description so we do not use it.

### Aggregation function codes (`QueryAggregateFunction`)

`0=Sum, 1=Average, 2=DistinctCount, 3=Min, 4=Max, 5=Count, 6=Median, 7=StdDev, 8=Variance`

### ComparisonKind codes

`0=Equal, 1=GreaterThan, 2=GreaterThanOrEqual, 3=LessThan, 4=LessThanOrEqual`

---

## Schema Bundling

Five schemas are fetched from the Microsoft CDN and written to `src/tableau2pbir/validate/_schemas/`. Each file is named with the path-encoded URL segments:

| Filename | URL path segment |
|---|---|
| `semanticQuery-1.0.0.json` | `semanticQuery/1.0.0/schema.json` |
| `semanticQuery-1.2.0.json` | `semanticQuery/1.2.0/schema.json` |
| `semanticQuery-1.4.0.json` | `semanticQuery/1.4.0/schema.json` |
| `filterConfiguration-1.1.0.json` | `filterConfiguration/1.1.0/schema-embedded.json` |
| `filterConfiguration-1.3.0.json` | `filterConfiguration/1.3.0/schema-embedded.json` |

`manifest.json` gains 5 new entries mapping each URL to its local file.

`refresh_schemas.py` (the CDN updater) adds these 5 URLs to its fetch list so the user cache also stays current.

### RefResolver wiring

`validate/json_schema.py` currently passes instance data directly to `Draft7Validator(schema).validate(instance)`. With nested `$ref` links, the validator must resolve sibling schemas. The fix: build a `jsonschema.RefResolver` whose `store` is pre-populated with all bundled schema `$id` → parsed schema dict mappings, then pass it to `Draft7Validator(schema, resolver=resolver)`.

---

## IR Design — Discriminated Union

**File:** `src/tableau2pbir/ir/sheet.py`

Replace the single `Filter` class with a `FilterBase` and five concrete subtypes. Pydantic v2 discriminated union handles JSON round-trips automatically.

```python
class FilterBase(IRBase):
    id: str
    field: FieldRef

class CategoricalFilter(FilterBase):
    kind: Literal["categorical"] = "categorical"
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()

class RangeFilter(FilterBase):
    kind: Literal["range"] = "range"
    min_val: str | None = None      # raw string; _format_literal handles type detection
    max_val: str | None = None
    agg_prefix: str | None = None   # "SUM"|"AVG"|... → emits Advanced type

class TopNFilter(FilterBase):
    kind: Literal["top_n"] = "top_n"
    n: int = 10
    direction: str = "Top"          # "Top" | "Bottom"
    by_field: FieldRef | None = None
    by_agg: str | None = None       # e.g. "SUM"

class ContextFilter(FilterBase):
    kind: Literal["context"] = "context"
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()

class ConditionalFilter(FilterBase):
    kind: Literal["conditional"] = "conditional"
    expr: str | None = None

Filter = Annotated[
    CategoricalFilter | RangeFilter | TopNFilter | ContextFilter | ConditionalFilter,
    Field(discriminator="kind")
]
```

`Sheet.filters` type declaration is unchanged (`tuple[Filter, ...]`); the union is transparent to callers.

### Extensibility rule

Adding a new filter kind in future:
1. Add a new `XxxFilter(FilterBase)` subclass with `kind: Literal["xxx"]`.
2. Add it to the `Filter` union.
3. Add one `isinstance(f, XxxFilter)` branch in `emit/pbir/filters.py`.
4. Add one extraction branch in `extract/worksheets.py` `_filters()`.
Nothing else changes — Pydantic handles serialization, `_build_sheets.py` uses the factory function.

---

## Extract Layer Changes

**File:** `src/tableau2pbir/extract/worksheets.py`

`_filters()` currently captures `kind`, `column`, `include`/`exclude`, and `expr`. It needs to also capture range bounds and top-N parameters from child XML elements.

```python
def _filters(view):
    for f in view.findall("filter"):
        kind = attr(f, "class", default="categorical")
        column = _unbracket(attr(f, "column"))

        if kind == "range":
            yield {
                "kind": "range",
                "column": column,
                "min_val": f.findtext("min"),
                "max_val": f.findtext("max"),
                # agg_prefix extracted from column name prefix (e.g. "sum__sales" → "SUM")
                "agg_prefix": _extract_agg_prefix(column),
            }
        elif kind == "top":
            spec = f.find("top-spec-field")
            yield {
                "kind": "top_n",
                "column": column,
                "n": int(f.findtext("top-spec-count") or 10),
                "direction": f.findtext("top-spec-direction") or "Top",
                "by_column": _unbracket(attr(spec, "column", default="")) if spec is not None else None,
                "by_agg": attr(spec, "aggregation", default=None) if spec is not None else None,
            }
        else:
            include, exclude = _filter_members(f)
            yield {
                "kind": kind,   # "categorical" | "context" | "conditional"
                "column": column,
                "include": include,
                "exclude": exclude,
                "expr": optional_attr(f, "formula"),
            }
```

`_extract_agg_prefix(column)` checks if the column name starts with a known aggregation prefix pattern (same slug logic already used in encoding channels).

### Tableau `class="top"` vs IR `kind="top_n"`

Tableau XML uses `class="top"` for top-N filters. The extract layer normalises this to `kind="top_n"` so the IR is self-describing.

---

## Canonicalize Layer Changes

**File:** `src/tableau2pbir/stages/_build_sheets.py`

`_build_filter()` currently always constructs `Filter(...)`. Replace with a factory that dispatches on `raw_f["kind"]`:

```python
def _build_filter(raw_f, sheet_idx, filter_idx, table_id):
    fid = f"filter__s{sheet_idx}_{filter_idx}"
    field = _ref(raw_f["column"], table_id)
    kind = raw_f["kind"]

    if kind == "range":
        return RangeFilter(id=fid, field=field,
                           min_val=raw_f.get("min_val"),
                           max_val=raw_f.get("max_val"),
                           agg_prefix=raw_f.get("agg_prefix"))
    if kind == "top_n":
        by_col = raw_f.get("by_column")
        return TopNFilter(id=fid, field=field,
                          n=raw_f.get("n", 10),
                          direction=raw_f.get("direction", "Top"),
                          by_field=_ref(by_col, table_id) if by_col else None,
                          by_agg=raw_f.get("by_agg"))
    if kind == "conditional":
        return ConditionalFilter(id=fid, field=field, expr=raw_f.get("expr"))
    # categorical, context (and any unknown kind — treat as categorical)
    cls = CategoricalFilter if kind == "categorical" else \
          ContextFilter if kind == "context" else CategoricalFilter
    return cls(id=fid, field=field,
               include=tuple(raw_f.get("include", ())),
               exclude=tuple(raw_f.get("exclude", ())))
```

---

## Emit Layer Rewrite

**File:** `src/tableau2pbir/emit/pbir/filters.py`

Full rewrite. Key helpers:

### `_format_literal(value: str) -> str`

Converts a raw Tableau filter value string to an official PBI Literal.Value string:

```
Tableau "#2023-01-03#"        → "datetime'2023-01-03T00:00:00'"
Tableau "#2023-01-03 12:00#"  → "datetime'2023-01-03T12:00:00'"
Integer string "42"           → "42L"
Float string "3.14"           → "3.14D"
String "East"                 → "'East'"
```

### `_entity_field(table_name, col_name, field_type) -> dict`

Builds the top-level `FilterContainer.field` using `StandaloneSourceRefExpression`:
```json
{"Column": {"Expression": {"SourceRef": {"Entity": "Sales"}}, "Property": "Region"}}
```

### `_alias_col_expr(alias, col_name) -> dict`

Builds a column expression inside `From`/`Where` using query alias `QuerySourceRefExpression`:
```json
{"Column": {"Expression": {"SourceRef": {"Source": "f"}}, "Property": "Region"}}
```

### Per-kind emit

**CategoricalFilter / ContextFilter → `"Categorical"`**

```json
{
  "name": "<id>",
  "field": {"Column": {"Expression": {"SourceRef": {"Entity": "Sales"}}, "Property": "Region"}},
  "type": "Categorical",
  "filter": {
    "Version": 2,
    "From": [{"Name": "f", "Entity": "Sales", "Type": 0}],
    "Where": [{
      "Condition": {
        "In": {
          "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "f"}}, "Property": "Region"}}],
          "Values": [[{"Literal": {"Value": "'East'"}}], [{"Literal": {"Value": "'West'"}}]]
        }
      }
    }]
  },
  "howCreated": "User",
  "isHiddenInViewMode": false
}
```

- Include-only: `In(...)` expression.
- Exclude-only: `Not({"Expression": {"In": ...}})`.
- Both include and exclude: `And({"Left": In(...), "Right": Not(In(...))})`.
- Empty include and empty exclude: filter is skipped (no-op).

**RangeFilter, no `agg_prefix` → `"Range"`**

- Both bounds: `Between(Expression=col, LowerBound=lit, UpperBound=lit)`.
- Min only: `Comparison(ComparisonKind=2, Left=col, Right=lit)`.
- Max only: `Comparison(ComparisonKind=4, Left=col, Right=lit)`.
- Neither bound: filter is skipped.

**RangeFilter with `agg_prefix` → `"Advanced"`**

Top-level `field` is an `Aggregation` wrapping a `StandaloneSourceRef` column.  
`Where.Condition` is a `Comparison` where `Left` is an `Aggregation` wrapping an alias-ref column.

**TopNFilter → skipped**

`_filter_to_pbir` returns `None`; `collect_page_filters` silently drops `None` entries. The `UnsupportedItem` with code `deferred_feature_topn_filter` is recorded in `_build_sheets.py` during the factory dispatch (same pattern as quick-table-calc items), not in the emit layer.

**ConditionalFilter → skipped**

Same — `_filter_to_pbir` returns `None`. `UnsupportedItem` with code `deferred_feature_conditional_filter` recorded in `_build_sheets.py`.

---

## Aggregation prefix mapping

Tableau agg prefixes → PBI `QueryAggregateFunction` integers:

| Tableau prefix | PBI function code |
|---|---|
| `SUM` / `sum` | 0 |
| `AVG` / `avg` / `average` | 1 |
| `CNTD` / `ctd` | 2 |
| `MIN` / `min` | 3 |
| `MAX` / `max` | 4 |
| `CNT` / `cnt` | 5 |
| `MEDIAN` / `median` | 6 |

Unknown prefixes: filter is skipped with a logged warning.

---

## Filter type / PBI schema mapping (complete)

| Tableau `class` | IR type | PBI `type` | Implemented |
|---|---|---|---|
| `categorical` | `CategoricalFilter` | `Categorical` | ✅ this plan |
| `range` (row-level) | `RangeFilter` | `Range` | ✅ this plan |
| `range` (with agg) | `RangeFilter` | `Advanced` | ✅ this plan |
| `top` | `TopNFilter` | `TopN` | ⏸ deferred |
| `context` | `ContextFilter` | `Categorical` | ✅ this plan |
| `condition` | `ConditionalFilter` | `Advanced` | ⏸ deferred |
| future | `RelativeDateFilter` | `RelativeDate` | future |
| future | `PassthroughFilter` | `Passthrough` | future |
| PBI-only | — | `VisualTopN` | future |
| PBI-only | — | `Include`/`Exclude`/`Tuple`/`RelativeTime` | future |

---

## Testing

### Unit tests

**`tests/unit/test_filter_literal.py`** — `_format_literal`:
- Tableau date `#2023-01-03#` → `datetime'2023-01-03T00:00:00'`
- Tableau datetime `#2023-01-03 12:30:00#` → `datetime'2023-01-03T12:30:00'`
- Integer `"42"` → `"42L"`
- Float `"3.14"` → `"3.14D"`
- String `"East"` → `"'East'"`
- Null/empty → `"null"`

**`tests/unit/test_filters_emit.py`** — `_filter_to_pbir` per kind:
- CategoricalFilter include-only: verify `In` expression, `type="Categorical"`, `Entity` in field
- CategoricalFilter exclude-only: verify `Not(In(...))` wrapper
- CategoricalFilter both: verify `And(In, Not(In))`
- CategoricalFilter empty: returns `None`
- RangeFilter both bounds: verify `Between` expression, `type="Range"`
- RangeFilter min-only: verify `Comparison(GTE=2)`
- RangeFilter max-only: verify `Comparison(LTE=4)`
- RangeFilter post-agg: verify `Aggregation` in field and Where, `type="Advanced"`
- ContextFilter: same structure as CategoricalFilter
- TopNFilter: returns `None`
- ConditionalFilter: returns `None`

**`tests/unit/test_build_sheets_filters.py`** — factory dispatch:
- `kind="categorical"` → `CategoricalFilter`
- `kind="range"` → `RangeFilter` with min_val/max_val populated
- `kind="top"` → `TopNFilter` with n/direction/by_field populated
- `kind="context"` → `ContextFilter`
- `kind="conditional"` → `ConditionalFilter`

**`tests/unit/test_schema_cache.py`** — new entries (5 schemas now resolvable via bundled fallback)

**`tests/unit/test_json_schema.py`** — RefResolver correctly resolves `$ref` into filter body:
- A valid CategoricalFilter `filterConfig` passes validation
- A filter with `type="categorical"` (lowercase) fails validation

### Integration gate

Run full E2E after every task: `pytest tests/integration/test_real_workbooks_e2e.py`
