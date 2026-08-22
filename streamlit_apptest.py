from streamlit.testing.v1 import AppTest

at = AppTest.from_file('app.py', default_timeout=30)
at.run()
assert not at.exception, at.exception
assert len(at.text_input) >= 1
assert len(at.radio) >= 1

# Complete required first-screen profile.
at.text_input[0].set_value('CI Driver')
at.radio[0].set_value('A1')
at.button[0].click().run()
assert not at.exception, at.exception
assert at.session_state['profile_ready'] is True
assert at.session_state['bank_scope'] == 'A1'

# Automated CI does not make a network TTS call. Runtime voice behavior is
# exercised manually after deployment via Settings > Test selected voice.
at.session_state['voice_mode'] = 'Off'
at.session_state['opt_voice'] = False

# Render every main route with real Streamlit widget semantics.
for route in ['Home','Play','Mistakes','Progress','Rankings','Bank']:
    at.session_state['route'] = route
    at.session_state['nav_choice'] = route
    at.session_state['sync_nav'] = False
    at.run()
    assert not at.exception, (route, at.exception)

# Start Smart Review through the actual UI.
at.session_state['route'] = 'Play'
at.session_state['nav_choice'] = 'Play'
at.run()
at.button(key='play_review').click().run()
assert not at.exception, at.exception
review = at.session_state['review']
assert review and review['ids']
assert all(qid.startswith('A1-') for qid in review['ids'])
qid = review['ids'][0]

# Bookmark is a real widget path and must survive a rerun.
at.button(key=f'review_bookmark_{qid}_0').click().run()
assert not at.exception, at.exception
assert qid in at.session_state['progress']['bookmarks']

# Answer one question and record confidence without creating an extra attempt.
at.button(key=f'review_true_{qid}_0').click().run()
assert not at.exception, at.exception
assert at.session_state['review_feedback'] is not None
attempts_before = at.session_state['progress']['question_stats'][qid]['attempts']
at.button(key=f'confidence_guess_{qid}_0').click().run()
assert not at.exception, at.exception
assert at.session_state['progress']['question_stats'][qid]['attempts'] == attempts_before
assert at.session_state['progress']['question_stats'][qid]['confidence_guessed'] >= 1

# Browsing away from Play must not erase the active run.
at.session_state['route'] = 'Progress'
at.session_state['nav_choice'] = 'Progress'
at.run()
assert not at.exception, at.exception
assert at.session_state['review'] is not None
at.session_state['route'] = 'Play'
at.session_state['nav_choice'] = 'Play'
at.run()
assert not at.exception, at.exception
assert at.session_state['review'] is not None

print('STREAMLIT_APPTEST_OK')
