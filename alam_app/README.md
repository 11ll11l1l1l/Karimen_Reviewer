# ALAM

**Ano'ng bago. Bakit mahalaga. Ano'ng gagawin.**

ALAM is a mobile-first Taglish intelligence system for Filipino readers. It is separate from the Karimen reviewer even though both currently live in the same GitHub repository.

## Streamlit deployment

Use a second Streamlit Community Cloud app with entry point `alam_app/streamlit_app.py`. Dependencies are isolated in `alam_app/requirements.txt`.

## Public lenses

- **Discover** — important new developments worth knowing early
- **Action** — practical Japan savings, safety, paperwork and risk actions
- **Market** — Japan market intelligence, cross-asset transmission and calibrated outlooks
- **Trends** — longitudinal signals, connections and prediction accountability

The private Global Engineering Job Radar is chat-only and never publishes into ALAM.

## ALAM v5 intelligence layer

The app now adds intelligence on top of the article feed rather than simply listing headlines:

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
- Settings / dark mode / relevance / alert rules

Article detail supports short reading, panel views, evidence, deep view, saving/following, copy/share text and the v5 Intelligence Snapshot.

## Architecture

Scheduled ChatGPT agents research the web and write structured JSON into GitHub. Streamlit does not call OpenAI or news APIs at runtime.

```text
alam_app/data/
  discover/
  practical/
  reflection/   # legacy key; now Market Intelligence
  trend/
  comments/
  wisdom/
```

The app accepts either a single JSON record or a JSON array. Agents batch multiple same-run comments/articles when practical to reduce Git churn. Article loading is isolated from the comments/wisdom archive to keep startup cost controlled.

GitHub remains the current ingestion and audit layer. A future database migration should preserve the same v5 contract rather than changing agent semantics; user account storage is intentionally not introduced until authentication/cross-device state is needed.

## Production rules

The original demo records were removed on September 2, 2026. Production folders must not contain sample or synthetic articles. Empty output is preferred when research does not clear the quality threshold.

Agents never overwrite historical intelligence. Material updates reuse a stable story ID but create a new timestamped record with an explicit change summary.

## Validation

Every ALAM app/data change is checked by GitHub Actions. The workflow runs:

```text
python alam_app/validate_alam_data.py
python -m py_compile ...
streamlit health check
```

See `AGENT_RESEARCH_PROTOCOL.md` and `AGENT_DATA_CONTRACT.md`.
