# ALAM Innovation handoff — 2026-09-04 12:00 JST

- Agent/lane: Innovation Agent — Today/Home product UX.
- User problem: Today selected a validated actionable Practical story but flattened every decision to the generic `DO` label and `Open action`, forcing readers to open the story before knowing whether ALAM was telling them to prepare, avoid, apply, buy, wait, or act now.
- Root cause: `DO` is an internal briefing-slot type and was also being reused as reader-facing decision language even though validated v5 records already carry a structured `content.action` decision verb.
- Decision: preserve the stable internal `DO` selection/ranking contract, but derive the visible kicker and CTA from the already-published structured action. Do not infer urgency or advice from prose.
- Implementation: `alam_daily_brief.py` now maps validated `DO NOW`, `APPLY`, `AVOID`, `PREPARE`, `BUY`, and `WAIT` actions to decision-specific visible labels and mobile CTAs. Missing/unknown metadata fails closed to generic `DO` / `Open action`. Ranking, Saved-update priority, anti-filter-bubble fallback, and the three-slot limit are unchanged.
- Mobile behavior: existing full-width briefing buttons remain; the verb now communicates the decision before the tap without adding another card or extending Today vertically.
- Files affected: `alam_app/alam_daily_brief.py`, `alam_app/test_alam_daily_brief_action_labels.py`, this handoff. No schema, RLS, Auth, telemetry, service-role, or public-content changes.
- Live state inspected: required Supabase project `zecztyabmmoqzjumhxxf` reported 58 public articles and 0 Auth users. No evidence the external Auth blocker changed, so it was not revisited.
- Validation: focused regression file covers all six supported decision verbs plus malformed/missing fail-closed behavior and confirms WATCH cannot be overwritten by an action field. GitHub Actions was queued after the test commit; final full-suite status must be checked before calling the run fully green.
- Remaining limitation: this improves decision clarity, not prioritization. `content.action` quality remains governed by the publication/evidence pipeline.
- Recommended next step: continue Today personalization with a compact, explainable urgency/deadline cue only where validated structured deadline metadata exists; never infer urgency from prose.
