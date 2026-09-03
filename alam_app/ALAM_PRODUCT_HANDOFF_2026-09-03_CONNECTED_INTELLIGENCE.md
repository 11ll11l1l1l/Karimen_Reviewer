# ALAM Product Handoff — Connected Intelligence

Date: 2026-09-03
Owner: Innovation Agent

## User problem
Opened stories were strong as standalone explainers but did not give readers a simple evidence-constrained path into adjacent ALAM intelligence. Readers had to return to feeds/search and infer relationships themselves.

## Root cause
`alam_intelligence.connected_stories()` already had deterministic shared-tag/connection-tag ranking, but the opened-story product route did not surface it.

## Decision
Add a compact `Connected intelligence` section to article detail. Reuse the existing deterministic connection function; do not add generated relationships, embeddings, or causal language.

## Implementation
- Added `alam_related_views.py` as the render/product boundary.
- Article detail shows at most three related validated ALAM records.
- Every recommendation states the exact shared signal tags that produced the connection.
- The UI explicitly says shared signals are context, not proof of causality.
- Tapping a result opens that stable ALAM story directly.
- Zero/one-story and no-overlap states render nothing rather than filler.
- No public article content, schema, RLS, Auth, or service credentials changed.

## Mobile behavior
Cards are single-column, compact, full-width and use existing minimum button targets. The section appears only after the learning/action layer, so it does not enlarge the persistent Today shell or interfere with navigation.

## Validation
Focused regression covers shared-signal matching, explicit `connection_tags`, unrelated-story exclusion, and zero/one-story states. Repository ALAM Actions must remain the final compile/regression/Streamlit deployment gate after push.

## Remaining limitation
Current deterministic matching is intentionally conservative and tag-dependent. A story with poor/missing connection metadata may have no related recommendations. Do not fill this gap with model-memory similarity.

## Recommended next step
Measure whether connected-story opens are useful, then consider richer evidence-backed relationship types (`contradicts`, `affects`, `contributes_to`) only when the validated record contract supplies them explicitly.
