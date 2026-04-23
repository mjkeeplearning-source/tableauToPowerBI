# Design Review: Tableau -> PBIR Converter

## Findings

### 1. The IR is not rich enough to support the claimed coverage for LODs and table calculations

Severity: high

References:
- [2026-04-23-tableau-to-pbir-design.md](C:/Tableau_PBI/docs/superpowers/specs/2026-04-23-tableau-to-pbir-design.md:34)
- [2026-04-23-tableau-to-pbir-design.md](C:/Tableau_PBI/docs/superpowers/specs/2026-04-23-tableau-to-pbir-design.md:35)
- [2026-04-23-tableau-to-pbir-design.md](C:/Tableau_PBI/docs/superpowers/specs/2026-04-23-tableau-to-pbir-design.md:143)
- [2026-04-23-tableau-to-pbir-design.md](C:/Tableau_PBI/docs/superpowers/specs/2026-04-23-tableau-to-pbir-design.md:148)
- [2026-04-23-tableau-to-pbir-design.md](C:/Tableau_PBI/docs/superpowers/specs/2026-04-23-tableau-to-pbir-design.md:225)

The spec promises support for `FIXED` / `INCLUDE` / `EXCLUDE` and for running total, `% of total`, and rank, but the IR only carries raw expressions, dependency links, and a fairly thin sheet encoding model. That is not enough to preserve Tableau-specific evaluation context such as partitioning, addressing, sort order, pane/table scope, densification, or whether a calc is intended to execute at row, viz, or table-calc phase. Without those semantics, stage 3 will be forced to infer too much from incomplete context, and the converter will either emit syntactically valid but behaviorally wrong DAX or mark large parts of the advertised coverage unsupported.

Recommendation:
- Extend the IR before implementation to model calculation semantics explicitly: calc kind, aggregation phase, partition/address fields, order-by fields, frame/window definition, and LOD grain.
- Treat table calcs as a separate feature family, not just a calc-translation rule set.
- Narrow the supported table-calc scope now if the team does not want to model those semantics in v1.

### 2. The validation plan does not actually meet the stated goal of "opened and validated locally in Power BI Desktop"

Severity: high

References:
- [2026-04-23-tableau-to-pbir-design.md](C:/Tableau_PBI/docs/superpowers/specs/2026-04-23-tableau-to-pbir-design.md:9)
- [2026-04-23-tableau-to-pbir-design.md](C:/Tableau_PBI/docs/superpowers/specs/2026-04-23-tableau-to-pbir-design.md:273)
- [2026-04-23-tableau-to-pbir-design.md](C:/Tableau_PBI/docs/superpowers/specs/2026-04-23-tableau-to-pbir-design.md:275)

The goal says the output is opened and validated locally in Power BI Desktop, but stage 8 only guarantees schema checks, structural checks, and an optional or manual Desktop smoke step. Those are not equivalent. A PBIR project can pass structural validation and still fail to open cleanly in Desktop because of model/report compatibility details, unsupported visual payload combinations, or connection metadata issues.

Recommendation:
- Promote Desktop-open validation to a required acceptance gate for at least the golden real-workbook suite. 
- Define exactly what "validated locally in Power BI Desktop" means: opens without repair prompts, all pages load, no broken fields, no fatal model errors.

### 3. Data source conversion is underspecified relative to the promised output

Severity: medium

References:
- [2026-04-23-tableau-to-pbir-design.md](C:/Tableau_PBI/docs/superpowers/specs/2026-04-23-tableau-to-pbir-design.md:13)
- [2026-04-23-tableau-to-pbir-design.md](C:/Tableau_PBI/docs/superpowers/specs/2026-04-23-tableau-to-pbir-design.md:138)
- [2026-04-23-tableau-to-pbir-design.md](C:/Tableau_PBI/docs/superpowers/specs/2026-04-23-tableau-to-pbir-design.md:257)

The scope promises a complete PBIR project including datasource definitions, but the design only sketches `connection` in the IR and then jumps straight to TMDL rendering. Tableau connection semantics, Power BI connection metadata, credential handling, extract vs live behavior, and unsupported connector families are where many conversions fail in practice. Right now the spec does not define the supported connector matrix or the fallback behavior when a Tableau connection cannot be represented faithfully in PBIR/TMDL.

Recommendation:
- Add a connector support matrix to the design: file-based, SQL, extracts, custom connectors, published data sources, all relation database like databricks, snowflake, teraddata, sql  server tec.
- Specify how connection metadata is normalized in the IR and how unsupported connectors degrade.
- Make "opens in Desktop" contingent on a supported connector class, otherwise emit a partial project with an explicit datasource warning.

### 4. Parameter handling is too vague and risks incorrect behavior

Severity: medium

References:
- [2026-04-23-tableau-to-pbir-design.md](C:/Tableau_PBI/docs/superpowers/specs/2026-04-23-tableau-to-pbir-design.md:36)
- [2026-04-23-tableau-to-pbir-design.md](C:/Tableau_PBI/docs/superpowers/specs/2026-04-23-tableau-to-pbir-design.md:145)
- [2026-04-23-tableau-to-pbir-design.md](C:/Tableau_PBI/docs/superpowers/specs/2026-04-23-tableau-to-pbir-design.md:247)
- [2026-04-23-tableau-to-pbir-design.md](C:/Tableau_PBI/docs/superpowers/specs/2026-04-23-tableau-to-pbir-design.md:257)
- [2026-04-23-tableau-to-pbir-design.md](C:/Tableau_PBI/docs/superpowers/specs/2026-04-23-tableau-to-pbir-design.md:265)

The spec mixes Tableau parameters, Power BI slicers, and what-if parameters as if they were interchangeable. They are not. Some Tableau parameters drive calculations but are not natural slicers; some Power BI what-if parameters imply generated tables and measures; some categorical parameters should be disconnected tables, not numeric what-if objects. The current `what_if?` flag in the IR is too thin to preserve those distinctions.

Recommendation:
- Split parameter intent into explicit modes in the IR: numeric what-if, disconnected selector, formatting/control parameter, and unsupported.
- Add parameter-to-calc binding rules and tests before implementation starts.
- Avoid auto-mapping every parameter card to a slicer unless the parameter type actually supports that UX in Power BI.

### 5. "Fail-open" is sensible, but the placeholder policy needs tighter acceptance rules

Severity: medium

References:
- [2026-04-23-tableau-to-pbir-design.md](C:/Tableau_PBI/docs/superpowers/specs/2026-04-23-tableau-to-pbir-design.md:124)
- [2026-04-23-tableau-to-pbir-design.md](C:/Tableau_PBI/docs/superpowers/specs/2026-04-23-tableau-to-pbir-design.md:126)
- [2026-04-23-tableau-to-pbir-design.md](C:/Tableau_PBI/docs/superpowers/specs/2026-04-23-tableau-to-pbir-design.md:295)

The design says the pipeline always finishes and drops unconvertible records into `unsupported[]`, but it never defines when a workbook is still considered a success versus a materially broken conversion. That leaves a large quality gap for batch runs: a workbook with most critical measures dropped could still look "successful" because the pipeline completed.

Recommendation:
- Add severity thresholds that upgrade a workbook from `success` to `partial` when critical assets are missing.
- Define criticality rules for dropped calculations, datasource failures, and dashboard pages that render only placeholders.
- Include those thresholds in `workbook-report.md` and `run-manifest.md`.

## Suggestions

1. Add an explicit feature-coverage table with three columns: `supported`, `partial with degradation`, and `unsupported`. The current "practical" tier is directionally useful but still leaves too much room for interpretation.
2. Make stage ownership stricter: stage 3 should own semantic normalization for calculations, not just expression translation; stage 4 should consume a normalized semantic model rather than infer from raw encodings.
3. Add a compatibility ledger for each Tableau concept that has no first-class Power BI equivalent, especially highlight actions, dual-axis behavior, reference lines, and floating dashboard layout.
4. Define a golden acceptance rubric for the 3-5 real workbooks now. Without that, the team will optimize for file validity rather than analytical fidelity.

## Overall recommendation

The architecture is strong in its separation of stages, bounded AI usage, and test-first posture. The main issue is not orchestration; it is semantic completeness. I would not start implementation until the team tightens the IR around calculation semantics, parameter semantics, and datasource mapping, and aligns the stated success criteria with the actual validation plan.
