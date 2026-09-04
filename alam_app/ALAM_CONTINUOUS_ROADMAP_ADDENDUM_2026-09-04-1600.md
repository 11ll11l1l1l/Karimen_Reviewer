# ALAM Continuous Roadmap Addendum — 2026-09-04 16:00 JST

Lane: Today / Home personalized decision briefing

User problem: a reader could already see the validated action, deadline, and affected audience on Today, but still had to open the story to understand the consequence of doing nothing. That weakens fast mobile triage because “what should I do?” was visible while “why does ignoring this matter?” was not.

Root cause: Practical v5 records already carry `content.risk_if_ignored`, but `alam_daily_brief.py` did not expose that field in the primary DO card or the bounded additional deadline queue. Live project `zecztyabmmoqzjumhxxf` has 62 public articles; 31 current Practical records carry a usable string `risk_if_ignored` value, with an average length around 203 characters, so dumping the full field would also make Today too dense.

Decision: add a compact, explicit `If ignored · …` preview to actionable Today cards only when the validated Practical record itself publishes `risk_if_ignored`. Do not infer risk from title, summary, article prose, urgency metadata, user behavior, interests, deadlines, or profile state.

Implementation: `alam_daily_brief.py` now includes `_risk_note(record)`. It accepts only a string from `content.risk_if_ignored`, collapses whitespace, suppresses empty/TBD/unknown/N/A placeholders and non-string/structured values, and caps the mobile preview at 140 characters. The primary Today DO card and `More action deadlines` use the same helper and label the consequence explicitly so it cannot be confused with a newly generated recommendation.

Mobile behavior: the consequence is a single compact stacked `intel-mini` row inside the existing card. No new horizontal layout, modal, navigation step, or touch target was added; the existing full-width action CTA remains unchanged. The 140-character cap prevents the average ~203-character live field from turning the Today surface into long-form article detail.

Validation: focused local fail-closed checks passed before the repository write. GitHub `ALAM app checks` run 669 for feature/test revision `b61bd7d72d99d7a849fbd5643a399256ce2d8970` completed successfully: production-data validation, all regression assertions, Today personalization, publication/evidence gates, Ask ALAM grounding, accessibility contract, compact mobile shell, full ALAM Python syntax compilation, and Streamlit startup all passed.

Security/data impact: no schema, migration, RLS, Auth, service-role, telemetry, synchronization, AI generation, publication gate, or public article content changes. Anonymous fallback is unchanged. Live Auth user count remains 0, so the previously recorded external Auth blocker was not revisited.

Remaining limitation: `risk_if_ignored` is free-form validated article metadata, not a structured probability or severity estimate. Today therefore shows the published consequence but does not rank by that text, compute urgency from it, or claim that the consequence will occur.

Recommended next step: keep Today bounded and move deeper action guidance into article detail. A strong next increment is to make validated `action_plan` requirements/progress easier to scan on mobile, especially “what is left” and “what do I need before starting,” without inventing steps that are absent from the source record.
