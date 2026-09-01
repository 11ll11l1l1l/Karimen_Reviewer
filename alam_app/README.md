# ALAM

**Ano'ng bago. Bakit mahalaga. Ano'ng gagawin.**

ALAM is a Taglish intelligence aggregator designed for Filipino readers. It is intentionally separate from the Karimen reviewer even though it currently lives in the same GitHub repository.

## Streamlit deployment

Create a second Streamlit Community Cloud app and use:

```text
alam_app/streamlit_app.py
```

as the entry point.

Dependencies are isolated in:

```text
alam_app/requirements.txt
```

## Architecture

The Streamlit app does **not** call OpenAI or news APIs.

Scheduled ChatGPT agents research the web and write structured JSON records into GitHub:

```text
data/
  discover/
  practical/
  reflection/
  trend/
```

Streamlit reads those records and renders the feed.

## User experience

- **Today** — curated catch-up
- **Discover** — what is new and worth knowing
- **Practical** — Japan savings, safety and risk actions
- **Reflect** — psychology, philosophy and modern Christian reflection
- **Trends** — longitudinal signals and prediction accountability

## Demo data

The included `demo.json` files are clearly marked with `"demo": true`. They exist only to make the first deployment visually useful before scheduled agents begin writing live records.

Once live ingestion is working, delete the four demo files.

## Agent write rule

Agents should add new JSON files or append new day partitions. They should not modify `streamlit_app.py`.

See `AGENT_DATA_CONTRACT.md`.
