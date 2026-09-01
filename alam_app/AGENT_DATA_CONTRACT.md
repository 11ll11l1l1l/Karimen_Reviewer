# ALAM Agent Data Contract v2

App agents write JSON only under their own data folder:

- Agent 2 → `alam_app/data/discover/`
- Agent 3 → `alam_app/data/reflection/`
- Agent 4 → `alam_app/data/practical/`
- Agent 5 → `alam_app/data/trend/`

The app recursively loads every `.json` file under `alam_app/data/`. A file may contain one JSON object or a JSON array. Never overwrite old intelligence records; create a new timestamped file for every material update.

## Required top-level fields

```json
{
  "id": "stable-story-id",
  "agent": "discover",
  "created_at": "2026-09-01T23:40:00+09:00",
  "type": "technology",
  "title": "Concise factual title",
  "summary": "1-3 sentence natural Taglish summary",
  "why_it_matters": "Why the reader should care",
  "importance": 82,
  "confidence": 90,
  "tags": ["Japan", "AI"],
  "geography": ["Japan"],
  "status": "new",
  "sources": [],
  "claims": [],
  "content": {}
}
```

`importance` and `confidence` are integers 0-100. Confidence is confidence in the overall assessment; it does NOT turn an inference into a fact.

## Source requirement

Every factual story must include usable sources. Prefer primary/official sources. Japan-specific claims should use Japanese official/primary sources first when practical.

```json
{
  "publisher": "Agency / company / publication",
  "title": "Exact source title",
  "url": "https://...",
  "published_at": "2026-09-01",
  "source_type": "official"
}
```

Recommended `source_type`: `official`, `primary`, `research`, `filing`, `news`, `analysis`, `other`.

## Mandatory claim ledger: FACT vs INFERENCE vs ASSUMPTION

Do not mix sourced facts with analysis in one unlabeled paragraph when a claim matters to the recommendation.

```json
"claims": [
  {
    "kind": "FACT",
    "text": "The ministry announced the measure on September 1.",
    "source_refs": [1],
    "basis": "Official ministry announcement"
  },
  {
    "kind": "INFERENCE",
    "text": "This likely increases household pressure after the subsidy expires.",
    "source_refs": [1, 2],
    "basis": "Inference from the end date and household-cost data"
  },
  {
    "kind": "ESTIMATE",
    "text": "A typical affected household may pay about ¥1,200-¥1,800 more per month.",
    "source_refs": [1, 3],
    "basis": "Calculated estimate; assumptions stated in content"
  },
  {
    "kind": "ASSUMPTION",
    "text": "Assumes current consumption remains similar through winter.",
    "source_refs": [],
    "basis": "Working assumption used for the estimate"
  }
]
```

Allowed kinds: `FACT`, `INFERENCE`, `ESTIMATE`, `ASSUMPTION`, `OPINION`.

Hard rule: a `FACT` should normally include one or more `source_refs` pointing to the 1-based position in `sources`. If it cannot be sourced, do not label it FACT.

## Reading levels

When practical, provide:

```json
"content": {
  "reading_levels": {
    "30_sec": "Compact event + impact + action.",
    "2_min": "More context, evidence and caveats.",
    "deep": "Optional prewritten deep-dive."
  }
}
```

## Updates and story timelines

Reuse the same stable `id` when the SAME story materially changes, but write a new file:

```json
"content": {
  "change_summary": {
    "previous": "Proposal only; implementation unclear.",
    "now": "Official implementation date confirmed."
  }
}
```

Never delete or silently rewrite old predictions or assessments.

## PR vs Reality

For government/corporate/political/product announcements where framing matters:

```json
"content": {
  "pr_vs_reality": {
    "official_claim": "What the organization says or implies.",
    "evidence_says": ["Supported point", "Important limitation"],
    "verdict": "Short balanced ALAM assessment."
  }
}
```

Do not invent a PR-vs-reality conflict if the evidence does not support one.

## What would change our mind?

For uncertain or developing stories add:

```json
"content": {
  "what_would_change_mind": "Specific new evidence that would strengthen, weaken, or reverse the conclusion."
}
```

## Agent 2 / Discover

Recommended keys: `whats_new`, `skeptical_view`, `what_next`, `what_would_change_mind`, `recommendation`, `usefulness`, `novelty`.

## Agent 4 / Practical

Recommended keys:

```json
{
  "who_is_affected": "...",
  "when": "...",
  "financial_impact": "¥...",
  "estimated_saving_yen": 8400,
  "time_minutes": 15,
  "travel_minutes": 0,
  "risk_if_ignored": "...",
  "action": "DO NOW / WATCH / AVOID / BUY / WAIT / APPLY / PREPARE / IGNORE",
  "deadline": "...",
  "effort": "LOW",
  "potential_benefit": "...",
  "downside": "...",
  "what_would_change_mind": "...",
  "usefulness": 95,
  "novelty": 70
}
```

Omit savings/time fields rather than inventing values. They power the app's `Sulit ba?` calculation.

## Agent 3 / Reflection

Recommended keys: `human_problem`, `psychology`, `philosophical_conflict`, `christian_analysis`, `secular_challenge`, `christian_response`, `modern_christian_life`, and exactly three `questions`. Clearly distinguish psychological evidence from philosophical/theological interpretation.

## Agent 5 / Trend and Prediction

Recommended trend keys: `current_strength`, `previous_strength`, `direction`, `evidence_for`, `evidence_against`, `connection`, `alternative_explanation`, `watch_next`, `what_would_change_mind`, `implications`, `history`.

Prediction keys: `statement`, `initial_probability`, `current_probability`, `status`, `evidence_for`, `evidence_against`.

Prediction statuses: `OPEN`, `STRENGTHENING`, `WEAKENING`, `CONFIRMED`, `PARTLY_CONFIRMED`, `WRONG`, `EXPIRED`.

## Hard rules

1. Do not modify app code.
2. Do not delete or silently rewrite historical intelligence.
3. Use natural Taglish understandable to ordinary Filipino readers.
4. Explicitly separate FACT, INFERENCE, ESTIMATE and ASSUMPTION.
5. Include sources for factual claims; never fabricate source URLs, titles or dates.
6. Do not create a record just because a scheduled run happened.
7. Zero output is valid when nothing clears the quality threshold.
8. Use Japanese primary/official sources first for Japan-specific claims when practical.
9. Never mark demo records as live.
10. Facts describe what sources establish; recommendations and predictions remain clearly analytical.
11. If evidence conflicts, show the conflict instead of choosing a convenient narrative.
12. When ALAM is wrong, preserve the old record and publish a correction.
