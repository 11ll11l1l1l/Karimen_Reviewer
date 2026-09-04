# ALAM Innovation handoff — 2026-09-04 21:00 JST

## User problem
Connected intelligence already explained why a related story was linked and, when available, why it may matter. For actionable Practical Japan connections, readers still had to open the story to discover whether the validated record said APPLY, PREPARE, AVOID, WATCH, etc. or carried an explicit timing/deadline.

## Root cause
`alam_related_views.py` intentionally rendered only relationship signals plus `why_it_matters`. The existing v5 Practical contract already carries bounded `action`, `deadline`, and `when` metadata, but the connected-story shelf did not use it.

## Decision
Add compact, evidence-preserving Action and Timing cues to connected Practical stories. Do not infer urgency, eligibility, action labels, dates, or deadlines from prose. Only the contract's allowed action labels are rendered. Structured, placeholder, malformed, non-Practical, and unknown values fail closed.

## Implementation
- Added `related_story_action_cues()` in `alam_related_views.py`.
- Practical connected cards can show small `Action · PREPARE` / `Timing · September 30, 2026` chips.
- Refactored scalar sanitization into `_safe_scalar()` so the existing Why-it-may-matter preview and new cues share the same placeholder/structured-value safety boundary.
- Added focused regressions in `test_alam_related_views.py` for valid Practical cues and malformed/non-Practical fail-closed states.
- No ranking change: related stories still must pass `connected_stories()` shared-signal evidence logic, including the existing anti-echo-category insertion.

## Mobile behavior
Cues wrap rather than force horizontal overflow. Text remains compact and cards retain the existing full-width Open connected story control. No additional shelf depth or infinite-scroll behavior was added.

## Validation
- Exact target files were re-fetched from current `main` immediately before each write.
- Live Supabase project `zecztyabmmoqzjumhxxf`: 64 public articles; Auth users remain 0. No schema/RLS/Auth change was required, so the unchanged external Auth blocker was not revisited.
- Feature commit: `b89e6eff930fe59784fcd543b6eec93ff01913a2`.
- Regression commit: `a6f7304c54a2d736f03569f69f6f1dead8c363e1`.
- ALAM app checks for the regression head were queued at handoff time; do not claim the full production-data/compile/Streamlit gate green until that workflow completes successfully.

## Remaining limitation
A connected Practical story with no explicit allowed action or scalar deadline/timing correctly shows no action cue. This is preferable to manufacturing urgency from its title, tags, or prose.

## Recommended next step
After CI is green, consider whether connected stories with explicit saved-update/change metadata deserve a similarly bounded `Changed` cue. Keep that separate from action cues so relationship context, change state, and advice semantics do not blur together.
