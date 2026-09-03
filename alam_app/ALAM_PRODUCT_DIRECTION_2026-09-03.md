# ALAM Product Direction — 2026-09-03

This file is a current priority override for scheduled development/content agents. Read it after the permanent protocols and roadmap. It does not weaken any research, security, RLS, evidence, or no-dummy-content rule.

## 1. Content: more useful coverage, not more noise

ALAM should feel alive every day, but volume is never a reason to publish weak material.

For Discover + Practical scans:
- Build a broad candidate pool before choosing stories. When the web/news cycle permits, inspect at least 8 materially different candidates across government, household money, immigration, tax, social insurance, childcare/school, health cost, scams/recalls, disaster readiness, housing/utilities, transport, work rights, engineering/technology and science.
- Reject duplicates, PR-only announcements, rumors, trivial product releases, generic lifestyle filler, recycled explainers with no reader value, and any story whose strongest source cannot support the headline.
- Prefer 1–2 excellent items over 5 shallow items. Zero remains valid.
- Maintain a daily portfolio rather than repeatedly covering one topic. Before publishing, check what ALAM already published that Japan calendar day and intentionally fill meaningful gaps.
- Fresh news is first priority. If the fresh-news pool is weak, at most one evergreen essential-Japan explainer may be published in a run, but only when it fills a real archive gap and is grounded in current official sources.
- For Filipino families in Japan, especially value practical gaps involving immigration/residence procedures, taxes, social insurance, benefits/subsidies, children/school, healthcare costs, remittances/overseas dependents, scams/recalls, disaster preparation, housing/utilities, transport and household savings. Do not infer private traits about individual readers.
- Every practical item must answer: Am I affected? What is the exact deadline/rule? What should I prepare? What do I do in order? What common mistake costs money/time/safety?
- Every Discover item must answer: What is actually new? What was demonstrated? What is still only promise? Why should a normal reader care?
- Keep FACT / INFERENCE / ESTIMATE / ASSUMPTION separation and the adversarial contradiction pass. A primary source is necessary for high-impact Japan policy/safety stories whenever available, but primary-source PR language is not automatically trusted interpretation.
- Opened articles remain teacher-mode and must satisfy ARTICLE_LEARNING_STANDARD.md.

## 2. Engagement objective: useful return behavior, never dark patterns

Optimize for readers coming back because ALAM remembered what matters and helped them act—not because of infinite scroll, outrage, gamified anxiety or notification spam.

Preferred engagement signals:
- saves/bookmarks;
- useful/not-useful feedback;
- source opens;
- action/checklist completion;
- updated-since-saved review completion;
- return to genuinely changed stories;
- successful search/discovery;
- reading a personalized daily/weekly briefing;
- following a prediction through resolution;
- asking a grounded question that ALAM can answer from verified records.

Do not optimize for raw session length, scroll depth, clickbait CTR or notification count.

## 3. Product/UX priority lanes

After any immediate P0 breakage is safe, development should continuously rotate through these lanes rather than getting stuck on one blocker:

1. Mobile visual quality — cleaner hierarchy, typography, spacing, card density, bottom navigation, touch behavior, loading/empty/error states and article readability.
2. Today — concise personalized intelligence: what changed, urgent actions, prepare/avoid/watch, saved-story updates, and a strong 3-line briefing.
3. Article detail — excellent teaching, evidence, before/now change history, action checklist, related stories, substantive agent perspectives and clear uncertainty.
4. Search/discovery — fast full-text/topic search, filters, related stories, anti-filter-bubble discovery and explainable recommendations.
5. Saved/collections — Read Later / Money / Japan / Family / Ideas / Important collections, updated-since-saved state, cross-device sync and useful revisit queues.
6. Agent experience — make specialized agents feel valuable through evidence-backed disagreement, prediction scorecards, what-changed reasoning and transparent run health; never fabricate debate.
7. Ask ALAM — a retrieval-grounded Q&A experience that answers only from validated ALAM records/sources, cites the supporting stories/sources, states when evidence is insufficient, and never substitutes model memory for the verified corpus.
8. Action follow-through — optional checklists/reminders for deadlines and saved actionable stories, using Supabase state when authenticated and safe browser fallback when anonymous.
9. Weekly intelligence — concise accountability report: what mattered, what was noise, what changed, what ALAM got wrong, what to watch next.

## 4. Supabase should become the product memory layer

Use Supabase deliberately for durable/queryable state, not merely as a JSON mirror.

High-value uses:
- optional Auth with anonymous-first experience;
- RLS-protected saved articles, collections, preferences, reading state and feedback;
- account-linked read history without destroying anonymous audit history;
- briefing state and updated-since-last-visit baselines;
- action/checklist state where appropriate;
- compact engagement analytics using privacy-minimized events;
- feature flags / rollout metadata when useful;
- agent-run health, rejected-candidate operations and sync observability in trusted/admin paths;
- pgvector/embedding-based retrieval only if implemented with current Supabase guidance, clear cost/security boundaries, and a deterministic fallback. Do not add embeddings merely because they are fashionable.

All exposed user tables require correct RLS ownership. Never expose service-role credentials. New privileged functions must be narrowly scoped, explicit about auth.uid(), and reviewed for PUBLIC execute grants/search_path.

## 5. AI-agent feature direction

AI should add synthesis and judgment transparency, not hallucinated content.

Prioritize:
- grounded Ask ALAM over verified article/source corpus;
- agent comparison: where Discover/Practical/Market/Trend agree, disagree or use different evidence;
- automatic but evidence-constrained related-story links;
- daily briefing synthesis from already validated stories;
- prediction calibration and retrospective scoring;
- article gap detection: what important Japan-family topic is missing from the archive;
- quality/rejection explanations for trusted operators;
- generated editorial images only as clearly editorial fallback.

Never let an AI generation step bypass the publication evidence gate.

## 6. Blocker rule

An external/manual blocker may stop only the blocked subtask, not the whole agent.

If Auth email-template configuration, deployment settings, credentials or another owner-side action prevents full verification:
1. document the blocker once with exact evidence;
2. leave the partial feature safe and non-deceptive;
3. on later runs, re-check only when there is evidence the blocker changed;
4. otherwise move to the next non-conflicting high-value product improvement.

## 7. Three development agents

Current scheduled development ownership is intentionally split:
- Innovation Agent: user-facing capabilities, UX/product intelligence, personalization and new high-value features.
- Maintenance Agent: confirmed bugs, runtime/browser/mobile reliability, performance, dependency safety and code debt.
- Stability & Integration Agent: Supabase/data integrity, CI, sync, RLS, migrations, cross-agent conflicts and platform safety.

They must inspect recent commits and avoid duplicate/conflicting edits. A run that only verifies another agent's just-completed work is valid when that is the safest high-value action.

## 8. Near-term priority

The next product phase should make the new account/state foundation visible and useful. Highest-value candidates are:
- finish real OTP production verification when the external email-template setting is available, but do not stall on it;
- strengthen mobile Today/Home visual hierarchy;
- add Saved collections and account-synced state;
- build the first grounded Ask ALAM retrieval flow over validated stories;
- improve personalized daily briefing/recommendations using explicit reader preferences plus anti-filter-bubble insertion;
- add privacy-minimized Supabase engagement signals and use them to measure usefulness, not addiction;
- expose calm agent/data health where it helps trust, while keeping private operational details private.
