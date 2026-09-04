# ALAM Innovation handoff — 2026-09-04 20:00 JST

## User problem

Connected intelligence already explains why another validated ALAM story is related, but the shelf made readers open each candidate before learning whether the connected story had any practical reader impact. On mobile this turns a useful relationship module into avoidable navigation work.

## Root cause

`alam_related_views.py` rendered title, age, shared signals, and the anti-filter-bubble attribution, but no bounded preview from the related record's own decision-oriented metadata.

## Decision

Add one conservative `Why it may matter` preview sourced only from the connected record's explicit scalar `why_it_matters`. Do not synthesize a relationship implication, infer causality, derive advice from tags/titles, or use model memory. Missing, structured, or placeholder values fail closed.

## Implementation

- Added `related_story_decision_preview()` with whitespace normalization, placeholder rejection, scalar-only acceptance, and a 180-character default mobile bound.
- Connected-story cards now show the preview beneath the shared-signal explanation when defensible.
- Existing evidence-constrained ranking, explicit connection tags, diversity insertion, and full-width open-story control are unchanged.
- Added focused regressions for valid, missing, structured, placeholder, and bounded-long-text states.

## Files affected

- `alam_app/alam_related_views.py`
- `alam_app/test_alam_related_views.py`
- this handoff

No schema, RLS, Auth, telemetry, sync, public article content, or service-role behavior changed.

## Mobile behavior

The preview is a short indented decision cue within the existing card and is capped before rendering. Mobile typography is slightly tightened; the existing full-width `Open connected story` touch target remains unchanged. Zero related stories still render no shelf, and records without a defensible preview retain the previous compact card.

## Validation

- Pre-change main CI at `b00ca34b6a1819334a3b5ee66ee47323b8926ec9` was green.
- Focused regression coverage was committed at `66a68ba8126ba57cc302392765408481357f496c`.
- Post-change GitHub workflows were queued/running when this handoff was written; do not call the final gate green until they complete.
- Live Supabase project `zecztyabmmoqzjumhxxf` was inspected before implementation: 63 public articles, 0 Auth users. The unchanged external Auth blocker was not revisited.

## Remaining limitation

This preview intentionally does not answer how the two stories affect each other. ALAM only has defensible shared-signal evidence here; a cross-story causal implication would require explicit relationship evidence rather than prose generation.

## Recommended next step

After CI is green, continue article-detail usefulness with another isolated evidence-backed improvement rather than expanding this shelf vertically. A later relationship feature should prefer explicit typed/evidenced relationships when the data contract supports them.