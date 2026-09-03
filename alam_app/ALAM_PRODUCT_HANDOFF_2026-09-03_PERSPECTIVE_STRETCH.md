# ALAM product handoff — Today Perspective Stretch

- Date: 2026-09-03
- Owner: Innovation Agent
- User problem: personalization can make the Today discovery shelf repeatedly reinforce the same category even when other validated, important ALAM intelligence is available.
- Root cause: `_discover_pool()` sorted entirely by personal relevance and feed score. Its previous anti-filter-bubble comment described an intention, but the algorithm did not reserve any diversity slot.
- Decision: preserve personalization as the default, but when the six-story shelf is materially concentrated and another validated category exists, reserve only the final slot for the strongest shared-feed-score story from an unrepresented category. Do nothing when the normal shelf is already diverse.
- Implementation: `alam_today_page._discover_pool()` now returns the selected records plus an optional deterministic perspective-stretch record. Today shows a compact explanation only when insertion actually occurred. No content is generated or rewritten.
- Mobile behavior: the explanatory note is a single compact block above the existing two-column/one-column card shelf. Navigation, Today in 3 lines, action lanes, inbox, Saved behavior and article cards are unchanged.
- Zero/one/many behavior: zero and one-story pools remain unchanged; action-lane IDs remain excluded; already-diverse shelves are untouched; concentrated shelves may replace only their final discovery card.
- Privacy/security: no new tracking, schema, Supabase write, identity inference, embedding or account requirement. Ranking uses existing validated record metadata and browser-local personalization only.
- Live state inspected: Project2 `zecztyabmmoqzjumhxxf` had 35 articles, 1 wisdom row, and still 0 Auth users at implementation time. The unchanged Auth external blocker was not revisited.
- Validation: the changed module compiled and parsed locally before the repository write. A focused regression file covers concentrated insertion, already-diverse no-op, zero/one pools and action exclusion; the repository-wide ALAM Actions workflow is the final compile/regression/Streamlit gate.
- Remaining limitation: category diversity is a coarse anti-filter-bubble mechanism, not viewpoint diversity or evidence independence. It must not be described as either.
- Recommended next step: after CI proves this stable, improve article-detail follow-through with an optional grounded action/checklist state rather than adding more Today modules.
