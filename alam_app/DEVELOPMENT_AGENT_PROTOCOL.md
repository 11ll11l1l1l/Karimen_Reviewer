# ALAM.ph Continuous Development Agent Protocol

This document governs ALAM's three scheduled development agents and all manual development passes. It exists so continuous improvement is cumulative, reviewable, and safe instead of becoming a sequence of unrelated or conflicting changes.

## Cadence and ownership

ALAM has three development lanes with explicit non-overlapping ownership:

- **Innovation Agent** owns user-facing capabilities, UX/product intelligence, personalization and new high-value features.
- **Maintenance Agent** owns confirmed bugs, runtime/browser/mobile reliability, performance, dependency safety and ordinary code debt.
- **Stability & Integration Agent** owns Supabase/data integrity, CI, synchronization, RLS, migrations, telemetry, deployment/config integration, agent-run health and cross-agent conflict prevention.

The exact automation schedule may change independently of this protocol. Do not infer ownership from a historical clock slot or agent letter. `alam_app/ALAM_PRODUCT_DIRECTION_2026-09-03.md` is the current priority/ownership override and must be read on every development run.

Manual ChatGPT development may occur between scheduled runs. Every development agent must inspect the latest `main`, recent commits and active CI before touching code because another development lane or a manual pass may have changed the repository.

Before a write, re-fetch the file being changed and verify branch head. If another development change is in flight, prefer read-only verification, tests, CI hardening or a non-overlapping task instead of forcing a competing edit.

Content agents are data-only. They may create/update validated ALAM data through approved content flows but must never modify application code, migrations, workflows or development protocols.

## Files every development agent must inspect first

1. `alam_app/ALAM_CONTINUOUS_ROADMAP.md`
2. `alam_app/DEVELOPMENT_AGENT_PROTOCOL.md`
3. `alam_app/ALAM_PRODUCT_DIRECTION_2026-09-03.md`
4. recent `main` commits
5. current ALAM GitHub Actions / CI results
6. relevant application modules
7. `alam_app/AGENT_DATA_CONTRACT.md` when data semantics are involved
8. `alam_app/PANEL_COMMENT_SYSTEM.md` when discussion/comment behavior is involved
9. Supabase migrations/data access/ingestion files when persistence is involved

Never develop from remembered code. The repository and live system state are the sources of truth.

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
- Innovation must not bypass Stability ownership for schema, RLS, synchronization or telemetry safety.
- Maintenance must not rewrite product behavior merely to resolve an integration concern when a boundary-safe fix exists.
- Stability must not compete with Innovation on feature design or Maintenance on isolated ordinary bugs unless the issue is specifically cross-system or integration-related.

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
- which user-visible friction or operational risk is currently highest;
- whether another development lane is actively changing overlapping files or behavior.

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
- potential interaction/conflict with either of the other development agents.

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
- operational diagnostics and failure handling;
- cross-agent ownership or synchronization invariants.

Comments should explain **why** the rule exists, what failure it prevents, and what invariants future developers must preserve. Do not clutter obvious one-line syntax with comments.

### 5. Validate before commit

Use all relevant available checks. At minimum when applicable:

- `python alam_app/validate_alam_data.py`
- Python syntax/compile checks
- Streamlit startup/health smoke check
- relevant unit/helper/integration tests when present
- GitHub Actions / ALAM app checks after push
- live Supabase verification after any DDL or synchronization change

A code commit is not "verified" merely because GitHub accepted the file update.

For DDL, use an idempotent repository migration, apply it to the intended live Supabase project only when authorized tooling is available, and verify the resulting live schema/state. Never treat a checked-in migration as proof that production was changed.

### 6. Commit and hand off

Every material iteration should leave a roadmap/handoff note when the change needs future coordination, containing:

- date/time;
- development lane/agent;
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

## Innovation Agent responsibility

Innovation owns, or coordinates, the following areas:

- mobile-first navigation and layout;
- Today/Home hierarchy and action usefulness;
- new product capabilities;
- article detail/evidence teaching experience;
- Search/Discovery/Saved/collections UX;
- personalization and recommendation behavior;
- grounded Ask ALAM product experience;
- action/checklist and briefing UX;
- cross-agent perspectives/disagreement presentation;
- accessibility and user-facing visual quality.

Innovation may request persistence or telemetry support, but Stability owns the cross-system schema/RLS/sync/security implementation and verification.

## Maintenance Agent responsibility

Maintenance owns, or coordinates, the following areas:

- confirmed application bugs;
- runtime and browser-state reliability;
- mobile rendering defects;
- performance regressions;
- dependency safety and routine upgrades;
- code debt/refactors that preserve behavior;
- loading/error/fallback reliability;
- ordinary test failures isolated to application behavior.

Maintenance should hand off schema/RLS/sync/telemetry/data-integrity failures to Stability rather than independently changing those boundaries.

## Stability & Integration Agent responsibility

Stability owns, or coordinates, the following areas:

- Supabase schema, migrations, grants and RLS;
- GitHub audit -> Supabase synchronization and reconciliation;
- article/source/version/comment/topic/prediction integrity;
- user-state persistence boundaries and ownership correctness;
- telemetry privacy/minimization and agent-run health;
- CI/workflow races and deployment/config integration;
- migration ordering/replay safety;
- partial-write recovery, duplicate/orphan detection and stale-read prevention;
- backend/browser trust boundaries;
- inter-agent overwrite/conflict prevention;
- security-advisor findings caused by ALAM changes.

Priority order:

1. runtime/security/data-loss risks;
2. cross-agent conflicting writes or stale ownership instructions;
3. Supabase/RLS/migration correctness;
4. synchronization/reconciliation/partial-write correctness;
5. CI/deployment integration health;
6. telemetry and agent-run observability;
7. recovery and durable regression guards;
8. lower-priority integration polish.

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

A development iteration is successful when it leaves ALAM measurably better in at least one core dimension—reliability, usefulness, trust, maintainability, performance, accessibility, or recovery—without making another core dimension materially worse and without violating another development lane's ownership.
