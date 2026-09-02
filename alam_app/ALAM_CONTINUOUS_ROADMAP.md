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
- Saved-story version awareness with updated-since-saved detection, updated-first ordering, compact Before/Now preview when defensible, and explicit review acknowledgement that clears the current update without unsaving the story.
- Detailed ALAM Panel presentation preserving substantive SUPPORT/CHALLENGE/MIXED reasoning.
- Evidence view with source count, official/primary count, publisher/domain diversity, classified-claim coverage, and source-to-claim support. Diversity is explicitly not treated as proof of editorial independence.
- Cross-cutting accessibility contract installed after feature/theme styles: visible `:focus-visible` keyboard focus, minimum 44px desktop interaction targets, 48px mobile targets, operating-system reduced-motion support, and non-colour link affordance for evidence-bearing links.
- Selected article detail now scopes cross-agent comment hydration to that one current story; feed/list views retain the full current-story comment scope, reducing unnecessary Supabase payload without weakening the detailed Panel contract.
- Selected article detail now also scopes Supabase `article_versions` hydration to that one validated stable story ID while preserving its complete Before/Now timeline; stale selections fail back to the established feed path and local migration fallback remains compatible.
- Supabase-first public article loading with local JSON migration fallback.
- Supabase hydration for sources, history, comments, wisdom, predictions, relationships, and database health.
- Core v5 Supabase schema with RLS plus non-destructive compatibility bridge for the earlier UUID schema.
- Trusted GitHub JSON -> Supabase incremental ingestion for Discover, Practical, Market/reflection, Trend, comments, wisdom, sources, topics, predictions, versions, and explicit shared-signal relationships.
- Trusted sync wrapper records sanitized provenance/statistics in private `agent_runs`; service credentials remain server-side.
- GitHub Actions serializes Supabase sync jobs to avoid ordinary overlapping dispatches.
- Self-healing reconciliation deterministically converges current articles, numbered history, sources, topics, and predictions from the GitHub audit archive.
- Reconciliation repairs partial-write cases where the current article advances but derived tables fail.
- CI now directly proves the multi-table failure sequence where `articles` succeeds, `article_versions` fails, an equal-timestamp incremental retry remains unchanged, and reconciliation restores history plus normalized evidence without duplicate versions.
- Source reconciliation uses upsert-before-delete to avoid deliberately erasing the prior good evidence set before desired rows are accepted.
- Incremental article-source synchronization now upserts every desired evidence row before deleting stale rows, so transient source-write failures preserve the previous good evidence set until retry/reconciliation.
- Incremental topic synchronization now resolves/upserts desired topics and links before deleting stale links, so transient failures do not deliberately erase the prior topic set.
- Exact duplicate audit payloads are removed before deterministic version numbering.
- Fail-closed chronology preflight rejects materially different versions of one stable article ID sharing the same explicit `created_at` before public content writes.
- Legacy records with no explicit `created_at` remain compatible; path ordering is retained only as a deterministic fallback for those historical shapes.
- Reconciliation is scoped to the four public ALAM article directories, so private Job Radar data is unreachable by construction.
- A public-safe sync-health RPC contract exists in migration `005_public_sync_health.sql`; direct public reads of `agent_runs` remain blocked by RLS.
- Backend readiness classification distinguishes disconnected, diagnostics unavailable, never synchronized, running, failed, partial, stale sync, local fallback, synchronized-empty, unknown status, and ready.
- Settings renders one calm Data status verdict from that classifier and keeps raw private workflow/error metadata out of the public UI.
- CI gates reconciliation/chronology, multi-table partial-write recovery, source/topic failure safety, Evidence, backend readiness, product readiness, Saved material-update review state, comment/history hydration scope, accessibility, syntax, production data, image behavior, dependency installation, and Streamlit startup health.

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
2. Add stronger source/evidence quality gates before publication with structured rejection reasons.
3. Add stale/outdated lifecycle checks and safe story-expiration rules.
4. Consider a separately reviewed policy for orphan Supabase rows absent from GitHub; do not delete broadly by default.

### P1 — Core reader/product quality

1. Keep Today decision-first and prevent secondary modules from making the page endless.
2. Preserve detailed cross-agent reasoning, uncertainty, implications, and disagreement.
3. Improve Saved/history change previews only when complete history or explicit v5 `change_summary` exists; never infer a change from weak metadata.
4. Revisit fallback/stale-data communication only after real production readiness telemetry exists.
5. Refine Evidence only when backend metadata can improve trust without inventing source independence.

### P1 — Persistent user state

1. Select an auth/account approach without a login wall.
2. Keep anonymous use fully functional.
3. Sync authenticated bookmarks, preferences, reads, feedback, inbox, briefing state, and saved-update review baselines through RLS-protected tables.
4. Preserve browser-local state as anonymous/offline fallback.

### P2 — Intelligence layer

- Improve Connect the Dots using explicit relationships/evidence only; shared occurrence is not causality.
- Surface meaningful agent confidence differences/disagreement.
- Expand prediction accountability with status-history and evidence-based resolution.
- Generate daily/weekly briefings only from validated ALAM stories.
- Add saved-story-change notifications only after persistent identity exists.

### P2 — Performance / accessibility

- Continue auditing Supabase query/cache boundaries. Selected article comment and version-history hydration are now scoped; next measure normalized source payload/call counts before changing source hydration or broader feed history behavior.
- Perform a real-device keyboard/screen-reader/manual mobile accessibility audit; the CSS contract is a safeguard, not a claim of full WCAG conformance.
- Consolidate conflicting CSS only with regression coverage.
- Continue reviewing labels, contrast, mobile density, and semantic behavior as Streamlit widgets evolve.

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

- Multiple visual/CSS modules remain layered in install order; `alam_accessibility.py` is intentionally installed last to protect focus/motion/target rules, but future code must preserve that ordering.
- Browser-local Saved/preferences remain primary user state until auth synchronization exists.
- Saved update acknowledgement is intentionally browser-local; cross-device review state requires future authenticated persistence.
- The current four-argument Saved renderer remains backward-compatible. Explicit v5 `content.change_summary` can render Before/Now without hydrated history; legacy records without explicit change summaries safely omit the preview.
- Local JSON fallback protects cutover but can eventually mask stale database synchronization; narrow it only after Supabase stability is proven.
- Production migration 005 plus a real trusted sync are still required before repository readiness logic proves live cutover.
- The six-hour threshold is operational sync freshness, not a claim that article facts expire after six hours.
- Historical audit records may lack current v5 fields. The chronology preflight deliberately does not treat missing `created_at` as an explicit timestamp conflict.
- Same explicit timestamp + different payload now fails trusted sync before content writes. Correct the GitHub audit timestamp/payload rather than bypassing this guard.
- Reconciliation does not delete unrelated Supabase articles absent from GitHub; broad orphan cleanup requires a separate reviewed policy.
- Article/current-version/source/topic writes remain separate database operations. Deterministic CI now proves recovery for the highest-risk current-row-success/version-failure/equal-timestamp-retry sequence, while source/topic helpers and archive reconciliation remain convergent. A destructive live-database/network chaos test is still intentionally absent.
- Supabase reconciliation is service-role-only; missing trusted credentials stop repair before database content writes.
- Evidence source-group diversity cannot establish editorial independence.
- Public sync-health intentionally exposes no raw errors/workflow metadata; operator diagnosis belongs in trusted logs/admin tooling.
- Accessibility CSS improves baseline interaction behavior but does not by itself prove screen-reader semantics or full WCAG conformance; Streamlit-generated markup must be manually audited periodically.
- Feed/list pages still request comments across all current story IDs because those surfaces can render discussion across multiple stories. Further narrowing should be route-aware and measured rather than assuming every list view can drop comment bodies.
- Local JSON comment fallback remains compatible but still scans its local comment archive; this specifically reduces Supabase payload on selected article detail pages.
- Local JSON article fallback also remains intentionally full-history; the new selected-story version scoping applies to Supabase network hydration, where it removes unrelated query payload without inventing a second local audit-file contract.
- Current Supabase article loading still hydrates normalized source rows across the current feed because cards display evidence/source counts. Future source scoping should first provide or measure a compact count/quality contract rather than silently weakening card trust cues.

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
- Remaining risk at that checkpoint: higher-fidelity partial-write failure injection had not yet been added.

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
- Validation performed: deterministic regression tests cover exact duplicates, normal chronology, explicit equal-time conflict rejection through both helper and public preflight entry point, and backward compatibility for missing timestamps.
- Remaining limitation/risk: malformed explicit timestamp strings still use the existing parser fallback semantics; stronger schema validation can be considered with source-quality gates.
- Recommended next action: Backend should move to pre-publication source/rejection quality gates after proving partial-write recovery.

### 2026-09-03 — Saved material-update review queue

- Agent: Product Builder.
- Problem found: Saved correctly detected a newer material story version, but the `UPDATED SINCE SAVED` signal had no completion path. After reading the change, the badge remained permanently until the reader unsaved and re-saved the story.
- Root cause: bookmark version state was captured only when the story was first saved. There was no separate acknowledgement action to say “I reviewed this version, keep watching for the next one.”
- Decision: treat a Saved update as an explicit review state. Acknowledgement advances only the local saved-version baseline; it does not mark the story unsaved and does not silently conflate Saved review with general Read state.
- Implementation: added monotonic `_advance_saved_snapshot()` and `acknowledge_saved_update()` in `alam_local_state.py`; Saved keeps updated stories first, shows conservative Before/Now copy when `change_snapshot()` has defensible evidence, and provides a full-width `Mark this update reviewed` action. Existing four-argument renderer compatibility is preserved for rolling deployments.
- Files/schema affected: `alam_app/alam_local_state.py`, `alam_app/alam_saved_views.py`, `alam_app/test_alam_saved_update_flow.py`, `.github/workflows/alam-checks.yml`, and this roadmap. No Supabase schema or RLS change.
- Mobile behavior: the existing wrapped card layout is preserved; update preview copy uses a compact high-contrast block and the acknowledgement action remains a full-width touch target. On narrow screens the preview typography is increased slightly for readability.
- Validation performed: deterministic tests prove acknowledgement is monotonic/idempotent, an older rerun cannot move the review baseline backward, explicit v5 change summaries work without hydrated history, and no preview is manufactured for a static record. CI now runs these tests and compiles the Saved view explicitly; the compatibility checkpoint passed the full ALAM workflow before this roadmap update.
- Remaining limitation/risk: acknowledgement is anonymous browser-local state today. Imported legacy Saved ID codes intentionally do not invent historical review baselines. Full cross-device review persistence belongs with future authenticated state.
- Recommended Backend action: no backend change is required for this flow. When authenticated persistence is designed, include the saved-story reviewed-version baseline under per-user RLS rather than deriving it from generic read history.
- Recommended Product action: next prioritize accessibility/performance or another reader friction with measurable utility; do not auto-clear a Saved update merely because a story page was opened.

### 2026-09-03 — Failure-safe incremental topic synchronization

- Agent: Backend Architect.
- Problem found: incremental topic sync deleted every existing article-topic link before resolving the replacement set, creating a partial-failure window where a published story could temporarily lose all topic relationships.
- Decision: resolve/upsert all desired topics and links first, then delete only stale links after the replacement set is known-good.
- Validation performed: deterministic failure-injection coverage proves old links survive mid-sync failure, stale deletion does not happen early, retries converge, explicit empty tags remove old links, and case/duplicate tags normalize safely.
- Remaining backend risk at that checkpoint: incremental article-source synchronization still had a delete-before-insert window; the following backend iteration removed it.

### 2026-09-03 — Cross-cutting mobile accessibility contract

- Agent: Product Builder.
- Problem found: ALAM had generally good mobile sizing, but keyboard focus, reduced-motion behavior, evidence-link affordance, and minimum interaction targets were distributed across independent CSS layers. A later theme/feature style could silently undo one safeguard.
- Root cause: feature-specific visual modules evolved independently and install order had no explicit accessibility boundary.
- Decision: create one rendering-only accessibility contract and install it after all visual/theme layers. It must not read Supabase, session data, or alter product state.
- Implementation: added `alam_accessibility.py`; visible `:focus-visible` treatment for native and semantic controls; 44px desktop and 48px mobile minimum targets; `prefers-reduced-motion` handling; underlined evidence/detail links as a non-colour affordance; explicit late installation in `streamlit_app.py`; deterministic contract test and CI gate.
- Files/schema affected: `alam_app/alam_accessibility.py`, `alam_app/streamlit_app.py`, `alam_app/test_alam_accessibility.py`, `.github/workflows/alam-checks.yml`, and this roadmap. No database/schema/RLS change and no additional runtime database queries.
- Mobile behavior: navigation, segmented controls, buttons and semantic interactive roles receive a 48px minimum target at <=760px. Reduced-motion users keep the same content/information hierarchy while decorative animation/transitions collapse to effectively instant behavior.
- Validation performed: ALAM app checks run for code/CI commit `3431a17b84becc4a417a745b2115638e882d2ec5` completed successfully, including the new accessibility regression test, the existing data/backend/product tests, syntax compilation, dependencies, and Streamlit health gate.
- Remaining limitation/risk: CSS safeguards do not substitute for a real keyboard, screen-reader, contrast, and touch audit on actual devices; Streamlit markup can change between framework releases.
- Recommended Backend action: none required. Continue the incremental article-source failure-safety work independently.
- Recommended Product action: next measure query/render performance or perform a focused real-device/manual accessibility audit before adding more visual polish.

### 2026-09-03 — Failure-safe incremental article-source synchronization

- Agent: Backend Architect.
- Problem found: first-pass `sync_article()` deleted all normalized evidence rows before inserting replacements, creating a user-visible trust regression if Supabase failed after deletion.
- Root cause: incremental ingestion had not adopted the convergent source ordering already used by archive reconciliation.
- Decision: add one `_sync_sources()` boundary that upserts every desired source first and removes stale rows only after all desired writes succeed. Preserve explicit empty-source cleanup and dry-run compatibility.
- Implementation: `alam_supabase_ingest.py` now routes source writes through `_sync_sources()`; `test_alam_source_sync.py` injects a later-source failure and proves the prior evidence remains, no cleanup happens early, retry converges, and claim/source normalization remains intact; ALAM CI gates the new test.
- Files/schema affected: `alam_app/alam_supabase_ingest.py`, `alam_app/test_alam_source_sync.py`, `.github/workflows/alam-checks.yml`, `alam_app/ALAM_BACKEND_CHANGELOG.md`, and this roadmap. No migration or RLS change.
- Validation performed: deterministic failure-injection test plus the full repository ALAM workflow before merge to `main`.
- Remaining limitation/risk at that checkpoint: current-article, version, source, topic, and prediction writes were separate transactions without an integration-level partial-write proof.
- Recommended Backend action at that checkpoint: test article-row success followed by version/derived failure, then add structured evidence-quality rejection gates.
- Recommended Product action: no UI change is required; preserve the existing Evidence trust surface.

### 2026-09-03 — Multi-table partial-write recovery proof

- Agent: Backend Architect.
- Problem found: the trusted-sync architecture depended on reconciliation repairing a run where `articles` had advanced but `article_versions` and later derived rows had not, yet no CI test exercised that complete sequence.
- Root cause: helper tests proved pieces independently but did not connect production `sync_article()` behavior to equal-timestamp retry and archive reconciliation.
- Decision: preserve the existing architecture and make the recovery invariant executable. A production-code rewrite or transaction emulation would add complexity without improving the GitHub-audit-source-of-truth model.
- Implementation: `test_alam_multitable_recovery.py` injects failure on the first version insert after the current article upsert, confirms the next incremental retry returns `unchanged`, then runs `reconcile_public_archive()` against the validated prepared snapshot and proves deterministic history plus claim-linked normalized source recovery. A second reconciliation proves no duplicate history slot is manufactured. CI runs and syntax-compiles the test.
- Files/schema affected: `alam_app/test_alam_multitable_recovery.py`, `.github/workflows/alam-checks.yml`, `alam_app/ALAM_BACKEND_CHANGELOG.md`, and this roadmap. No production code, migration, RLS, credential, Streamlit, or Job Radar change.
- Validation performed: deterministic fake-PostgREST integration test plus the complete ALAM pull-request workflow before merge.
- Remaining limitation/risk: this does not deliberately interrupt a live production Supabase network connection. The deterministic contract protects recovery semantics while real service outages remain handled by trusted-job retry/reconciliation and operational diagnostics.
- Recommended Backend action: source/evidence publication quality gates with structured rejection reasons, then stale/outdated lifecycle handling.
- Recommended Product action: no frontend change required; continue route-specific history/source query measurement.

### 2026-09-03 — View-scoped article comment hydration

- Agent: Product Builder.
- Problem found: selected article pages hydrated published cross-agent comments for every current story before selection was resolved, adding unrelated Supabase payload and parsing to mobile detail navigation.
- Root cause: `load_comments()` ran before `selected_story` lookup in the Streamlit entry point, so the data layer had no view scope.
- Decision: resolve the selected story first; request one story's comments for a valid detail page, preserve full current-feed comment scope for feed/list views, and fail safe to feed scope for stale browser selection state.
- Implementation: added pure `comment_scope_ids()` in `alam_comment_scope.py`, integrated it before comment hydration in `streamlit_app.py`, and added deterministic regression coverage plus CI gating.
- Files/schema affected: `alam_app/alam_comment_scope.py`, `alam_app/streamlit_app.py`, `alam_app/test_alam_comment_scope.py`, `.github/workflows/alam-checks.yml`, and this roadmap. No database/schema/RLS change and no new database calls.
- Mobile behavior: article detail preserves the same content, detailed agent comments, stance/reply relationships, deep-link/session selection, and controls while narrowing the Supabase comment query from all current story IDs to the selected story ID. Feed/list pages remain behaviorally unchanged.
- Validation performed: deterministic tests cover selected/feed/stale/empty scopes. ALAM app checks for code/CI commit `ee223610ecd37991fcab8eb4c7b58bb004e77750` completed successfully, including the new scope test, production-data validation, source/topic/reconciliation/readiness/Evidence/Saved/accessibility regressions, Python compilation, dependency installation, and Streamlit startup health.
- Remaining limitation/risk: local JSON fallback still scans its local comment archive. Broader route-aware lazy hydration for history/sources/comments should be measured before changing list behavior.
- Recommended Backend action: none required for this view boundary; continue source-quality gates. If future cards need only comment counts, expose compact counts separately instead of forcing full comment-body hydration.
- Recommended Product action: next measure article history/source hydration and route-specific query counts; avoid broader lazy loading until Saved, Weekly, and history behavior are proven safe.

### 2026-09-03 — View-scoped selected article history hydration

- Agent: Product Builder.
- Problem found: selected article detail still hydrated `article_versions` for every current story before the selected story could render, even after comment hydration had already been scoped.
- Root cause: `extras.load_article_records()` combined current Supabase rows with the entire history set before `selected_story` was validated.
- Decision: load current rows first, validate detail selection against the current feed, then request version history for exactly that stable story ID. Keep non-detail routes on the established full-history contract until their actual history dependencies are measured. Preserve full local-file fallback rather than inventing a second migration contract.
- Implementation: added `alam_article_scope.py` with current-only read selection, one-ID detail history scope and current/history de-duplication; integrated the boundary in `streamlit_app.py`; added deterministic `test_alam_article_scope.py` coverage and CI gating.
- Files/schema affected: `alam_app/alam_article_scope.py`, `alam_app/streamlit_app.py`, `alam_app/test_alam_article_scope.py`, `.github/workflows/alam-checks.yml`, `alam_app/ALAM_PRODUCT_CHANGELOG.md`, and this roadmap. No database migration, RLS, ingestion, trusted-sync, credential, or Job Radar change.
- Mobile behavior: opening a valid article keeps the same 30-sec, Panel, Evidence, Deep, Before/Now, related-story, save and share experience while its Supabase version-history query contains one article ID instead of all current article IDs. Stale browser selection safely returns to the mature feed path.
- Zero/one/many/fallback behavior: empty selection does not widen a detail query; one valid selection requests one ID; feed/list many-story history behavior is unchanged; Supabase failure/local migration fallback keeps the existing local record scan. A history-query failure leaves the current story readable and surfaces the existing sanitized history diagnostic.
- Validation performed: deterministic scope/dedup regression test plus CI inclusion and Python syntax coverage; full workflow result must be green before merge.
- Remaining limitation/risk: current article reads still hydrate normalized sources across all current stories because article cards expose evidence counts. Source scoping should be measured and backed by a compact trust/count contract before changing that behavior.
- Recommended Backend action: continue source/evidence publication quality gates. If a future safe aggregate contract exposes source count/primary count on current rows, Product can reduce list-source payload without weakening trust cues.
- Recommended Product action: measure source payload and route-specific query counts next; do not broaden lazy-loading changes speculatively.

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