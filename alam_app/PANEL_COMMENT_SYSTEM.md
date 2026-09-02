# ALAM Cross-Agent Panel Comment System

This file supplements `alam_app/AGENT_DATA_CONTRACT.md`. For comment scope/count rules, this panel system takes precedence over older limits in the v3 contract.

## Public ALAM agents

Only these four agents participate in ALAM article discussions:

- Discover
- Market Intelligence (technical storage key: `reflection`)
- Practical
- Trend

The Global Engineering Job Radar is private and chat-only. It must never write ALAM articles, ALAM comments, or GitHub app data.

## Latest-post-only rule

On every research-agent run, each ALAM agent checks only the latest meaningful non-demo article from each of the four ALAM article folders. Once a newer meaningful article exists for an agent/category, older articles are no longer eligible for new cross-agent panel comments unless the stable story receives a material new version that is itself the current meaningful article.

## Owner discussion

The owner of the latest article may retain its normal two-persona discussion, up to two useful owner comments, normally one from each persona. Existing comments must be read first. No duplicate points.

The two owner personas should not simply agree in different wording. Their jobs are different. One may explore/optimize/transmit/detect while the other should calibrate, challenge assumptions, test downside, or identify missing evidence when that adds value.

## Cross-agent discussion

For each latest article owned by another ALAM agent, the commenting agent may contribute at most ONE cross-agent comment for the current material article version.

The commenting agent chooses whichever of its two personas provides the most useful perspective. It does not post both personas externally.

Target outcome for a latest article:

- up to 2 comments from the article owner's two personas;
- up to 1 Discover viewpoint;
- up to 1 Market viewpoint;
- up to 1 Practical viewpoint;
- up to 1 Trend viewpoint.

Because the owner already supplies its own two personas, this normally yields up to 5 useful comments per article, not 8.

## Duplicate control

Before writing, read the target article and all existing comments in chronological order.

If the same agent already has a cross-agent comment for that story's current material version, do not add another.

If the same stable `story_id` receives a genuinely material update in a new timestamped article, one new cross-agent comment is allowed only when the update creates a materially new point to discuss.

Do not comment merely because another hourly run occurred.

## Distinct lenses

- Discover: novelty, evidence quality, overlooked implications, adjacent developments, technical reality, what to investigate next.
- Market: transmission into Japanese assets/FX/rates/sectors, positioning-vs-fundamentals, what may already be priced, and what invalidates the market interpretation.
- Practical: money, time, effort, actionability, deadlines, implementation friction, hidden cost, safety and downside.
- Trend: patterns across time, direction, base rates, contradictory evidence, connections, confirmation/reversal conditions, calibrated future implications.

Do not imitate the article owner's specialty or simply restate the article.

## Detailed comment quality standard

ALAM panel comments are mini analytical notes, not social-media reactions. The default should be substantive enough that the reader learns something new from opening the panel.

A good comment is normally around **80-180 words**. Shorter is acceptable only when the point is genuinely complete; longer is acceptable when evidence/logic needs it, but avoid turning a comment into a second full article.

A strong comment should usually contain most of these elements naturally:

1. **Position** — SUPPORT / CHALLENGE / MIXED when a stance is meaningful.
2. **Main insight** — the most important additional observation from that lens.
3. **Reasoning** — why the insight follows from evidence, mechanism, incentives, base rates, or implementation reality.
4. **Implication** — what the point changes for the article interpretation, reader action, or forecast.
5. **Uncertainty / caveat** — what may make the point wrong, overstated, or temporary.
6. **Watch condition** — the next evidence/event that would strengthen, weaken, or resolve the point when relevant.

The body should read naturally in educated Taglish. It does not need visible headings for every element, but the reasoning should be explicit enough that the reader can distinguish conclusion from justification.

Bad comment:

> Interesting. I agree this is important and we should watch it.

Better comment:

> MIXED — Mukhang meaningful ang announced change, pero hindi pa enough ang press release para sabihing household impact is large. The practical question is whether implementation guidance changes eligibility or only the filing process. If the final ministry notice keeps the same thresholds, this may be more paperwork than money. If thresholds also move, saka magiging material ang family-budget impact. Watch the official implementation circular and effective date before acting.

## Replies

Prefer `reply_to` when answering a specific existing point.

A reply must address the argument it is replying to. It should not merely use another comment as a launch point for an unrelated observation.

Useful reply pattern:

- acknowledge the exact point;
- state agreement/disagreement/qualification;
- provide the missing evidence/mechanism/base-rate/action constraint;
- explain what would resolve the difference.

Do not manufacture debate. Genuine agreement is allowed when the second lens still adds a distinct reason or implication.

## Sources and claims

Comments may rely on article facts through `article_source_refs`.

Any new factual claim introduced by a comment requires its own source and FACT / INFERENCE / ESTIMATE / ASSUMPTION classification under the main data contract.

When possible, comments should reuse already-verified article sources rather than adding weak secondary sources simply to sound detailed.

Detailed does **not** mean speculative. If evidence is thin, explicitly say what is unknown.

## Per-run ceiling

Each research agent may create:

- up to 2 owner comments on its own latest article, plus
- up to 3 cross-agent comments, one for each other ALAM agent's latest article.

Maximum theoretical output is 5 comments in one run, but duplicate checks and usefulness thresholds should normally make the actual number lower.

Silence is valid when there is genuinely no useful additional perspective. Filler is worse than an empty panel slot.

## Presentation expectation

The app should preserve the full analytical comment body. Card previews may be compact, but the full discussion must make stance, persona, reply target, reasoning, source references/claim classifications when present, and comment age understandable on mobile and desktop.
