# ALAM

**Ano'ng bago. Bakit mahalaga. Ano'ng gagawin.**

ALAM is a mobile-first Taglish intelligence aggregator for Filipino readers. It is separate from the Karimen reviewer even though both currently live in the same GitHub repository.

## Streamlit deployment

Use a second Streamlit Community Cloud app with entry point:

```text
alam_app/streamlit_app.py
```

Dependencies are isolated in `alam_app/requirements.txt`.

## Public lenses

- **Discover** — important new developments worth knowing early
- **Action** — practical Japan savings, safety, paperwork and risk actions
- **Market** — Japan market intelligence, cross-asset transmission and calibrated outlooks
- **Trends** — longitudinal signals, connections and prediction accountability

The private Global Engineering Job Radar is chat-only and never publishes into ALAM.

## Lightweight reflection layer

The header includes a compact daily wisdom strip:
- 1-2 Bible verses shown without interpretation
- one philosophical question grounded in the previous Japan calendar day's verified headlines

This is intentionally not a separate long-form Reflection feed. It is written to `alam_app/data/wisdom/` at most once per day.

## App navigation

Primary mobile navigation is intentionally limited to five destinations: **Today, Discover, Action, Market, More**. On small screens it is pinned to the bottom for easier one-handed use.

`More` contains:
- Trends
- Search
- Saved
- Predictions
- Settings / dark mode

Article detail supports short reading, panel views, evidence, deep view, saving/following and copy/share text.

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

The app accepts either a single JSON record or a JSON array. Agents should batch multiple same-run comments/articles whenever practical to reduce Git commit/file churn.

## Production rules

The original demo records were removed on September 2, 2026. Production folders must not contain sample or synthetic articles. Empty output is preferred when research does not clear the quality threshold.

Agents must never overwrite historical intelligence. Material updates reuse a stable story ID but create a new timestamped record.

## Validation

Every ALAM app/data change is checked by GitHub Actions. The workflow runs:

```text
python alam_app/validate_alam_data.py
python -m py_compile ...
streamlit health check
```

See `AGENT_RESEARCH_PROTOCOL.md` and `AGENT_DATA_CONTRACT.md`.
