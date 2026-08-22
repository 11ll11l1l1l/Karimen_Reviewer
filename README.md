# Karimen Professional Reviewer — Streamlit

Phone-first Japanese provisional driving-license theory reviewer prepared for Streamlit Community Cloud.

## Included question banks

- KM14 — 50 questions
- KM15 — 50 questions
- KM16 — 50 questions
- Menkyoblog — 500 questions in 10 sets
- Total — 650 questions
- Image questions — 133
- No demo/sample questions

The latest corrected KM answers are preserved, including:
- KM15-Q033 = True
- KM16-Q036 = False
- KM16-Q048 = False

## Features

- Mobile-responsive Streamlit interface
- Review mode: due/adaptive, wrong answers, unseen, weakest, random
- Exam mode with 50-question / 30-minute defaults
- True/False exam navigation, flags, unanswered tracking and final review
- Image questions
- English-first display plus optional original Japanese where available
- Explanations and source/verification details
- Per-question attempts, accuracy, streak and mastery estimate
- Category coverage and accuracy
- Weakest-question table
- Session and exam history
- TRUE/FALSE performance split
- Progress export/import as JSON
- Searchable question browser

## Run locally

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

Streamlit will normally open `http://localhost:8501`.

## Deploy to Streamlit Community Cloud

1. Create a GitHub repository.
2. Upload the contents of this folder to the repository root.
3. Go to Streamlit Community Cloud and sign in with GitHub.
4. Create a new app from the repository.
5. Set the main file path to `app.py`.
6. Deploy.

No secrets or environment variables are required for this version.

## Progress persistence

This build does not use a shared cloud database. Progress is kept in the active Streamlit session and can be exported as `karimen_progress.json` from the Home or Statistics page. Re-import the file to restore progress after a deployment reset or on another device.

This approach avoids mixing one user's study history with another user's history on a public Streamlit server. A future version can add authenticated persistent storage (for example, Supabase) without changing the question-bank format.

## Exam simulation basis

The default provisional-license simulation is 50 questions in 30 minutes with a 90% pass threshold. Official reference used during this build:

Osaka Prefectural Police — 普通免許 / 仮免許学科試験
https://www.police.pref.osaka.lg.jp/tetsuduki/untenmenkyo/juken/choku/3709.html

The reviewer itself is a study aid and is not an official police examination service.
