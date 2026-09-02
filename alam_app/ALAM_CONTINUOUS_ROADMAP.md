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
- Evidence view now surfaces attached-source count, primary/official count, publisher/domain diversity, classified-claim coverage, and source-to-claim support before the long source list. It explicitly treats source-group diversity as a heuristic rather than proof of independent confirmation.
- Evidence source cards identify source type, primary/official status, diversity group, mapped claim count, reliability metadata when supplied, and the exact classified claims supported by each source. Mobile layout collapses the summary to a 2x2 grid and stacks source badges cleanly.
- Supabase public-client module and Supabase-first article loading with local JSON migration fallback.
- Supabase source hydration, public article history, public cross-agent comments, daily wisdom, predictions, article relationships, and database-health reads.
- Core v5 Supabase schema with RLS, article/source/history/comment/run/topic/media/user-state/briefing/prediction/relationship/event tables.
- Non-destructive bridge for the earlier UUID ALAM schema; user confirmed the compatibility/full setup SQL ran successfully on 2026-09-02.
- Trusted GitHub JSON -> Supabase incremental ingestion for public Discover, Practical, Market/reflection, Trend, comments, wisdom, sources, topics, predictions, versions, and explicit shared-signal relationships.
- Trusted sync wrapper records sanitized GitHub run provenance and ingestion totals in `agent_runs`; service credentials remain server-side.
- GitHub Actions serializes ALAM Supabase synchronization with a concurrency group so ordinary workflow dispatches do not overlap.
- **Self-healing reconciliation layer** (`alam_supabase_reconcile.py`) added on 2026-09-03. After incremental ingestion it deterministically converges public current articles, numbered article history, normalized current sources, topics, and predictions from the GitHub audit archive.
- Reconciliation specifically repairs the partial-write failure mode where `articles` was updated but later version/source/topic writes failed and a retry would otherwise incorrectly skip the record as unchanged.
- Source reconciliation uses upsert-before-delete so a transient failure does not intentionally erase the previous good evidence set before desired sources are accepted.
- Exact duplicate audit payloads are deduplicated before deterministic version numbering; equal timestamps use archive path ordering as a stable tie-breaker.
- Reconciliation is scoped only to the four public ALAM article directories, preventing private Job Radar ingestion by construction.
- Pure helper regression tests cover canonical payload identity, duplicate removal, chronological ordering, and deterministic equal-time ordering.
- ALAM CI now runs reconciliation and Evidence trust-view regression tests and compiles the new trusted-sync/evidence modules.

## B. In progress / requires production verification

### Supabase production cutover

Goal: prove that verified GitHub ALAM content is mirrored into the v5 Supabase tables and that production Streamlit is actually reading Supabase rather than silently relying on local fallback.

Required evidence:

- `articles` has published stable text IDs.
- `article_sources`, `article_versions`, `agent_comments`, `wisdom_entries`, predictions, and relationships have expected mirrored rows where applicable.
- A trusted `agent_runs` entry shows a successful synchronization and contains reconciliation totals.
- ALAM Settings reports the live feed as Supabase, not local fallback.
- Article evidence/history still render correctly after cutover.
- No private Job Radar data is present in public ALAM tables.

### Deployment readiness

- CI must remain green after backend and product changes.
- Streamlit startup/health smoke test must continue to pass.
- Supabase failures must degrade to an explicit diagnosable state rather than crash the application or falsely report a healthy live mirror.

## C. Next highest-priority improvements

### P0 — Reliability / data integrity

1. Complete explicit cutover/readiness diagnostics that distinguish: connected, schema ready, synchronized, live-on-Supabase, local fallback, stale sync, history unavailable, comments unavailable, and trusted-sync failure.
2. Verify a real successful `agent_runs` sync entry in production. Repository support is implemented; external workflow credentials/execution still determine whether this is live.
3. Extend reconciliation/idempotency tests to failure-injection cases for article-row success followed by version/source failure. Current deterministic helpers are tested; database-level failure simulation is not yet implemented.
4. Harden same-story/same-timestamp-but-different-payload conflict handling so agent bugs cannot silently create ambiguous chronological versions.
5. Add stronger source/evidence quality gates before publication and structured rejection reasons.
6. Add stale/outdated lifecycle checks and safe story-expiration rules.

### P1 — Core reader/product quality

1. Keep Today hierarchy decision-first and prevent secondary modules from making the page feel endless.
2. Preserve detailed cross-agent reasoning, uncertainty, implication, and disagreement; group stance only when it improves comprehension without duplicating the full thread.
3. Continue refining material-change notices for saved stories and history.
4. Improve partial-data/loading/fallback/stale-data states so operational truth is visible without overwhelming ordinary readers.
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
- A healthy public Supabase connection does not prove ingestion is current. Trusted run status and freshness must become part of readiness diagnostics.
- Existing audit records may contain historical shapes; maintain translation compatibility until archive normalization is safe.
- Reconciliation intentionally treats GitHub JSON as authoritative for known public article IDs. It does not delete unrelated Supabase articles that are absent from the GitHub archive; broad orphan cleanup requires a separately reviewed policy.
- Deterministic reconciliation can repair derived version slots, including deleting trailing duplicate version numbers not justified by the GitHub audit. The GitHub audit itself is never deleted by this process.
- Topic reconciliation currently uses the existing small delete/rebuild helper. It is retryable but does not yet use the safer upsert-before-delete pattern implemented for sources.
- Supabase reconciliation is server-side only and relies on service-role workflow credentials. A missing credential stops the trusted job before database repair can begin.
- Evidence source-group diversity is intentionally conservative but cannot establish editorial independence or prove that separate outlets did not repeat the same upstream report.
- Supabase article hydration preserves v5 claim `source_refs`; normalized source fields such as `reliability` are available when populated. If future ingestion adds stronger provenance/independence metadata, the Evidence UI should consume it without inventing a score.

## G. Verification evidence / development log

### 2026-09-02 — Supabase foundation

- Problem: setup SQL failed against an existing UUID-era ALAM schema.
- Root cause: `CREATE TABLE IF NOT EXISTS` does not migrate table shape, and old article IDs were UUID while v5 uses stable text IDs.
- Change: non-destructive legacy bridge plus fresh v5 tables; user confirmed SQL completion.
- Result: repository/app can target the v5 Supabase contract while retaining legacy rollback tables.

### 2026-09-02 — Decision-first product passes

- Article page orchestration moved the immediate decision context ahead of deep reading modes while retaining full 30-sec/Panel/Evidence/Deep content.
- Today was tightened around decision-first sections.
- Saved view became update-aware.
- Panel/comment presentation was expanded for substantive reasoning and stance rather than shallow reactions.
- These changes were committed on main before the 2026-09-03 backend iteration and were not overwritten by the backend reconciliation work.

### 2026-09-03 — Backend self-healing mirror

- Agent: Backend Architect.
- Problem found: incremental ingestion could partially succeed by updating the current article row, then fail while writing history/sources/topics. On retry, equal `created_at` caused `sync_article` to return `unchanged`, leaving Supabase permanently incomplete unless manually repaired.
- Root cause: idempotency was implemented as a timestamp shortcut, but the database write sequence is not transactional across all derived tables.
- Decision: retain fast incremental ingestion, then run a deterministic convergence pass from the GitHub audit archive. This avoids invasive schema changes and makes retries repair state.
- Implementation: added `alam_supabase_reconcile.py`; wired it into `alam_supabase_sync_job.py`; added a deterministic helper regression test; added reconciliation module/test to ALAM CI; added the reconcile module to trusted-sync workflow path triggers.
- Files affected: `alam_app/alam_supabase_reconcile.py`, `alam_app/alam_supabase_sync_job.py`, `alam_app/test_alam_supabase_reconcile.py`, `.github/workflows/alam-checks.yml`, `.github/workflows/alam-supabase-sync.yml`, this roadmap.
- Security: reconciliation only reads the allow-listed public article directories and runs behind the existing service-role boundary. No public credential scope changed and no private Job Radar path was added.
- Rollback: GitHub JSON remains untouched. Derived Supabase rows can be regenerated from it. No new database migration was required.
- Validation performed: deterministic helper test added to CI; syntax gate expanded; Streamlit health/data/image gates remain in the same ALAM workflow. Final workflow conclusions must be checked after the roadmap commit before this iteration is considered fully green.
- Remaining risk: no database-level failure-injection test yet; topic repair still uses delete/rebuild; production cutover still requires a successful trusted workflow with valid secrets.
- Recommended next backend action: finish cutover/freshness diagnostics and expose only sanitized trusted-sync health to the public Settings/admin experience. Recommended product action: continue Evidence/source-quality presentation without changing the backend contract.

### 2026-09-03 — Evidence trust experience

- Agent: Product Builder.
- Problem found: Evidence exposed claims and a flat source list, but readers still had to infer whether citations were primary/official, whether apparent source diversity was real, and which claims each source actually supported.
- Root cause: the v5 contract already contained `source_type`, publisher, reliability metadata, and 1-based claim `source_refs`, but the reader did not synthesize those fields into a trust-oriented view.
- Decision: improve Evidence entirely at the presentation/derived-metric layer. No schema or article-contract change was needed. Source-group diversity is labelled as a publisher/domain heuristic and never presented as proof of independent corroboration.
- Implementation: added `alam_evidence_views.py` with a four-metric Evidence Health summary, conservative publisher/domain grouping, claim-coverage calculation, source-to-claim mapping, mobile-responsive source badges, and explicit limited-diversity warnings. Story Evidence now delegates to this module while retaining the existing PR-vs-Reality, classified-claims, and story-timeline renderers.
- Files affected: `alam_app/alam_evidence_views.py`, `alam_app/alam_story_page.py`, `alam_app/streamlit_app.py`, `alam_app/test_alam_evidence_views.py`, `.github/workflows/alam-checks.yml`, this roadmap. No database schema changed.
- Mobile behavior: the four Evidence Health metrics collapse to a 2x2 phone grid; source metadata/badges stack below the source title instead of squeezing into a desktop row.
- Validation performed: deterministic evidence tests cover primary counts, publisher-group deduplication, claim coverage, invalid source refs, numeric string refs, and zero-evidence behavior without fake precision. The ALAM workflow for commit `eb3a674` completed successfully, including production-data validation, image tests, evidence/reconciliation regression tests, syntax compilation, dependency installation, and Streamlit health startup.
- Current CI/deployment status: repository validation for the Evidence implementation is green. Production deployment remains subject to the existing Streamlit/Supabase external configuration and cutover verification described above.
- Remaining limitation/risk: publisher/domain diversity cannot prove true editorial independence or unique upstream evidence. The UI deliberately says so. Historical records with no classified claims show claim coverage as unavailable rather than a misleading 0%/100% score.
- Recommended next backend action: if defensible provenance metadata becomes available during source normalization, expose it consistently to the public hydration contract rather than deriving independence in the UI. Recommended next product action: improve partial-data/stale/fallback states or saved-story change clarity without expanding the first-screen article density.

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
