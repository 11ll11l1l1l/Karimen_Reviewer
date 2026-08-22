# Karimen Reviewer v4.4 Polished

Gamified mobile-first Streamlit reviewer for the Japanese driving knowledge test practice bank.

## Included content

- 650 questions
  - A1: 150 questions (Sets 14, 15, 16)
  - B1: 500 questions (Sets 1–10)
- 133 image-linked questions
- English explanations, optional Japanese text, and source/reference data
- Global A1+B1 / A1-only / B1-only scope

## Existing game modes retained

- Smart Review
- 50-question Exam Mode
- Daily Challenge
- Survival Mode
- Boss Exam
- Mistake Hunt / Mistake Book
- custom review missions
- Question Bank browser
- shared Supabase live/completed rankings

## Added study modes / tools

- Saved Rules bookmarks
- Image Drill
- Guess Check
- confidence tracking (`I knew it` / `I guessed`)
- skip-for-later
- immediate one-time retry of a missed rule during ordinary review
- retry only the misses from the current run
- resume unfinished review/exam after browsing other pages

## Voice v4.4

The default voice is **Natural neural voice (online)** using `en-US-AriaNeural` through `edge-tts`.

Other options:

- Cute neural voice (`en-US-AnaNeural`)
- Friendly neural voice (`en-US-JennyNeural`)
- Device voice (offline; quality depends on phone/browser)
- Cute bloops
- Off

v4.4 intentionally does **not** secretly fall back from neural speech to device speech. If neural speech fails, the app stays silent and reports the backend status. This prevents selecting a neural voice but unexpectedly hearing a robotic system TTS voice.

Sound effects and mascot speech are sequenced rather than layered. Separate voice/effect volume controls are available. The mascot panel also has **Hear mascot** for manual replay.

## Mascot v4.4

- same gray-and-white cat throughout
- blue traffic-officer uniform remains default
- category outfits retained
- correct/streak/wrong/pleading/double-wrong/comeback/victory reactions retained
- sprites have more breathing room and smaller contained display limits so they do not appear excessively zoomed on mobile
- original v4.3 mascot sprites retained under `assets/mascots/original_v43/`

## Progress and learning

- XP / levels / titles
- achievements
- daily streak
- world progression
- category mastery
- pass-readiness study estimate
- bookmarked rules
- guessed answers and correct guesses
- confident mistakes
- category mastery chart
- recent accuracy trend chart
- personalized “Mochi recommends” next-step card
- JSON progress backup/restore

Confidence is now part of Smart Review priority. A correct guess is not treated as equal to a confident mastered answer, and a confident wrong answer receives additional review priority.

## Supabase rankings

The robust v4.3 ranking path is preserved:

- `SUPABASE_SECRET_KEY` preferred
- `SUPABASE_SERVICE_ROLE_KEY` supported for legacy projects
- real temporary write/delete connection test
- live exam heartbeat
- abandoned exam handling
- idempotent final result submission
- A1/B1 leaderboard filtering
- visible diagnostic errors

Run `supabase_setup.sql` if you have not already applied the v4.3 migration. v4.4 does not require an additional schema change.

## Streamlit Secrets

```toml
SUPABASE_URL = "https://YOUR-PROJECT.supabase.co"
SUPABASE_SECRET_KEY = "YOUR-SUPABASE-SECRET-KEY"
```

Do not commit the real key to GitHub.

## Local verification

```bash
python validate.py
python release_audit.py
python smoke_test.py
python runtime_stub_test.py
python strict_runtime_test.py
python supabase_stub_test.py
```

## GitHub / real Streamlit verification

`.github/workflows/ci.yml` runs on push and pull request. It:

1. installs the real requirements
2. compiles the app
3. validates all questions/images
4. checks v4.3-function preservation
5. runs smoke/session/Supabase tests
6. runs Streamlit `AppTest`
7. launches a real headless Streamlit server and checks its health endpoint

See `GITHUB_UPDATE.txt` for the update commands.
