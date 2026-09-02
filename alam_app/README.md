# ALAM

**Ano'ng bago. Bakit mahalaga. Ano'ng gagawin.**

ALAM is a mobile-first Taglish intelligence system for Filipino readers. It is separate from the Karimen reviewer even though both currently live in the same GitHub repository.

## Streamlit deployment

Use a second Streamlit Community Cloud app with entry point `alam_app/streamlit_app.py`. Dependencies are isolated in `alam_app/requirements.txt`.

The Streamlit app deploys from `main`. ALAM code changes pushed to the connected repository are therefore picked up by the existing Streamlit Community Cloud deployment when that app is configured for this entry point.

Public Streamlit runtime requires:

- `SUPABASE_URL`
- `SUPABASE_PUBLISHABLE_KEY`

Never place a Supabase service-role/secret key in Streamlit Secrets or application code.

## Public lenses

- **Discover** — important new developments worth knowing early
- **Action** — practical Japan savings, safety, paperwork and risk actions
- **Market** — Japan market intelligence, cross-asset transmission and calibrated outlooks
- **Trends** — longitudinal signals, connections and prediction accountability

The private Global Engineering Job Radar is chat-only and never publishes into ALAM.

## ALAM v5 intelligence layer

The app adds intelligence on top of the article feed rather than simply listing headlines:

- **Today in 3 lines:** Know / Do / Watch
- **Story lifecycle:** NEW → DEVELOPING → CONFIRMED → FADING → RESOLVED
- **What changed:** previous state → current state for material story updates
- **Personal relevance:** local reader-selected interests rank and label stories without hiding important general news
- **Impact matrix:** money, family, career, Japan and urgency
- **Evidence health:** source strength, independence and FACT sourcing
- **ALAM disagreement:** surfaces meaningful cross-agent challenge instead of forcing consensus
- **Connect the dots:** links related stories through shared verified signal tags
- **Weekly intelligence:** rolling 7-day accountability plus a Sunday Trend-agent synthesis when enough material exists
- **In-app alert rules:** importance/action/material-change filters; these are not phone push notifications
- **Detailed panel discussion:** full persona reasoning, stance, reply context and evidence/claim metadata when available

## Lightweight reflection layer

The header includes a compact daily wisdom strip:

- 1-2 Bible verses shown without interpretation
- one philosophical question grounded in the previous Japan calendar day's verified headlines

This is intentionally not a separate long-form Reflection feed. It is written to `alam_app/data/wisdom/` at most once per day.

## App navigation

Primary mobile navigation is limited to **Today, Discover, Action, Market, More** and is pinned near the bottom on small screens.

`More` contains:

- Trends
- Weekly
- Search
- Saved
- Predictions
- Settings / dark mode / relevance / alert rules / production readiness

Article detail is decision-first: why it matters, what to do, evidence/lifecycle, material change, disagreement signal, then selectable 30-second / Panel / Evidence / Deep views.

## Production architecture

ALAM now uses a two-layer persistence design:

```text
Research agents
    ↓
GitHub JSON audit archive
    ↓ validated trusted sync
Supabase durable query/state layer
    ↓ public RLS-protected reads
Streamlit ALAM app
```

GitHub remains the human-readable research/audit trail. Agents write structured JSON under:

```text
alam_app/data/
  discover/
  practical/
  reflection/   # legacy technical key; now Market Intelligence
  trend/
  comments/
  wisdom/
```

Supabase is the preferred application read source once it contains published ALAM records. During migration/recovery, the app intentionally falls back to the committed JSON archive rather than going blank. Settings -> Production readiness shows whether the database is merely reachable, populated, fully mirrored, or actually serving the feed.

Historical Supabase article versions are folded back into ALAM's existing v5 history contract so Before/Now timelines survive the cutover.

## Trusted GitHub -> Supabase synchronization

Workflow: `.github/workflows/alam-supabase-sync.yml`

Trusted sync validates the audit archive first and then mirrors articles, sources, versions, topics, comments, wisdom, predictions and supported story relationships.

GitHub Actions requires:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`

The service-role key is used only by trusted GitHub Actions ingestion. It bypasses RLS by design and must never be copied into public Streamlit configuration.

The sync wrapper records sanitized run provenance/statistics in `agent_runs` when credentials and the table are available.

### Current manual cutover blocker

The database schema has been applied, but the first trusted GitHub Actions mirror attempt on 2026-09-02 failed because both Actions environment values were empty. Until the repository owner adds the two Actions secrets above, Supabase synchronization cannot authenticate and ALAM safely remains on the local audit fallback.

Do **not** weaken RLS or expose the service key as a workaround.

## Supabase schema

Primary one-shot setup:

- `supabase/ALAM_FULL_SETUP.sql`

For an earlier UUID-based ALAM Supabase schema, run first:

- `supabase/ALAM_EXISTING_DB_PATCH.sql`

The compatibility bridge preserves old UUID-era tables as `*_legacy_20260902` rather than destructively converting their primary/foreign keys.

Core durable entities include articles, article versions, sources, topics, comments, agent runs, rejected candidates, media assets, user preferences, saved articles, reads, feedback, notifications, briefings, predictions, relationships, wisdom and app events.

## Detailed panel comments

ALAM panel comments are analytical notes, not social reactions. See `PANEL_COMMENT_SYSTEM.md`.

The current standard expects substantial reasoning when useful: position, main insight, reasoning/mechanism, implication, uncertainty/caveat and a watch condition. New factual claims require source/claim classification. Empty panel slots are preferable to filler.

## Continuous development

See:

- `ALAM_CONTINUOUS_ROADMAP.md`
- `DEVELOPMENT_AGENT_PROTOCOL.md`

Two staggered development agents share the roadmap: backend/reliability at the hour and product/UX at half past, producing one development iteration every 30 minutes overall. Every run must inspect latest `main` and CI first, preserve newer manual/agent work, validate before committing, and leave a roadmap handoff.

## Production rules

The original demo records were removed on September 2, 2026. Production folders must not contain sample or synthetic articles. Empty output is preferred when research does not clear the quality threshold.

Agents never overwrite historical intelligence. Material updates reuse a stable story ID but create a new timestamped record with an explicit change summary.

## Validation

Every ALAM app/data change is checked by GitHub Actions. The ALAM workflow runs data validation, Python compile checks and a Streamlit health/startup smoke check.

At minimum, development agents should inspect the current ALAM workflow conclusion after pushing rather than assuming a commit is deployable merely because GitHub accepted it.

See `AGENT_RESEARCH_PROTOCOL.md`, `AGENT_DATA_CONTRACT.md`, `PANEL_COMMENT_SYSTEM.md`, `ALAM_CONTINUOUS_ROADMAP.md`, and `DEVELOPMENT_AGENT_PROTOCOL.md`.
