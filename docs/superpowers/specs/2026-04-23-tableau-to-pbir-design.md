# Tableau → Power BI (PBIR) Converter — Design

- **Date:** 2026-04-23
- **Status:** Approved (post-review patch) for implementation planning
- **Working directory:** `C:\Tableau_PBI`
- **Review:** `C:\Tableau_PBI\review.md` (findings 1–5 + suggestions 1–4, all applied — see Appendix A for change log)

## 1. Scope

**Goal.** Automate conversion of local Tableau workbooks (`.twb` / `.twbx`) into full Power BI projects in **PBIR format** (`.pbip` containing both report PBIR `definition/` and TMDL semantic model). Output is opened and validated locally in **Power BI Desktop** per a specific automated gate (§9 layer vii; §15 acceptance rubric).

**In scope.**
- Read `.twb` / `.twbx` files from the local filesystem.
- Produce a complete PBIR project: report + semantic model + datasource definitions, suitable for opening in PBI Desktop.
- Multi-stage pipeline; each stage emits a markdown summary AND a JSON handoff for the next stage.
- Anthropic Claude permitted ONLY where Python is non-deterministic AND AI can produce a near-deterministic mapping.
- Per-stage tests at every layer defined in §9.
- Batch operation across many workbooks; Python library underneath, CLI on top.

**Out of scope.**
- Publishing PBIR to the Power BI service (no `pbi-tools deploy`, no REST publish, no workspace management).
- Live data refresh, gateway config, RLS rollout.
- Visual regression testing (deferred — see §11).
- Tableau Server / Online published datasources (`.tdsx` references to a server) — file-only conversion scope.

**Reference docs.**
- Tableau: <https://github.com/tableau/document-api-python> and <https://github.com/tableau/tableau-document-schemas>
- PBI PBIR: <https://learn.microsoft.com/en-us/power-bi/developer/embedded/projects-enhanced-report-format> and <https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-report?tabs=v2%2Cdesktop#pbir-format>
- TabularEditor 2: <https://tabulareditor.com/> (TMDL validation)
- pbi-tools: <https://pbi.tools/> (PBIR→.pbix compile)
- tableauhyperapi: <https://tableau.github.io/hyper-db/docs/> (not a runtime dep; only relevant if Appendix A§change 8 reopened)

## 2. Coverage (three-column truth table)

Replaces the earlier two-list format. Every Tableau concept in the **Practical** tier lands in exactly one column.

| Category | **Supported (full fidelity)** | **Partial / degraded** | **Unsupported (placeholder + warning)** |
|---|---|---|---|
| **Marks** | bar, line, area, scatter, text-table, pie, filled map | stacked area with mixed measures (AI may pick; §14), symbol map | custom shapes (see §14), polygon, density, Gantt |
| **Calculated fields** | row calcs, simple aggregates (SUM/AVG/COUNT/MIN/MAX), IF/THEN/ELSEIF, IIF, ZN, IFNULL, DATEPART, DATEDIFF | LOD FIXED (per-calc DAX), LOD INCLUDE/EXCLUDE (per-sheet measure expansion; see §5.6), simple table calcs (running total, % of total, rank), table calcs with lookup+restart_every patterns (AI fallback; §5.6) | R/Python script calcs, geographic spatial calcs |
| **Parameters** | numeric_what_if, categorical_selector (see §5.7) | formatting_control (switch-pattern) | parameters driving Tableau-only UI behavior (classified as `unsupported` intent) |
| **Filters** | categorical (include/exclude), range, top-N by measure | context filters (mapped to PBI filter precedence; may not be identical) | conditional filters referencing table calcs outside the filter's own sheet |
| **Encodings** | color, size, label, tooltip (basic), detail, shape, angle | dual-axis with mismatched mark types, custom shape palettes, viz-in-tooltip (mapped to PBI report-page tooltips; see §14) | — |
| **Dashboards** | tiled + floating layout, text, image, filter card, parameter card, legend suppression, navigation button | relative/range-sized sheets (resolved to midpoint), Device Designer mobile layout (best-effort to PBIR mobile page) | web-page object, blank object beyond pass-through |
| **Sets/Groups/Hierarchies** | static sets, groups (discrete bins), hierarchies | computed sets (when dependency graph resolves) | combined sets, set actions |
| **Dual axis** | matched-type dual axis (both line, both bar) | mismatched marks (e.g., line + bar) — emitted as overlay visual; AI chooses | chart types with no PBIR dual-axis support |
| **Reference lines / bands** | constant, average, median reference lines | computed reference lines using LOD | trend lines, forecast bands (see §14) |
| **Actions** | filter action, highlight action (mapped to PBI visual interactions) | URL action (emitted as button; Tableau parameter embedding best-effort) | set actions, parameter-change actions with calc-dependency cascades |
| **Story points** | — | — | unsupported (see §14 — suggested alternative: bookmarks, but not auto-emitted) |
| **Annotations** | — | — | unsupported (see §14) |
| **Data sources** | Tier 1 connectors (§5.8) | Tier 2 (credentials) + Tier 3 (degraded) | Tier 4 (forces workbook `failed`) |

"Unsupported" objects are recorded across three layers (stage 1 detects, stage 2 populates IR's `unsupported[]`, runner aggregates to workbook-level `unsupported.json`).

## 3. AI usage rules

**Where AI is allowed at run-time:**
- **Calc translation** — Tableau calc syntax → DAX, as a fallback when the Python rule library (enriched by IR calc semantics, §5.6) doesn't match. Returns `{dax_expr, confidence ∈ {high, medium, low}, notes}`.
- **Visual mapping** — Tableau `(mark, shelves)` → PBIR visual + encoding bindings, as a fallback when the dispatch table doesn't match or is ambiguous.
- **Naming cleanup** — Tableau auto-names (e.g., `SUM(Sales)`) → human-readable PBIR object names.

**Where AI is *not* used at run-time:**
- Layout reflow — fully deterministic Python (container-tree walker + arithmetic).
- Parameter classification — deterministic detection rules in stage 2 (§5.7).
- Connector mapping — deterministic matrix lookup (§5.8).
- Any structural decision: which stage runs, retries, file emission.

**Net effect of IR enrichment on AI surface:** Because the IR now carries explicit calc semantics (kind, partitioning, addressing, frame, LOD dimensions) and parameter intent, most translations that would previously have required AI can now be handled by Python rule patterns. AI fallback is restricted to calcs that **combine semantics in unusual ways** (nested LODs, mixed table-calc+LOD expressions, rare lookup frames with `restart_every`). This strengthens the "AI rare and audited" posture.

**Build-time AI use** (developer ergonomics, never at conversion time):
- Generating and reviewing entries in the calc rule library.
- Suggesting test fixtures and reviewing diffs of generated outputs.

**Anti-pattern explicitly avoided:** agentic orchestration. The pipeline is a deterministic dataflow that *uses* AI as a typed function; an agent does not *run* the pipeline.

## 4. Architecture

### 4.1 Surface

- Library underneath, thin CLI on top. CLI is `tableau2pbir` with subcommands `convert`, `resume`, and one per stage.
- Built-in batch: `tableau2pbir convert ./inbox/*.twbx --out ./out/`. Worker pool of size `cpu_count()`. One workbook per worker (process-isolated).
- Direct Anthropic SDK usage (no provider abstraction layer). Default model `claude-sonnet-4-6`. Per-call-site model overridable in `config.yaml`.

### 4.2 Per-workbook pipeline (8 stages)

```
1. extract              (pure python)
2. canonicalize → IR    (pure python) — owns semantic normalization (calc kinds, parameter intents, connector classification)
3. translate calcs      (python rules + AI fallback)
4. map visuals          (python rules + AI fallback) — consumes normalized IR, does not re-infer semantics
5. compute layout       (pure python)
6. build TMDL           (pure python)
7. build report PBIR    (pure python)
8. package + validate   (pure python) — includes TE2 + pbi-tools + Desktop-open gate (real-workbook subset)
```

**Stage ownership rule** (from review suggestion 2): semantic normalization is concentrated in stage 2. Stages 3 and 4 consume a normalized IR and do not perform semantic inference; stage 3 emits DAX, stage 4 emits visual bindings. This prevents the same semantic question being answered differently in two places.

### 4.3 Per-stage contract

Every stage is a pure function:

```python
def run(input_json: dict, ctx: StageContext) -> StageResult: ...

class StageResult:
    output: dict           # the next stage's input
    summary_md: str        # human-readable per-stage summary
    errors: list[StageError]
```

The pipeline runner persists `output` to `<n>_<stage>.json` and `summary_md` to `<n>_<stage>.summary.md` after each stage. In the normal path stages chain in-memory; persistence is for inspectability and for `--gate`/`--from`.

### 4.4 Output structure

```
./out/<wb>/
  <wb>.pbip                        # final artifact (open in PBI Desktop)
  SemanticModel/                   # TMDL files
  Report/definition/               # PBIR JSON files
  stages/
    01_extract.json
    01_extract.summary.md
    02_ir.json
    02_ir.summary.md
    ...
    08_package.summary.md
  unsupported.json                 # cumulative across all stages
  workbook-report.md               # human-readable conversion report
  acceptance.json                  # §15 rubric scores (real-workbook subset only)
./out/run-manifest.md              # portfolio-level summary
                                   # columns: workbook | status | trigger_reasons | link
```

### 4.5 Failure mode (fail-open with `--gate`)

- Default: pipeline always finishes; unconvertible objects become labelled placeholders + entries in `unsupported.json`.
- Workbook `status` is computed per the rule in §8.1 (`ok` / `partial` / `failed`).
- `--gate <stage>` flag: pause after the named stage, write artifacts, exit. User may hand-edit the JSON.
- `tableau2pbir resume ./out/<wb> --from <next-stage>` reads from disk and continues.
- Per-workbook isolation in batch: a failure in one workbook never affects another.

## 5. Intermediate Representation (IR)

### 5.1 Top-level shape

```
Workbook { ir_schema_version, source_path, source_hash, tableau_version, config }
├─ data_model: DataModel
│   ├─ datasources[]: { id, name, connector_tier (1|2|3|4), tableau_kind,
│   │                   pbi_m_connector, connection_params{},
│   │                   user_action_required[],        # ["enter credentials", "install oracle client", ...]
│   │                   tables[], extract_ignored? }   # extract_ignored=true when we skip the .hyper
│   ├─ tables[]: { id, name, datasource_id, columns[], primary_key? }
│   │   └─ columns[]: { id, name, datatype, role (dim|measure),
│   │                   kind (raw|calculated), tableau_expr?, dax_expr? }
│   ├─ relationships[]: { from_table.column, to_table.column, cardinality, cross_filter,
│   │                     source ('tableau_join'|'tableau_blend'|'cross_db_flatten') }
│   ├─ calculations[]: Calculation    # see §5.6
│   ├─ parameters[]:   Parameter      # see §5.7
│   ├─ hierarchies[]: { id, name, levels[] }
│   └─ sets[]: { id, name, source_column, definition }
├─ sheets[]: Sheet { id, name, datasource_refs[], mark_type,
│                    encodings, filters[], sort, dual_axis?,
│                    reference_lines[], format,
│                    uses_calculations[] }             # back-refs for topo-sort
│   └─ encodings: { rows[], columns[], color?, size?, label?,
│                   tooltip?, detail[], shape?, angle? }
├─ dashboards[]: Dashboard { id, name, size{w,h,kind}, layout_tree, actions[] }
│   └─ layout_tree: Container | Leaf (recursive)
└─ unsupported[]: { object_kind, object_id, source_excerpt, reason }
```

### 5.2 Layout tree (recursive)

```
Container { kind: 'h'|'v'|'floating', children[], padding, background? }
Leaf      { kind, position?{x,y,w,h}, payload }

Leaf.kind ∈ {
  'sheet'          → payload.sheet_id
  'text'           → payload.text + format
  'image'          → payload.path
  'filter_card'    → payload.field_id
  'parameter_card' → payload.parameter_id
  'legend'         → payload.host_sheet_id
  'navigation'     → payload.target
  'blank' | 'web_page' (placeholder)
}

# position is None at extract time; populated by stage 5 (layout).
```

### 5.3 Action

```
Action {
  id, name,
  kind: 'filter'|'highlight'|'url'|'parameter',
  trigger: 'select'|'hover'|'menu',
  source_sheet_ids[], target_sheet_ids[],
  source_fields[]?, target_fields[]?,
  clearing_behavior
}
```

### 5.4 Versioning rules

- `ir_schema_version` is a semver string. Stage 2 stamps it; stages 3+ assert match (or migrate).
- Initial version: `1.0.0` (this spec).
- Adding optional fields → minor bump. Removing/renaming → major bump + migrator.
- Migrators live in `tableau2pbir.ir.migrations.v<from>_to_v<to>` as pure functions.
- The IR JSON Schema is **auto-generated from the dataclasses**, committed to repo, used by stage contract tests. One source of truth (Python types), one derived artifact (JSON Schema).

### 5.5 Out of IR (deliberate)

- PBIR-specific concepts (visual containers, themes, bookmarks) live only in stages 6+.
- Tier-C Tableau concepts (story points, R/Python, custom shapes, forecast, annotations, web-page objects) — recorded in `unsupported[]`, never modeled.

### 5.6 Calculation semantics (enriched — addresses review finding 1)

```
Calculation {
  # core
  id, name, scope: 'measure' | 'column',
  tableau_expr, dax_expr?, depends_on[],

  # semantic normalization (filled by stage 2)
  kind:  'row' | 'aggregate' | 'table_calc' | 'lod_fixed' | 'lod_include' | 'lod_exclude',
  phase: 'row' | 'aggregate' | 'viz',

  # for kind == 'table_calc'
  table_calc: {
    partitioning[]:   field_ref[]            # dims partitioning the calc
    addressing[]:     field_ref[]            # direction of flow
    sort[]:           { field_ref, dir: 'asc'|'desc' }[]
    frame:            { type: 'cumulative' | 'window' | 'lookup' | 'rank',
                        offset?: int, window_size?: int }
    restart_every?:   field_ref
  }?,

  # for kind == 'lod_fixed'
  lod_fixed: { dimensions: field_ref[] }?,

  # for kind == 'lod_include' | 'lod_exclude'
  lod_relative: {
    extra_dims?:     field_ref[]             # INCLUDE
    excluded_dims?:  field_ref[]             # EXCLUDE
  }?,

  # for anonymous quick-table-calc records (created by stage 2)
  owner_sheet_id?: str,                      # null for named calcs; set for quick-table-calc
}
```

**Why this enrichment.** Without it, stage 3 would have to infer partitioning, addressing, and LOD grain from incomplete context (the `tableau_expr` alone). With it, most translations become deterministic Python rule patterns and AI falls back only to unusual compositions.

**Quick table calcs** (pill-modifier shortcuts applied directly on a sheet, not a named calc field) are modeled as **anonymous `Calculation` records** with auto-generated ids and `owner_sheet_id` back-reference. This unifies the translation pipeline: one calc translator, one set of rules.

**LOD INCLUDE/EXCLUDE** are *relative* to the consuming sheet's viz LoD — the same calc evaluates differently on different sheets. Stage 3 emits **one DAX measure per `(calc, consuming_sheet)` pair**, named `<calc_name>__<sheet_safe_name>`. The consuming sheet's `pbir_visual` binding (stage 4) references the sheet-specific variant.

**Topo-sort gets a (calc × sheet) lane** for LOD INCLUDE/EXCLUDE expansions and for anonymous quick-table-calc records. Global lane unchanged for `row`, `aggregate`, `lod_fixed`, and named `table_calc` calcs. Stage 3 emits in `global → per-sheet` order.

### 5.7 Parameter intent (enriched — addresses review finding 4)

```
Parameter {
  id, name, datatype, default, allowed_values,

  intent: 'numeric_what_if' | 'categorical_selector'
        | 'internal_constant' | 'formatting_control' | 'unsupported',
  exposure: 'card' | 'shelf' | 'calc_only',        # raw extract metadata

  binding_target?: { measure_ids[], format_pattern?: str }   # formatting_control only
}
```

**Detection in stage 2 → emission in stages 6/7:**

| Intent | Detected when | Stage 6 (TMDL) emits | Stage 7 (PBIR) emits |
|---|---|---|---|
| `numeric_what_if` | `<allowable-values type='range' min/max/step>` + parameter card | disconnected table via `GENERATESERIES(min,max,step)` + `SelectedValue` measure | numeric slicer bound to the table |
| `categorical_selector` | discrete `<allowable-values>` + parameter card | disconnected table with `allowed_values` rows + `SelectedValue` measure | dropdown slicer bound to the table |
| `internal_constant` | no card AND no shelf use; referenced only in calc bodies | hidden measure with literal default value | no slicer |
| `formatting_control` | switch-pattern detected: parameter drives CASE controlling format/unit/aggregation choice | disconnected switch table + format-string DAX on consuming measures | slicer + measure-driven format strings |
| `unsupported` | classification heuristic fails; or drives Tableau-only behavior | — | no slicer; logged to `unsupported.json` |

**Stage 3 calc translator** reads `Parameter.intent` and translates `[ParamName]` references differently per intent:
- `numeric_what_if` / `categorical_selector` → `[ParamName SelectedValue]` measure reference.
- `internal_constant` → DAX literal expansion (the default value inlined).
- `formatting_control` → routed through the format-string switch machinery.

### 5.8 Connector matrix (new — addresses review finding 3)

Stage 2 classifies each `<datasource>` in the `.twb` into one of four tiers. The mapping is deterministic — no AI.

**Tier 1 — full fidelity** (M emitted with real values; status unaffected)

| Tableau source | PBI / M target |
|---|---|
| CSV (`text-direct`) | `Csv.Document(File.Contents)` |
| Excel (`excel-direct`) | `Excel.Workbook(File.Contents)` |
| SQL Server (`sqlserver`) | `Sql.Database(server, db)` |
| `.hyper` extract | emit M for the original `<connection>` (Tier-1 or Tier-2 mapping via that connection's class); **ignore the materialized hyper file**. If `<connection>` is missing/null → escalated to Tier 4. |

**Tier 2 — credential placeholders** (M emitted, server/db pulled from Tableau, credentials stripped; status unaffected)

| Tableau source | PBI / M target |
|---|---|
| Snowflake | `Snowflake.Databases(server, warehouse)` |
| Databricks | `DatabricksMultiCloud.Catalogs(host, http_path)` |
| BigQuery | `GoogleBigQuery.Database(billing_project)` |
| Postgres | `PostgreSQL.Database(server, db)` |
| Oracle | `Oracle.Database(server)` (user install step) |
| Redshift | `AmazonRedshift.Database(server, db)` |
| Teradata | `Teradata.Database(server)` (user install step) |
| MySQL | `MySql.Database(server, db)` |

**Tier 3 — degraded fidelity** (attempted with caveats, per-case decision logged to `workbook-report.md`; status → `partial`)

| Tableau source | Strategy |
|---|---|
| Cross-database joins | Attempt: flatten into single M query reading both sources. Fallback: emit two M tables + model relationship. |
| Data blends (viz-time joins) | Model as semantic-model relationship when grain matches linking field (one-to-many). Demote to "unsupported viz binding" when grain/cardinality looks risky. |
| Custom SQL (`<custom-sql>`) | Emit as `Value.NativeQuery` with SQL preserved verbatim; warn that PBI connector SQL dialect may differ. |
| Initial SQL (pre-query) | Preserved as a `Native` step prefix; warned. |

**Tier 4 — unsupported** (forces workbook status → `failed` because no working report without data)

| Tableau source | Reason |
|---|---|
| Tableau Server / Online published datasources | Out of scope per project scope (file-only). |
| Web Data Connector (WDC) | No PBI equivalent. |
| R / Python Tableau data connectors | No PBI equivalent. |
| OData / Statistical / SAS / SPSS / etc. (anything not in Tier 1–3) | Not mapped. |
| `.hyper` extract with null/missing `<connection>` | No recoverable upstream source. |

**Credentials policy:** PBI projects do not store credentials in the file (intentional, by Microsoft). We emit M with server/database/path from Tableau, but **never credentials**. The per-workbook `workbook-report.md` lists each datasource and the user action required on first open ("enter credentials", "OAuth in Desktop", "install Oracle client", etc.). Captured in IR field `Datasource.user_action_required[]`.

## 6. Stages — purpose, IO, AI, tests

### Stage 1 — extract (pure python)

- **Input:** path to `.twb` / `.twbx`.
- **Output:** `01_extract.json` (raw structured dump of Tableau XML).
- **Algorithm:** `tableau/document-api-python` for elements within its coverage; `lxml` against `tableau-document-schemas` XSDs for the rest. Walk: datasources → connections (preserving both the original `<connection>` and any `<extract>` block separately) → columns → calculations → worksheets → dashboards → actions. **Lift worksheet-level table-calc metadata** (compute-using, partitioning, addressing) so it can be associated back to the consuming calc in stage 2. **Detect quick-table-calc pill modifiers** on sheet encodings — record them as pending anonymous-calc candidates. Tier-C objects detected here.
- **Summary.md:** file size, datasource/sheet/dashboard/calc/parameter counts, list of tier-C objects detected, count of quick-table-calc modifiers detected.
- **Tests:** unit per parser; golden on ~20 single-feature `.twb` fixtures (includes extract-detection fixtures for table-calc metadata).

### Stage 2 — canonicalize → IR (pure python)

- **Input:** `01_extract.json`.
- **Output:** `02_ir.json` (validates against IR JSON Schema; `ir_schema_version` stamped).
- **Algorithm:**
  - Map raw extract to IR dataclasses; resolve internal refs to IR ids.
  - **Discriminate calc `kind` and `phase`**: parse `tableau_expr` for LOD prefix (FIXED/INCLUDE/EXCLUDE); use worksheet metadata to identify `table_calc`; default to `row` or `aggregate` based on presence of aggregation functions.
  - Build `table_calc`, `lod_fixed`, `lod_relative` sub-records per kind.
  - **Generate anonymous `Calculation` records for quick-table-calc pill modifiers** with `owner_sheet_id` back-ref.
  - Build `depends_on` graph; detect cycles.
  - **Classify each `Parameter` into an `intent`** using the §5.7 detection table.
  - **Classify each `Datasource` into a `connector_tier`** using the §5.8 matrix; record `pbi_m_connector` and `user_action_required[]`.
  - Drop tier-C objects to `unsupported[]` with source excerpts.
- **Summary.md:** IR object counts by kind; calc kind histogram (row/aggregate/table_calc/lod_*); parameter intent histogram; datasource tier histogram; dependency graph stats; unsupported breakdown.
- **Tests:** unit; contract (output validates against IR JSON Schema); golden against IR fixtures; cycle detection on calc dependency graph; classification fixtures per calc-kind / parameter-intent / connector-tier.

### Stage 3 — translate calcs (python + AI fallback)

- **Input:** `02_ir.json`.
- **Output:** `03_calcs.json` = IR with `dax_expr` populated on every `Calculation` (including anonymous ones) and calculated `Column`.
- **Algorithm:**
  - Topo-sort calcs in two lanes: **global** (row, aggregate, lod_fixed, named table_calc) and **per-sheet** (lod_include, lod_exclude, anonymous quick-table-calcs) — global emitted first.
  - For each calc: select rule by `kind` × `frame` / `phase`. Rule library covers:
    - `row` — existing arithmetic + string + date rules.
    - `aggregate` — SUM/AVG/COUNT/MIN/MAX + conditional variants.
    - `lod_fixed` — `CALCULATE(<agg>, REMOVEFILTERS(other), KEEPFILTERS(dims))`.
    - `lod_include` / `lod_exclude` — per-sheet viz-LoD expansion using ALLEXCEPT/ALLSELECTED patterns.
    - `table_calc.frame=cumulative` — CALCULATE+FILTER on sort-field ≤ current.
    - `table_calc.frame=rank` — RANKX with ALLEXCEPT(partition_cols).
    - `table_calc.frame=window` — DATESINPERIOD or window measure pattern.
    - `table_calc.frame=lookup` — LOOKUPVALUE or offset measure pattern.
  - On rule miss → `LLMClient.translate_calc(calc_subset)` → `{dax_expr, confidence, notes}`. Input bundle includes the enriched IR subset (kind, table_calc/lod_fixed/lod_relative, depends_on signatures).
  - Validate output by parsing as DAX (sqlglot tsql dialect or msdax-py). Failed validation → drop to `unsupported[]`.
  - For `lod_include` / `lod_exclude` and anonymous calcs, emit one DAX measure per `(calc, consuming_sheet)` named `<calc_name>__<sheet_safe_name>`.
- **AI:** structured-output via tool-use; strict output schema `{dax_expr, confidence ∈ {high,medium,low}, notes}`; validator: parses as DAX; per-fixture snapshot; cached by hash.
- **Summary.md:** count by translation source (rule vs AI); rule hit counts; AI confidence histogram; AI cache hit rate; calcs that failed validation.
- **Tests:** unit per rule (one per kind × frame combo, ~25 cases); AI snapshot per fixture calc; contract on output IR; integration test against synthetic `.twb` containing each rule.

### Stage 4 — map visuals (python + AI fallback)

- **Input:** `03_calcs.json`.
- **Output:** `04_viz_map.json` = IR with each `Sheet` annotated with `pbir_visual` `{visual_type, encoding_bindings[], format}`. Bindings reference per-sheet measure names for LOD INCLUDE/EXCLUDE calcs.
- **Algorithm:** Python dispatch table on `(mark_type, shelf_signature)` → PBIR visual + encoding plan. Consumes the already-normalized IR — does NOT re-infer semantics. On miss or ambiguity → `LLMClient.map_visual(sheet_subset)`. Output schema enumerates the PBIR visual catalog so the model cannot invent a non-existent visual. Validator: every binding's source field exists in IR; every target slot exists for that visual.
- **AI:** structured-output via tool-use; constrained enum; per-fixture snapshot.
- **Summary.md:** visual-type histogram; rule-hit vs AI-fallback rate; sheets with low-confidence AI decisions; unsupported mark types.
- **Tests:** rule-table coverage (each row exercised); AI snapshot per ambiguous-sheet fixture; contract on output.

### Stage 5 — compute layout (pure python)

- **Input:** `04_viz_map.json`.
- **Output:** `05_layout.json` = IR with every Dashboard `Leaf.position` resolved to `(x,y,w,h)`; z-order populated.
- **Algorithm:**
  1. Walk container tree top-down; resolve every leaf rect at the dashboard's nominal size.
  2. Choose canvas size (nearest standard or exact custom; user-overridable in `config.yaml`).
  3. Apply uniform scale if canvas ≠ dashboard size.
  4. Map object types via fixed table (worksheet→visual, filter card→slicer, parameter card→slicer + what-if param per §5.7 intent, legend→suppress + flip `legend.show=true` on host visual, text→textbox, image→image, web page→placeholder+warning, blank→drop, navigation→button).
  5. Preserve z-order from Tableau floating layouts.
  6. Clamp off-canvas leaves; log warning to `unsupported.json`.
- **Summary.md:** per-dashboard chosen canvas size, leaf count, clamped count, dropped count, placeholder-leaf-ratio.
- **Tests:** unit on container-tree walker; property test (every position within canvas after clamp); golden on 5 dashboard fixtures.

### Stage 6 — build TMDL (pure python)

- **Input:** `05_layout.json`.
- **Output:** `./out/<wb>/SemanticModel/` directory of TMDL files + `06_tmdl.json` manifest.
- **Algorithm:** Render IR `data_model` to TMDL: `database.tmdl`, `model.tmdl`, one `tables/<name>.tmdl` per table (columns, measures, calculated columns, hierarchies). Relationships in `relationships/`. **Datasource-to-M**: render each `Datasource.pbi_m_connector` with `connection_params{}` substituted, credentials omitted. **Parameters** emitted per §5.7 intent (what-if tables, disconnected selectors, hidden constants, formatting switches). **LOD INCLUDE/EXCLUDE per-sheet measures** named `<calc_name>__<sheet>`.
- **Summary.md:** file count by TMDL file type; table/column/measure/relationship counts; parameters emitted by intent; total bytes.
- **Tests:** unit per renderer; golden on TMDL output; validity via TE2 CLI + Microsoft AnalysisServices .NET load probe.

### Stage 7 — build report PBIR (pure python)

- **Input:** `05_layout.json` (reads stage 4 + stage 3 transitively via IR).
- **Output:** `./out/<wb>/Report/definition/` tree of PBIR JSON files + `07_pbir.json` manifest.
- **Algorithm:** For each Tableau dashboard → one PBIR `page/`. For each leaf with a sheet → a PBIR `visual/` using the `pbir_visual` binding from stage 4 + position from stage 5. Filter cards → slicers. Parameter cards → slicers bound to the §5.7-emitted tables. Actions → PBIR `visualInteractions` + bookmark navigation. Workbook-level filters → page filters (promoted to report filter when the same filter applies to all pages).
- **Summary.md:** page count; visual count by type; slicers/filters/actions; bookmark count.
- **Tests:** unit per emitter; golden on PBIR JSON; validity via `pbi-tools compile`.

### Stage 8 — package + validate (pure python)

- **Input:** stages 6 + 7 outputs.
- **Output:** `<wb>.pbip` + `workbook-report.md` + `acceptance.json` (real-workbook subset only, per §15).
- **Algorithm:**
  1. Write `.pbip` root file with project pointers; assemble `SemanticModel/` + `Report/` per PBIR project layout.
  2. **TMDL validity:** TabularEditor 2 CLI (`TabularEditor.exe -B /c <path>`) + AnalysisServices .NET load probe.
  3. **PBIR compile validity:** `pbi-tools compile <path>` must succeed.
  4. **Structural checks:** every visual references an existing measure/column; every relationship's tables exist; no orphan slicers; per-sheet LOD measure names resolve.
  5. **Desktop-open gate (real-workbook subset only):** `tableau2pbir.validate.desktop_open` launches `PBIDesktop.exe /Open <pbip>`, parses `%LOCALAPPDATA%\Microsoft\Power BI Desktop\Traces\` for events; passes iff no ERROR events, no `RepairPrompt` event, both `ReportLoaded` and `ModelLoaded` events present. Timeout: **300s per workbook**. One retry on suspected flake.
  6. Compute workbook `status` per §8.1.
  7. Emit `acceptance.json` per §15 rubric for real workbooks.
- **Summary.md:** validation pass/fail per check; Desktop-open trace event highlights; total artifact size; link to `workbook-report.md`.
- **Tests:** end-to-end golden (synthetic + 3-5 real workbooks); TMDL validity; PBIR compile validity; Desktop-open gate on real-workbook subset; rubric pass/fail.

## 7. LLMClient — single AI entry point

```python
class LLMClient:
    def translate_calc(calc_subset)  -> TranslateCalcResult   # {dax_expr, confidence, notes}
    def map_visual(sheet_subset)     -> MapVisualResult
    def cleanup_name(raw_name, kind) -> CleanupNameResult
```

Each method:

1. Build pydantic input bundle from the enriched IR subset (§5.6 / §5.7 data included).
2. `cache_key = hash(model + system_prompt_hash + tool_schema_hash + input)`.
3. If cache hit → return cached parsed output (zero tokens).
4. If `PYTEST_SNAPSHOT=replay` → return from `tests/llm_snapshots/` (zero network).
5. Else: `anthropic.messages.create(model="claude-sonnet-4-6", temperature=0, system=[{type:"text", text:PROMPT, cache_control:{type:"ephemeral"}}], tools=[OUTPUT_TOOL], tool_choice={type:"tool", name:OUTPUT_TOOL.name})`.
6. Parse the `tool_use` block strictly into pydantic.
7. Run domain validator (DAX parses; visual_type ∈ catalog).
8. Valid → write to cache, return. Invalid → retry once with validator feedback; then drop the record into `unsupported[]`.

Properties:

- Model pinned per call site in `config.yaml`; default `claude-sonnet-4-6`.
- Anthropic prompt caching on every system prompt.
- On-disk response cache at `.tableau2pbir-cache/llm/<hash>.json` — reruns spend zero tokens.
- Snapshot mode `PYTEST_SNAPSHOT=replay` for tests — zero network.
- Invalid-output policy: retry once with validator feedback, then drop. Bounded.
- Calc `confidence` (high/medium/low) feeds into §8.1 status promotion.

## 8. Error handling and workbook status

### 8.1 Workbook status rule (addresses review finding 5)

Evaluated top-to-bottom; first match wins:

```
status = 'failed' if ANY of:
  • any datasource has connector_tier == 4
  • any datasource lookup fails (Tableau source kind not in matrix §5.8)
  • >50% of measures (Calculation.scope=='measure') dropped to unsupported[]
  • any dashboard with placeholder-leaf-ratio >= 0.5
  • TMDL validity or PBIR compile fails (stage 8)
  • Desktop-open gate fails (real-workbook subset only)

elif status = 'partial' if ANY of:
  • any placeholder leaves in any dashboard (placeholder-leaf-ratio > 0)
  • any AI-translated calc with confidence != 'high'
  • any clamped layout leaf or dropped object
  • any datasource with connector_tier == 3
  • any datasource with user_action_required including driver install (Oracle, Teradata)
  • any parameter with intent == 'unsupported'

else status = 'ok'
```

**Reporting:** each promotion records its trigger reason(s) in `workbook-report.md`. `run-manifest.md` has columns `workbook | status | trigger_reasons | link`. CI fails the run on any `failed` in the real-workbook gate.

### 8.2 StageError

```python
class StageError:
    severity: 'info' | 'warn' | 'error' | 'fatal'
    code: str          # stable, e.g. "calc.invalid_dax"
    object_id: str     # affected IR object
    message: str
    fix_hint: str | None
```

Runner behavior:

- `info / warn / error` → append to `unsupported.json`, continue to next stage.
- `fatal` → halt **this workbook**, compute status per §8.1, batch continues with next workbook.
- Batch driver uses `multiprocessing.Pool.imap_unordered`; a crashed child process is caught and its workbook marked `failed`.

## 9. Testing strategy

Seven layers (was six; added vii):

| Layer | Runs on | Lives in |
|---|---|---|
| i — per-stage unit | every commit | `tests/unit/stages/test_<n>_*.py` |
| ii — stage contract (JSON Schema) | every commit | `tests/contract/test_<n>_output.py` |
| iii — golden-file (.twb→.pbip) | every PR | `tests/golden/{synthetic,real,expected}/` |
| iv — TMDL validity (TE2 + AS load probe) | every PR | `tests/validity/tmdl/` |
| iv-b — PBIR compile validity (`pbi-tools compile`) | every PR | `tests/validity/pbir/` |
| vi — AI snapshot | PRs touching prompts/schemas + nightly + pre-release | `tests/llm_snapshots/<method>/<fixture>.json` |
| **vii — Desktop-open gate (real-workbook subset)** | every PR | `tests/desktop_open/` (Windows CI runner only) |

Visual regression (v) deferred — see §11.

**Corpus (layered):**

- `tests/golden/synthetic/*.twb` — ~50 hand-authored single-feature workbooks (one calc per file, one viz per file, one dashboard layout pattern per file). Includes:
  - One per calc `kind` × `frame` combination (~25 fixtures).
  - One per `Parameter.intent` (~5 fixtures).
  - One per connector Tier-1 and Tier-2 kind (~12 fixtures).
  - Edge-case fixtures: missing hyper `<connection>` (→ Tier 4), cross-DB join (→ Tier 3), quick table calc.
- `tests/golden/real/*.twbx` — 3–5 representative production workbooks for end-to-end coverage. Each paired with `tests/golden/real/<wb>.rubric.yaml` (§15).

**AI snapshot details:**

- Snapshot stores `{model, system_prompt_hash, tool_schema_hash, input, expected_output}`.
- Comparison is structural (parse DAX to AST; compare IR JSON semantically).
- Failure prompts human to reject (regression) or accept (intentional improvement).

**Desktop-open gate details** (layer vii):

- Windows CI runner with PBI Desktop installed.
- Timeout: **300s per workbook**. Budget: ~15–25 min added per PR for 3–5 real workbooks.
- One retry on suspected flake (trace shows no load events within first 60s — assume process hung).
- Trace event parser is version-tolerant: maps multiple Desktop versions' event names to the canonical set `{ReportLoaded, ModelLoaded, RepairPrompt, ModelError, VisualError}`. Small per-version probe fixtures maintained in `tests/desktop_open/version_probes/`.

## 10. Project layout

```
tableau2pbir/
├── pyproject.toml
├── config.yaml.example         # model pins, canvas defaults, cache dir
├── README.md
├── src/tableau2pbir/
│   ├── cli.py                  # argparse, batch driver, run-manifest
│   ├── pipeline.py             # stage runner, --gate, --from, status rule
│   ├── ir/
│   │   ├── __init__.py         # dataclasses (Calculation, Parameter, Datasource enriched)
│   │   ├── schema.py           # JSON Schema autogen
│   │   ├── version.py          # IR_SCHEMA_VERSION = "1.0.0"
│   │   └── migrations/
│   ├── llm/
│   │   ├── client.py           # LLMClient
│   │   ├── cache.py            # on-disk response cache
│   │   ├── snapshots.py        # test replay mode
│   │   └── prompts/
│   │       ├── translate_calc.md
│   │       ├── map_visual.md
│   │       └── cleanup_name.md
│   ├── stages/
│   │   ├── s01_extract.py
│   │   ├── s02_canonicalize.py
│   │   ├── s03_translate_calcs.py
│   │   ├── s04_map_visuals.py
│   │   ├── s05_compute_layout.py
│   │   ├── s06_build_tmdl.py
│   │   ├── s07_build_pbir.py
│   │   └── s08_package_validate.py
│   ├── translators/
│   │   ├── calc/
│   │   │   ├── rules.py        # rule library indexed by (kind, frame, phase)
│   │   │   └── ai.py           # LLMClient wrapper
│   │   └── viz/{rules.py, ai.py}
│   ├── classify/
│   │   ├── calc_kind.py        # stage 2 helper — LOD / table_calc discrimination
│   │   ├── parameter_intent.py # stage 2 helper — §5.7 detection
│   │   └── connector_tier.py   # stage 2 helper — §5.8 matrix lookup
│   ├── emit/{tmdl.py, pbir.py}
│   ├── validate/
│   │   ├── pbir_schema.py
│   │   ├── tmdl_schema.py      # wraps TE2 CLI + AS .NET load probe
│   │   ├── structural.py
│   │   ├── pbir_compile.py     # wraps pbi-tools compile
│   │   ├── desktop_open.py     # §9 layer vii
│   │   └── status.py           # §8.1 status rule
│   └── util/{xml.py, zip.py, dax_parser.py}
├── tests/
│   ├── unit/stages/
│   ├── contract/
│   ├── golden/
│   │   ├── synthetic/*.twb
│   │   ├── real/*.twbx
│   │   ├── real/<wb>.rubric.yaml    # §15
│   │   └── expected/<wb>/
│   ├── validity/
│   │   ├── tmdl/
│   │   └── pbir/
│   ├── desktop_open/
│   │   └── version_probes/          # trace-event-name mapping per PBI Desktop version
│   └── llm_snapshots/
│       ├── translate_calc/
│       ├── map_visual/
│       └── cleanup_name/
├── docs/
│   ├── architecture.md
│   ├── stages/<n>_<name>.md
│   └── superpowers/specs/      # this spec
└── .superpowers/               # gitignored (brainstorm artifacts)
```

## 11. Explicit deferrals

- **Visual regression testing.** PBI Desktop has no reliable headless rendering; pixel-diff against a non-deterministic renderer is high noise. Revisit with an opt-in `--with-visual-tests` flag.
- **Provider abstraction over Anthropic SDK.** Speculative; not added until a real second provider is required.
- **Multi-tenant / service deployment.** Local-only by current scope.
- **Live data refresh / gateway / RLS.** Out of scope.
- **Tableau Server / Online published datasources.** Out of scope (file-only).
- **`tableauhyperapi` dependency and Parquet export.** Considered and rejected in favor of "emit M for original `<connection>`, ignore the materialized hyper" (§5.8). Revisit only if a large share of real workbooks have null upstream `<connection>` on their hyper extracts.

## 12. Key design rules (one-line summaries)

- Python first; AI is a typed fallback function with strict schemas + validators.
- **Semantic normalization is owned by stage 2.** Stages 3+ consume a normalized IR and do not re-infer.
- IR is the contract. Stage 2 stamps the version; stages 3+ assert.
- Stages are pure functions returning `(output, summary, errors)`. They never throw.
- Failure isolation per workbook in batch.
- AI output is always validated structurally before being accepted; invalid AI output is dropped, never silently shipped.
- All AI calls are cached on disk by content hash; reruns spend zero tokens.
- Snapshot tests gate every model bump and prompt edit.
- Workbook `status` (ok / partial / failed) is computed by an explicit rule (§8.1), not by "pipeline finished".
- "Opens in Power BI Desktop" means the §9 layer vii gate passes, not just that schema validation succeeds.

## 13. Glossary

- **PBIR** — Power BI Project / Enhanced Report Format. JSON-based source format for PBI projects.
- **TMDL** — Tabular Model Definition Language. Text format for the PBI semantic model.
- **`.pbip`** — root project file pointing at `SemanticModel/` and `Report/`.
- **IR** — Intermediate Representation. The neutral, versioned, JSON-serializable Python dataclass tree this converter passes between stages 2–7.
- **Tier-C objects** — Tableau features deferred to "unsupported with placeholder + warning" (story points, R/Python visuals, custom shapes, forecast/trend, annotations, web-page objects).
- **Connector tier** — §5.8 classification (1=full, 2=credential placeholders, 3=degraded, 4=unsupported).
- **Quick table calc** — a Tableau pill-modifier table calc applied directly on a sheet without creating a named calc field. Modeled as an anonymous `Calculation` with `owner_sheet_id`.
- **Per-sheet measure expansion** — the technique for translating LOD INCLUDE/EXCLUDE and quick-table-calc records: one DAX measure per `(calc, consuming_sheet)` pair, named `<calc_name>__<sheet>`.

## 14. Compatibility ledger (addresses review suggestion 3)

For each Tableau concept without a first-class PBI equivalent, the fallback and fidelity loss:

| Tableau concept | PBI target | Fidelity loss | Notes |
|---|---|---|---|
| **Highlight action** | PBI visual interaction mode "highlight" | Partial — PBI's highlight behaves differently for non-filtered visuals; color intensity rules don't carry | Classified as Tier 3 visual binding; stage 7 emits `visualInteractions.type='highlight'` |
| **Dual axis with mismatched mark types** | Combo chart (line + clustered column) OR stacked visual | Partial — not all mark combinations have a PBI combo visual | AI fallback may pick the closest combo; low-confidence → `partial` |
| **Reference lines (computed)** | `analytics` pane constant/average/median | Full for constant/avg/median; partial for LOD-based reference lines | LOD-based reference lines emit as hidden measures + analytics binding |
| **Floating dashboard layout** | PBIR absolute positioning | Full (coordinates preserved) | Z-order preserved; transparency preserved per PBIR support |
| **Tiled dashboard layout** | PBIR absolute positioning | Full after container-tree resolution | Range-sized sheets resolved to midpoint |
| **Context filter** | PBI filter precedence | Partial — PBI's model filter order differs; ordering may shift | Emit as page filter; note in workbook-report |
| **Filter action** | PBI visual interaction "filter" | Full | |
| **Set action** | — | **Unsupported** (§2) | Logged to unsupported.json |
| **Parameter action** | — | **Unsupported** when it drives cascade; supported when static | |
| **Story points** | — | **Unsupported** (§2) | Suggested manual mapping in report: bookmarks + navigation buttons |
| **Annotations** | — | **Unsupported** (§2) | No PBI equivalent |
| **R / Python viz** | — | **Unsupported** (§2) | PBI Python visual exists but is not 1:1 |
| **Custom shape** | — | **Unsupported** (§2) | Could map to PBI custom visual in future — deferred |
| **Forecast / trend line** | — | **Unsupported** (§2) | Analytics pane has similar features but different math; deferred |
| **Tableau Parameter → formatting** | Measure-driven format string | Full when switch-pattern is detected | See §5.7 `formatting_control` |
| **Tooltip with viz embedded** | PBI report page tooltip | Partial — PBIR report page tooltips exist but have layout constraints | AI chooses layout; `partial` status |
| **Data blend (viz-time)** | Semantic model relationship | Partial — only works when grain matches linking field | See §5.8 Tier 3 |

This table is the source of truth for placeholder text shown in the final `.pbip`: each unsupported item emits a visual with the label `⚠ Unsupported: <concept> — <one-line reason>`.

## 15. Golden acceptance rubric (addresses review suggestion 4)

For each of the 3–5 real workbooks in `tests/golden/real/*.twbx`, a human author writes a `<wb>.rubric.yaml` capturing analytical-fidelity expectations. Stage 8 computes `acceptance.json` against it. This answers the reviewer's point that "optimizing for file validity rather than analytical fidelity" is a real risk.

**Rubric schema (`<wb>.rubric.yaml`):**

```yaml
workbook: SalesAnalysis.twbx

pages:
  - name: "Revenue Overview"
    must_render_visuals: [kpi_total_revenue, bar_by_region, line_by_month]
    must_have_slicers: [region, quarter]
    known_degradations: []

  - name: "Forecast"
    must_render_visuals: [line_forecast]
    must_have_slicers: [region]
    known_degradations: ["trend line replaced with hidden placeholder"]

measures:
  - name: "Total Revenue"
    must_match_tableau_value_within: 0.0001   # tolerance for floating-point
  - name: "YoY Growth"
    must_match_tableau_value_within: 0.001

datasources:
  - name: "Sales"
    expected_tier: 2      # Snowflake
    user_action: "enter credentials"

pass_criteria:
  all_pages_load: true
  all_must_render_visuals_present: true
  all_measure_values_within_tolerance: true
  no_unexpected_placeholders: true   # placeholders outside `known_degradations` are failures
  desktop_open_gate: passed
```

**Stage 8 evaluation:**

- For each rubric item, `acceptance.json` records `pass|fail` with the observed value.
- "measure value tolerance" checks: run a DAX probe query via AS load probe, compare to an expected value the rubric author captured from Tableau.
- Any `pass_criteria: true` that evaluates `fail` forces the workbook to `failed` even if §8.1 would have classified it `partial` or `ok`. This keeps analytical fidelity as the overriding signal on named-fidelity workbooks.

**What the rubric does NOT try to capture:**

- Pixel fidelity (deferred to visual regression testing, §11).
- Exact visual type match (PBI visuals are often "close enough"; dropping to strict equality causes false failures).
- Formatting details (font, color shades, gridline weights) — low information value, high churn.

## Appendix A — Change log from 2026-04-23 v1

Applied in this revision (all from `C:\Tableau_PBI\review.md`):

1. **Finding 1 (IR calc semantics, HIGH)** — §5.6 added. `Calculation` gains `kind`, `phase`, `table_calc`, `lod_fixed`, `lod_relative`, `owner_sheet_id`. Quick table calcs modeled as anonymous calcs. LOD INCLUDE/EXCLUDE handled via per-sheet measure expansion. Topo-sort gets a (calc × sheet) lane.
2. **Finding 2 (Desktop validation, HIGH)** — §9 adds layer vii (Desktop-open gate on real-workbook subset). §6 stage 8 adds TE2 + pbi-tools + Desktop-open. Timeout 300s. §15 golden acceptance rubric ties analytical fidelity to workbook status.
3. **Finding 3 (connector matrix, MED)** — §5.8 added. Four tiers. `.hyper` handled by emitting M for the original `<connection>`; null upstream → Tier 4. Credentials policy explicit. `tableauhyperapi` not added as a dependency.
4. **Finding 4 (parameter modes, MED)** — §5.7 added. `Parameter.intent` replaces `what_if?`. Five intents. Emission rules per intent in stages 6 and 7.
5. **Finding 5 (success thresholds, MED)** — §8.1 added. Explicit `ok / partial / failed` rule. `run-manifest.md` gains `trigger_reasons` column.
6. **Suggestion 1 (3-col coverage table)** — §2 rewritten.
7. **Suggestion 2 (stage ownership)** — §4.2 + §12 explicit rule; §6 stage 4 now consumes normalized IR and does not re-infer.
8. **Suggestion 3 (compatibility ledger)** — §14 added.
9. **Suggestion 4 (acceptance rubric)** — §15 added; `<wb>.rubric.yaml` schema defined.

Also fixed in this revision: §1 and §9 `§10 → §11` stale references (carried over from v1 self-review); §9 `(5b = layered)` Q-number footprint removed.
