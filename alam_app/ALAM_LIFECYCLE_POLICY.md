# ALAM.ph Story Lifecycle Safety Policy

This document extends the shared `ALAM_CONTINUOUS_ROADMAP.md` lifecycle work and is the backend handoff for the current iteration.

## Completed and verified in this iteration

- Lifecycle aging remains evidence/editorial-state driven rather than clock driven. The six-hour Supabase freshness threshold is operational health only and never expires article facts.
- `FADING` and `RESOLVED` are treated as explicitly retired lifecycle states for reactivation safety.
- A later version of the same stable story ID may return to `NEW`, `DEVELOPING`, or `CONFIRMED` only when `content.lifecycle.reactivation_reason` contains a substantive non-empty explanation.
- Trusted Supabase synchronization runs this rule against the complete chronology/evidence-preflighted public archive before incremental public content mutation.
- Unsafe reactivation is represented through the existing `PublicationQualityError` rejection contract and is persisted best-effort to the RLS-private `rejected_candidates` diagnostics table.
- The public Job Radar boundary is unchanged: only Discover, Practical, Market/reflection, and Trend archive inputs reach this preflight.

Example of a legitimate reopening:

```json
"content": {
  "lifecycle": {
    "reactivation_reason": "The ministry reopened consultation after publishing a materially revised draft."
  },
  "change_summary": {
    "previous": "The consultation had closed and ALAM marked the story resolved.",
    "now": "A revised draft reopened consultation.",
    "why_change_matters": "Readers have a new deadline and the previous settled state no longer applies."
  }
}
```

Do not create a new stable story ID merely to bypass a retired-state reactivation guard when it is still materially the same story.

## In progress

- Production Supabase cutover still requires migration `005_public_sync_health.sql` plus a real trusted sync/readiness verification.
- This iteration prevents accidental resurrection but does not yet decide how `FADING` stories should be suppressed from main-feed ranking while remaining reachable from Saved/history/detail surfaces.

## Next highest-priority improvements

1. Design route-safe treatment for `FADING`: no longer main-feed active, but still historically/read-later accessible. This likely requires a backend query contract plus Product Builder coordination rather than changing `articles.status` to `archived`, because current public RLS exposes only published stories.
2. Define explicit expiration only for stories that have a defensible event/deadline validity boundary. Do not derive expiry from `created_at` age.
3. Consider a separately reviewed orphan-Supabase policy; never introduce broad deletion by default.

## Blocked/manual-owner actions

- Apply/verify `supabase/migrations/005_public_sync_health.sql` in production.
- Run a trusted production Supabase sync with service credentials and confirm Settings readiness, mirror coverage, and absence of Job Radar data.

## Longer-term opportunities

- Persist a trusted stale-story diagnostic/report for admin use once lifecycle semantics are mature.
- Add explicit validity/deadline metadata only where agents can cite the underlying date or authority.
- Track correction/reactivation rates as an accountability metric rather than an engagement metric.

## Known risks / technical debt

- `FADING` currently remains publication-status `published`; therefore the current generic feed query can still return it. Automatically mapping `FADING` to database `archived` would make it disappear behind current RLS and could break Saved/detail/history access, so that shortcut is intentionally not taken here.
- `RESOLVED` is not automatically hidden. A resolved outcome can remain valuable intelligence; retirement from a main feed and public availability are separate concerns.
- The reactivation reason proves editorial intent, not factual correctness. Normal evidence/FACT/source gates still apply independently.
- A malicious or poor-quality agent could write a superficial reason; substantive quality remains a research/review concern. The hard gate guarantees that reactivation cannot be silent.

## Verification evidence

- `alam_app/test_alam_lifecycle.py` covers active progression, retirement, FADING and RESOLVED silent-reactivation rejection, explicit reopening, whitespace bypass rejection, non-terminal CONFIRMED->DEVELOPING movement, and timestamp ordering.
- `.github/workflows/alam-checks.yml` executes and syntax-compiles the lifecycle module/test alongside all existing ALAM regressions and the Streamlit health smoke test.
- `.github/workflows/alam-supabase-sync.yml` now triggers when the lifecycle policy module changes.

## Handoff

Problem found: lifecycle state existed in the v5 contract and database, but trusted ingestion did not protect a retired story from later being silently reintroduced as active.

Root cause: chronology validation proved which version was later, while evidence validation proved minimum sourcing; neither validated the semantic transition between lifecycle versions.

Backend decision: protect explicit retirement/reopening rather than inventing a time-to-live. Require an auditable reopening reason and fail before public content mutation when it is absent.

Files affected: `alam_app/alam_lifecycle.py`, `alam_app/alam_supabase_sync_job.py`, `alam_app/test_alam_lifecycle.py`, `.github/workflows/alam-checks.yml`, `.github/workflows/alam-supabase-sync.yml`, and this roadmap extension. No schema/RLS migration is required.

Recommended Agent B next step: when product work touches lifecycle presentation, distinguish “not active in the main feed” from “deleted/unavailable.” Preserve Saved/history/detail access for retired stories and never infer staleness solely from article age.
