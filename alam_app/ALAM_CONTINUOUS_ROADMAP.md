# ALAM.ph Continuous Improvement Roadmap

This file is the shared planning and handoff document for the ALAM.ph continuous-development cycle. Agent A (backend/reliability) and Agent B (product/UX) must inspect the latest main branch and this file before making changes. Do not mark work complete unless the implementation exists and has been validated.

## Product contract

ALAM.ph is a mobile-first intelligence and action product for Filipino readers. It should answer, as quickly and credibly as possible:

1. What happened?
2. Why does it matter?
3. What changed?
4. What should I do, prepare for, avoid, or watch?
5. How strong is the evidence?
6. What do the other agents think, including meaningful disagreement?

Permanent constraints:

- The Global Engineering Job Radar is private/chat-only and must never be published to the ALAM app or public Supabase tables.
- Public ALAM content must be based on real events and real sources. Do not manufacture dummy/sample stories to fill empty UI states.
- GitHub JSON remains the human-readable agent/audit trail; Supabase is the durable query/read/state layer.
- Public Streamlit code uses only the Supabase publishable/public credential. Service-role/secret credentials belong only in trusted server-side automation.
- Real/official/relevant images are preferred. Generated editorial imagery is a fallback when no suitable real image is available and must not be presented as documentary photography.
- Taglish should remain natural, clear, and broadly understandable rather than forced slang.
- Optimize for usefulness and trust, not engagement addiction or infinite-scroll time.

## A. Completed and verified

- Existing ALAM Streamlit application with Today, Discover, Action, Market, More, Weekly, Search, Saved, Predictions, Settings, article detail, mobile rendering, time-of-day visual system, and editorial image fallback.
- Supabase public-client connection module using Streamlit secrets.
- Supabase-first article loading with temporary local JSON fallback while the database contains no published ALAM records.
- Supabase article source hydration back into the existing ALAM v5 record contract.
- Read-only article-version loading so Before/Now/history features survive the database cutover.
- Supabase-backed public cross-agent comment loading with local comment archive fallback.
- Supabase-backed daily wisdom loading with local fallback.
- Public prediction and article-relationship data access.
- Database health/status display in Settings.
- Trusted GitHub JSON -> Supabase ingestion utility for articles, sources, article versions, topics, comments, wisdom, predictions, and shared-signal relationships.
- GitHub Actions workflow for validated ALAM data synchronization.
- Core Supabase v5 schema, RLS policies, article history, comments/wisdom support, media storage foundation, predictions, relationships, user-state tables, and analytics tables.
- Non-destructive compatibility bridge for the earlier UUID-based ALAM Supabase schema. Legacy tables are preserved as `*_legacy_20260902` rather than destructively converted.
- User confirmed the compatibility/setup SQL was successfully run in Supabase on 2026-09-02.
- CI was previously observed passing after the initial Supabase integration changes. Every future iteration must re-check current CI rather than relying on this historical status.

## B. In progress

### Supabase production cutover

Goal: confirm that verified GitHub ALAM content has actually been mirrored into the new v5 Supabase tables and that the live Streamlit app is reading Supabase rather than the local migration fallback.

Required verification:

- `articles` contains published rows using stable text IDs.
- `article_sources`, `article_versions`, `agent_comments`, `wisdom_entries`, `predictions`, and relationships contain the expected mirrored data where applicable.
- ALAM Settings reports `Live article feed: Supabase`.
- Article detail history and source evidence still render correctly after the cutover.
- No private Job Radar data exists in public ALAM tables.

### Deployment readiness

- Verify the current Streamlit deployment entry point and dependency files.
- Ensure CI exercises the ALAM modules and Streamlit startup path.
- Ensure failures in Supabase do not crash the whole app and are visible enough to diagnose.

## C. Next highest-priority improvements

### P0 — Reliability / data integrity

1. Add explicit Supabase cutover/readiness diagnostics that distinguish: connected, schema ready, data synchronized, live-on-Supabase, local fallback, history unavailable, comments unavailable, and stale synchronization.
2. Record trusted ingestion runs in `agent_runs`/sync-health data so the app/admin view can answer when the database last synchronized and whether failures occurred.
3. Make synchronization idempotency and update/version logic robust against duplicate workflow execution and out-of-order records.
4. Add stronger source/evidence quality checks before publication and explicit rejection reasons for bad candidates.
5. Add stale/outdated lifecycle checks and safe story expiration rules.

### P1 — Core reader/product quality

1. Tighten Today/Home hierarchy around: Today in 3 Lines -> Do Now -> Prepare -> Avoid -> Watch -> Discover.
2. Improve article detail ordering and scannability: summary -> why it matters -> what changed -> what to do -> primary analysis -> other-agent perspectives -> disagreement -> evidence -> timeline -> related stories.
3. Ensure cross-agent perspectives support substantive reasoning, evidence, uncertainty, implication, and disagreement rather than shallow one-line reactions.
4. Surface evidence strength and source type in a compact, understandable way.
5. Add clearer `Updated since you saved this`/material-change behavior using version timestamps.

### P1 — Persistent user state

1. Decide and implement account/auth approach without introducing a login wall.
2. Keep ALAM usable anonymously.
3. When authenticated, sync bookmarks, preferences, reading history, feedback, inbox state, and briefing state across devices using RLS-protected user tables.
4. Preserve browser-local state as an anonymous/offline fallback.

### P2 — Intelligence layer

1. Improve Connect the Dots using explicit relationships and evidence; never infer causality merely from co-occurrence.
2. Surface meaningful agent disagreement and confidence differences.
3. Build prediction accountability with status history and evidence-based resolution.
4. Generate Daily and Weekly briefings only from already-validated ALAM stories.
5. Add saved-story-change notifications/inbox once persistent user identity is available.

### P2 — Performance / accessibility

1. Audit Supabase query count and cache boundaries.
2. Avoid repeated hydration queries and oversized Streamlit rerenders.
3. Consolidate conflicting CSS overrides when safe.
4. Improve touch targets, labels, contrast, mobile card density, and keyboard behavior.
5. Add useful empty/loading/error states for zero data, partial data, database fallback, and stale data.

### P3 — Admin / operations

1. Admin dashboard for agent/sync runs, rejected candidates, failure reasons, stale stories, article merge/update status, and media issues.
2. Safe publish/unpublish/merge/regenerate-image controls through trusted backend paths.
3. Recovery/rollback documentation for Supabase schema/data issues.
4. Correction history and visible accountability where a published story materially changes.

## D. Blocked / manual-owner actions

These actions require credentials or external consoles and must never be falsely marked complete by an agent that only changed repository files:

- Supabase SQL execution when a new migration requires manual application.
- GitHub repository secret creation or rotation for `SUPABASE_SERVICE_ROLE_KEY` if not already present.
- Streamlit Cloud secret creation/rotation for `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY`.
- Manual workflow dispatch when the connector/runtime cannot invoke GitHub Actions directly.
- DNS/domain changes or Streamlit Cloud deployment configuration not available through repository files.

When blocked, provide exact instructions and leave the repository in a safe state.

## E. Longer-term opportunities

- Installable PWA-quality experience where Streamlit constraints allow it.
- Offline access for selected saved stories where practical.
- Explicit topic preference controls with decaying weights and anti-filter-bubble discovery insertion.
- Collections for saved stories: Read Later, Japan, Money, Ideas, Important.
- Knowledge-graph relationships such as contributes_to, contradicts, affects, and shared_signal, only when supported by explicit evidence/agent reasoning.
- Quality dashboards for source diversity, correction rate, duplicate rejection, agent usefulness, and prediction calibration.
- Selective notifications instead of engagement spam.

## F. Known risks / technical debt

- The application currently contains several visual/CSS modules layered in install order. Future work should avoid creating endless override chains and should consolidate carefully after regression checks.
- Browser-local Saved/preferences remain the current primary user-state mechanism until authentication/account synchronization is completed.
- Supabase-first loading intentionally keeps local JSON as a temporary fallback. Once cutover is stable, decide whether fallback should remain as disaster recovery or be narrowed so stale local content cannot silently mask a failed sync.
- GitHub-to-Supabase synchronization depends on trusted secrets and workflow execution. A healthy public Supabase connection alone does not prove that ingestion is current.
- Existing ALAM data may contain multiple historical record shapes. Maintain translation compatibility until the audit archive is normalized.

## G. Verification evidence / CI log

Agents should append concise dated entries here after material iterations.

### 2026-09-02 — Supabase foundation

- Existing UUID-era schema incompatibility identified after SQL failed on a missing `category` column.
- Root cause: `CREATE TABLE IF NOT EXISTS` does not migrate an existing table shape, and the old ALAM article PK was UUID while v5 uses stable text IDs.
- Non-destructive legacy bridge added and user confirmed SQL setup completed.
- Supabase-first application/data-access and ingestion foundation committed.

## H. Agent handoff template

Every material iteration should leave enough context for the other agent to continue without re-discovering the same problem:

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
