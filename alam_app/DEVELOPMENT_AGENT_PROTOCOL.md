# ALAM.ph Continuous Development Agent Protocol

This document governs ALAM's two scheduled development agents and all manual development passes. It exists so continuous improvement is cumulative, reviewable, and safe instead of becoming a sequence of unrelated feature changes.

## Cadence and ownership

- **Agent A — Backend Architect** runs at `:00` each hour.
- **Agent B — Product Builder** runs at `:30` each hour.
- Together they create one ALAM development iteration every 30 minutes without asking either automation to run more frequently than once per hour.
- Manual ChatGPT development may occur between scheduled runs. Scheduled agents must always inspect the latest `main` before touching code because a manual pass may have changed the repository.
- The older generic ALAM upgrade automation is disabled so only two development agents are active.

## Files every development agent must inspect first

1. `alam_app/ALAM_CONTINUOUS_ROADMAP.md`
2. `alam_app/DEVELOPMENT_AGENT_PROTOCOL.md`
3. recent `main` commits
4. current ALAM GitHub Actions / CI results
5. relevant application modules
6. `alam_app/AGENT_DATA_CONTRACT.md` when data semantics are involved
7. `alam_app/PANEL_COMMENT_SYSTEM.md` when discussion/comment behavior is involved
8. Supabase migrations/data access/ingestion files when persistence is involved

Never develop from remembered code. The repository is the source of truth.

## Product objective

ALAM is a mobile-first Taglish intelligence and action product. A useful screen should help the reader answer:

1. What happened?
2. Why does it matter?
3. What changed?
4. What should I do, prepare for, avoid, or watch?
5. How strong is the evidence?
6. What do the other ALAM lenses think?
7. Where do they genuinely disagree or remain uncertain?

Optimize for decision usefulness and trust. Do not optimize for feature count, page-view time, scrolling, or visual novelty.

## Permanent boundaries

- The Global Engineering Job Radar remains private/chat-only and never enters public ALAM code/data flows.
- Never create fake/demo/sample articles to populate the interface.
- GitHub JSON remains the human-readable research/audit archive.
- Supabase is the durable query/read/state layer after verified synchronization.
- Supabase service-role/secret credentials are trusted-backend-only. Never expose them in Streamlit, repository content, logs, or public diagnostics.
- Preserve ALAM v5 data semantics unless a backward-compatible migration is explicitly implemented.
- Prefer additive/idempotent migrations and preserved history over destructive conversion.
- Real/official/relevant images precede generated editorial fallback.
- Generated editorial imagery must not be presented as documentary photography.
- Taglish must remain natural and accessible, not forced slang.

## Required iteration method

Every run must perform the following sequence.

### 1. Observe

Inspect the latest repository and determine:

- what changed since the previous development iteration;
- whether current CI is passing;
- whether the Streamlit startup/smoke check is healthy;
- whether Supabase is merely reachable or actually synchronized/live;
- which roadmap items are already completed;
- which manual credential/configuration blockers exist;
- which user-visible friction or operational risk is currently highest.

### 2. Diagnose

Before editing code, identify:

- user-visible symptom;
- operational symptom;
- root cause;
- relevant module/schema/state path;
- backward-compatibility implications;
- security/RLS implications;
- likely failure modes;
- rollback/recovery path;
- potential interaction/conflict with the other development agent.

Fix root causes rather than stacking cosmetic workarounds.

### 3. Select one coherent iteration

A single run should normally finish one well-defined improvement. Examples:

- good: make trusted Supabase sync runs observable and update the workflow;
- good: rebuild article panel presentation so long detailed comments, stances and replies are understandable on mobile;
- good: make Saved state cross-device-ready while preserving anonymous local fallback;
- bad: simultaneously rewrite navigation, schema, article cards, authentication and notifications.

Large projects belong in the roadmap and should be decomposed into deployable increments.

### 4. Implement with explanatory comments

Detailed comments/docstrings are required for non-obvious behavior, especially:

- migration compatibility and legacy-table rules;
- RLS/security boundaries;
- Supabase/local fallback and disaster-recovery behavior;
- ingestion idempotency and update/version ordering;
- ranking/personalization logic;
- source/evidence quality rules;
- complex Streamlit session-state behavior;
- responsive/mobile workarounds;
- operational diagnostics and failure handling.

Comments should explain **why** the rule exists, what failure it prevents, and what invariants future developers must preserve. Do not clutter obvious one-line syntax with comments.

### 5. Validate before commit

Use all relevant available checks. At minimum when applicable:

- `python alam_app/validate_alam_data.py`
- Python syntax/compile checks
- Streamlit startup/health smoke check
- relevant unit/helper tests when present
- GitHub Actions / ALAM app checks after push

A code commit is not "verified" merely because GitHub accepted the file update.

For migrations that require the Supabase console, committing SQL is not equivalent to applying it. Record the manual blocker explicitly in the roadmap.

### 6. Commit and hand off

Every material iteration should leave a roadmap/handoff note containing:

- date/time;
- agent/manual developer;
- problem found;
- root cause;
- decision;
- implementation;
- files/schema affected;
- validation performed;
- current CI/deployment status;
- remaining limitation/risk;
- recommended next action.

Do not mark a roadmap item complete until implementation and validation both exist.

## Backend Architect responsibility

Agent A owns, or coordinates, the following areas:

- Supabase schema/migrations/RLS;
- GitHub audit -> Supabase synchronization;
- article/source/version/comment/topic/prediction persistence;
- deduplication and update-vs-new-story logic;
- stale/outdated lifecycle handling;
- rejected candidate records and quality gates;
- media metadata/storage foundation;
- ingestion retries/failure diagnostics;
- deployment health and observability;
- data-access query efficiency/caching;
- recovery/rollback tooling;
- user-state backend readiness.

Priority order:

1. runtime/security/data-loss risks;
2. Supabase cutover correctness;
3. ingestion/data quality;
4. evidence/source trustworthiness;
5. observability/recovery;
6. performance;
7. intelligence infrastructure;
8. lower-priority backend polish.

## Product Builder responsibility

Agent B owns, or coordinates, the following areas:

- mobile-first navigation and layout;
- Today/Home hierarchy;
- Action Center clarity;
- article cards and article detail experience;
- source/evidence presentation;
- story update/history presentation;
- cross-agent detailed perspectives/disagreement UX;
- Saved/Search/personalization controls;
- browser-local and eventual authenticated-state experience;
- loading/empty/error/fallback/stale-data states;
- accessibility and touch-target quality;
- render performance and CSS consolidation;
- editorial image presentation.

Priority order:

1. broken runtime/navigation/mobile usability;
2. Today/Home and Action usefulness;
3. article reading/evidence/trust;
4. persistent-state integration readiness;
5. Saved/Search/personalization;
6. perspectives/history/related stories;
7. accessibility/performance;
8. visual polish.

## Detailed cross-agent discussion standard

ALAM comments are not social reactions. They are mini analytical notes from specialized lenses.

A useful comment should normally include:

- **position:** SUPPORT / CHALLENGE / MIXED when natural;
- **main insight:** the single strongest additional point;
- **reasoning:** why that point follows from evidence or domain knowledge;
- **implication:** what changes for the reader, story interpretation, or forecast;
- **uncertainty/caveat:** what could make the comment wrong or less important;
- **watch condition:** what evidence should be checked next when relevant.

If a comment introduces a new factual claim, it must follow the main ALAM claim/source classification rules. A reply should address the point it replies to instead of starting a disconnected mini-essay.

The UI must support detailed comments without forcing them into one-line snippets. Compact previews are acceptable only when the full reasoning remains immediately expandable/readable.

## Manual blocker rule

When an external credential/configuration is missing, development must not stop entirely if safe unrelated work remains.

Example: if GitHub Actions lacks `SUPABASE_SERVICE_ROLE_KEY`, agents should:

1. record the exact blocker and failure evidence;
2. avoid pretending synchronization is live;
3. keep public fallback behavior safe;
4. continue improving code, UX, tests, documentation, or readiness diagnostics that do not require the credential;
5. never weaken RLS or put the service key in public code as a workaround.

## Definition of a production-quality iteration

A development iteration is successful when it leaves ALAM measurably better in at least one core dimension—reliability, usefulness, trust, maintainability, performance, accessibility, or recovery—without making another core dimension materially worse.
