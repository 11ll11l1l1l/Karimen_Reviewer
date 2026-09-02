# ALAM Backend Continuous-Improvement Changelog

This file supplements `ALAM_CONTINUOUS_ROADMAP.md` with concise backend iteration handoffs. The shared roadmap remains the source for overall priority and product sequencing.

## 2026-09-03 — Failure-safe incremental article-source convergence

- Agent: Backend Architect / Reliability.
- Problem found: `sync_article()` deleted every existing `article_sources` row before inserting the replacement evidence set. A transient Supabase failure during replacement could temporarily publish a story with zero normalized evidence until reconciliation later repaired it.
- Root cause: first-pass incremental ingestion still used the original delete/rebuild source path even though archive reconciliation had already moved to the safer upsert-before-delete model.
- Decision: make incremental evidence synchronization convergent without a schema migration. Upsert every desired source under the existing `(article_id, url)` uniqueness boundary first, then read the accepted current set and delete only stale source IDs. If any desired upsert fails, abort before stale cleanup so the prior good evidence remains readable.
- Implementation: added `_sync_sources()` in `alam_supabase_ingest.py` and routed normal and dry-run article ingestion through it. Added deterministic fake-PostgREST failure injection in `test_alam_source_sync.py`. CI now executes and syntax-compiles the new regression test.
- Files/schema affected: `alam_app/alam_supabase_ingest.py`, `alam_app/test_alam_source_sync.py`, `.github/workflows/alam-checks.yml`, this changelog, and the shared roadmap. No Supabase migration, RLS change, public credential change, or Job Radar path is involved.
- Validation intent: prove normal source convergence, claim-to-source normalization, injected failure on a later desired source with zero stale-delete operations, retry convergence, explicit empty-source cleanup, and dry-run behavior. The repository workflow remains the authoritative integration gate.
- Rollback: revert the code/test/workflow commits. No database rollback is required because table shape and uniqueness keys are unchanged.
- Remaining risk: `articles` and `article_versions` are still separate writes, so a process can advance the current article row and then fail before version/evidence/topic completion. Archive reconciliation repairs equal-timestamp retries, but database-level integration/failure-injection coverage for that multi-table sequence remains open.
- Recommended next Backend action: add database-level or higher-fidelity failure injection for article-row success followed by version/derived-table failure, then implement structured pre-publication source/evidence quality gates with persisted rejection reasons.
- Recommended Product action: no UI change is required. Evidence rendering should simply become less vulnerable to transient trusted-sync failures.

## 2026-09-03 — Failure-safe article-topic convergence

- Agent: Backend Architect / Reliability.
- Problem found: `_sync_topics()` deleted every existing `article_topics` row before resolving/upserting the replacement topic set. A transient Supabase failure after that delete could temporarily strip a published article of all topic relationships and damage Discover/search/intelligence behavior until a later reconciliation succeeded.
- Root cause: topic synchronization retained the original delete/rebuild implementation even after normalized source reconciliation had moved to the safer upsert-before-delete model.
- Decision: make topic synchronization convergent and failure-safe without a schema migration. Normalize and de-duplicate desired tags by database slug, cap the contract at 30 stable tags, resolve/upsert every desired topic and article-topic join first, then read current joins and remove only stale topic IDs. If any desired topic cannot be resolved, fail closed before stale cleanup.
- Implementation: added `_topic_tags()` and rewrote `_sync_topics()` in `alam_supabase_ingest.py`. Added deterministic fake-PostgREST failure injection in `test_alam_topic_sync.py`. CI now runs the new regression test and syntax-compiles it.
- Files/schema affected: `alam_app/alam_supabase_ingest.py`, `alam_app/test_alam_topic_sync.py`, `.github/workflows/alam-checks.yml`, and this changelog. No Supabase migration, RLS change, public credential change, or Job Radar path is involved.
- Validation intent: test normal convergence, slug de-duplication, explicit old-topic removal after success, injected mid-resolution failure with zero stale-delete operations, successful retry convergence, and intentional cleanup for an explicit empty tag set. The repository workflow remains the authoritative integration gate.
- Rollback: revert the code/test/workflow commits. No database rollback is required because the data model and keys are unchanged.
- Remaining risk: incremental article sources were still delete-before-insert at the time of this iteration; the next backend iteration addressed that path separately.
- Recommended next Backend action: harden the incremental source path so both first-pass ingestion and reconciliation preserve the previous good evidence set under transient failures; then move to structured pre-publication source-quality/rejection gates.
- Recommended Product action: no UI change is required for this iteration. Existing topic-driven discovery should simply become less vulnerable to transient trusted-sync failures.
