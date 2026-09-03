from types import SimpleNamespace

import alam_action_checklist as checklist


def _record(action="Submit through the official route", *, goal="Finish the application", deadline="Before Friday", minutes=10, title=None, category=None):
    record = {
        "id": "story-outcome",
        "content": {
            "action_plan": {
                "goal": goal,
                "deadline": deadline,
                "steps": [
                    {
                        "step": "Submit",
                        "action": action,
                        "done_when": "Accepted",
                        "time_minutes": minutes,
                    }
                ],
            }
        },
    }
    if title is not None:
        record["title"] = title
    if category is not None:
        record["_category"] = category
    return record


def test_reflection_key_tracks_current_plan_shape():
    baseline = checklist._reflection_key(_record())
    assert baseline != checklist._reflection_key(_record("Submit using the revised official form"))
    assert baseline != checklist._reflection_key(_record(goal="Complete the corrected application"))
    assert baseline != checklist._reflection_key(_record(deadline="Before Monday"))
    assert baseline != checklist._reflection_key(_record(minutes=30))
    assert checklist._reflection_key({"id": "none", "content": {}}) is None


def test_reflection_key_uses_normalized_effort_shape():
    assert checklist._reflection_key(_record(minutes="10")) == checklist._reflection_key(_record(minutes=10))
    assert checklist._reflection_key(_record(minutes="invalid")) == checklist._reflection_key(_record(minutes=None))


def test_completion_outcome_uses_minimized_existing_event(monkeypatch):
    fake_st = SimpleNamespace(session_state={})
    events = []
    monkeypatch.setattr(checklist, "st", fake_st)
    monkeypatch.setattr(checklist.alam_identity, "log_event", lambda *args: events.append(args) or True)
    record = _record()
    assert checklist.record_completion_outcome(record, "yes") is True
    key = checklist._reflection_key(record)
    assert fake_st.session_state[key] == "yes"
    assert events == [("ui_control_changed", "story-outcome", {"control": "action_plan_outcome", "value": "yes"})]


def test_completion_outcome_rejects_unknown_values_without_telemetry(monkeypatch):
    fake_st = SimpleNamespace(session_state={})
    events = []
    monkeypatch.setattr(checklist, "st", fake_st)
    monkeypatch.setattr(checklist.alam_identity, "log_event", lambda *args: events.append(args) or True)
    assert checklist.record_completion_outcome(_record(), "free-text") is False
    assert fake_st.session_state == {}
    assert events == []


def test_reflection_taxonomy_stays_small_and_non_textual():
    assert set(checklist.COMPLETION_OUTCOMES) == {"yes", "partly", "no"}


def test_recovery_query_prefers_validated_story_title_then_goal():
    assert checklist.recovery_query(_record(title="Residence renewal checklist")) == "Residence renewal checklist"
    assert checklist.recovery_query(_record(goal="Finish the application")) == "Finish the application"
    assert checklist.recovery_query({"id": "empty", "content": {}}) == ""


def test_recovery_lenses_exclude_originating_lens():
    assert checklist.recovery_lenses(_record(category="practical")) == ["Discover", "Market", "Trends"]
    assert checklist.recovery_lenses(_record(category="discover")) == ["Action", "Market", "Trends"]
    assert checklist.recovery_lenses(_record()) == []


def test_grounded_recovery_routes_to_other_lenses_without_user_text(monkeypatch):
    fake_st = SimpleNamespace(session_state={"selected_story": "story-outcome"})
    monkeypatch.setattr(checklist, "st", fake_st)
    record = _record(title="Residence renewal checklist", category="practical")
    assert checklist.open_grounded_recovery(record) is True
    assert fake_st.session_state["selected_story"] is None
    assert fake_st.session_state["main_nav"] == "More"
    assert fake_st.session_state["more_nav"] == "Ask ALAM"
    assert fake_st.session_state["alam_ask_query"] == "Residence renewal checklist"
    assert fake_st.session_state["alam_ask_lenses"] == ["Discover", "Market", "Trends"]


def test_grounded_recovery_clears_stale_lenses_for_unknown_category(monkeypatch):
    fake_st = SimpleNamespace(session_state={"selected_story": "legacy", "alam_ask_lenses": ["Discover", "Market", "Trends"]})
    monkeypatch.setattr(checklist, "st", fake_st)
    record = _record(title="Legacy verified story")
    assert checklist.open_grounded_recovery(record) is True
    assert fake_st.session_state["alam_ask_lenses"] == []
    assert fake_st.session_state["alam_ask_query"] == "Legacy verified story"


def test_grounded_recovery_fails_closed_without_validated_topic(monkeypatch):
    fake_st = SimpleNamespace(session_state={"selected_story": "empty"})
    monkeypatch.setattr(checklist, "st", fake_st)
    assert checklist.open_grounded_recovery({"id": "empty", "content": {}}) is False
    assert fake_st.session_state == {"selected_story": "empty"}
