# Karimen Reviewer v4.4 Polished — second audit

This release is a conservative upgrade of v4.3 Robust. Existing v4.3 top-level application and core functions were preserved; new behavior was added around them.

## What was still weak in v4.3

1. **Voice quality was improved, but not fully solved.** Neural speech existed, but sound effects could overlap speech, online TTS could block while waiting on the service, and a browser/device fallback could still sound robotic.
2. **Mascot art was still visually too close on some states.** CSS containment alone could not fix reaction PNGs that had already been tightly cropped.
3. **Changing profile could destroy an unfinished run.** This was a usability/data-loss risk.
4. **Confidence data was not influencing adaptive review.** The app could record a guess but Smart Review did not use that information.
5. **A missed practice question was not reinforced inside the same run.** Spaced scheduling existed across sessions, but there was no immediate retrieval retry.
6. **Progress was mostly tables and metrics.** It lacked clear visual trend charts.
7. **Question images could dominate a phone screen.** They now use contained maximum-height rendering.
8. **There was no regression guard proving v4.3 functions had been retained.** v4.4 includes a compatibility manifest and release audit.

## v4.4 corrections and additions

### Voice

- Default: `en-US-AriaNeural` through `edge-tts`.
- Additional neural styles: Ana and Jenny.
- Sound effect plays first; speech follows instead of playing on top of it.
- Neural generation now has shorter connection/receive timeouts so a slow TTS service cannot stall the app for a long period.
- Neural failure stays silent instead of silently switching to a robotic device voice.
- Device speech remains available only when the user explicitly selects it.
- Added separate mascot-voice and sound-effect volume controls.
- `Hear mascot` remains available after feedback as a manual replay path if mobile autoplay is blocked.
- Neural results are cached per phrase/voice/settings for 24 hours by Streamlit.

### Mascot

- Same gray-and-white cat and blue traffic-officer default identity.
- Existing category and reaction sprites remain separate.
- Reaction/category sprites now include additional visual breathing room.
- CSS maximum display sizes were reduced further for desktop and mobile.
- Original v4.3 sprites are retained under `assets/mascots/original_v43/` as a rollback reference.

### Learning engine

- Bookmarks / Saved Rules drill.
- Image-only drill.
- Guess Check drill.
- Confidence tags: `I knew it / I was sure` versus `I guessed`.
- Correct guesses and confident mistakes are tracked separately.
- Confidence now affects adaptive priority: guessed rules and confident misconceptions return sooner.
- Ordinary review modes queue a missed rule one additional time a few questions later for immediate retrieval practice. Daily, Survival and Boss structures are unchanged.
- Skip-for-later does not score the question.
- Current-run misses can be retried directly from the summary.

### Run safety

- Navigating to Progress, Rankings, Mistakes or Bank no longer destroys an unfinished review/exam.
- Home and Play show a resume action.
- Changing player/bank scope is disabled while a run is unfinished, preventing accidental run loss.
- Exam abandonment continues to update the live Supabase room.

### UI / analytics

- More compact mascot frames.
- Contained road-question images on phone screens.
- Responsive review cards/buttons/HUD.
- Category mastery bar chart.
- Recent session accuracy trend chart.
- Saved-rule, guessed-answer and confident-miss metrics.
- Voice backend status and explicit diagnostics in Settings.

### Ranking / Supabase

All v4.3 robust ranking behavior is retained:

- service/secret-key server access
- write/delete health probe
- RLS-safe setup
- live exam heartbeat
- abandoned exam cleanup
- idempotent completed-result upsert
- A1/B1 ranking filters
- connection re-test and visible error details

No new Supabase schema is required specifically for v4.4. The v4.3 `supabase_setup.sql` remains included.

## Regression verification

`release_audit.py` verifies that all v4.3 top-level functions remain present.

Current result:

- v4.3 app functions preserved: 92 / 92
- v4.3 core functions preserved: 16 / 16
- current app functions: 102
- current core functions: 19

Other packaged tests cover:

- 650-question validation
- A1 = 150 / B1 = 500
- 133 image references
- adaptive review
- global bank isolation
- daily challenge
- survival lives
- wrong → pleading → comeback mascot states
- exam construction/scoring
- bookmarks
- confidence tagging
- immediate retry queue
- skip-for-later
- run resume
- Supabase read/write diagnostic stubs
- strict Streamlit session-state mutation rules

The local build environment does not have the real Streamlit/Supabase/edge-tts packages installed, so actual browser/server execution is delegated to the included GitHub Actions workflow after a push. The workflow installs the real requirements, runs Streamlit `AppTest`, and starts a real headless Streamlit server health check.
