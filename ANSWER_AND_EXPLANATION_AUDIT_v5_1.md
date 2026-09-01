# Answer and Explanation Audit — v5.1

This release separates three things that older builds tended to mix together:

1. **Source transcription** — the exact Japanese question and answer state recovered from the uploaded practice page.
2. **Reviewer answer** — the answer the app actually grades against.
3. **Teaching explanation** — the structured explanation anchored to the governing Japanese traffic rule.

## Explanation standard

All 1,550 questions must have:

- a question-specific `why_answer`;
- a `rule_summary`;
- a `practical_meaning` block;
- a `exam_trap` block;
- an `official_section`;
- an NPA official-guide source anchor;
- a combined detailed explanation of at least 500 characters.

The validator rejects the former generic placeholders (for example, “apply the rule above” with no question linkage).

## Official anchor

Primary rule framework:

- 警察庁 / National Police Agency — **交通の方法に関する教則**
- Current PDF used by the bank: https://www.npa.go.jp/bureau/traffic/20241113kyousoku.pdf

Exam-format reference:

- 大阪府警察 — ordinary licence: 95 questions / 50 minutes / 90% pass threshold; provisional licence: 50 questions / 30 minutes / 90%.

## Source-key correction policy

The uploaded MHTML pages are study sources, not official police question banks. If an answer key conflicts with a high-confidence current official rule, v5.1 does not erase the original value. It stores:

- `source_answer`
- `answer`
- `answer_corrected_from_source = true`
- `answer_correction_reason`

The app displays an **Answer-key audit** warning on those records.

The current bank contains **41 high-confidence corrected source keys**. Most are in uploaded Honmen Set 4, whose saved HTML itself contains a number of internally implausible `correct-answer` states. The original source values remain auditable.

## 2026 statutory-speed change

The app contains an effective-date schedule for legacy questions affected by the change taking effect **2026-09-01**. From that date, qualifying unsignposted general roads without a centre line/vehicle lanes/directional separation use a 30 km/h statutory maximum; specified structural categories remain 60 km/h. The runtime applies scheduled answers/explanations according to the date rather than permanently rewriting historical question wording.

## Integrity policy

- Never delete the original question to hide an answer conflict.
- Never silently overwrite a source key.
- Do not create a false 95-question Honmen simulation from 90-question uploaded sets; the app labels the built-in Honmen exam as a **90-question source-set simulation**.
- Exact duplicate source records are retained for provenance but de-duplicated for normal question selection.
