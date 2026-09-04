# ALAM Continuous Roadmap Addendum — 2026-09-04 18:00 JST

Lane: Article detail / action teaching

User problem: Practical stories already exposed a recommendation and, when present, an action checklist, but the opened article did not put the three most important decision qualifiers together before the reader started acting: who the rule applies to, the published deadline/timing, and the published consequence of ignoring it. Those facts existed in validated v5 records and had become visible on Today, yet article detail still forced readers to hunt through deeper content.

Root cause: `alam_story_page.py` rendered the decision grid and then jumped directly into the checklist/change/learning sequence. It had no compact article-detail projection for `content.who_is_affected`, `content.deadline`/`content.when`, and `content.risk_if_ignored`.

Decision: add a bounded `Before you act` snapshot immediately below the decision grid for Practical records. It is retrieval/display-only: no eligibility inference, urgency calculation, deadline parsing, or generated advice.

Implementation: `alam_story_page.py` now normalizes only explicit string metadata through `_safe_action_fact()` and builds `_practical_action_snapshot()`. The renderer shows up to three compact fields: Affected, Deadline / timing, and If ignored. Placeholder, structured, boolean, missing, or non-string values fail closed. `deadline` takes precedence over the older `when` field; `when` is only a direct-record fallback. Desktop uses a compact three-column row; mobile collapses to one stacked column before the existing validated checklist.

Validation: focused regression coverage in `test_alam_story_page.py` proves the three explicit fields, whitespace normalization, non-Practical suppression, and fail-closed malformed/placeholder behavior. Repository CI was green on the pre-change main (`d8d3705...`). Post-change ALAM app checks for feature/test head `9186ab7...` were in progress at handoff, so full production-data/compile/Streamlit validation is not yet claimed complete.

Security/data impact: no schema, migration, RLS, Auth, service-role, synchronization, telemetry, AI generation, publication gate, or public article content changes. Anonymous behavior is unchanged. Live project `zecztyabmmoqzjumhxxf` had 62 public articles and 0 Auth users at this run; the unchanged external Auth blocker was not revisited.

Remaining limitation: these are free-form validated article fields, not a machine-readable eligibility/deadline engine. The UI therefore displays what the record explicitly says and does not decide whether a specific reader qualifies or whether a deadline is urgent.

Recommended next step: continue article-detail action quality by making prerequisites/documents explicit only when the validated action-plan contract gains a defensible structured field; do not infer required documents from prose.
