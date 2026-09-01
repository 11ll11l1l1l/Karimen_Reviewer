# v5.1 Upgrade Plan and Design Decisions

## 1. Product identity
- Rename product to **Japan Driving License Exam Reviewer**.
- Replace A1/B1 public bank labels with **Karimen** and **Honmen**.
- Preserve the existing mascot/game UI instead of rebuilding the app from zero.
- Keep legacy question IDs migratable so old JSON progress backups remain useful.

## 2. Driver/profile architecture
### Required behavior
- Login screen shows saved driver profiles as avatar cards.
- Seed profiles: Geesene and Quennie.
- Registration form creates another name + avatar profile.
- Bank scope is selected at login.

### Progress isolation
Each profile owns a separate progress object containing:
- attempts / correct / wrong / streak
- last-seen / last-correct timestamps
- confidence flags
- bookmarks
- session history

This prevents one family member's answers from causing another person's questions to be treated as already encountered.

### Persistence
- Local session map is always available.
- If Supabase is configured, `player_profiles.progress` stores the JSON progress object.
- Profile registration and progress updates are best-effort: app study functions still work if Supabase is unavailable.

## 3. Coverage-first selection engine
### Problem in v4.4
`Due / adaptive` could score an already-seen, weak/due question higher than a never-seen item. Exam mode used `random.sample`, so consecutive exams could repeatedly draw overlapping questions before the full bank was covered.

### New normal priority
For Smart Review, Daily, Survival, Image Drill, and Exam:
1. unseen content group
2. fewer total encounters
3. oldest last encounter
4. adaptive weakness / category weakness / confidence issue
5. random jitter only as a final tie-breaker

### Intentional targeted modes
- Wrong answers: only missed questions
- Guessed: only confidence-marked guesses
- Weakest: intentionally repeated weakness training
- Random: explicit pure-random option

### Duplicate-content handling
Every record has a `content_key`. Exact duplicate records remain in the dataset, but only one representative from a duplicate group is eligible until distinct-content coverage is exhausted. This keeps source completeness without degrading variety.

## 4. Question-bank migration
### Karimen
- old A1 Sets 14–16 -> Karimen Sets 14–16
- old B1 Sets 1–10 -> Karimen Sets 1–10
- 650 records retained
- 650-entry `legacy_id_map.json` included

### Honmen
- 10 uploaded MHTMLs parsed as saved quiz-result pages
- 90 questions per set = 900 records
- exact Japanese question text extracted from `.show-question-content`
- furigana (`rt`) and page question numbering removed
- `li.correct-answer` is used as answer authority where present
- images inside each question block are matched to MHTML `Content-Location` payloads and exported locally
- 95 Honmen question images recovered

### Four missing source-result correctness markers
Four questions did not contain `correct-answer` on either response option in the saved HTML. Those entries are explicitly tagged `officially_verified_fallback` and contain references in the JSON rather than silently guessing.

## 5. Exam behavior
### Karimen
- 50 questions
- 30 minutes
- 90% practice pass threshold

### Honmen source-set simulation
- 90 questions
- 50 minutes
- 90% practice threshold
- UI explicitly states this is based on the uploaded 90-question source sets

The real ordinary-license test is 95 questions. The package does not manufacture the missing five special illustration/hazard questions.

## 6. UI/analytics improvements
- Header shows source-record coverage and distinct-rule coverage.
- Progress page shows Karimen and Honmen coverage separately.
- Question Bank handles Japanese-only Honmen records cleanly.
- Honmen questions automatically render Japanese when no verified English translation exists.
- Standard rankings support both 50-question Karimen and 90-question Honmen practice results.

## 7. Database migration
Run `supabase_setup.sql` once after deploying v5.1.
- create/upgrade `player_profiles`
- seed default profiles
- migrate A1/B1 historical ranking labels to Karimen
- preserve existing exam ranking rows
- grant only service-role table access under RLS

## 8. Validation gates
Release package must pass:
- Python compile
- 1,550-record bank validation
- all 228 image-path validation
- 650 legacy-ID migration validation
- unseen-first logic tests
- runtime route stubs
- strict Streamlit session-state behavior stubs
- Supabase permission/path stubs
- top-level v4.3/v4.4 function compatibility audit
- Streamlit AppTest in CI after dependencies are installed


## v5.1 explanation layer

The bank now uses a structured explanation schema for all 1,550 questions. The UI renders the reasoning, governing rule, real-driving implication, and exam trap separately so a learner can understand both *why* and *what to remember*. Generic explanation placeholders are rejected by `validate.py`.

Honmen source keys are preserved independently from the answer used by the reviewer. High-confidence contradictions against current official rules are recorded as audited corrections rather than silently changing the source. Current official rule anchor: National Police Agency `交通の方法に関する教則` (`20241113kyousoku.pdf`).
