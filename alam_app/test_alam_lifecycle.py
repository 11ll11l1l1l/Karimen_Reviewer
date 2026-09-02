"""Deterministic regression tests for ALAM story-lifecycle reactivation safety."""

from pathlib import Path

from alam_lifecycle import lifecycle_rejections


def version(status, created_at, *, reason=None, story_id="story-1"):
    content = {}
    if reason is not None:
        content["lifecycle"] = {"reactivation_reason": reason}
    return {
        "id": story_id,
        "agent": "discover",
        "created_at": created_at,
        "type": "technology",
        "title": "Lifecycle test story",
        "status": status,
        "content": content,
    }


def prepared(*records):
    story_id = str(records[0].get("id")) if records else "story-1"
    return {
        story_id: [
            ("discover", Path(f"v{index}.json"), record)
            for index, record in enumerate(records, start=1)
        ]
    }


def test_normal_active_progression_is_allowed():
    archive = prepared(
        version("NEW", "2026-09-03T01:00:00+09:00"),
        version("DEVELOPING", "2026-09-03T02:00:00+09:00"),
        version("CONFIRMED", "2026-09-03T03:00:00+09:00"),
    )
    assert lifecycle_rejections(archive) == []


def test_retirement_is_allowed_without_clock_based_expiry():
    archive = prepared(
        version("CONFIRMED", "2026-09-03T01:00:00+09:00"),
        version("FADING", "2026-09-03T02:00:00+09:00"),
        version("RESOLVED", "2026-09-03T03:00:00+09:00"),
    )
    assert lifecycle_rejections(archive) == []


def test_fading_story_cannot_silently_reactivate():
    archive = prepared(
        version("FADING", "2026-09-03T01:00:00+09:00"),
        version("DEVELOPING", "2026-09-03T02:00:00+09:00"),
    )
    rejected = lifecycle_rejections(archive)
    assert len(rejected) == 1
    assert rejected[0]["reasons"] == ["retired_story_reactivation_reason_required"]
    assert rejected[0]["metrics"]["previous_lifecycle"] == "FADING"
    assert rejected[0]["metrics"]["incoming_lifecycle"] == "DEVELOPING"


def test_resolved_story_cannot_silently_look_new_again():
    archive = prepared(
        version("RESOLVED", "2026-09-03T01:00:00+09:00"),
        version("NEW", "2026-09-03T02:00:00+09:00"),
    )
    assert len(lifecycle_rejections(archive)) == 1


def test_explicit_reactivation_reason_allows_legitimate_reopening():
    archive = prepared(
        version("RESOLVED", "2026-09-03T01:00:00+09:00"),
        version(
            "DEVELOPING",
            "2026-09-03T02:00:00+09:00",
            reason="The ministry reopened the consultation after publishing a new draft.",
        ),
    )
    assert lifecycle_rejections(archive) == []


def test_whitespace_reason_does_not_bypass_guard():
    archive = prepared(
        version("FADING", "2026-09-03T01:00:00+09:00"),
        version("CONFIRMED", "2026-09-03T02:00:00+09:00", reason="   "),
    )
    assert len(lifecycle_rejections(archive)) == 1


def test_active_state_can_become_fluid_again_without_fake_terminal_rule():
    archive = prepared(
        version("CONFIRMED", "2026-09-03T01:00:00+09:00"),
        version("DEVELOPING", "2026-09-03T02:00:00+09:00"),
    )
    assert lifecycle_rejections(archive) == []


def test_versions_are_evaluated_by_timestamp_not_input_order():
    archive = prepared(
        version("DEVELOPING", "2026-09-03T03:00:00+09:00"),
        version("RESOLVED", "2026-09-03T02:00:00+09:00"),
        version("NEW", "2026-09-03T01:00:00+09:00"),
    )
    # Chronological order is NEW -> RESOLVED -> DEVELOPING, so the final transition
    # is a real reactivation even though the synthetic input arrived out of order.
    assert len(lifecycle_rejections(archive)) == 1


if __name__ == "__main__":
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
    print(f"ALAM lifecycle tests passed ({len(tests)})")
