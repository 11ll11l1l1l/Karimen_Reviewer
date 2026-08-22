> Historical v4.3 diagnosis retained for reference. Current second-audit notes are in `RECHECK_v4_4.md`.

# v4.3 diagnosis

Observed in v4.2 source/testing:

1. **Ranking health check was incomplete.** It only tested table reads. With Supabase RLS, an anon/publishable key can return an empty result without proving write access, so the UI could report connected while exam updates/results never reached the leaderboard.
2. **Ranking failures were mostly swallowed.** `sync_live_exam()` and result saving stored an error string but gameplay gave little indication that writes were failing.
3. **The SQL file was not a true migration and did not explicitly handle newer Supabase Data API grants.** `CREATE TABLE IF NOT EXISTS` does not add missing columns/indexes to an existing table. The v4.3 SQL explicitly adds missing columns and unique indexes, then grants Data API access only to the trusted `service_role`.
4. **Voice quality depended on browser speech synthesis.** Voice quality therefore varied by phone/browser and could sound robotic. v4.3 adds neural online TTS with fallback.
5. **Mascot display was still visually oversized.** Even with `object-fit: contain`, a square generated sprite could still fill a large frame. v4.3 caps actual pixel display size.
6. **Testing did not use the real Streamlit runtime.** Earlier builds relied on custom stubs. v4.3 adds strict widget-state tests plus Streamlit `AppTest` and a real server health check in GitHub Actions.

Offline verification completed in the build environment:

- Python compile: PASS
- Question validation: PASS (650 total, A1 150, B1 500, 133 image refs, 0 errors)
- Core smoke test: PASS
- Runtime stub: PASS
- Strict widget-state runtime + gameplay state checks: PASS
- Supabase integration stub: PASS

The build container cannot install Streamlit because outbound package access is disabled. Real Streamlit `AppTest` and server startup are therefore delegated to the included GitHub Actions workflow, which runs with installed dependencies after the repository is pushed.
