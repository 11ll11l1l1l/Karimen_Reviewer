# ALAM.ph Continuous Improvement Roadmap

This is the shared planning and handoff document for ALAM.ph continuous development. Backend/reliability and product/UX work must inspect the newest `main` branch and this file before changing code. Do not mark a capability complete merely because code exists; distinguish repository implementation, CI verification, and external production activation.

## Product contract

ALAM.ph is a mobile-first intelligence and action product for Filipino readers. It should answer quickly and credibly: What happened? Why does it matter? What changed? What should I do, prepare for, avoid, or watch? How strong is the evidence? What do the other agents think, including meaningful disagreement?

Permanent constraints:

- Global Engineering Job Radar is private/chat-only and must never enter the public ALAM app or public Supabase content tables.
- Public ALAM content must represent real events with usable real sources. Never add fake/sample stories merely to populate a screen.
- GitHub JSON is the human-readable agent/audit trail. Supabase is the durable query/read/state layer and may be rebuilt from that audit trail where explicitly designed.
- Public Streamlit code uses only public/publishable Supabase credentials. Service-role/secret credentials are trusted automation only.
- Prefer real relevant images, then official images, then suitable sourced web images. Generated editorial imagery is fallback-only and must not masquerade as documentary photography.
- Taglish should be natural and broadly understandable.
- Optimize for usefulness, trust, accountability, and action rather than engagement addiction.

## A. Completed and verified in the repository

- Mobile Streamlit app with Today, Discover, Action, Market, More, Weekly, Search, Saved, Predictions, Settings, article detail, time-aware visual system, and editorial-image fallback.
- Decision-first Today hierarchy and decision-first article-page orchestration are on `main`.
- Saved-story version awareness is on `main`, including updated-since-saved behavior where version state is available.
- Detailed ALAM Panel/cross-agent comment presentation preserves substantive SUPPORT/CHALLENGE/MIXED reasoning rather than reducing comments to one-line reactions.
- Evidence view surfaces attached-source count, primary/official count, publisher/domain diversity, classified-claim coverage, and source-to-claim support before the long source list. Source-group diversity is explicitly a heuristic, not proof of independent confirmation.
- Supabase public-client module and Supabase-first article loading with local JSON migration fallback.
- Supabase source hydration, public article history, public cross-agent comments, daily wisdom, predictions, article relationships, and database-health reads.
- Core v5 Supabase schema with RLS, article/source/history/comment/run/topic/media/user-state/briefing/prediction/relationship/event tables.
- Non-destructive bridge for the earlier UUID ALAM schema; user confirmed the compatibility/full setup SQL ran successfully on 2026-09-02.
- Trusted GitHub JSON -> Supabase incremental ingestion for public Discover, Practical, Market/reflection, Trend, comments, wisdom, sources, topics, predictions, versions, and explicit shared-signal relationships.
- Trusted sync wrapper records sanitized GitHub run provenance and ingestion totals in `agent_runs`; service credentials remain server-side.
- GitHub Actions serializes ALAM Supabase synchronization with a concurrency group so ordinary workflow dispatches do not overlap.
- Self-healing reconciliation (`alam_supabase_reconcile.py`) deterministically converges public current articles, numbered article history, normalized current sources, topics, and predictions from the GitHub audit archive after incremental ingestion.
- Reconciliation repairs the partial-write failure where `articles` advances but history/sources/topics fail and an equal-timestamp retry would otherwise skip the record.
- Source reconciliation uses upsert-before-delete to avoid intentionally erasing the previous good evidence set before desired sources are accepted.
- Exact duplicate audit payloads are deduplicated before deterministic version numbering; equal timestamps use archive path ordering as a stable tie-breaker.
- Reconciliation is scoped only to the four public ALAM article directories, preventing private Job Radar ingestion by construction.
- Pure helper regression tests cover canonical payload identity, duplicate removal, chronological ordering, deterministic equal-time ordering, Evidence calculations, and Supabase-readiness classification.
- A public-safe synchronization health contract now exists in repository code: migration `005_public_sync_health.sql` exposes only sanitized aggregate trusted-sync status through `alam_public_sync_health()`, while direct anonymous access to `agent_runs` remains blocked by RLS.
- `alam_supabase_health.py` converts connection, sanitized sync status, freshness, article count, and actual feed source into explicit readiness states rather than treating “Supabase connected” as equivalent to “cutover healthy.”
- ALAM CI gates reconciliation, Evidence, and Supabase-readiness regression tests and compiles the trusted-sync/readiness modules.

## B. In progress / requires production verification

### Supabase production cutover

Goal: prove that verified GitHub ALAM content is mirrored into the v5 Supabase tables and that production Streamlit is actually reading Supabase rather than silently relying on local fallback.

Required evidence:

- `articles` has published stable text IDs.
- `article_sources`, `article_versions`, `agent_comments`, `wisdom_entries`, predictions, and relationships have expected mirrored rows where applicable.
- A trusted `agent_runs` entry shows a successful synchronization and contains reconciliation totals.
- Migration `005_public_sync_health.sql` has been applied to production so the public app can read sanitized trusted-sync health without opening `agent_runs` RLS.
- ALAM Settings reports the live feed as Supabase, not local fallback, and uses the readiness classifier once Product Agent integration is complete.
- Article evidence/history still render correctly after cutover.
- No private Job Radar data is present in public ALAM tables.

### Deployment readiness

- CI must remain green after backend and product changes.
- Streamlit startup/health smoke test must continue to pass.
- Supabase failures must degrade to an explicit diagnosable state rather than crash the application or falsely report a healthy live mirror.

## C. Next highest-priority improvements

### P0 — Reliability / data integrity

1. Product Agent: integrate `load_public_sync_health()` + `classify_supabase_readiness()` into Settings/operational-state presentation without exposing private diagnostics.
2. Apply and verify migration `005_public_sync_health.sql` in production, then verify a real successful trusted sync and readiness output.
3. Extend reconciliation/idempotency tests to database-level failure injection for article-row success followed by version/source failure.
4. Harden same-story/same-timestamp-but-different-payload conflict handling so agent bugs cannot silently create ambiguous chronological versions.
5. Add stronger source/evidence quality gates before publication and structured rejection reasons.
6. Add stale/outdated lifecycle checks and safe story-expiration rules.

### P1 — Core reader/product quality

1. Keep Today hierarchy decision-first and prevent secondary modules from making the page feel endless.
2. Preserve detailed cross-agent reasoning, uncertainty, implication, and disagreement; group stance only when it improves comprehension without duplicating the full thread.
3. Continue refining material-change notices for saved stories and history.
4. Improve partial-data/loading/fallback/stale-data states using the backend readiness contract, without overwhelming ordinary readers.
5. Refine Evidence only where new backend metadata materially improves trust; do not imply source independence from publisher/domain diversity alone.

### P1 — Persistent user state

1. Select an auth/account approach that does not introduce a login wall.
2. Keep anonymous use fully functional.
3. For authenticated users, sync bookmarks, preferences, reading history, feedback, inbox, and briefing state through RLS-protected tables.
4. Preserve browser-local state as anonymous/offline fallback.

### P2 — Intelligence layer

1. Improve Connect the Dots using explicit relationships/evidence only; shared occurrence is not causality.
2. Surface meaningful agent confidence differences and disagreements.
3. Expand prediction accountability with status-history/evidence-based resolution.
4. Generate daily/weekly briefings only from validated ALAM stories.
5. Add saved-story-change notifications after persistent identity exists.

### P2 — Performance / accessibility

1. Audit Supabase query count and cache boundaries.
2. Avoid repeated hydration queries and oversized rerenders.
3. Consolidate conflicting CSS layers only with regression coverage.
4. Improve touch targets, labels, contrast, mobile density, and keyboard behavior.

### P3 — Admin / operations

1. Trusted admin view for sync runs, rejected candidates, failure reasons, stale stories, merge/update status, and media issues.
2. Safe publish/unpublish/merge/regenerate-image operations through trusted backend paths.
3. Recovery/rollback documentation for schema and mirror problems.
4. Correction history and visible accountability for materially changed published stories.

## D. Blocked / manual-owner actions

These require credentials or external consoles and must never be falsely marked complete from repository changes alone:

- Run `supabase/migrations/005_public_sync_health.sql` in the production Supabase SQL editor. It is additive/idempotent and does not weaken `agent_runs` RLS.
- Supabase SQL execution when future migrations require it.
- GitHub Actions secret creation/rotation for `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`.
- Streamlit Cloud secret creation/rotation for `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY`.
- Manual workflow dispatch when the available connector cannot trigger Actions.
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

- Multiple visual/CSS modules remain layered in install order. Avoid endless override chains; consolidate only after regression checks.
- Browser-local Saved/preferences remain primary user state until auth synchronization is implemented.
- Local JSON fallback is intentionally protective during cutover but can eventually mask stale database synchronization. Decide whether it becomes explicit disaster recovery or is narrowed after production Supabase stability is proven.
- A healthy public Supabase connection does not prove ingestion is current. The new readiness contract solves the classification layer, but the production RPC migration and Product Settings integration remain pending.
- The six-hour stale threshold in `alam_supabase_health.py` is a conservative operational default, not a claim that article content itself becomes factually stale after six hours. Product UI should phrase it as sync freshness.
- Existing audit records may contain historical shapes; maintain translation compatibility until archive normalization is safe.
- Reconciliation intentionally treats GitHub JSON as authoritative for known public article IDs. It does not delete unrelated Supabase articles absent from the GitHub archive; broad orphan cleanup requires a separately reviewed policy.
- Deterministic reconciliation can repair derived version slots, including deleting trailing duplicate version numbers not justified by the GitHub audit. The GitHub audit itself is never deleted.
- Topic reconciliation currently uses the existing small delete/rebuild helper. It is retryable but does not yet use the safer upsert-before-delete source pattern.
- Supabase reconciliation is server-side only and relies on service-role workflow credentials. Missing credentials stop trusted repair before database changes begin.
- Evidence source-group diversity cannot establish editorial independence or prove separate outlets did not repeat the same upstream report.
- The public sync-health RPC deliberately exposes no raw error text or workflow metadata. Operator-level diagnosis still belongs in trusted GitHub Actions logs/admin tooling.

## G. Verification evidence / development log

### 2026-09-02 — Supabase foundation

- Problem: setup SQL failed against an existing UUID-era ALAM schema.
- Root cause: `CREATE TABLE IF NOT EXISTS` does not migrate table shape, and old article IDs were UUID while v5 uses stable text IDs.
- Change: non-destructive legacy bridge plus fresh v5 tables; user confirmed SQL completion.
- Result: repository/app can target the v5 Supabase contract while retaining legacy rollback tables.

### 2026-09-02 — Decision-first product passes

- Article page orchestration moved immediate decision context ahead of deep reading modes while retaining full 30-sec/Panel/Evidence/Deep content.
- Today was tightened around decision-first sections.
- Saved became update-aware.
- Panel/comment presentation was expanded for substantive reasoning and stance rather than shallow reactions.

### 2026-09-03 — Backend self-healing mirror

- Agent: Backend Architect.
- Problem found: incremental ingestion could update the current article row, then fail while writing history/sources/topics; an equal-timestamp retry would return unchanged and preserve incomplete derived state.
- Root cause: timestamp idempotency shortcut covered the current row but the multi-table write sequence is not transactional.
- Decision: keep fast incremental ingestion, then deterministically converge derived state from the GitHub audit archive.
- Implementation: `alam_supabase_reconcile.py`, sync-job integration, deterministic helper tests, CI gates, workflow triggers.
- Security: only public ALAM archive directories are allow-listed; no Job Radar path is reachable.
- Rollback: GitHub JSON remains untouched and is the rebuild source.
- Validation: reconciliation helper tests, syntax gate, data/image gates, and Streamlit health remain in ALAM CI.
- Remaining risk: no database-level failure injection yet; topic reconciliation is still delete/rebuild.

### 2026-09-03 — Evidence trust experience

- Agent: Product Builder.
- Problem found: Evidence was a flat source/claim presentation that forced readers to infer source quality and mapping.
- Root cause: existing v5 metadata was not synthesized into a trust-oriented reader view.
- Decision: derive conservative presentation metrics only; do not invent independence/provenance scores.
- Implementation: `alam_evidence_views.py`, article Evidence integration, deterministic tests, mobile-responsive Evidence Health/source cards.
- Validation: Evidence implementation workflow passed production-data validation, image tests, evidence/reconciliation regression tests, syntax compilation, dependency installation, and Streamlit health startup.
- Remaining risk: publisher/domain diversity cannot prove editorial independence.

### 2026-09-03 — Sanitized Supabase readiness contract

- Agent: Backend Architect.
- Problem found: the app can report “Supabase connected” when the trusted mirror has never synchronized, the latest sync failed/was partial, the sync is operationally stale, or the reader is still on local fallback.
- Root cause: connection health and table counts were available publicly, while `agent_runs` correctly remained private under RLS; there was no sanitized bridge between trusted sync telemetry and public readiness presentation.
- Decision: keep `agent_runs` private and add a narrow SECURITY DEFINER RPC returning only approved aggregate fields. Put readiness rules in a pure Python classifier so Product/UI code does not duplicate backend semantics.
- Implementation: added `supabase/migrations/005_public_sync_health.sql`, `alam_supabase_health.py`, `test_alam_supabase_health.py`, and ALAM CI gates. States cover disconnected, diagnostics unavailable, never synchronized, running, failed, partial, stale, local fallback, synchronized-empty, unknown status, and ready.
- Files/schema affected: one additive SQL function/grant migration plus the new backend health module/test and `.github/workflows/alam-checks.yml`. Existing table/RLS policies were not loosened.
- Security: direct public reads of `agent_runs` remain prohibited. RPC output excludes metadata, raw error messages, workflow/private-repository identifiers, credentials, and Job Radar state. The function grants execution only to `anon` and `authenticated` after revoking default PUBLIC execution.
- Rollback: dropping `public.alam_public_sync_health()` removes the public diagnostic surface without touching content or trusted run records. The Python module already treats a missing RPC as diagnostics-unavailable rather than healthy.
- Validation performed: deterministic tests cover PostgREST list normalization, disconnected precedence, missing migration, never-synced, failed, partial, stale, fallback, synchronized-empty, and fully-ready states. ALAM CI was triggered by the implementation; final conclusion must be checked after this roadmap commit.
- Remaining limitation/risk: production Supabase still needs migration 005 applied; Settings has not yet been wired to the classifier; six-hour freshness is an operational sync threshold and should not be presented as article factual freshness.
- Recommended next action: Product Builder should render the readiness contract in Settings and any compact operational state using calm user-facing language. Next Backend pass should add failure-injection coverage or same-timestamp conflict hardening after production cutover health is observable.

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
