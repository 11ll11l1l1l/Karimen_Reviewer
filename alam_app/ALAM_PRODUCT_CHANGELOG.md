# ALAM Product Builder Handoff

## 2026-09-03 — Selected-story history hydration

- User problem found: opening one article detail page on the Supabase-backed app hydrated `article_versions` for every current story before rendering the selected story. This added unrelated network payload and parsing to the most latency-sensitive mobile navigation path.
- Root cause: `extras.load_article_records()` combined current rows with all history before `selected_story` was resolved.
- Product/design decision: resolve the current feed first, validate the selected story, then hydrate history for only that stable story ID. Keep feed/list routes on the existing full-history contract for now because Today, Weekly, inbox/change detection, profile and offline flows legitimately consume `all_records`.
- Implementation summary: added `alam_article_scope.py` with a current-only Supabase loader and selected-story history merge; `streamlit_app.py` now resolves valid detail selection before version-history hydration. Stale/invalid selection fails safely back to the existing full-feed history path. Local/GitHub fallback deliberately preserves its existing full-file behavior.
- Files/components affected: `alam_app/alam_article_scope.py`, `alam_app/streamlit_app.py`, `alam_app/test_alam_article_scope.py`, `.github/workflows/alam-checks.yml`.
- Mobile behavior: article detail keeps the same headline, decision summary, Before/Now timeline, Evidence, Deep view, Panel, save/share controls and deep selection state while reducing the Supabase history query from all current story IDs to one selected story ID.
- Zero/one/many behavior: zero or invalid selection does not widen from an empty detail scope; one valid selected story requests one ID; many feed stories remain unchanged outside detail. Supabase unavailable/local migration fallback continues using the mature local record scan.
- Backend/error behavior: a selected-history query failure leaves the current article readable and records the existing sanitized history error for Settings diagnostics. Backend errors are not converted into a fake healthy state.
- Validation: deterministic scope/dedup regression test added and CI now syntax-compiles the scope module/test alongside the normal ALAM production-data, backend, product, accessibility and Streamlit health gates.
- Remaining limitation: current article loading still hydrates normalized sources for all current stories because article cards display evidence counts. Route-specific source query reduction needs a backend/current-row aggregate contract or measured UI redesign; do not remove source data from cards speculatively.
- Recommended Agent A next step: continue structured source/evidence publication quality gates and persisted rejection reasons. If performance work exposes compact source-count/primary-count columns safely, Agent B can later avoid full source-body hydration on list routes.
- Recommended Agent B next step: after this scoped-history change is proven in CI, measure route-level source payload/call counts before changing source hydration or non-detail history behavior.
