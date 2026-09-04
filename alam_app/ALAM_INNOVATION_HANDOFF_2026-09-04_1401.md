# ALAM Innovation handoff — 2026-09-04 14:01 JST

- Agent/lane: Innovation Agent — Today/Home product usefulness.
- User problem: Today can show only one actionable Practical item inside its three-line diversity contract. A second validated action with an explicit deadline can therefore disappear from the decision surface even though the deadline is already present in the published record.
- Root cause: the three-slot briefing intentionally balances REVIEW/KNOW/DO/WATCH and had no bounded continuation surface for additional explicit-deadline actions.
- Decision: add a compact `More action deadlines` queue below the existing briefing/Saved-change continuation. Include only validated Practical records with a supported action and an explicit non-placeholder `content.deadline`. Do not parse deadline prose, calculate urgency, reorder by date, or infer a deadline from article text.
- Implementation: `select_deadline_actions()` returns up to two unique additional actions, excludes stories already visible in the three-line briefing, ranks with ALAM's existing relevance/feed ranking, and fails closed for missing/malformed deadlines. `_render_deadline_queue()` uses vertically stacked full-width mobile buttons and the already validated action-specific CTA labels.
- Files affected: `alam_app/alam_daily_brief.py`, `alam_app/test_alam_deadline_queue.py`. No schema, RLS, Auth, telemetry, AI-generation, or public article changes.
- Mobile behavior: maximum two continuation cards; one full-width action button per card; the core three-line brief remains unchanged and bounded.
- Validation: pre-change main ALAM app checks were green. Focused regression was added for zero/malformed/excluded/duplicate/one/many deadline candidates. Post-change GitHub Actions was running when this handoff was written; do not claim final green until it completes.
- Live state checked: required Supabase project `zecztyabmmoqzjumhxxf` had 60 public articles and 0 Auth users at this run. No evidence the external Auth blocker changed, so it was not revisited.
- Remaining limitation: deadline text remains intentionally verbatim. ALAM does not yet distinguish expired/near/far deadlines because that would require a separately reviewed deterministic date contract rather than guessing from free-form text.
- Recommended next step: after CI is green, consider an explicit structured deadline/date contract at the publication layer before adding chronological deadline sorting or due-soon semantics.
