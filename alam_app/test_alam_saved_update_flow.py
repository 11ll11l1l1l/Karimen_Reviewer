"""Regression tests for ALAM's Saved material-update review state.

These tests stay deterministic and browser-independent. They protect the product
contracts around Saved review state and browser-cookie restoration.
"""

from types import SimpleNamespace

import alam_core
from alam_local_state import _advance_saved_snapshot, _sid
from alam_saved_views import _change_preview


def test_saved_snapshot_advances_monotonically():
    profile = {"b": {}}
    story_id = "story-123"
    assert _advance_saved_snapshot(profile, story_id, 100) is True
    assert profile["b"][_sid(story_id)] == 100

    # An older rerun/history record must never move the review baseline backwards.
    assert _advance_saved_snapshot(profile, story_id, 90) is False
    assert profile["b"][_sid(story_id)] == 100

    assert _advance_saved_snapshot(profile, story_id, 140) is True
    assert profile["b"][_sid(story_id)] == 140


def test_same_version_is_idempotent():
    profile = {"b": {_sid("story-1"): 220}}
    assert _advance_saved_snapshot(profile, "story-1", 220) is False
    assert profile["b"][_sid("story-1")] == 220


def test_change_preview_uses_explicit_v5_change_summary_without_history():
    record = {
        "id": "story-change",
        "created_at": "2026-09-03T01:00:00+09:00",
        "content": {
            "change_summary": {
                "previous": "Application deadline was September 10.",
                "now": "Application deadline moved to September 20.",
            }
        },
    }
    preview = _change_preview(record, [record])
    assert preview == (
        "Application deadline was September 10.",
        "Application deadline moved to September 20.",
    )


def test_change_preview_does_not_invent_change():
    record = {
        "id": "story-static",
        "created_at": "2026-09-03T01:00:00+09:00",
        "summary": "No material update yet.",
        "content": {},
    }
    assert _change_preview(record, [record]) is None


def test_native_cookies_restore_saved_state_without_optional_cookie_manager():
    original_st = alam_core.st
    original_stx = alam_core.stx
    fake_st = SimpleNamespace(
        session_state={},
        context=SimpleNamespace(
            cookies={
                "alam_followed": '["story-7", "story-8"]',
                "alam_last_visit": "2026-09-03T02:30:00+00:00",
            }
        ),
    )
    try:
        alam_core.st = fake_st
        alam_core.stx = None
        manager = alam_core.init_browser_state()

        assert manager is None
        assert fake_st.session_state["followed_stories"] == ["story-7", "story-8"]
        assert fake_st.session_state["visit_reference"].isoformat() == "2026-09-03T02:30:00+00:00"
        assert fake_st.session_state["cookie_loaded"] is True
    finally:
        alam_core.st = original_st
        alam_core.stx = original_stx


if __name__ == "__main__":
    tests = [
        value for name, value in globals().items()
        if name.startswith("test_") and callable(value)
    ]
    for test in tests:
        test()
    print(f"{len(tests)} Saved-update tests passed")
