# ALAM Backend Continuous-Improvement Changelog

This file supplements `ALAM_CONTINUOUS_ROADMAP.md` with concise backend iteration handoffs. The shared roadmap remains the source for overall priority and product sequencing.

## 2026-09-03 — Failure-safe article-topic convergence

- Agent: Backend Architect / Reliability.
- Problem found: `_sync_topics()` deleted every existing `article_topics` row before resolving/upserting the replacement topic set. A transient Supabase failure after that delete could temporarily strip a published article of all topic relationships and damage Discover/search/intelligence behavior until a later reconciliation succeeded.
- Root cause: topic synchronization retained the original delete/rebuild implementation even after normalized source reconciliation had moved to the safer upsert-before-delete model.
- Decision: make topic synchronization convergent and failure-safe without a schema migration. Normalize and de-duplicate desired tags by database slug, cap the contract at 30 stable tags, resolve/upsert every desired topic and article-topic join first, then read current joins and remove only stale topic IDs. If any desired topic cannot be resolved, fail closed before stale cleanup.
- Implementation: added `_topic_tags()` and rewrote `_sync_topics()` in `alam_supabase_ingest.py`. Added deterministic fake-PostgREST failure injection in `test_alam_topic_sync.py`. CI now runs the new regression test and syntax-compiles it.
- Files/schema affected: `alam_app/alam_supabase_ingest.py`, `alam_app/test_alam_topic_sync.py`, `.github/workflows/alam-checks.yml`, and this changelog. No Supabase migration, RLS change, public credential change, or Job Radar path is involved.
- Validation intent: test normal convergence, slug de-duplication, explicit old-topic removal after success, injected mid-resolution failure with zero stale-delete operations, successful retry convergence, and intentional cleanup for an explicit empty tag set. The repository workflow remains the authoritative integration gate.
- Rollback: revert the code/test/workflow commits. No database rollback is required because the data model and keys are unchanged.
- Remaining risk: `sync_article()` still uses delete-before-insert for its *incremental* `article_sources` write before the later reconciliation pass repairs it. Reconciliation itself is source-safe. A future backend pass should either route incremental source writes through the convergent helper or add direct failure-injection coverage for article-row/version/source sequencing.
- Recommended next Backend action: harden the incremental source path so both first-pass ingestion and reconciliation preserve the previous good evidence set under transient failures; then move to structured pre-publication source-quality/rejection gates.
- Recommended Product action: no UI change is required for this iteration. Existing topic-driven discovery should simply become less vulnerable to transient trusted-sync failures.
