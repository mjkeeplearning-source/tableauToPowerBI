# Final Design Review Recommendations

The revised design is materially stronger than the first version. The previous concerns around calculation semantics, parameter intent, datasource mapping, Desktop validation, and workbook status thresholds have been addressed well enough to proceed toward implementation planning.

## Remaining Recommendations

### 1. Fix Stage 8 validation order

Stage 8 currently computes workbook status before emitting `acceptance.json`, but the golden acceptance rubric says rubric failures can force a workbook to `failed`.

Recommendation:
- Run rubric evaluation before final status computation.
- Add `acceptance_failed` as an explicit failed-status trigger in the §8.1 workbook status rule.

### 2. Clarify Tier 2 credential behavior in Desktop validation

Tier 2 connectors are marked as status-unaffected, but credential prompts can affect the Desktop-open gate. The design should state whether Desktop validation runs without refresh, with mocked credentials, or treats expected credential prompts as non-failures.

Recommendation:
- Define Desktop-open gate behavior for credential-required datasources.
- Record expected credential prompts separately from actual model/report load failures.


### 3. Narrow Tier 3 cross-database join support

The current Tier 3 strategy for cross-database joins is still broad. Flattening multiple sources into a single M query is not generally portable across connector pairs.

Recommendation:
- Support cross-database joins only for explicitly tested source-pair combinations.
- Otherwise fall back to separate tables plus relationships, or classify the case as unsupported if grain/cardinality cannot be proven safe.

### 4. Add an MVP cut line

The architecture is solid but ambitious. A defined MVP will reduce implementation risk and make progress measurable.

Recommendation:
- Define v1 around Tier 1/2 connectors, basic visuals, row/aggregate calculations, `FIXED` LOD, basic parameters, and tiled/floating dashboard layout.
- Put table calcs, Tier 3 connectors, mismatched dual-axis visuals, viz-in-tooltip, and advanced parameter formatting behind feature flags or later milestones.

## Overall Recommendation

Proceed with implementation planning after the above edits. The design now has the right architecture: deterministic stages, bounded AI use, enriched IR semantics, explicit connector tiers, and real validation gates. The main remaining work is to tighten execution order, credential assumptions, semantic validation, and MVP scope.
