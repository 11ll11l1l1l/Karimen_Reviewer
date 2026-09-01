# Japan Driving License Exam Reviewer v5.1 — Detailed Explanations

A mobile-first Streamlit reviewer for Japanese driving-license written-exam study, upgraded from the v4.4 Karimen Reviewer without removing the existing game, progress, mascot, sound, ranking, or review features.


## v5.2 additions

### Rankings now cover the whole reviewer
- **Overall Study League** aggregates answer history across Review, Daily Challenge, Survival, Boss and Practice Exam activity.
- The shared board shows league points, total correct/attempts, accuracy, unique rules covered, coverage percentage and session count.
- **By Study Mode** boards compare cumulative activity separately for Smart/Targeted Review, Daily Challenge, Daily Replay, Survival, Boss Exam and Practice Exam.
- Existing standard-exam best scores and the live exam room are retained.
- Shared all-activity ranking is derived from each Supabase `player_profiles.progress` record, so v5.2 does not need another ranking table.

### Wrong-answer motivation and humor
- Review mistakes now trigger a short Tagalog/English motivational roast from Mochi.
- Feedback adds a clearly fictional **“If this were a cartoon”** consequence related to the tested driving rule (signals, crossings, pedestrians, parking, speed, visibility, emergency vehicles, seat belts, bicycles, etc.).
- The joke is shown only after the answer is known; practice-exam questions are not spoiled while the exam is running.
- Repeated mistakes get stronger encouragement rather than insults or personal attacks.

### Remember the driver on this browser
- Optional browser cookie remembers only the selected **driver profile name + Karimen/Honmen scope** for 180 days.
- The same browser can automatically reopen the last driver; **Settings → Change driver** always remains available.
- This is convenience only, not authentication. The app does **not** use IP/device fingerprinting.
- Requires `extra-streamlit-components`; if browser cookies/components are unavailable, normal profile selection still works.

## Question banks

### Karimen — 650 questions
- Previous A1 Sets 14–16: 150 questions
- Previous B1 Sets 1–10: 500 questions
- The old public A1/B1 labels are now merged into the single **Karimen** bank.
- Old progress/backups using A1/B1 IDs are migrated automatically to the new `KARIMEN-Sxx-Qxxx` IDs.

### Honmen — 900 questions
- 10 uploaded Honmen practice sets
- 90 true/false questions per set
- 95 embedded question images recovered from the uploaded MHTML result pages
- Japanese source wording is preserved after removing furigana/page numbering; no unverified English translation was invented
- 896 answers were explicitly marked by the saved quiz-result HTML; 4 source-result items lacked an explicit correct-answer class and are separately verified against driving/safety references in `questions.json`

### Total
- **1,550 source question records**
- **228 image references**
- A compressed deployment copy of the full question bank (`data/questions_v51.json.xz`) is included; the readable JSON remains in the downloadable package.
- **1,539 distinct content keys** (11 exact duplicate-content records retained for source completeness)

## Exam format handling

Current Osaka Prefectural Police guidance states:
- provisional/Karimen written test: 50 questions, 30 minutes, at least 90%
- ordinary-license/Honmen written test: 95 questions, 50 minutes, at least 90%

The uploaded Honmen practice pages contain 90 true/false questions per set and do not contain the five additional official-format hazard/illustration scoring items. Therefore v5.1 labels its default Honmen exam as a **90-question source-set simulation** rather than claiming it is a complete 95-question official-format reproduction.

## Major v5.0 foundation

### Driver profile login
- First screen is now profile selection instead of free-text nickname entry.
- Default profiles: **Geesene 🚙** and **Quennie 🌸**.
- Additional drivers can be registered with their own avatar.
- Every driver has separate question history, coverage, mistakes, confidence, bookmarks, sessions, and adaptive priority.
- With the included Supabase migration, profiles/progress can persist across browser sessions/devices. Without Supabase, additional profiles work within the current Streamlit session and progress can still be exported/imported.

### Coverage-first question engine
Normal review/exam selection now uses a hard priority order:
1. never-encountered distinct content
2. least-exposed content
3. least-recently-seen content
4. adaptive weakness/difficulty as a tie-breaker

A heavily missed or due question can no longer displace a never-seen question in normal Smart Review or Exam mode. Targeted modes remain intentionally targeted: Mistake Hunt, Guess Check, Weakest, and explicit Pure Random.

Exact duplicate source records are retained in the bank, but equivalent content is not allowed to crowd a run until the distinct-content pool has been covered.

### Bank-aware exams
- Karimen default exam: 50 Q / 30 min
- Honmen default source-set simulation: 90 Q / 50 min
- Coverage-first selection is used for normal exam construction.
- Custom exam remains available.

### Existing v4.x features retained
- Smart Review
- Daily Challenge
- Survival Mode
- Boss Exam
- Mistake Hunt / Mistake Book
- Saved Rules bookmarks
- Image Drill
- Guess Check
- confidence tracking (`I knew it` / `I guessed`)
- immediate retry of a missed rule during ordinary review
- skip-for-later
- retry current-run misses
- unfinished-run resume
- XP, levels, achievements, streaks, charts, weak-topic analytics
- mascot reactions / themes / sounds / neural voice options
- Supabase live exam room and completed rankings
- JSON progress backup/restore

## Supabase migration

**Run `supabase_setup.sql` once for v5.1**, even if your v4.4 ranking database was already working. It:
- retains/upgrades `live_exams` and `exam_results`
- migrates old leaderboard bank labels `A1` / `B1` to `Karimen`
- adds `player_profiles`
- seeds Geesene and Quennie
- adds JSON progress storage for each driver profile
- keeps RLS enabled and grants server-side `service_role` access

Recommended Streamlit Secrets:

```toml
SUPABASE_URL = "https://YOUR-PROJECT.supabase.co"
SUPABASE_SECRET_KEY = "YOUR-SUPABASE-SECRET-KEY"
```

`SUPABASE_SERVICE_ROLE_KEY` is also supported for older projects. Never commit a real key to GitHub.

## Install and run

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Verification

```bash
python -m compileall -q app.py karimen_core.py
python validate.py
python release_audit.py
python smoke_test.py
python runtime_stub_test.py
python strict_runtime_test.py
python supabase_stub_test.py
python streamlit_apptest.py
```

The last command requires the real Streamlit dependency installed from `requirements.txt`. GitHub Actions installs it automatically.

## Important data note

Honmen questions remain source-derived from the uploaded MHTML files, but v5.1 adds a separate teaching layer to every record: WHY, RULE TO REMEMBER, PRACTICAL MEANING, COMMON EXAM TRAP, official-guide section, and verification sources. The original Japanese statement and original source answer are preserved. When an uploaded answer key conflicts with a high-confidence current official rule, the original key is retained in `source_answer` and the reviewer uses an audited corrected answer with an explicit correction reason.

## v5.1 detailed-explanation upgrade

Every one of the 1,550 questions now carries structured teaching fields rather than a single short feedback paragraph:

- `why_answer` — the reason the exact statement is true or false
- `rule_summary` — the governing rule to memorize
- `practical_meaning` — how the rule changes real driving behavior
- `exam_trap` — the wording/number/exception/timing trap to watch for
- `official_section` — the relevant official-guide topic
- `sources` — original source plus the National Police Agency *Traffic Methods Guide* anchor
- `explanation_detailed` — combined long-form explanation used for export/backward compatibility

The v5.1 audit also removes the former generic WHY/TRAP/PRACTICAL placeholders. Numerical questions call out the tested value; absolute-permission wording is flagged; timing questions distinguish 3-second/30-metre/immediate timing; and image questions explicitly warn the learner to identify the depicted sign/marking/signal before answering.

The official rule anchor was refreshed to the current National Police Agency PDF: `https://www.npa.go.jp/bureau/traffic/20241113kyousoku.pdf`.

### Answer-key audit

The original MHTML answer key is not silently overwritten. v5.1 currently contains 41 high-confidence source-key corrections. For each corrected item the JSON retains `source_answer`, `answer_corrected_from_source`, and `answer_correction_reason`, and the UI shows a visible answer-key-audit warning. This matters because the uploaded Set 4 result page contains several demonstrably inconsistent keys (for example, it marks the statement that airbags make seat belts unnecessary as correct).

The bank is a study aid, not an official police question bank. Source-page answers without an audited correction remain traceable to the uploaded source, while teaching explanations are separately anchored to the official rule framework.
