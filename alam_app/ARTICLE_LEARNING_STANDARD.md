# ALAM Opened-Article Learning Standard

ALAM feed summaries stay concise. Opening an article switches the product into **teacher mode**: assume the reader is intelligent but may know nothing about the topic yet. The goal is not longer prose. The goal is that the reader leaves with something they can explain, watch, decide, or do.

## Required outcome

Every newly published article should answer: **What should the reader be able to understand or do after reading this?**

A valid outcome may be:
- knowledge — understand a concept, mechanism, policy, market relationship, or technical idea;
- judgment — know the boundary between what is established and what is still uncertain;
- watch — know exactly which signal/event would matter next;
- action — know exactly what to prepare and what steps to take.

Do not assume acronyms, institutional knowledge, financial vocabulary, engineering vocabulary, government-process knowledge, or prior knowledge of earlier ALAM articles.

## Keep the feed short

Do not lengthen `summary` to satisfy this standard. `summary` remains the 1–2 sentence scan layer. Put education and procedure inside the opened-story fields below.

## `content.learning`

New material articles should include this object whenever there is something useful to teach:

```json
"learning": {
  "outcomes": [
    "Explain in plain language what X means.",
    "Recognize why Y changes the conclusion."
  ],
  "background": "Start from zero. Give only the context needed to understand this story.",
  "terms": [
    {
      "term": "JGB",
      "meaning": "Japanese Government Bond — debt issued by Japan's government.",
      "why_it_matters": "Its yield is a benchmark for borrowing costs and rate expectations in Japan."
    }
  ],
  "how_it_works": [
    {
      "title": "First link in the chain",
      "explanation": "Explain the mechanism in ordinary language."
    },
    {
      "title": "What changes next",
      "explanation": "Explain the next causal or procedural link without overstating certainty."
    }
  ],
  "example": "Use one concrete numerical example, analogy, or everyday scenario when it genuinely improves understanding.",
  "takeaways": [
    "Three to five short things worth remembering after the details fade."
  ]
}
```

Rules:
- Background should normally be 1–4 short paragraphs, not a textbook chapter.
- Define a technical term the first time a normal reader could reasonably stumble on it.
- `how_it_works` should explain mechanism/procedure, not merely repeat facts.
- Use a concrete example where it reduces abstraction. Label estimates as estimates.
- End with 3–5 non-repetitive takeaways.
- Never invent educational detail that is not supported by the evidence or well-established background knowledge.
- Do not pad simple stories. If one paragraph and three takeaways are enough, stop there.

## `content.action_plan`

For an actionable item, especially `DO NOW`, `PREPARE`, `APPLY`, `AVOID`, `BUY`, or a time-sensitive `WAIT`, a vague recommendation is not sufficient. Include a usable procedure:

```json
"action_plan": {
  "goal": "What successful action achieves.",
  "who_should_act": "Who this checklist applies to; clearly say who can ignore it.",
  "deadline": "Exact date/timing when known, otherwise the verified timing rule.",
  "prepare": [
    "Documents, account details, measurements, photos, money, contact information, route information, or other things to gather before starting."
  ],
  "steps": [
    {
      "step": "Check eligibility",
      "action": "The exact thing to do.",
      "how": "Where/how to do it, including official channel when available.",
      "needed": ["What must be in hand for this step"],
      "time_minutes": 10,
      "cost_yen": 0,
      "done_when": "An observable completion condition so the reader knows this step is finished."
    }
  ],
  "mistakes_to_avoid": [
    "Common misunderstanding, scam, unnecessary purchase, missed field, wrong assumption, or unsafe shortcut."
  ],
  "decision_rules": [
    {
      "if": "a specific condition is true",
      "then": "the corresponding action or no-action choice"
    }
  ],
  "follow_up": "What to confirm afterwards and when to re-check."
}
```

Action rules:
- Be procedural: tell the reader where to start, what to have ready, what to do in order, and how to know they are done.
- If the action is simply “watch,” specify exactly what to watch, where, what threshold/change matters, and what the reader should do if it happens.
- If there is no application, document, purchase, or deadline, explicitly say so when that prevents wasted effort.
- Use official channels for legal, government, safety, benefits, residency, tax, driving, recall, and similar actions when available.
- Never invent a form name, fee, document requirement, office procedure, eligibility rule, deadline, URL, phone number, or cost.
- Do not turn market intelligence into personal buy/sell instructions. Market action plans should be observation/preparation/decision-boundary checklists, not trades.
- For safety stories, instructions must not encourage unsafe handling or distract a user while driving/operating equipment.

## Lens-specific teaching goals

**Discover:** Teach what the new thing is, the basic mechanism, what has actually been demonstrated, and the boundary between demonstrated result and future promise.

**Practical:** Teach eligibility/scope first, then give the exact checklist. The reader should know what to prepare, what to do, when, common traps, and what counts as completion.

**Market:** Define the instruments/terms that drive the story and teach the transmission chain. The reader should understand why a move can help one group and hurt another, what is fact vs market interpretation, and which indicators would confirm or invalidate the thesis.

**Trend:** Teach why several observations count as a pattern (or do not), distinguish signal from noise/common-cause explanations, and give the reader the next observations that would strengthen or weaken the trend.

## Final learning audit

Before publishing, ask:
1. Could a reader with no prior topic knowledge follow the opened article?
2. Is every necessary acronym/technical term explained once in plain language?
3. Does the article explain *why/how*, not only *what*?
4. Is there a concrete example where abstraction would otherwise make the idea hard to grasp?
5. Are there 3–5 memorable takeaways?
6. If action is required, could the reader execute it without having to guess the preparation, order, completion condition, or follow-up?
7. Did we keep the feed summary short despite adding the learning layer?

If the answer to a relevant item is no, improve the record before publishing.