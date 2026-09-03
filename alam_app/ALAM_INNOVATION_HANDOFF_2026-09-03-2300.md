# ALAM Innovation handoff — article action follow-through

## User problem

ALAM already tells readers what matters and, on stronger Practical records, stores a validated structured `action_plan`. The reader page previously stopped at advice: there was no lightweight way to turn those verified steps into follow-through or remember progress when the reader returned.

## Root cause

Structured action metadata existed in validated article records but the product did not expose completion state. Adding generated tasks would weaken the evidence boundary, while waiting for optional account Auth would leave anonymous readers without the capability.

## Decision

Ship an optional browser-persistent checklist only when the opened article already contains a valid `content.action_plan.steps` list. Do not synthesize or infer missing steps. Keep this iteration schema-free and anonymous-first; authenticated cross-device action state can be coordinated later when production Auth is actually active.

## Implementation

- Added `alam_action_checklist.py` with deterministic extraction, validation, deduplication, bounded browser-cookie persistence and progress helpers.
- Article detail now renders **Action checklist** immediately after the decision-first answer cards.
- Each item displays the article-supplied step name and action, plus `time_minutes` and `done_when` when provided.
- The article-supplied goal and deadline are surfaced above the checklist when available.
- Completion state is stored for up to 32 stories in a dedicated one-year browser cookie. If cookie persistence is unavailable, the current Streamlit session still works without blocking article reading.
- Step identity includes stable story ID + step/action/done-definition. A later story version preserves completion only for genuinely unchanged steps; materially changed instructions receive a new ID and therefore return incomplete.
- No article content, evidence, source, confidence or public-state data is mutated.

## Mobile behavior

The checklist is a single-column native Streamlit control stack, so it avoids horizontal layouts and uses the app's existing accessible checkbox/touch behavior. Progress (`x/y complete`) stays visible above the steps, and there is no modal or forced flow.

## Validation coverage

`test_alam_action_checklist.py` covers:

- extraction of explicit structured action plans,
- fail-closed behavior for missing/unstructured plans,
- invalid/duplicate-step filtering,
- changed-step completion identity,
- corrupt/bounded cookie decoding,
- article-page integration.

The repository's existing `run_regression_suite.py` auto-discovers every `test_*.py`, so no CI architecture change was required.

## Live Supabase observation

Production project `zecztyabmmoqzjumhxxf` had 41 articles, 0 Auth users, 0 Saved rows, 0 preference rows and 0 authenticated app events at inspection time. Several live Practical stories already contain rich validated `action_plan.steps`, confirming immediate user value. The unchanged external Auth blocker was not revisited. No Supabase schema change was made.

## Remaining limitation

Action completion is browser-local, not cross-device. That is intentional while production Auth remains unused. Browser cookie clearing removes local checklist progress. Stories without structured validated action-plan steps show no checklist rather than receiving generated filler.

## Recommended next Innovation step

Once this action-follow-through behavior has real usage, surface unfinished high-urgency/deadline action plans on Today as a small **Continue your actions** lane. When real Auth is active, coordinate an additive RLS-backed action-state table/migration with Stability & Integration so browser progress can merge into an account without weakening anonymous fallback or ownership boundaries.
