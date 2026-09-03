# ALAM Innovation handoff — next verified action focus

## User problem

Article action checklists made follow-through possible, but a returning reader still had to rescan every completed and unfinished item to decide what to do next. On mobile this adds friction precisely where ALAM should convert validated intelligence into a small next action.

## Root cause

The checklist exposed progress but not a deterministic continuation cue. The validated action-plan order and per-step time estimates were already available, so adding generated prioritization would be unnecessary and would weaken the evidence boundary.

## Decision

Make the first unfinished article-supplied step the **Next verified step**. Show remaining step count and total remaining time only when every unfinished step has an explicit valid `time_minutes`. Never infer priority, urgency, duration, or missing instructions.

## Implementation

- Added pure `action_focus()` to `alam_action_checklist.py`.
- The article checklist now surfaces a compact next-step callout before the full checklist.
- The callout uses only the validated action-plan ordering and exact article-supplied action text.
- Remaining effort is summed only when all unfinished steps have explicit valid estimates; otherwise ALAM omits the estimate instead of guessing.
- Fully completed plans retain the existing completion state and do not show a redundant next-step prompt.
- Anonymous browser persistence and changed-step identity behavior are unchanged.

## Mobile behavior

The focus cue is a single native Streamlit info block above the existing one-column checklist. It adds no modal, horizontal layout, navigation layer, or extra interaction target. The full checklist remains immediately visible for context and correction.

## Validation

Focused regressions cover first-unfinished ordering, known remaining effort, missing-estimate fail-closed behavior, fully completed plans, and missing action plans. Existing action extraction, changed-step identity, bounded cookie decoding, and story-page integration tests remain intact.

At run start, current main CI for `2094b5a1516df6e99cd61aa3229466c595eeed5f` was green. Post-change GitHub Actions must complete before this revision is called fully verified.

## Live Supabase observation

Production project `zecztyabmmoqzjumhxxf` had 42 articles, 0 Auth users, 0 Saved rows and 0 preference rows. There was no evidence that the external Auth blocker changed, so it was not revisited. No schema, RLS, service-role or public-content change was required.

## Remaining limitation

Progress is still browser-local and the next-step cue appears only after opening a story. Cross-device continuation should wait for real Auth usage and coordinated RLS-backed action state.

## Recommended next Innovation step

After this interaction is stable, surface genuinely in-progress action plans in a small Today **Continue your actions** lane, without creating urgency from incomplete deadline metadata and without displacing higher-priority breaking/action intelligence.
