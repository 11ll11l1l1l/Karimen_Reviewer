# Japan Driving License Exam Reviewer v5.2

## Main changes

- Added **Overall Study League** using every driver's persisted question history, not only completed exams.
- Added **By Study Mode** leaderboards for Review, Daily, Daily Replay, Survival, Boss and Practice Exam.
- Kept the existing standard-exam leaderboard and live exam room.
- Added contextual Tagalog/English wrong-answer motivational taunts.
- Added a clearly fictional/cartoon consequence matched to the rule/category after a mistake.
- Added optional last-driver browser memory (profile name + bank scope only) using a cookie; no IP or device fingerprinting.
- Added a settings control to save/forget the browser preference and a safe driver-switch path.
- Ranking diagnostics now verify `player_profiles` read/write access as well as the existing exam tables.
- Added `extra-streamlit-components>=0.1.81,<0.2` for writable cookie support.

## Compatibility

- Retains the complete v5.1 question/explanation bank: 1,550 source records (650 Karimen + 900 Honmen), 228 image references.
- Retains v4.x game, mascot, voice, progress, Supabase exam and backup behavior.
- No new Supabase table is required beyond the v5 `player_profiles` migration; all-activity rankings read the existing JSON progress column.
