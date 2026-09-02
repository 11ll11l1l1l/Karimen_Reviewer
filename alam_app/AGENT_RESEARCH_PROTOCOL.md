# ALAM Deep Research Protocol

All ALAM research passes should use this protocol on every scheduled run. The goal is to maximize useful research work, not output length.

## 1. Archive-first state check
- Read the latest meaningful records in all relevant ALAM folders before searching the web.
- Identify what is already known, what is still uncertain, what is being watched, and what would constitute a material update.
- Never spend a full research pass rediscovering a story already captured unless there is a new fact, changed number, changed policy, changed market reaction, or new contradictory evidence.

## 2. Two-stage discovery
### Stage A — broad scan
Search broadly enough to build a candidate set rather than accepting the first plausible result. Prefer multiple query formulations and, for Japan, Japanese-language searches. Look across primary sources plus reputable reporting.

### Stage B — deep verification
For the strongest candidates only, verify dates, numbers, scope, affected population/sector, primary-source wording, and whether secondary reporting adds context rather than merely repeating a press release.

## 3. Evidence-quality target
For a material factual article, aim when practicable for:
- at least one primary/official source for the core event;
- a second independent source or independent dataset for cross-checking;
- for contested, market-moving, policy, technical, or high-impact claims, a third source or contradictory-data check when it could change the conclusion.
A unique primary announcement may legitimately have one source, but the article must explicitly state what remains unverified.

For Japan-specific claims, search Japanese primary/official sources first when practical. Use ministries, regulators, municipalities, JPX/BOJ/MOF, company filings, official manufacturer notices, original papers/labs, and other first-party evidence appropriate to the subject.

## 4. Adversarial research pass
Before publishing, actively search for evidence that would make the story less important, less certain, less novel, or opposite in implication. Ask:
- Is the headline exaggerating the underlying data?
- Is this a PR announcement rather than demonstrated performance?
- Is the comparison period cherry-picked?
- Is there a base-rate explanation?
- Is there an alternative causal explanation?
- Is there conflicting official data?
- Is the claimed effect already priced in or already known?
Record the strongest contradiction or limitation, not a token disclaimer.

## 5. Claim ledger
Separate:
- FACT — directly supported by cited evidence;
- INFERENCE — reasoned conclusion from facts;
- ESTIMATE — calculated/reported estimate with basis;
- ASSUMPTION — working premise not established.
Never promote an inference into a fact because multiple articles repeat it.

## 6. Numerical discipline
- Check units, dates, denominators, nominal vs real, monthly vs annual, seasonally adjusted vs unadjusted, gross vs net, percentage vs percentage points, and currency basis.
- Recalculate simple derived values where useful.
- Do not invent averages, market levels, savings, probabilities, cost estimates, salary equivalents, or impact magnitudes.

## 7. Causality discipline
Do not confuse timing with causality. When explaining why something happened, rank plausible drivers and identify which are directly evidenced versus inferred. State what observation would distinguish competing explanations.

## 8. Quality gate
Before publishing, internally score the candidate on:
- significance;
- novelty/material change;
- source quality;
- cross-check strength;
- practical or analytical usefulness;
- uncertainty calibration.
One deeply verified item is better than several shallow items. Zero publication is valid.

## 9. No-dead-run fallback
If no new article clears the quality gate, do useful maintenance instead of manufacturing content. Depending on the section mission:
- revisit the most important open WATCH item;
- check whether a deadline, price, policy, recall, job, market regime, or forecast changed;
- search for contradictory evidence against an existing ALAM conclusion;
- audit a prior forecast/recommendation against what actually happened;
- improve confidence downward or upward only when evidence changed;
- add a correction when prior reasoning failed.
Do not create a visible article solely to prove the run did work.

## 10. Research-effort policy
Use available model/tool effort on evidence gathering, verification, contradiction searches, calculations, and cross-source synthesis rather than verbose prose. There is no requirement to make the final article long. Continue research while another credible source or cross-check has a realistic chance of changing the conclusion; stop when additional searching is mostly repetitive.

## 11. Reader clarity — 10-second comprehension rule
Research can be deep; the article must be easy to pick up. A reader should understand the main point within about 10 seconds.

### Headline
- Use plain language and one main idea.
- Prefer roughly 8–16 words when possible.
- Avoid jargon, acronym chains, multiple semicolons, or titles that try to contain the whole article.
- If a technical term is necessary, explain it immediately in ordinary language.

### Summary
Use no more than two short sentences:
1. **What changed?** State the new fact or movement directly.
2. **Why it matters?** State the consequence in normal language.
Do not open with background history.

### Scan-first article structure
Put the following ideas near the top, using these fields when the schema permits:
- `key_message` — one sentence; the single thing to remember.
- `what_changed` or the section-specific equivalent — 1–3 short sentences or 2–4 bullets.
- `why_it_matters` — 1–3 short sentences.
- `what_to_do_or_watch` — one clear action, watch item, or interpretation boundary.
- `bottom_line` — one sentence.
- `confidence_reason` — one short line explaining why confidence is high/medium/low.

### 30-second reading level
The `reading_levels["30 sec"]` version should normally contain only four compact points:
- **What happened**
- **Why it matters**
- **What to do/watch**
- **Bottom line**
It should not repeat the full article or claim ledger.

### Writing discipline
- Prefer short paragraphs of 1–3 sentences.
- Prefer concrete nouns and verbs over abstract phrases.
- Define abbreviations on first use: e.g. “Purchasing Managers’ Index (PMI)”.
- Put the most decision-useful number first; do not dump every number from a source.
- If a number lacks an obvious baseline, explain the comparison.
- Separate “we know” from “we think this means.”
- When uncertainty is material, express it in one clear sentence rather than burying it in caveats.
- Avoid repeating the same idea in summary, why-it-matters, recommendation and bottom line.
- Natural educated Taglish is welcome, but clarity beats clever phrasing.

### Section-specific clarity
- **Discover:** “What is new, and why should I care?”
- **Practical:** “Am I affected, and what exactly should I do?”
- **Market:** “What moved, why, and what should I watch next?”
- **Trend:** “What pattern is forming, how strong is the evidence, and what would disprove it?”

## 12. Image policy — real image first, generated editorial image second, SVG emergency fallback third
Every published article should have a useful visual path, but the visual must never weaken evidence quality.

### Priority 1 — verified real image
Try first to find a stable, directly usable image from an official/primary source when it genuinely represents the story. If one is available and appropriate, add `image_url`, `image_alt`, and `image_credit`. Do not invent image URLs, scrape unstable thumbnails, hotlink questionable assets, or use a photo merely as decoration.

### Priority 2 — persistent AI-generated editorial image
If no suitable real image exists, the publishing agent MUST add `editorial_visual` and art-direct a unique ALAM editorial illustration. The post-publish image workflow uses this art direction plus the verified article title, summary and why-it-matters to generate a 16:9 WebP image, stores it under `alam_app/assets/editorial/generated/YYYY/MM/`, and stamps system-managed `generated_image` metadata into the article JSON.

Publishing agents own the art direction; they must NOT invent a `generated_image.path`, model result or generation timestamp themselves. Those fields are written only after an image is actually generated and persisted.

Use this agent-owned shape:

```json
"editorial_visual": {
  "style": "editorial",
  "motif": "chip",
  "secondary_motif": "factory",
  "scene": "oversized chip looming over a tiny factory",
  "caption": "AI demand feels larger than the factory floor",
  "silliness": 28,
  "exaggeration": 64
}
```

Allowed motifs are `yen`, `chip`, `robot`, `factory`, `train`, `family`, `shield`, `document`, `market`, `policy`, `home`, `earthquake`, `car`, `weather`, `globe`, and `battery`. `motif` is required for the fallback; `secondary_motif` is optional. `silliness` and `exaggeration` are integers from 0–100 and are chosen by the publishing agent to fit the story.

The generated image should behave like a magazine/newspaper editorial illustration, not like fabricated evidence. Prefer one clear metaphor over a collage. Do not request visible headlines, captions, logos, trademarks, watermarks, fake charts with readable labels, or fake UI inside the image. Do not depict an unverified event as documentary photography or imply an unverified action by a named person.

Serious safety, disaster, death, legal, medical, war, crime, scam, recall or human-harm stories should use restrained respectful imagery and very low silliness. Lighter consumer, technology, market, engineering or absurd-policy stories may use more playful exaggeration when it improves comprehension.

When generation succeeds, system-managed metadata looks like:

```json
"generated_image": {
  "status": "ready",
  "path": "alam_app/assets/editorial/generated/2026/09/story-id-1234abcd.webp",
  "model": "gpt-image-2",
  "size": "1536x864",
  "quality": "medium",
  "format": "webp",
  "prompt_signature": "...",
  "generated_at": "2026-09-02T19:30:00+09:00"
}
```

### Priority 3 — deterministic SVG emergency fallback
If AI generation is temporarily unavailable, rejected, rate-limited or not configured, the article remains publishable. ALAM renders the existing deterministic SVG editorial visual from `editorial_visual` so there is no broken-image state. A later image-generation run may retry and replace the SVG display with a persistent WebP without changing the factual article.

Existing legacy records that lack both a real image and `editorial_visual` are still supported: the app infers a restrained topic motif automatically for the emergency SVG.

## 13. Final self-audit before write
Confirm:
- no duplicate/superseded story;
- timestamps and dates are correct;
- core numbers match sources;
- strongest contrary evidence is represented;
- claims are correctly classified;
- conclusion is proportional to evidence;
- headline and first two sentences are understandable without specialist knowledge;
- 30-second version gives a clear message rather than a compressed data dump;
- sources are usable;
- a verified real image is supplied OR `editorial_visual` is present so the generated-image pipeline can run;
- serious-story image direction is respectful and non-sensational;
- JSON is valid;
- written file is fetched back and verified after GitHub write.
