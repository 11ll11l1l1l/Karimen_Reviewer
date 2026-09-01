from streamlit.testing.v1 import AppTest

at = AppTest.from_file('app.py', default_timeout=30)
at.run()
assert not at.exception, at.exception
assert at.session_state['profile_ready'] is False

# Choose the requested default Geesene profile and Karimen bank.
at.radio(key='login_bank_scope').set_value('Karimen')
at.button(key='profile_pick_0').click().run()
assert not at.exception, at.exception
assert at.session_state['profile_ready'] is True
assert at.session_state['player_name'] == 'Geesene'
assert at.session_state['bank_scope'] == 'Karimen'

# Avoid network TTS calls in CI.
at.session_state['voice_mode'] = 'Off'
at.session_state['opt_voice'] = False

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
assert all(qid.startswith('KARIMEN-') for qid in review['ids'])
qid = review['ids'][0]

# Bookmark and answer one question.
at.button(key=f'review_bookmark_{qid}_0').click().run()
assert qid in at.session_state['progress']['bookmarks']
answer = at.session_state['progress']  # force session access before widget operation
at.button(key=f'review_true_{qid}_0').click().run()
assert not at.exception, at.exception
assert at.session_state['review_feedback'] is not None
attempts_before = at.session_state['progress']['question_stats'][qid]['attempts']
at.button(key=f'confidence_guess_{qid}_0').click().run()
assert at.session_state['progress']['question_stats'][qid]['attempts'] == attempts_before
assert at.session_state['progress']['question_stats'][qid]['confidence_guessed'] >= 1

# Browsing away does not erase the active run.
at.session_state['route'] = 'Progress'; at.session_state['nav_choice'] = 'Progress'; at.run()
assert at.session_state['review'] is not None
print('STREAMLIT_APPTEST_OK')
