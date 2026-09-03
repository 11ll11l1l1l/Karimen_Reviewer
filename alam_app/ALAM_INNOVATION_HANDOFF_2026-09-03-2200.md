# ALAM Innovation handoff — 2026-09-03 22:00 JST

## User problem
Connected intelligence could be evidence-grounded yet still become a narrow echo shelf when the highest-ranked related stories all came from one ALAM category.

## Decision
Keep the existing deterministic shared-signal ranking as the authority, but when a full related-story shelf is concentrated in one category, reserve only its final slot for the strongest already-connected candidate from another category. Never introduce an unrelated record merely to create diversity.

## Implementation
`alam_related_views.related_story_candidates` now requests a bounded candidate pool from the existing `connected_stories` evidence gate. If the normal top-N has one category and a lower-ranked evidence-connected candidate from another category exists, only the last slot changes. Already-diverse shelves, sparse shelves, and zero/one-story states remain unchanged. The reader sees a concise Different lens label and an explicit reminder that shared signals are context, not causation.

## Mobile behavior
The existing stacked connected-story cards and full-width touch targets are preserved. The new Different lens explanation is a short inline label, so it does not add another navigation control or materially increase mobile interaction cost.

## Validation
Focused regression coverage now checks: unrelated-story rejection, explicit connection tags, zero/one-story safety, concentrated-shelf diversification, and preservation of already-diverse ranking. ALAM CI was green on the inspected pre-change main (`720f818...`). The post-change workflow must be allowed to finish before final green status is claimed.

## Supabase / Auth
Live project `zecztyabmmoqzjumhxxf` was inspected this run: 39 articles, 0 Auth users, 0 saved rows, 0 authenticated reads, 0 preference rows. There is no evidence the external Auth activation blocker changed, so it was not revisited. No schema change was needed for this feature.

## Remaining limitation
Category is a coarse diversity proxy. The feature does not infer ideology, sentiment, or causal disagreement, and it deliberately refuses to broaden the shelf when no evidence-connected alternative exists.

## Recommended next Innovation step
Add optional article action follow-through using validated action/checklist fields, with anonymous browser persistence first and RLS-backed account persistence only when Auth is genuinely active.