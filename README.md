# Karimen Reviewer v4.1 Stable

A mobile-first Streamlit driving-test reviewer built from the v3.2 question package.

## What is included

- 650 questions total: A1 150 + B1 500
- 133 image questions and all existing question images preserved
- Review Mode with explanations and spaced/adaptive prioritization
- 50-question / 30-minute default Exam Mode with 90% practice target
- Daily Challenge with deterministic daily questions and 3 image questions
- Survival Mode with three lives
- Boss Exam based on weak questions
- Mistake Book containing only questions the learner actually missed
- XP, levels, achievements, world progression, weak-topic statistics and pass-readiness study estimate
- Optional Supabase shared rankings
- Progress JSON backup/restore

## Mascot system

The same gray-and-white cat is retained throughout the app. The default identity is the blue traffic-officer uniform.

Category uniforms are genuinely different images, not recolors:

- Signals/signs: blue traffic officer with baton
- Parking: green parking/safety vest
- Pedestrians: yellow crossing-safety outfit
- Railroad: railway staff uniform
- Speed/highway: motorcycle/highway outfit
- Hazards/vehicle operation: night-road safety outfit
- Legal/general rules: instructor/legal outfit
- Exam scene: exam-study outfit

Reaction images are also different poses:

- idle
- correct
- streak
- wrong
- repeated-wrong / losing streak
- pleading
- comeback
- victory

`MASCOT_STATES_PREVIEW.png` shows the bundled assets.

## Spoken mascot phrases

`assets/voice/` contains real WAV speech clips for ready, correct, streak, wrong, pleading, comeback, victory and focus. They are bundled locally, so the feature does not depend on browser text-to-speech support.

## Deploy to Streamlit Community Cloud

1. Replace the contents of your existing GitHub app with the contents of this folder.
2. Keep `app.py`, `karimen_core.py`, `data/`, `assets/`, `.streamlit/`, and `requirements.txt` in the repository.
3. Set the Streamlit main file to `app.py`.
4. Optional: restore your existing Supabase secrets if you want shared rankings.

The reviewer works without Supabase.

## Validation performed

- Python syntax compile: passed
- Question validator: 650 questions, 133 image references, 0 errors
- Pure core smoke tests: passed
- Stubbed Streamlit page smoke test: Home, Play, Mistakes, Progress, Rankings, Bank, Review and Exam paths passed
- Review state machine: correct, repeated wrong, comeback passed
- Survival 3-life termination: passed
- Daily replay bonus protection: passed
- Exam scoring/submission: passed
- Duplicate top-level function scan: none

A real browser/Streamlit runtime could not be launched in the build container because Streamlit is not installed there and external package download is blocked. The package therefore includes `smoke_test.py` so the pure logic can be retested after changes.
