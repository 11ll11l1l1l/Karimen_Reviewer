"""Regression tests for ALAM's Saved material-update review state.

These tests stay deterministic and browser-independent. They protect the two product
contracts that matter most: review acknowledgement advances monotonically without
removing the bookmark, and explicit v5 change summaries remain usable even when the
Saved page has only the current record rather than hydrated history.
"""

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


if __name__ == "__main__":
    tests = [
        value for name, value in globals().items()
        if name.startswith("test_") and callable(value)
    ]
    for test in tests:
        test()
    print(f"{len(tests)} Saved-update tests passed")
