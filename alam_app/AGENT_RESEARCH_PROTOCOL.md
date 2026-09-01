# ALAM Agent Deep Research Protocol

All ALAM research agents should use this protocol on every scheduled run. The goal is to maximize useful research work, not output length.

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
If no new article clears the quality gate, do useful maintenance instead of manufacturing content. Depending on agent mission:
- revisit the most important open WATCH item;
- check whether a deadline, price, policy, recall, job, market regime, or forecast changed;
- search for contradictory evidence against an existing ALAM conclusion;
- audit a prior forecast/recommendation against what actually happened;
- improve confidence downward or upward only when evidence changed;
- add a correction when prior reasoning failed.
Do not create a visible article solely to prove the run did work.

## 10. Research-effort policy
Use available model/tool effort on evidence gathering, verification, contradiction searches, calculations, and cross-source synthesis rather than verbose prose. There is no requirement to make the final article long. Continue research while another credible source or cross-check has a realistic chance of changing the conclusion; stop when additional searching is mostly repetitive.

## 11. Image metadata
The app already renders a branded fallback visual for every article. If a stable, directly usable image from an official/primary source is available and appropriate, an agent may add `image_url`, `image_alt`, and `image_credit`. Do not invent image URLs, scrape unstable thumbnails, or use an image merely to decorate the story. If no suitable real image exists, omit it and let ALAM use its built-in editorial fallback.

## 12. Final self-audit before write
Confirm:
- no duplicate/superseded story;
- timestamps and dates are correct;
- core numbers match sources;
- strongest contrary evidence is represented;
- claims are correctly classified;
- conclusion is proportional to evidence;
- sources are usable;
- JSON is valid;
- written file is fetched back and verified after GitHub write.