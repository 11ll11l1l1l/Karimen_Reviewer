# ALAM.ph Continuous Improvement Roadmap

This is the shared planning and handoff document for ALAM.ph continuous development. Backend/reliability and product/UX work must inspect the newest `main` branch and this file before changing code. Distinguish repository implementation, CI verification, and external production activation.

## Product contract

ALAM.ph is a mobile-first intelligence and action product for Filipino readers. It should answer: What happened? Why does it matter? What changed? What should I do, prepare for, avoid, or watch? How strong is the evidence? What do other agents think?

Permanent constraints:

- Global Engineering Job Radar is private/chat-only and must never enter public ALAM or public Supabase content tables.
- Public ALAM content must represent real events with usable real sources. Never add dummy/sample/fake stories to fill screens.
- GitHub JSON is the human-readable audit trail. Supabase is the durable query/read/state layer and may be rebuilt from that audit trail only through explicitly designed trusted paths.
- Public Streamlit uses only public/publishable Supabase credentials. Service-role/secret credentials are trusted automation only.
- Prefer real relevant images, then official images, then suitable sourced web images; generated editorial imagery is fallback-only and must not masquerade as documentary photography.
- Taglish should be natural and broadly understandable.
- Optimize for usefulness, trust, accountability, and action rather than engagement addiction.

## A. Completed and verified in the repository

- Mobile Streamlit app with Today, Discover, Action, Market, More, Weekly, Search, Saved, Predictions, Settings, article detail, time-aware visual system, and editorial-image fallback.
- Decision-first Today and article-page hierarchy.
- Saved-story version awareness and updated-since-saved behavior where version state exists.
- Detailed ALAM Panel presentation preserving substantive SUPPORT/CHALLENGE/MIXED reasoning.
- Evidence view with source count, official/primary count, publisher/domain diversity, classified-claim coverage, and source-to-claim support. Diversity is explicitly not treated as proof of editorial independence.
- Supabase-first public article loading with local JSON migration fallback.
- Supabase hydration for sources, history, comments, wisdom, predictions, relationships, and database health.
- Core v5 Supabase schema with RLS plus non-destructive compatibility bridge for the earlier UUID schema.
- Trusted GitHub JSON -> Supabase incremental ingestion for Discover, Practical, Market/reflection, Trend, comments, wisdom, sources, topics, predictions, versions, and explicit shared-signal relationships.
- Trusted sync wrapper records sanitized provenance/statistics in private `agent_runs`; service credentials remain server-side.
- GitHub Actions serializes Supabase sync jobs to avoid ordinary overlapping dispatches.
- Self-healing reconciliation deterministically converges current articles, numbered history, sources, topics, and predictions from the GitHub audit archive.
- Reconciliation repairs partial-write cases where the current article advances but derived tables fail.
- Source reconciliation uses upsert-before-delete to avoid deliberately erasing the prior good evidence set before desired rows are accepted.
- Exact duplicate audit payloads are removed before deterministic version numbering.
- **Fail-closed chronology preflight:** materially different versions of one stable article ID may no longer share the same explicit `created_at`. The trusted sync validates the complete public archive before incremental content writes and aborts on ambiguity rather than letting archive path ordering choose the production current version.
- Legacy records with no explicit `created_at` remain compatible; path ordering is retained only as a deterministic fallback for those historical shapes.
- Reconciliation is scoped to the four public ALAM article directories, so private Job Radar data is unreachable by construction.
- A public-safe sync-health RPC contract exists in migration `005_public_sync_health.sql`; direct public reads of `agent_runs` remain blocked by RLS.
- Backend readiness classification distinguishes disconnected, diagnostics unavailable, never synchronized, running, failed, partial, stale sync, local fallback, synchronized-empty, unknown status, and ready.
- Settings renders one calm Data status verdict from that classifier and keeps raw private workflow/error metadata out of the public UI.
- CI gates reconciliation/chronology, Evidence, backend readiness, product readiness, syntax, production data, image behavior, dependency installation, and Streamlit startup health.

## B. In progress / requires production verification

### Supabase production cutover

Required evidence before declaring cutover complete:

- Production `articles` contains published stable text IDs.
- Related source/history/comment/wisdom/prediction/relationship rows are mirrored where applicable.
- A trusted `agent_runs` row shows successful sync with reconciliation totals.
- Migration `005_public_sync_health.sql` has been applied to production.
- Settings reports Supabase as the actual live feed and a healthy readiness state.
- Evidence/history still render after cutover.
- No private Job Radar data exists in public ALAM tables.

### Deployment readiness

- CI remains green after backend/product changes.
- Streamlit startup health remains green.
- Supabase problems degrade to explicit diagnosable states rather than crashes or false healthy reporting.

## C. Next highest-priority improvements

### P0 — Reliability / data integrity

1. Apply/verify migration `005_public_sync_health.sql` in production, run a real trusted sync, and verify Settings readiness.
2. Add database-level failure-injection coverage for article-row success followed by version/source failure.
3. Add stronger source/evidence quality gates before publication with structured rejection reasons.
4. Add stale/outdated lifecycle checks and safe story-expiration rules.
5. Consider a separately reviewed policy for orphan Supabase rows absent from GitHub; do not delete broadly by default.

### P1 — Core reader/product quality

1. Keep Today decision-first and prevent secondary modules from making the page endless.
2. Preserve detailed cross-agent reasoning, uncertainty, implications, and disagreement.
3. Continue refining material-change notices for saved stories/history.
4. Revisit fallback/stale-data communication only after real production readiness telemetry exists.
5. Refine Evidence only when backend metadata can improve trust without inventing source independence.

### P1 — Persistent user state

1. Select an auth/account approach without a login wall.
2. Keep anonymous use fully functional.
3. Sync authenticated bookmarks, preferences, reads, feedback, inbox, and briefing state through RLS-protected tables.
4. Preserve browser-local state as anonymous/offline fallback.

### P2 — Intelligence layer

- Improve Connect the Dots using explicit relationships/evidence only; shared occurrence is not causality.
- Surface meaningful agent confidence differences/disagreement.
- Expand prediction accountability with status-history and evidence-based resolution.
- Generate daily/weekly briefings only from validated ALAM stories.
- Add saved-story-change notifications only after persistent identity exists.

### P2 — Performance / accessibility

- Audit Supabase query count/cache boundaries.
- Avoid repeated hydration queries and oversized rerenders.
- Consolidate conflicting CSS only with regression coverage.
- Improve touch targets, labels, contrast, mobile density, and keyboard behavior.

### P3 — Admin / operations

- Trusted admin view for sync runs, rejected candidates, failure reasons, stale stories, merge/update status, and media issues.
- Safe publish/unpublish/merge/regenerate-image paths through trusted backend operations.
- Recovery/rollback documentation for schema and mirror failures.
- Correction history/accountability for materially changed published stories.

## D. Blocked / manual-owner actions

These require external credentials/consoles and must not be falsely marked complete from repository changes alone:

- Run `supabase/migrations/005_public_sync_health.sql` in production Supabase SQL Editor.
- Future Supabase SQL execution when migrations require it.
- GitHub Actions secret creation/rotation for `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`.
- Streamlit Cloud secret creation/rotation for `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY`.
- Manual workflow dispatch when available connector actions cannot trigger Actions.
- Streamlit Cloud deployment configuration or DNS/domain operations outside repository control.

## E. Longer-term opportunities

- Installable/PWA-quality experience where Streamlit allows it.
- Offline access for selected saved stories.
- Explicit topic preferences with decaying weights and anti-filter-bubble discovery insertion.
- Saved collections such as Read Later, Japan, Money, Ideas, Important.
- Evidence-backed relationship types such as contributes_to, contradicts, affects, and shared_signal.
- Quality dashboards for source diversity, correction rate, duplicate rejection, agent usefulness, sync reliability, and prediction calibration.
- Selective notifications rather than engagement spam.

## F. Known risks / technical debt

- Multiple visual/CSS modules remain layered in install order.
- Browser-local Saved/preferences remain primary user state until auth synchronization exists.
- Local JSON fallback protects cutover but can eventually mask stale database synchronization; narrow it only after Supabase stability is proven.
- Production migration 005 plus a real trusted sync are still required before repository readiness logic proves live cutover.
- The six-hour threshold is operational **sync freshness**, not a claim that article facts expire after six hours.
- Historical audit records may lack current v5 fields. The chronology preflight deliberately does not treat missing `created_at` as an explicit timestamp conflict.
- Same explicit timestamp + different payload now fails trusted sync before content writes. Correct the GitHub audit timestamp/payload rather than bypassing this guard.
- Reconciliation does not delete unrelated Supabase articles absent from GitHub; broad orphan cleanup requires a separate reviewed policy.
- Topic reconciliation still uses delete/rebuild rather than source-style upsert-before-delete.
- Supabase reconciliation is service-role-only; missing trusted credentials stop repair before database content writes.
- Evidence source-group diversity cannot establish editorial independence.
- Public sync-health intentionally exposes no raw errors/workflow metadata; operator diagnosis belongs in trusted logs/admin tooling.

## G. Verification evidence / development log

### 2026-09-02 — Supabase foundation

- Existing UUID-era ALAM schema conflicted with v5 text IDs.
- Added a non-destructive legacy bridge and fresh v5 tables; user confirmed SQL completion.

### 2026-09-02 — Decision-first product passes

- Tightened Today and article reading around decisions/actions.
- Added update-aware Saved behavior.
- Expanded substantive Panel/cross-agent reasoning.

### 2026-09-03 — Backend self-healing mirror

- Problem: partial incremental writes could leave derived Supabase state incomplete on equal-timestamp retry.
- Change: deterministic reconciliation from GitHub audit archive after normal ingestion.
- Security: public article directories are allow-listed; Job Radar is unreachable.
- Remaining risk: no DB-level failure injection yet; topics still delete/rebuild.

### 2026-09-03 — Evidence trust experience

- Problem: flat evidence presentation forced readers to infer trust/mapping.
- Change: conservative Evidence Health and source-to-claim presentation without invented independence scores.

### 2026-09-03 — Sanitized Supabase readiness contract

- Problem: “Supabase connected” did not prove trusted synchronization or actual feed cutover.
- Change: narrow SECURITY DEFINER sync-health RPC plus pure Python readiness classifier.
- Security: `agent_runs` remains private; public output excludes raw errors, workflow/repository identifiers, credentials, and Job Radar state.
- Remaining action: production migration 005 plus real trusted sync.

### 2026-09-03 — Trusted sync status UX

- Problem: Settings forced users/operators to infer health from multiple independent metrics.
- Change: one calm Data status verdict backed by the backend readiness classifier, with detailed mirror diagnostics retained separately.

### 2026-09-03 — Fail-closed archive chronology

- Agent: Backend Architect.
- Problem found: two materially different records for the same stable story could carry the exact same explicit `created_at`; reconciliation would resolve the tie by archive path, which is reproducible but not valid chronological evidence.
- Root cause: deterministic ordering had been treated as sufficient for all timestamp ties, and validation happened only during reconciliation after incremental ingestion had already been allowed to write.
- Decision: distinguish harmless exact duplicates from ambiguous material ties. Fail trusted sync closed when distinct payloads share an explicit timestamp. Preserve historical records with no explicit timestamp for backward compatibility.
- Implementation: `ArchiveConflictError`, explicit timestamp normalization, `_validate_archive_chronology()`, and `prepare_public_archive()` in `alam_supabase_reconcile.py`. `alam_supabase_sync_job.py` now preflights the complete public archive before incremental ingestion and reuses the validated snapshot for reconciliation.
- Files/schema affected: `alam_app/alam_supabase_reconcile.py`, `alam_app/alam_supabase_sync_job.py`, `alam_app/test_alam_supabase_reconcile.py`, and this roadmap. No database migration or RLS change.
- Security/rollback: no public access was widened. On conflict, only the trusted run audit record may be written; public content mutation is stopped. GitHub audit files remain the rollback/source-of-truth layer.
- Validation performed: deterministic regression tests cover exact duplicates, normal chronology, explicit equal-time conflict rejection through both helper and public preflight entry point, and backward compatibility for missing timestamps. Full ALAM CI is the release gate.
- Remaining limitation/risk: malformed explicit timestamp strings still use the existing parser fallback semantics; stronger schema validation can be considered with source-quality gates. Database-level partial-write failure injection remains open.
- Recommended next action: after CI confirms this iteration, Backend should move to database-level failure injection or pre-publication source/rejection quality gates. Product requires no UI change for this guard because audit conflicts are operator failures, not reader states.

## H. Agent handoff template

Every material iteration should leave enough context for the other agent to continue without rediscovery:

- Date/time:
- Agent:
- Problem found:
- Root cause:
- Decision:
- Implementation:
- Files/schema affected:
- Validation performed:
- Current CI/deployment status:
- Remaining limitation/risk:
- Recommended next action:
