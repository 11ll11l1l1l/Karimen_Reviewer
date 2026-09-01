# ALAM Agent Data Contract

App agents write JSON only under their own data folder:

- Agent 2 → `alam_app/data/discover/`
- Agent 3 → `alam_app/data/reflection/`
- Agent 4 → `alam_app/data/practical/`
- Agent 5 → `alam_app/data/trend/`

The app recursively loads every `.json` file under `alam_app/data/`.

A file may contain one JSON object or a JSON array.

## Required fields

```json
{
  "id": "stable-unique-id",
  "agent": "discover",
  "created_at": "2026-09-01T21:00:00+09:00",
  "type": "technology",
  "title": "Concise factual title",
  "summary": "1-3 sentence Taglish summary",
  "why_it_matters": "Why the reader should care",
  "importance": 82,
  "confidence": 90,
  "tags": ["Japan", "AI"],
  "geography": ["Japan"],
  "status": "new",
  "sources": [],
  "content": {}
}
```

`importance` and `confidence` are integers from 0 to 100.

## Common status values

- `new`
- `update`
- `watch`
- `resolved`

## Source shape

```json
{
  "publisher": "Publisher or agency",
  "title": "Source title",
  "url": "https://...",
  "published_at": "2026-09-01",
  "source_type": "official"
}
```

## Agent 2 / Discover content

Recommended keys:

```json
{
  "whats_new": "...",
  "skeptical_view": "...",
  "what_next": "...",
  "recommendation": "WATCH / LEARN / TRY / IGNORE",
  "usefulness": 75,
  "novelty": 80
}
```

## Agent 4 / Practical content

Recommended keys:

```json
{
  "who_is_affected": "...",
  "when": "...",
  "financial_impact": "¥...",
  "risk_if_ignored": "...",
  "action": "DO NOW / WATCH / AVOID / BUY / WAIT / APPLY / PREPARE / IGNORE",
  "deadline": "...",
  "effort": "LOW",
  "potential_benefit": "...",
  "downside": "...",
  "usefulness": 95,
  "novelty": 70
}
```

## Agent 3 / Reflection content

Recommended keys:

```json
{
  "human_problem": "...",
  "psychology": "...",
  "philosophical_conflict": "...",
  "christian_analysis": "...",
  "secular_challenge": "...",
  "christian_response": "...",
  "modern_christian_life": "...",
  "questions": ["...", "...", "..."]
}
```

## Agent 5 / Trend content

Recommended keys:

```json
{
  "current_strength": 76,
  "previous_strength": 61,
  "direction": "ACCELERATING",
  "evidence_for": [],
  "evidence_against": [],
  "connection": "...",
  "alternative_explanation": "...",
  "watch_next": "...",
  "implications": "...",
  "history": [
    {"label": "May", "value": 32},
    {"label": "Jun", "value": 45}
  ]
}
```

Prediction records may instead use:

```json
{
  "statement": "...",
  "initial_probability": "55%",
  "current_probability": "72%",
  "status": "STRENGTHENING",
  "evidence_for": [],
  "evidence_against": []
}
```

## Hard rules

1. Do not modify app code.
2. Do not delete or silently rewrite old predictions.
3. Use Taglish that is clear to ordinary Filipino readers.
4. Separate verified facts from estimates and inference.
5. Do not create a record just because a scheduled run happened.
6. Zero output is valid when nothing clears the quality threshold.
7. Use Japanese primary/official sources first for Japan-specific claims when practical.
8. Never mark demo records as live.
