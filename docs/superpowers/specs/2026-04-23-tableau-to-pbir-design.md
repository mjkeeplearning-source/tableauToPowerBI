# Tableau → Power BI (PBIR) Converter — Design

- **Date:** 2026-04-23
- **Status:** Approved (post-final_1 review patch) for implementation planning
- **Working directory:** `C:\Tableau_PBI`
- **Reviews applied:** `C:\Tableau_PBI\review.md` (5 findings + 4 suggestions), `C:\Tableau_PBI\final.md` (4 findings), `C:\Tableau_PBI\final_1.md` (5 findings) — see Appendix A

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
| Cross-database joins | Strategy depends on the pair — see sub-matrix below. Never blindly flatten DB↔DB pairs. |
| Data blends (viz-time joins) | Model as semantic-model relationship when grain matches linking field (one-to-many). Demote to "unsupported viz binding" when grain/cardinality looks risky. |
| Custom SQL (`<custom-sql>`) | Emit as `Value.NativeQuery` with SQL preserved verbatim; warn that PBI connector SQL dialect may differ. |
| Initial SQL (pre-query) | Preserved as a `Native` step prefix; warned. |

**Cross-database join sub-matrix** (narrowed per review finding 3 — flatten only for tested, safe pairs):

| Pair | Strategy | Status |
|---|---|---|
| File + File (CSV / Excel) | Flatten into single M using `Table.Join` on in-memory sources | `partial` |
| SQL-backed + File (SQL Server / Postgres / Snowflake / BigQuery / Redshift / MySQL / Oracle / Databricks / Teradata + CSV or Excel) | Flatten into single M: `Value.NativeQuery` (or connector query) on the SQL side + `Csv.Document` / `Excel.Workbook` on the file side, joined in M | `partial` |
| Any other DB↔DB pair (e.g., Snowflake + Oracle, Postgres + BigQuery) | **Never flatten.** Emit as two separate M tables + model relationship **iff** grain/cardinality of the link field can be inferred from IR (link column is a key or tagged unique). Otherwise drop the join, classify as `unsupported`, log to `unsupported.json`. | `partial` if relationship emitted; forces `failed` trigger path (dropped measures) if grain unprovable for all joins |
| Any pair where the link field has no clear grain and is not tagged as a key | Drop the join, classify as `unsupported`. | contributes to `>50% measures dropped` check |

Rationale: in-process M flattening only works well when at least one side is local/small (a file) or queryable (SQL pushdown). DB↔DB flattening via `Table.Join` pulls both datasets into the mashup engine and is slow, fragile, and connector-dependent. A provable relationship is honest; a silently-dropped join is not.

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
  - **Syntax gate:** validate output by parsing as DAX (sqlglot tsql dialect or msdax-py). Parse failure → drop to `unsupported[]`. Note: this is syntax only; semantic correctness is verified by §9 layer iv-c on the downstream TMDL.
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
- **Algorithm:** For each Tableau dashboard → one PBIR `page/`. For each leaf with a sheet → a PBIR `visual/` using the `pbir_visual` binding from stage 4 + position from stage 5. Filter cards → slicers. Parameter cards → slicers bound to the §5.7-emitted tables. Actions → PBIR `visualInteractions` + bookmark navigation. Workbook-level filters → page filters (promoted to report filter when the same filter applies to all pages). **Emit `blocked_visuals[]`** in the stage manifest: for every rendered-page visual whose backing field traces to a `deferred_feature_*` or `connector_tier == 4` datasource, record `{page_id, visual_id, blocked_by: [unsupported.id, ...]}`. §8.1 consumes this list.
- **Summary.md:** page count; visual count by type; slicers/filters/actions; bookmark count; `blocked_visuals` count.
- **Tests:** unit per emitter; golden on PBIR JSON; validity via `pbi-tools compile`.

### Stage 8 — package + validate (pure python)

- **Input:** stages 6 + 7 outputs.
- **Output:** `<wb>.pbip` + `workbook-report.md` + `acceptance.json` (real-workbook subset only, per §15). Step order: package → TMDL validity → PBIR compile → structural checks → Desktop-open gate → rubric evaluation → final status. Rubric is an input to the status rule, not a post-hoc override.
- **Algorithm:**
  1. Write `.pbip` root file with project pointers; assemble `SemanticModel/` + `Report/` per PBIR project layout.
  2. **TMDL validity:** TabularEditor 2 CLI (`TabularEditor.exe -B /c <path>`) + AnalysisServices .NET load probe.
  3. **PBIR compile validity:** `pbi-tools compile <path>` must succeed.
  4. **Structural checks:** every visual references an existing measure/column; every relationship's tables exist; no orphan slicers; per-sheet LOD measure names resolve.
  5. **Desktop-open gate (real-workbook subset only):** `tableau2pbir.validate.desktop_open` launches `PBIDesktop.exe /Open <pbip>` and parses `%LOCALAPPDATA%\Microsoft\Power BI Desktop\Traces\` for events. Pass criteria split by datasource tier of the workbook:
     - **All datasources Tier 1**: require `ReportLoaded` **AND** `ModelLoaded`; no ERROR events; no `RepairPrompt`.
     - **Any datasource Tier 2**: require `ReportLoaded` only. `AuthenticationNeeded` / `AuthUIDisplayed` events are **expected credential prompts** — recorded separately in the trace summary, do not count as failures. Absence of `ModelLoaded` is acceptable. ERROR events that are not auth-related are still failures.
     - **Any datasource Tier 4** would have already forced `failed` at §8.1; Tier 3 follows the Tier 1 or Tier 2 rule based on whether the degraded connector prompts for credentials (per §5.8).
     Timeout: **300s per workbook**. One retry on suspected flake.
  6. **Rubric evaluation (real-workbook subset only):** load `<wb>.rubric.yaml`; evaluate each `pass_criteria` item; emit `acceptance.json` with `pass|fail` + observed value per item. Any failing `pass_criteria: true` produces an `acceptance_failed` signal that feeds §8.1.
  7. **Compute final workbook `status` per §8.1** (reads all validation results including `acceptance_failed`).
- **Summary.md:** validation pass/fail per check; Desktop-open trace event highlights; total artifact size; link to `workbook-report.md`.
- **Tests:** end-to-end golden (synthetic + 3-5 real workbooks); TMDL validity; PBIR compile validity; Desktop-open gate on real-workbook subset; rubric pass/fail.

## 7. LLMClient — single AI entry point

```python
class LLMClient:
    def translate_calc(calc_subset)  -> TranslateCalcResult   # {dax_expr, confidence, notes}
    def map_visual(sheet_subset)     -> MapVisualResult
    def cleanup_name(raw_name, kind) -> CleanupNameResult
```

**Prompt layout** — every AI call site has its own folder under `src/tableau2pbir/llm/prompts/<method>/` containing:

- `system.md` — the system prompt text (sent with `cache_control: ephemeral` so prompt caching kicks in).
- `tool_schema.json` — the Anthropic tool-use input schema, single source of truth. The pydantic output model is derived from this file; the tool passed to `anthropic.messages.create` is derived from this file.
- `examples/` (optional) — few-shot fixtures concatenated into the system prompt.
- `VERSION` — semver string. Bumping this version invalidates matching entries in `.tableau2pbir-cache/llm/` and in `tests/llm_snapshots/<method>/`, forcing fresh re-record under review.

At LLMClient init time, each method's folder is loaded once; the hash of `(system.md + tool_schema.json + VERSION + examples/*)` becomes `system_prompt_hash + tool_schema_hash` in the cache key below.

Each method:

1. Build pydantic input bundle from the enriched IR subset (§5.6 / §5.7 data included).
2. `cache_key = hash(model + system_prompt_hash + tool_schema_hash + input)`.
3. If cache hit → return cached parsed output (zero tokens).
4. If `PYTEST_SNAPSHOT=replay` → return from `tests/llm_snapshots/` (zero network).
5. Else: `anthropic.messages.create(model="claude-sonnet-4-6", temperature=0, system=[{type:"text", text: system_md, cache_control:{type:"ephemeral"}}], tools=[OUTPUT_TOOL], tool_choice={type:"tool", name:OUTPUT_TOOL.name})`.
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
  • acceptance_failed: any `pass_criteria: true` item in `<wb>.rubric.yaml` evaluates `fail` (real-workbook subset only)
  • any deferred datasource (`unsupported.code` starts with `deferred_feature_` AND object_kind == 'datasource') is referenced by any rendered page visual — read from stage 7's `blocked_visuals[]` list
  • any deferred feature blocks a required rubric item (real-workbook subset; `must_render_visuals` / `must_have_slicers` entry maps to a `deferred_feature_*` item)

elif status = 'partial' if ANY of:
  • any placeholder leaves in any dashboard (placeholder-leaf-ratio > 0)
  • any AI-translated calc with confidence != 'high'
  • any clamped layout leaf or dropped object
  • any datasource with connector_tier == 3
  • any datasource with user_action_required including driver install (Oracle, Teradata)
  • any parameter with intent == 'unsupported'
  • any unsupported[] item with `code` starting `deferred_feature_` (deferred behind a v1 feature flag)

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

Seven primary layers (validity layer iv has three sub-layers: iv / iv-b / iv-c):

| Layer | Runs on | Lives in |
|---|---|---|
| i — per-stage unit | every commit | `tests/unit/stages/test_<n>_*.py` |
| ii — stage contract (JSON Schema) | every commit | `tests/contract/test_<n>_output.py` |
| iii — golden-file (.twb→.pbip) | every PR | `tests/golden/{synthetic,real,expected}/` |
| iv — TMDL validity (TE2 + AS load probe) | every PR | `tests/validity/tmdl/` |
| iv-b — PBIR compile validity (`pbi-tools compile`) | every PR | `tests/validity/pbir/` |
| **iv-c — synthetic DAX semantic probes** | every PR | `tests/validity/dax_semantic/` |
| vi — AI snapshot | PRs touching prompts/schemas + nightly + pre-release | `tests/llm_snapshots/<method>/<fixture>.json` |
| **vii — Desktop-open gate (real-workbook subset)** | every PR | `tests/desktop_open/` (Windows CI runner only) |

Visual regression (v) deferred — see §11.

**Role of the DAX validator in stage 3.** The `util/dax_parser.py` validator that runs inside stage 3 is a **syntax gate** only — it ensures the string parses as DAX. Passing it does **not** certify semantic correctness. Semantic correctness is verified by testing layer iv-c below.

**Corpus (layered) — full roadmap.** The corpus below is the **full-roadmap target**. The v1 CI run executes the v1-scope subset (see §16 for the fixture count and rule); deferred-feature fixtures live alongside v1 fixtures in the same tree but are tagged with their feature-flag name and skipped by pytest collection unless the matching `--with-*` flag is on in the CI matrix.

- `tests/golden/synthetic/*.twb` — ~50 hand-authored single-feature workbooks (one calc per file, one viz per file, one dashboard layout pattern per file). Includes:
  - One per calc `kind` × `frame` combination (~25 fixtures).
  - One per `Parameter.intent` (~5 fixtures).
  - One per connector Tier-1 and Tier-2 kind (~12 fixtures).
  - Edge-case fixtures: missing hyper `<connection>` (→ Tier 4), cross-DB join (→ Tier 3), quick table calc.
- `tests/golden/real/*.twbx` — 3–5 representative production workbooks for end-to-end coverage. Each paired with `tests/golden/real/<wb>.rubric.yaml` (§15).

**DAX semantic probes (layer iv-c) — details:**

- Every synthetic calc fixture in v1 scope (`row`, `aggregate`, `lod_fixed`, `Parameter.intent ∈ {numeric_what_if, categorical_selector, internal_constant}`, filter-sensitive measures) ships with a sibling file `<fixture>.expected_values.yaml`:
  ```yaml
  probes:
    - calc: "Total Sales"
      filter_context: {}                                   # no filters
      expected: 1234.56
      tolerance: 0.0001
    - calc: "Sales Per Region FIXED"
      filter_context: { Region: "West", Year: 2024 }
      expected: 423.10
      tolerance: 0.0001
  ```
- CI loads the generated TMDL via the existing AnalysisServices .NET load probe, runs each `(calc, filter_context)` as a DAX `EVALUATE ROW(...)` query, and compares against `expected` within `tolerance`.
- Author once per fixture (the fixture author captures expected values from Tableau). Regenerate only when the fixture's Tableau semantics change.
- v1 calc kinds **require** at least one probe per fixture. Deferred kinds (`table_calc`, `lod_include`, `lod_exclude`) ship probes alongside their fixtures so they are ready when the feature flag flips on.

**AI snapshot details:**

- Snapshot stores `{model, system_prompt_hash, tool_schema_hash, input, expected_output}`.
- Comparison is structural (parse DAX to AST; compare IR JSON semantically).
- Failure prompts human to reject (regression) or accept (intentional improvement).

**Desktop-open gate details** (layer vii):

- Windows CI runner with PBI Desktop installed.
- Timeout: **300s per workbook**. Budget: ~15–25 min added per PR for 3–5 real workbooks.
- One retry on suspected flake (trace shows no load events within first 60s — assume process hung).
- Trace event parser is version-tolerant: maps multiple Desktop versions' event names to the canonical set `{ReportLoaded, ModelLoaded, RepairPrompt, ModelError, VisualError, AuthenticationNeeded, AuthUIDisplayed}`. Auth events are expected for Tier 2 workbooks and are recorded as "expected credential prompts" separately from failures (see §6 stage 8 step 5). Small per-version probe fixtures maintained in `tests/desktop_open/version_probes/`.

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
│   │       ├── translate_calc/
│   │       │   ├── system.md           # the system prompt text (Anthropic prompt-cached)
│   │       │   ├── tool_schema.json    # output tool-use JSON Schema (single source of truth)
│   │       │   ├── examples/           # optional few-shot fixtures loaded into system prompt
│   │       │   │   ├── 001_lod_fixed.json
│   │       │   │   ├── 002_table_calc_rank.json
│   │       │   │   └── ...
│   │       │   └── VERSION             # semver; bump invalidates snapshot cache + AI on-disk cache entries
│   │       ├── map_visual/
│   │       │   ├── system.md
│   │       │   ├── tool_schema.json    # enumerates the PBIR visual catalog; constrains output
│   │       │   ├── examples/
│   │       │   └── VERSION
│   │       └── cleanup_name/
│   │           ├── system.md
│   │           ├── tool_schema.json
│   │           └── VERSION
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
│   │   ├── pbir/
│   │   └── dax_semantic/              # §9 layer iv-c — expected_values.yaml + runner
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

- Stage 8 evaluates the rubric **before** computing final status (§6 stage 8 step 6; see also §8.1).
- For each rubric item, `acceptance.json` records `pass|fail` with the observed value.
- "measure value tolerance" checks: run a DAX probe query via AS load probe, compare to an expected value the rubric author captured from Tableau.
- Any failing `pass_criteria: true` contributes `acceptance_failed` to the §8.1 rule, which forces the workbook to `failed`. This keeps analytical fidelity as the overriding signal on named-fidelity workbooks without bypassing the single source-of-truth status rule.

**What the rubric does NOT try to capture:**

- Pixel fidelity (deferred to visual regression testing, §11).
- Exact visual type match (PBI visuals are often "close enough"; dropping to strict equality causes false failures).
- Formatting details (font, color shades, gridline weights) — low information value, high churn.

## 16. MVP cut line (addresses final.md finding 4)

v1 is deliberately smaller than the full coverage table so we can ship a usable converter quickly, harden Stage 8 + Desktop-open-gate telemetry on a focused surface, then expand.

**v1 — in scope**

| Area | Included |
|---|---|
| Connectors | Tier 1 + Tier 2 (see §5.8) |
| Marks | bar, line, area, scatter, text-table, pie, filled map |
| Calculations | `kind ∈ {row, aggregate, lod_fixed}`; full `row` + `aggregate` rule library; FIXED LOD |
| Parameters | `intent ∈ {numeric_what_if, categorical_selector, internal_constant}` |
| Dashboards | tiled + floating layout with absolute position resolution (§6 Stage 5 fully) |
| Filters | categorical, range, top-N, context (with precedence caveat) |
| Encodings | color, size, label, tooltip (basic), detail, shape, angle |
| Dual axis | matched-type dual axis |
| Reference lines | constant, average, median |
| Actions | filter action, highlight action |
| Validation | all 7 testing layers, including Desktop-open gate on real-workbook subset |

**v1 — deferred (feature-flagged, post-v1 milestones)**

| Area | Flag / milestone | Reason |
|---|---|---|
| `table_calc` (all frames) | `--with-table-calcs` (v1.1) | Highest-complexity translation + AI fallback surface; iterate after v1 telemetry shows which frames matter |
| `lod_include` / `lod_exclude` | `--with-lod-relative` (v1.1) | Per-sheet measure expansion adds volume; wait for real-workbook distribution |
| Tier 3 connectors (cross-DB joins, blends, custom SQL, initial SQL) | `--with-tier3` (v1.2) | Each sub-case has narrow tested surface; scale once Tier 1/2 is stable |
| Mismatched dual-axis marks | `--with-mixed-dual-axis` (v1.1) | AI combo-chart mapping; low-confidence by nature |
| viz-in-tooltip | `--with-report-page-tooltips` (v1.2) | PBI report-page tooltips have layout constraints; requires care |
| `formatting_control` parameters | `--with-format-switch` (v1.1) | Depends on `table_calc` rule library for switch patterns |
| Device Designer mobile layout | `--with-mobile-layout` (v1.2) | Separate reflow pass |
| URL actions | `--with-url-actions` (v1.1) | Parameter embedding in URLs is best-effort |
| Symbol map | `--with-symbol-map` (v1.1) | No tested PBIR visual mapping yet — §2 classifies as Partial; defer until a tested mapping ships |

**v1 — unchanged (still unsupported, both v1 and v2)**

Story points, annotations, R/Python visuals, custom shapes, forecast/trend lines, set actions, parameter-change cascades, Tier 4 connectors, Tableau Server / Online datasources. See §2 and §14.

**v1 acceptance scope**

Relationship to §9 corpus: **§9 describes the full-roadmap corpus (~50 synthetic fixtures + 3–5 real workbooks). §16 defines the v1 CI subset (~30 fixtures, strict subset).** One tree, two run modes — selection driven by pytest markers + CI matrix flags, not by separate directories.

- `tests/golden/synthetic/`:
  - **~30 v1 fixtures** run on every PR: one per v1 calc kind (`row`, `aggregate`, `lod_fixed`), one per v1 `Parameter.intent`, one per Tier-1 and Tier-2 connector kind, v1-scope mark types, dashboard layout patterns.
  - **~20 deferred fixtures** also present in the tree (authored alongside v1 fixtures for future-proofing). Each is tagged `@pytest.mark.feature_flag("with_table_calcs")` etc. and **skipped by default**. CI matrix adds jobs `v1`, `v1.1-preview`, `v1.2-preview` that toggle the flag sets accordingly.
- `tests/golden/real/*.twbx`:
  - Real workbooks are curated for v1 end-to-end coverage. Each `.rubric.yaml` declares the v1 features it exercises.
  - Workbooks that require a deferred feature are authored once and tagged — skipped in v1 CI, run in the matching preview matrix job.
- **`workbook-report.md` for a v1 conversion** lists any v1-deferred feature encountered as `deferred-feature-detected: <feature> requires flag <name> (v1.x)` — distinct from `unsupported[]`, though the object also lives in `unsupported[]` with a `deferred_feature_*` code so §8.1 triggers fire per finding-3 rules.

**Status rule behavior in v1:** flags gate *execution*, not detection. Stage 2 still classifies every object per §5.6 / §5.7 / §5.8 regardless of flag state. When a required flag is off and a deferred feature is encountered, stage 2 routes the affected object to `unsupported[]` with a stable code `deferred_feature_<name>`. §8.1 now handles these directly (see that section for the full rule):
- **`partial`** on encountering *any* `deferred_feature_*` item — surfaces the degradation even when the volume thresholds are not crossed.
- **`failed`** when a deferred datasource is referenced by a rendered page visual (stage 7 emits `blocked_visuals[]` for this), or when a deferred feature blocks a rubric item marked `must_*` (real-workbook subset).

This gives direct, deterministic status feedback for v1-deferred objects rather than relying on indirect volume thresholds.

## Appendix A — Change log

### A.1 From 2026-04-23 v1 — applied from `C:\Tableau_PBI\review.md`

1. **Finding 1 (IR calc semantics, HIGH)** — §5.6 added. `Calculation` gains `kind`, `phase`, `table_calc`, `lod_fixed`, `lod_relative`, `owner_sheet_id`. Quick table calcs modeled as anonymous calcs. LOD INCLUDE/EXCLUDE handled via per-sheet measure expansion. Topo-sort gets a (calc × sheet) lane.
2. **Finding 2 (Desktop validation, HIGH)** — §9 adds layer vii (Desktop-open gate on real-workbook subset). §6 stage 8 adds TE2 + pbi-tools + Desktop-open. Timeout 300s. §15 golden acceptance rubric ties analytical fidelity to workbook status.
3. **Finding 3 (connector matrix, MED)** — §5.8 added. Four tiers. `.hyper` handled by emitting M for the original `<connection>`; null upstream → Tier 4. Credentials policy explicit. `tableauhyperapi` not added as a dependency.
4. **Finding 4 (parameter modes, MED)** — §5.7 added. `Parameter.intent` replaces `what_if?`. Five intents. Emission rules per intent in stages 6 and 7.
5. **Finding 5 (success thresholds, MED)** — §8.1 added. Explicit `ok / partial / failed` rule. `run-manifest.md` gains `trigger_reasons` column.
6. **Suggestion 1 (3-col coverage table)** — §2 rewritten.
7. **Suggestion 2 (stage ownership)** — §4.2 + §12 explicit rule; §6 stage 4 now consumes normalized IR and does not re-infer.
8. **Suggestion 3 (compatibility ledger)** — §14 added.
9. **Suggestion 4 (acceptance rubric)** — §15 added; `<wb>.rubric.yaml` schema defined.

Also fixed in that revision: §1 and §9 `§10 → §11` stale references; §9 `(5b = layered)` Q-number footprint removed.

### A.2 From final review — applied from `C:\Tableau_PBI\final.md`

1. **Finding 1 (Stage 8 validation order)** — §6 stage 8 algorithm reordered so rubric evaluation (step 6) precedes final-status computation (step 7). §8.1 gains `acceptance_failed` as an explicit `failed` trigger (real-workbook subset). §15 reframed: rubric contributes a signal to §8.1 rather than overriding it post-hoc. Output-description line in §6 stage 8 now states the step order explicitly.
2. **Finding 2 (Tier 2 credential behavior)** — §6 stage 8 step 5 split into per-tier pass criteria: Tier 1 workbooks require `ReportLoaded` + `ModelLoaded`; Tier 2 workbooks require `ReportLoaded` only and treat `AuthenticationNeeded` / `AuthUIDisplayed` as expected (recorded separately, not failures); Tier 3 defers to Tier 1 or Tier 2 rule based on the connector's credential behavior. §9 layer vii canonical event set extended with `AuthenticationNeeded` and `AuthUIDisplayed`.
3. **Finding 3 (Tier 3 cross-DB join narrowing)** — §5.8 Tier 3 cross-database-join strategy replaced with a tested-pair sub-matrix. File+File and SQL+File pairs flatten; DB↔DB pairs never flatten — they emit as two tables + relationship if grain/cardinality is provable, otherwise drop the join to `unsupported[]`. Unprovable grain still routes through §8.1's `>50% measures dropped` path.
4. **Finding 4 (MVP cut line)** — §16 added. v1 is Tier 1+2 connectors, basic marks, `row` / `aggregate` / `lod_fixed` calcs, 3 parameter intents, full tiled+floating layout, all 7 test layers. Deferred behind flags/milestones: table_calcs, LOD INCLUDE/EXCLUDE, Tier 3, mismatched dual-axis, viz-in-tooltip, formatting_control parameters, Device Designer mobile, URL actions. §10 project layout unchanged (v1-deferred code paths still exist; the flags gate their execution, not their presence in the tree).

### A.3 Prompt organization

Per-prompt folder structure introduced in §7 and §10: each LLM call site (`translate_calc`, `map_visual`, `cleanup_name`) has its own folder under `src/tableau2pbir/llm/prompts/<method>/` containing `system.md`, `tool_schema.json`, optional `examples/`, and a `VERSION` file that invalidates on-disk cache and snapshot entries when bumped.

### A.4 From MVP review — applied from `C:\Tableau_PBI\final_1.md`

1. **Finding 1 (symbol map scope)** — removed `symbol map` from §16 v1 marks list (§2 classifies it as Partial, and no tested PBIR visual mapping exists). Added row in the v1-deferred table behind `--with-symbol-map` flag.
2. **Finding 2 (synthetic DAX semantic probes)** — added testing layer **iv-c** in §9 (`tests/validity/dax_semantic/`). Each v1 synthetic calc fixture ships with a sibling `<fixture>.expected_values.yaml` consumed by an AS load-probe runner. Stage 3's existing DAX-parse validator is explicitly renamed to "syntax gate" in both §6 stage 3 and §9. Added `src/tableau2pbir/validate/` path alignment in §10.
3. **Finding 3 (deferred-feature status triggers)** — §8.1 gains direct triggers:
   - `failed` when a deferred datasource is referenced by any rendered-page visual (stage 7 now emits `blocked_visuals[]`), or when a deferred feature blocks a `must_*` rubric item.
   - `partial` on any `unsupported[]` item with `code` starting `deferred_feature_`.
   §16's "status rule behavior" section rewritten to point at the new direct triggers rather than the indirect volume-threshold path. Stage 7 output contract updated.
4. **Finding 4 (corpus split clarification)** — §9 header clarifies it describes the full-roadmap corpus; §16 states the v1 CI subset (~30 of ~50 fixtures) runs on every PR, deferred fixtures live in the same tree, tagged with their flag, and are skipped by default pytest collection. CI matrix jobs (`v1`, `v1.1-preview`, `v1.2-preview`) toggle flag sets.
5. **Finding 5 (§Stage 5 typo)** — fixed: now `§6 Stage 5`.
