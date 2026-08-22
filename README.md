# A1 B1 Karimen Reviewer — Streamlit Build 3.0

Phone-first Streamlit reviewer containing 650 questions and 133 image questions.

## Included

- A1: 150 questions, Sets 14–16
- B1: 500 questions, Sets 1–10
- Smart/adaptive review
- Wrong-answer and weak-area review
- 50-question timed exam simulation
- Progress dashboard and question search
- Cute mascot feedback, soft sound cues, optional haptics
- Optional shared live exam room and all-time ranking
- Progress export/import

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy on Streamlit Community Cloud

Push the folder contents to the GitHub repository used by your Streamlit app. The main file is `app.py`.

## Shared ranking setup

The app works without an external database. Shared rankings need one free Supabase project because Streamlit Community Cloud local files are not guaranteed to persist.

1. Create a project at Supabase.
2. Open **SQL Editor** and run the full contents of `supabase_setup.sql`.
3. In Supabase project settings, copy:
   - Project URL
   - Secret key
4. In Streamlit Community Cloud open your app > **Settings** > **Secrets**.
5. Add:

```toml
SUPABASE_URL = "https://YOUR-PROJECT.supabase.co"
SUPABASE_SECRET_KEY = "YOUR-SUPABASE-SECRET-KEY"
```

6. Save and reboot the Streamlit app.

The secret key must stay in Streamlit Secrets. Never commit the real key to GitHub.

### Ranking rules

- Live room: active exams checked in during the last 5 minutes.
- Live score: number currently correct, plus progress and elapsed time.
- All-time main ranking: each nickname's best completed 50-question exam.
- Tie-breaker: faster completion time.
- Other exam sizes can appear in Recent Finishes but not the main all-time board.

Use nicknames rather than full legal names. No email or Streamlit login is required for examinees when the deployed app is public.

## Updating the hosted app

Replace changed files in your local GitHub repository, then in GitHub Desktop:

1. Commit to `main`
2. Push origin
3. Streamlit redeploys automatically

## Validation

```bash
python validate.py
```

The validator checks question counts, unique IDs, image links, bank names, and the provenance scrub.
