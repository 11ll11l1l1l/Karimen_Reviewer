# ALAM Agent Data Contract v5

ALAM is a curated Taglish intelligence app. Zero article output is valid when nothing clears the quality threshold.

## Public lenses and write locations

- Agent 2 / Discover → `alam_app/data/discover/`
- Agent 3 / Japan Market Intelligence & Outlook → `alam_app/data/reflection/` (legacy folder key retained for compatibility)
- Agent 4 / Practical Japan → `alam_app/data/practical/`
- Agent 5 / Trend & Prediction → `alam_app/data/trend/`
- Public persona comments → `alam_app/data/comments/`
- Daily wisdom strip → `alam_app/data/wisdom/YYYY-MM-DD.json`

Job Radar is private/chat-only and never writes ALAM data.

Agents must never modify app code, requirements, another agent's article folder, or historical intelligence records. Material story updates reuse the same stable story `id` but always create a new timestamped file.

## Commit-efficiency rule

GitHub is an ingestion layer, not a chat transcript. Minimize repository churn.

- Prefer **one article file per run** containing an array when several articles qualify.
- Prefer **one comments file per run** containing an array of all useful comments from that run.
- Do not create one Git commit per persona comment when comments can be batched safely.
- Zero-output runs should create no empty files.
- The app loader supports either a single JSON object or a JSON array.

## Article record

Required fields:

```json
{
  "id": "stable-story-id",
  "agent": "discover",
  "created_at": "2026-09-02T00:12:00+09:00",
  "type": "technology",
  "title": "Concise factual title",
  "summary": "1-3 sentence natural Taglish summary",
  "why_it_matters": "Why the reader should care",
  "importance": 82,
  "confidence": 90,
  "tags": ["Japan", "AI"],
  "geography": ["Japan"],
  "status": "NEW",
  "sources": [],
  "claims": [],
  "content": {}
}
```

`importance` and `confidence` are integers 0-100. Confidence does not convert analysis into fact.

## Article image contract

Every article must have one of these two visual paths.

### A. Verified real image
Use a stable, directly usable official/primary image only when it genuinely represents the story.

```json
{
  "image_url": "https://official.example/image.jpg",
  "image_alt": "Accurate concise description",
  "image_credit": "Agency / company / photographer"
}
```

Do not invent URLs or use unstable scraped thumbnails.

### B. ALAM editorial fallback
If no suitable real image is available, the publishing agent MUST create an `editorial_visual` art direction. The app converts this into a local editorial illustration, so no external image is required.

```json
{
  "editorial_visual": {
    "style": "editorial",
    "motif": "chip",
    "secondary_motif": "factory",
    "scene": "oversized chip looming over a tiny factory",
    "caption": "AI demand feels larger than the factory floor",
    "silliness": 28,
    "exaggeration": 64
  }
}
```

Allowed `motif` / `secondary_motif` values: `yen`, `chip`, `robot`, `factory`, `train`, `family`, `shield`, `document`, `market`, `policy`, `home`, `earthquake`, `car`, `weather`, `globe`, `battery`.

Rules:
- `style` should be `editorial`.
- `motif` is required for fallback; `secondary_motif` is optional.
- `scene` should be a concise visual metaphor, normally 3-16 words.
- `caption` is optional art direction, not a factual claim.
- `silliness` and `exaggeration` are integers 0-100. The agent decides both based on topic and tone.
- Serious safety, disaster, death, legal, medical, or human-harm stories should normally keep silliness low.
- The illustration must not fabricate evidence, impersonate a real photograph, or depict unverified actions by named people.
- Prefer visual metaphor and exaggeration when useful; do not make every story silly.

## Sources

Every factual story must include usable sources. Prefer official/primary sources. For Japan-specific claims, search Japanese-language official/primary sources first when practical.

```json
{
  "publisher": "Agency / company / publication",
  "title": "Exact source title",
  "url": "https://...",
  "published_at": "2026-09-02",
  "source_type": "official"
}
```

Recommended source types: `official`, `primary`, `research`, `filing`, `news`, `analysis`, `other`.

## FACT / INFERENCE / ESTIMATE / ASSUMPTION separation

Important claims must be classified. Allowed kinds: `FACT`, `INFERENCE`, `ESTIMATE`, `ASSUMPTION`, `OPINION`.

```json
{
  "kind": "FACT",
  "text": "The ministry announced the measure on September 2.",
  "source_refs": [1],
  "basis": "Official ministry announcement"
}
```

A `FACT` must have valid 1-based `source_refs`. Unsourced material must not be labeled FACT.

## Reading levels and history

When useful, include `content.reading_levels.30_sec`, `2_min`, and optional `deep` text. For material story updates, add `content.change_summary` and never silently rewrite history.

For government, corporate, political or product framing, use `content.pr_vs_reality` only when evidence supports a meaningful distinction. For uncertain stories add `content.what_would_change_mind`.

## Agent 2 / Discover

Recommended content: `whats_new`, `skeptical_view`, `what_next`, `what_would_change_mind`, `recommendation`, `usefulness`, `novelty`.

Personas:
- `kiko-kuryoso` — Kiko Kuryoso 🔭, Curious Scout
- `mara-teka` — Mara Teka 🧐, Evidence Skeptic

## Agent 3 / Japan Market Intelligence

New records in the legacy `reflection` folder must use one of:
- `market_outlook`
- `market_recap`
- `market_risk`
- `market_regime`

Recommended content: `session`, `market_regime`, `what_moved`, `why_it_moved`, `japan_transmission`, `breadth_and_sectors`, `fx_rates_cross_asset`, `fundamental_vs_positioning`, `bull_case`, `bear_case`, `market_pricing_inference`, `opening_bias`, `forecast_next_session`, `forecast_5d`, `forecast_1_3m`, `catalysts`, `practical_guidelines`, `what_would_change_mind`, `forecast_scorecard`, `usefulness`, `novelty`.

Personas:
- `jiro-daloy` — Jiro Daloy 📈, Market Transmission Analyst
- `aya-presyo` — Aya Presyo ⚖️, Valuation & Risk Skeptic

Legacy philosophical Reflection records remain historical only and should not be created by Agent 3 anymore.

## Agent 4 / Practical Japan

Recommended content: `who_is_affected`, `when`, `financial_impact`, `estimated_saving_yen`, `time_minutes`, `travel_minutes`, `risk_if_ignored`, `action`, `deadline`, `effort`, `potential_benefit`, `downside`, `what_would_change_mind`, `usefulness`, `novelty`.

Allowed action labels: `DO NOW`, `WATCH`, `AVOID`, `BUY`, `WAIT`, `APPLY`, `PREPARE`, `IGNORE`.

Personas:
- `mika-sulit` — Mika Sulit 💸, Value Optimizer
- `ramon-ingat` — Ramon Ingat 🛡️, Risk Planner

## Agent 5 / Trend & Prediction

Recommended trend keys: `current_strength`, `previous_strength`, `direction`, `evidence_for`, `evidence_against`, `connection`, `alternative_explanation`, `watch_next`, `what_would_change_mind`, `implications`, `history`.

Prediction statuses: `OPEN`, `STRENGTHENING`, `WEAKENING`, `CONFIRMED`, `PARTLY_CONFIRMED`, `WRONG`, `EXPIRED`.

Personas:
- `nico-signal` — Nico Signal 📡, Pattern Hunter
- `bea-base-rate` — Bea Base Rate 📊, Statistical Skeptic

## Daily wisdom strip

This is the lightweight reflection layer and is not a fifth article feed. Once per Japan calendar day, one assigned public agent may write:

```json
{
  "date": "2026-09-02",
  "based_on": "2026-09-01 headlines",
  "question": "One concise philosophical question grounded in the previous day's real headlines.",
  "verses": [
    {
      "reference": "Proverbs 2:6",
      "translation": "KJV",
      "text": "Exact Bible verse text"
    }
  ]
}
```

Rules:
- Base the question on the previous Japan calendar day's verified ALAM headlines or verified major headlines.
- Keep the question philosophical rather than partisan, preachy, or advice-like.
- Include 1-2 concise Bible verses related to wisdom, knowledge, stewardship, truth, prudence, work, responsibility, or discernment.
- **Do not interpret, explain, harmonize, apply, or paraphrase the verses.** Display scripture only.
- Do not invent a verse or reference. Use a stable public-domain translation such as KJV unless another licensed/allowed translation is clearly available.
- Create at most one wisdom file per date.

## Comment records

Comments are optional. Silence beats filler. Each comment requires `id`, `story_id`, `created_at`, `agent`, `persona_id`, and `body`. New factual claims need sources/claim classification. Cross-agent comments should be batched into one JSON array file per run when more than one comment is written.

## Validation

`python alam_app/validate_alam_data.py` is a production gate. Agents should verify JSON after writing. Invalid JSON, invalid source references, missing required fields, malformed wisdom/comment records, or malformed editorial fallback metadata must be corrected immediately.