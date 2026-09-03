from types import SimpleNamespace

import alam_action_checklist as checklist


def _record(action="Submit through the official route"):
    return {
        "id": "story-outcome",
        "content": {"action_plan": {"steps": [{"step": "Submit", "action": action, "done_when": "Accepted"}]}},
    }


def test_reflection_key_tracks_current_plan_shape():
    assert checklist._reflection_key(_record()) != checklist._reflection_key(_record("Submit using the revised official form"))
    assert checklist._reflection_key({"id": "none", "content": {}}) is None


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
