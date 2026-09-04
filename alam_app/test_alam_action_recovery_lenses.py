from types import SimpleNamespace

import alam_action_checklist as checklist


def test_grounded_recovery_restores_cross_lens_scope_for_known_category(monkeypatch):
    fake_st = SimpleNamespace(session_state={"alam_ask_lenses": ["Action"]})
    monkeypatch.setattr(checklist, "st", fake_st)

    record = {"id": "practical-story", "title": "Verified local action", "_category": "practical"}

    assert checklist.open_grounded_recovery(record) is True
    assert fake_st.session_state["alam_ask_lenses"] == ["Discover", "Market", "Trends"]
    assert fake_st.session_state["alam_ask_excluded_story_ids"] == ["practical-story"]


def test_grounded_recovery_unknown_category_clears_stale_lens_state(monkeypatch):
    fake_st = SimpleNamespace(session_state={"alam_ask_lenses": ["Action"]})
    monkeypatch.setattr(checklist, "st", fake_st)

    record = {"id": "legacy-story", "title": "Legacy verified story", "_category": "legacy"}

    assert checklist.open_grounded_recovery(record) is True
    assert fake_st.session_state["alam_ask_lenses"] == []
