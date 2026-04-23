# Final MVP Design Review Recommendations

The design now has a clear MVP boundary and is close to implementation-ready. The prior recommendations around validation order, credential behavior, Tier 3 narrowing, and MVP scope have been incorporated. The remaining items are consistency and gate-definition fixes rather than architecture blockers.

## Remaining Recommendations

### 1. Resolve symbol map scope

The MVP section includes `symbol map` in v1, but the main coverage table classifies symbol map as partial/degraded.

Recommendation:
- Either move `symbol map` to the v1 deferred list, or update the coverage table to classify symbol map as supported.
- Prefer deferring it unless there is already a tested PBIR visual mapping.

### 2. Make synthetic DAX semantic probes explicit

The acceptance rubric includes DAX probe checks for real workbooks, but the testing strategy should also require expected-value DAX probes for synthetic fixtures.

Recommendation:
- Add synthetic DAX execution probes for v1 calculation types: row, aggregate, `FIXED` LOD, parameters, and filter-sensitive measures.
- Keep DAX parsing as a syntax check, but do not treat parsing alone as semantic validation.

### 3. Add explicit status handling for deferred features

The current v1 rule routes disabled feature-flag items into `unsupported[]`, but that may not reliably change status if thresholds are not crossed.

Recommendation:
- Add an explicit `partial` trigger for any `deferred_feature_*` item encountered.
- Add a `failed` trigger when a deferred datasource or deferred required calculation blocks a rendered page or required rubric item.

### 4. Clarify full-roadmap corpus versus v1 CI corpus

The testing section still describes a ~50-fixture full synthetic corpus, while the MVP section describes ~30 v1-only fixtures.

Recommendation:
- State that §9 describes the full-roadmap corpus.
- State that §16 defines the v1 CI subset.
- Keep deferred-feature fixtures present but skipped unless the corresponding feature flag is enabled.

### 5. Fix minor section reference typo

The MVP dashboard row references `§Stage 5`, which is not a valid section reference.

Recommendation:
- Replace `§Stage 5` with `Stage 5` or `§6 Stage 5`.

## Overall Recommendation

After these small edits, the design is ready for implementation planning. The MVP is appropriately scoped: Tier 1/2 connectors, basic marks, row/aggregate/FIXED LOD calculations, basic parameters, dashboard layout, core filters, and all seven validation layers. The next major risk is no longer design completeness; it is building reliable fixtures and validating generated PBIR/TMDL against real Power BI tooling.
