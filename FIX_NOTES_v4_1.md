# v4.1 repair notes

The v4.0 build was not simply visually rough; it had structural problems.

## Major corrections

1. **Navigation state collision removed**
   - v4.0 used `session_state.nav` as both a Streamlit widget key and a programmatic route.
   - Buttons changed that value after the widget had already been instantiated, which can raise Streamlit session-state exceptions.
   - v4.1 uses `route` for application routing and a separate `nav_choice` widget state.

2. **Duplicate function overrides removed**
   - v4.0 contained old and new definitions of key functions in the same file.
   - Examples included `page_home`, `page_review`, `render_question`, `priority_score`, `achievement_catalog`, `study_level_info`, `mascot_feedback`, and `render_exam_results`.
   - v4.1 has one top-level definition per function.

3. **Adaptive-selection performance fixed**
   - v4.0 recalculated category statistics for all 650 questions inside each individual candidate score.
   - v4.1 computes category statistics once per selection call in `karimen_core.py`.

4. **Mistake Hunt corrected**
   - v4.0 silently filled an empty mistake queue with random questions.
   - v4.1 returns no eligible questions when there are no actual mistakes.

5. **Daily challenge replay corrected**
   - Replaying the daily challenge no longer produces another daily-completion bonus/streak entry.

6. **Review state machine rewritten**
   - Correct, streak, wrong, repeated wrong, pleading, comeback and victory states are explicit.
   - Survival ends cleanly when lives reach zero.
   - Sessions are saved once only.

7. **Mascot assets replaced**
   - The old recolored copies were removed.
   - The new package contains visibly different poses and category uniforms.

8. **Voice made local and deterministic**
   - Bundled WAV spoken phrases replace reliance on browser speech synthesis.

9. **Exam routing repaired**
   - Result actions now change the separate app route rather than mutating a navigation widget key.

10. **Core logic separated and tested**
    - `karimen_core.py` contains progress, mastery, adaptive selection, deterministic daily challenge and session logic.
    - `smoke_test.py` tests these without requiring Streamlit.
