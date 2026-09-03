# ALAM Innovation handoff — cross-lens recovery after an unresolved action plan

## User problem

The previous recovery path correctly routed a Partly/No action outcome into grounded Ask ALAM, but its title-based query could rank the originating story first. That risked presenting the same plan the reader had just reported as insufficient as though it were new help.

## Root cause

The recovery route supplied a grounded topic but did not distinguish the already-tried evidence lens from genuinely additional validated evidence.

## Decision

When recovery starts from a known ALAM category, preselect the other ALAM lenses in Ask ALAM. This excludes the originating story by construction and asks the existing deterministic retriever for additional validated context. If the other lenses contain no relevant record, Ask ALAM must keep its existing explicit insufficient-evidence result rather than repeat the failed plan or generate advice.

## Implementation

- `alam_action_checklist.py` adds a small category-to-lens contract and deterministic `recovery_lenses()` helper.
- `open_grounded_recovery()` now preselects every validated lens except the originating story lens.
- The recovery explanation tells the reader that ALAM will check other lenses first and will say when no additional validated evidence exists.
- Unknown/legacy categories retain the prior safe behavior rather than guessing a category.
- No public article content, schema, migration, RLS, Auth, telemetry taxonomy, service-role path, or model generation was changed.

## Mobile behavior

The existing single full-width recovery button is preserved. No new control group or extra article-detail density was introduced; the differentiation happens in the destination's existing lens filter.

## Validation

`test_alam_action_outcome.py` now verifies Action -> Discover/Market/Trends recovery, Discover -> Action/Market/Trends recovery, unknown-category fallback, exact route/query state, and the existing no-topic fail-closed behavior.

Pre-change main was `c809ca26984c6e9205adf5a18346ca501e224f40` and its ALAM app checks were green. Post-change CI must be read from the workflow attached to the final revision.

## Live Supabase observation

A fresh aggregate read against required project `zecztyabmmoqzjumhxxf` was attempted. The first query exposed that older assumed account-state table names are not present; a narrower aggregate query was then blocked by the connector safety layer. No production counts are inferred. No evidence indicated that the external Auth activation blocker changed, so it was not revisited.

## Remaining limitation

Cross-lens recovery intentionally favors genuinely different evidence, so a useful second story from the same originating category is not considered during this recovery pass. This is preferable to falsely presenting the already-tried plan as new help; future retrieval can support explicit story-ID exclusion if that can be added without weakening deterministic evidence boundaries.

## Recommended next Innovation step

Add explicit retrieval-context exclusions to Ask ALAM only if they remain local, transparent, deterministic, and regression-tested. That would allow recovery to search all categories while excluding exactly the already-tried story.
