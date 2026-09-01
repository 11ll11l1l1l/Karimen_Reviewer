# Japan Driving License Exam Reviewer v5.3

## English-first exam practice

- All **1,550 / 1,550** question records now have English question text.
- All **900 Honmen** source questions now include a deliberately literal **Exam English** translation based on the preserved Japanese source wording.
- The original Japanese source is retained for audit/reference and is hidden by default.
- The question card always uses English as the primary language; it no longer silently falls back to Japanese.
- Settings includes **Show original Japanese source under English questions** for comparison when needed.
- The header shows live English-bank coverage so a future missing translation is visible immediately.

## Translation policy

The Honmen English is intentionally not over-polished. Japanese driving-test translations can feel rigid or awkward, so v5.3 preserves the logic, qualifiers, negatives, measurements and rule conditions while using literal exam-style English. This is practice wording, not a claim that the translation is an official police-issued English question.

## Regression guard

`validate.py` now fails the release if:

- any question is missing `question_en`;
- any question is missing `question_en_exam`;
- fewer than 1,550 English questions are present;
- fewer than all 900 Honmen translations are present;
- Japanese characters remain inside the Exam English field; or
- a Honmen translation is not marked as v5.3 reviewed.

All v5.2 features remain: all-activity rankings, per-mode leaderboards, standard/live exam rankings, browser driver memory, Tagalog/English mistake motivation, contextual cartoon humor, Supabase profiles/progress, coverage-first selection, explanations, images, voice, mascots, achievements and existing review/exam modes.
