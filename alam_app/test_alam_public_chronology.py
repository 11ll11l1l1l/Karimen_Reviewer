from alam_core import feed_score, latest_by_story


def _record(story_id, created_at, published_at, importance=70):
    return {
        "id": story_id,
        "title": story_id,
        "created_at": created_at,
        "published_at": published_at,
        "importance": importance,
        "confidence": 80,
        "content": {"usefulness": 70, "novelty": 70},
        "sources": [],
    }


def test_latest_version_selection_uses_created_at_but_public_order_uses_published_at():
    story_a_old = _record(
        "story-a",
        "2026-09-07T08:00:00+09:00",
        "2026-09-07T08:00:00+09:00",
    )
    story_a_new_version = _record(
        "story-a",
        "2026-09-07T12:00:00+09:00",
        "2026-09-07T09:00:00+09:00",
    )
    story_b = _record(
        "story-b",
        "2026-09-07T10:00:00+09:00",
        "2026-09-07T10:00:00+09:00",
    )

    current = latest_by_story([story_a_old, story_a_new_version, story_b])

    assert current[0]["id"] == "story-b"
    assert current[1] is story_a_new_version


def test_legacy_public_order_falls_back_to_created_at():
    legacy = _record(
        "legacy",
        "2026-09-07T11:00:00+09:00",
        "2026-09-07T11:00:00+09:00",
    )
    legacy.pop("published_at")
    explicit = _record(
        "explicit",
        "2026-09-07T10:30:00+09:00",
        "2026-09-07T10:30:00+09:00",
    )

    assert [r["id"] for r in latest_by_story([explicit, legacy])] == ["legacy", "explicit"]


def test_feed_freshness_does_not_reward_delayed_ingestion():
    published_earlier_but_ingested_later = _record(
        "delayed",
        "2026-09-07T12:30:00+09:00",
        "2026-09-06T09:00:00+09:00",
    )
    published_later = _record(
        "fresh",
        "2026-09-07T10:00:00+09:00",
        "2026-09-07T10:00:00+09:00",
    )

    assert feed_score(published_later) > feed_score(published_earlier_but_ingested_later)
