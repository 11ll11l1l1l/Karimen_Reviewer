# Karimen Reviewer — Build 4.0 Journey Edition

A phone-first, game-style Streamlit reviewer for the Japanese provisional-license (karimen) written test.

## Included question banks

- A1: 150 questions, Sets 14–16
- B1: 500 questions, Sets 1–10
- Total: 650 questions
- Image questions: 133
- Existing question text, answers, explanations, images, verification data, and official-source links are preserved from Build 3.2.

## What is new in Build 4.0

### Game progression

- XP and driver levels
- driver titles
- world/journey progression
- Daily Challenge
- Survival Mode with 3 lives
- Boss Exam using the user's hardest questions
- Smart Review using spaced-repetition due dates, weak-question history, unseen questions, and weak-category weighting
- Mistake Book
- achievement collection expanded for daily, survival, boss, mock-exam, streak, image, and coverage goals
- pass-readiness estimate on the Progress page

### Dynamic cat mascot

The blue traffic-officer cat is the default mascot.

The app includes 56 mascot variants under `assets/mascots/`.

Category changes alter the outfit automatically:

- traffic signals / signs → signal officer
- parking / stopping → yellow parking-safety uniform
- pedestrians / crossings → green crossing-guard uniform
- railroad crossings → orange rail-safety uniform
- speed / braking / lanes → red road-marshal uniform
- hazards / vehicle operation → purple night-patrol uniform
- legal / licensing topics → teal road-rules uniform
- fallback/default → blue traffic-officer uniform

Reaction images change automatically:

- idle
- correct
- streak
- wrong
- pleading after repeated misses
- comeback after breaking a losing streak
- victory

### Sound + spoken words

Build 3.2 WAV effects are retained.

Build 4.0 adds optional browser speech synthesis for mascot lines such as:

- “Correct! Nice one.”
- “Five in a row! Keep it going!”
- “Please get the next one right! Read every word for me.”
- “Yes! That's the comeback I wanted.”
- “Mission cleared! You did it!”

Speech can be turned off independently from sound effects.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy to Streamlit Community Cloud

Replace the contents of the repository currently used by the deployed app with this package, then commit and push.

The entry file remains:

```text
app.py
```

No new Python dependency was added compared with Build 3.2.

## Supabase ranking

The existing optional Supabase ranking backend is retained.

If the previous deployed version already has these Streamlit secrets, no change is required:

```toml
SUPABASE_URL = "https://YOUR-PROJECT.supabase.co"
SUPABASE_SECRET_KEY = "YOUR-SUPABASE-SECRET-KEY"
```

For a new project, run `supabase_setup.sql` in Supabase SQL Editor and then add the secrets above.

## Validation

```bash
python validate.py
```

Expected result:

```text
Questions: 650
A1: 150
B1: 500
Image refs: 133
Errors: 0
```

## Notes

- The 90% pass-readiness indicator is an app-local estimate, not an official probability.
- The reviewer is a study aid and is not an official Japanese driving-test system.
- Browser speech depends on the browser/device speech-synthesis implementation. WAV feedback remains available independently.
