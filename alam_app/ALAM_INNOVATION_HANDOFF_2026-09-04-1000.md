# ALAM Innovation Handoff — 2026-09-04 10:00 JST

## User problem
Today already gives one materially changed Saved story the REVIEW slot in the three-line briefing, but a returning reader with several changed Saved stories can see only one of them there. That makes useful return behavior incomplete: the reader can miss other saved decisions whose evidence changed.

## Root cause
`alam_daily_brief.render_daily_brief()` selected a single changed Saved story for REVIEW and rendered one review CTA. The existing `localstate.saved_has_update` material-change detector already knew about all changed Saved stories, but Today did not expose the remainder.

## Decision
Add a deterministic, retrieval-only **More Saved changes** queue directly below the three-line briefing. Reuse the existing material-change predicate and personalized ranking; do not synthesize new claims, mark ordinary saved stories as changed, or add schema/auth dependencies.

## Implementation
- Added `select_saved_updates()` in `alam_daily_brief.py`.
- It filters only records already reported as materially changed by `saved_has_update`, ranks those changed Saved stories by existing personal relevance/feed score, deduplicates stable story IDs, and caps the queue.
- The primary REVIEW story remains in `Today in 3 lines`; the queue excludes that primary story and exposes up to two additional changed Saved stories.
- Each additional update shows the existing deterministic `intelligence.change_snapshot()` copy when available and a full-width **Review update** CTA into the story detail.
- No public article content, AI generation, schema, RLS, Auth, service-role, or telemetry change.

## Mobile behavior
Additional changed stories are stacked vertically with full-width review buttons rather than compressed into columns. Zero or one changed Saved story adds no extra section, so sparse states stay compact.

## Validation
Focused regression coverage in `test_alam_daily_brief.py` now checks:
- multiple materially changed Saved stories are ranked and returned;
- stable story IDs are deduplicated;
- ordinary/non-changed stories never fill the queue;
- zero-change, one-change, and `limit=0` states fail closed/behave compactly;
- existing three-line briefing and semantic importance regressions remain covered.

GitHub ALAM app checks were triggered for the implementation/test commits. At handoff-write time the final test commit workflow was still in progress, so completion is not claimed here until the run is re-read.

Live Supabase project `zecztyabmmoqzjumhxxf` was checked during the run: 56 articles, 0 Auth users. There is no evidence that the external optional-Auth blocker changed, so it was not revisited. An attempted query for a non-existent `public.usefulness_events` table failed safely and caused no mutation.

## Remaining limitation
Saved-change durability remains limited by the existing anonymous/browser-vs-account state model. This feature deliberately does not invent cross-device persistence while Auth remains externally blocked.

## Recommended next step
After this queue proves useful, measure review/open completion through the existing approved usefulness-event path if/when the current telemetry table/API contract is confirmed from repository/live schema. Do not create a new analytics schema solely for this surface.
