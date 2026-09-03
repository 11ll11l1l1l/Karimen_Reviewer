# ALAM Product Handoff — Saved-aware Today briefing — 2026-09-03

## User problem

Today already ranked stories by personal relevance, but the compact `Today in 3 lines` summary did not recognize the strongest return-use case ALAM already knew locally: a Saved story receiving a newer material version. It also showed a numeric relevance score without explaining why a story was selected.

## Root cause

The previous `daily_three()` selector in `alam_intelligence.py` used fixed Discover / Practical / Trend-Market category slots and personal relevance ranking. Saved-update state lived separately in `alam_local_state.saved_has_update()`, so the briefing could overlook a story the reader explicitly saved and now needed to review. Missing category lanes also had no deliberate anti-filter-bubble fallback.

## Product decision

Keep the briefing to at most three lines and make it a deterministic retrieval product over already validated ALAM records:

1. If a Saved story has a newer material version, promote the strongest one into a `REVIEW` slot.
2. Preserve a verified actionable Practical `DO` slot when available.
3. Preserve cross-lens breadth through `WATCH` and `KNOW` candidates.
4. When a normal lane is missing, fill it by category novelty and public importance before personalized relevance. This is a small anti-filter-bubble guard, not a replacement for explicit preferences.
5. Explain each selection using existing interest matches, action state, Saved-change state, or high-importance balance.
6. Never generate claims or new article text. The feature only selects and summarizes fields already inside validated ALAM records.

## Implementation

- `alam_app/alam_daily_brief.py`
  - isolated deterministic selector `select_daily_brief_rows()`;
  - Saved material-update detection through existing browser/account-aware local state;
  - explainable selection reason;
  - conservative current-change copy through existing `change_snapshot()`;
  - one native full-width `Review changed Saved story →` action only when a changed Saved story exists;
  - HTML escaping before rendering validated record text.
- `alam_app/alam_today_page.py`
  - delegates the compact three-line block to the new briefing module;
  - existing alert, action lanes, inbox, Discover cards and navigation remain unchanged.
- `alam_app/test_alam_daily_brief.py`
  - proves Saved update precedence, uniqueness, normal no-Saved behavior, sparse category fallback and zero-record behavior.
- `.github/workflows/alam-checks.yml`
  - runs the new Today briefing regression in the ALAM-specific CI gate.

## Mobile / product behavior

The feature reuses the existing compact responsive three-line grid and does not add another persistent Today module. On mobile the cards retain the existing one-column collapse. Only a relevant Saved material update adds one native review button below the compact block. No CookieManager placement, brand shell, bottom navigation, fallback banner, wisdom/Bible verse rendering, or article-card CSS was changed.

## Production state observed during this iteration

Live Project2 `zecztyabmmoqzjumhxxf` had 31 articles and 1 wisdom row, with 0 Auth users and therefore 0 authenticated Saved, preference, or read rows at inspection time. The feature intentionally works immediately through the anonymous browser Saved/version fallback. No Supabase schema or privileged credential change was required.

The optional Auth email/provider configuration remains externally blocked and was not repeatedly reworked because no evidence of that production setting changing was present.

## Validation

ALAM app checks run `33721442031` completed successfully after implementation and CI integration. The run passed production-data validation, image regressions, Supabase reconciliation/recovery tests, publication/lifecycle gates, Saved-update behavior, the new Today briefing regression, Auth/device/read-mirror tests, Ask ALAM grounding, accessibility, compact mobile shell, full `python -m compileall -q alam_app`, and Streamlit startup.

## Remaining limitation

A Saved update can only be promoted when ALAM has a trustworthy saved-version baseline. Legacy browser saves created before version snapshots existed intentionally do not receive a false `UPDATED`/`REVIEW` state until a valid baseline is established. Cross-device Saved state remains dependent on the optional Auth path becoming actively used.

## Recommended next product step

Continue the Today/action lane rather than adding more feed surface: add optional per-story action/checklist follow-through using safe anonymous browser state first, then account state when Auth is genuinely available. This should remain grounded in explicit article actions/deadlines and must not invent tasks from weak or non-actionable stories.
