"""Regression tests for ALAM's compact personalized Today briefing."""

import alam_daily_brief as brief


def record(story_id, category, importance=70, action=None):
    content = {}
    if action:
        content["action"] = action
    return {
        "id": story_id,
        "_category": category,
        "importance": importance,
        "confidence": 80,
        "created_at": "2026-09-03T00:00:00+00:00",
        "title": story_id,
        "summary": story_id,
        "content": content,
    }


def relevance(item):
    return {
        "saved": 99,
        "saved-two": 95,
        "saved-three": 92,
        "practical": 90,
        "trend": 80,
        "discover": 70,
        "other": 60,
    }.get(item["id"], 50)


def main():
    records = [
        record("saved", "discover", 95),
        record("practical", "practical", 88, "DO NOW"),
        record("trend", "trend", 82),
        record("other", "reflection", 99),
    ]
    rows = brief.select_daily_brief_rows(
        records,
        saved_update_predicate=lambda item: item["id"] == "saved",
        relevance_fn=relevance,
    )
    assert [label for label, _ in rows] == ["REVIEW", "DO", "WATCH"]
    assert [item["id"] for _, item in rows] == ["saved", "practical", "trend"]
    assert len({item["id"] for _, item in rows}) == 3

    rows = brief.select_daily_brief_rows(
        records[1:],
        saved_update_predicate=lambda item: False,
        relevance_fn=relevance,
    )
    assert [label for label, _ in rows] == ["DO", "WATCH", "KNOW"]
    assert len({item["id"] for _, item in rows}) == len(rows) == 3

    sparse = [
        record("discover", "discover", 70),
        record("other", "reflection", 99),
        record("extra", "discover", 100),
    ]
    rows = brief.select_daily_brief_rows(
        sparse,
        saved_update_predicate=lambda item: False,
        relevance_fn=lambda item: 50,
    )
    assert len(rows) == 3
    assert len({item["id"] for _, item in rows}) == 3
    assert any(item["_category"] == "reflection" for _, item in rows), "Fallback must retain cross-category breadth."

    # Multiple material Saved changes must remain available beyond the single REVIEW
    # slot. Rank only changed Saved stories, dedupe stable IDs, and fail closed when
    # there are zero changes rather than filling the queue with ordinary stories.
    saved_records = [
        record("saved-two", "trend", 82),
        record("ordinary", "discover", 100),
        record("saved", "discover", 95),
        record("saved-three", "practical", 88, "PREPARE"),
        record("saved-two", "trend", 20),
    ]
    changed_ids = {"saved", "saved-two", "saved-three"}
    saved_updates = brief.select_saved_updates(
        saved_records,
        saved_update_predicate=lambda item: item["id"] in changed_ids,
        relevance_fn=relevance,
        limit=3,
    )
    assert [item["id"] for item in saved_updates] == ["saved", "saved-two", "saved-three"]
    assert len({item["id"] for item in saved_updates}) == 3
    assert brief.select_saved_updates(
        saved_records,
        saved_update_predicate=lambda item: False,
        relevance_fn=relevance,
    ) == []
    assert brief.select_saved_updates(
        saved_records,
        saved_update_predicate=lambda item: True,
        relevance_fn=relevance,
        limit=0,
    ) == []
    assert [item["id"] for item in brief.select_saved_updates(
        [record("saved", "discover", 95)],
        saved_update_predicate=lambda item: True,
        relevance_fn=relevance,
    )] == ["saved"]

    # Today may surface a deadline only when the validated Practical record explicitly
    # publishes one. Do not infer dates from prose and do not stringify malformed
    # structured values into user-facing instructions.
    deadline_story = record("deadline", "practical", 90, "APPLY")
    deadline_story["content"]["deadline"] = "2026-09-30"
    assert brief._deadline_note(deadline_story) == "2026-09-30"
    deadline_story["content"]["deadline"] = "  Apply by   September 30, 2026  "
    assert brief._deadline_note(deadline_story) == "Apply by September 30, 2026"
    for invalid in (None, "", "TBD", "unknown", {"date": "2026-09-30"}, ["2026-09-30"], True):
        deadline_story["content"]["deadline"] = invalid
        assert brief._deadline_note(deadline_story) == ""

    # Today may answer "Am I affected?" only from the explicit v5 audience field.
    # It must not infer eligibility from tags/profile state or stringify structures.
    affected_story = record("affected", "practical", 90, "PREPARE")
    affected_story["content"]["who_is_affected"] = "  Households   with children under age 3  "
    assert brief._affected_note(affected_story) == "Households with children under age 3"
    long_audience = "A" * 200
    affected_story["content"]["who_is_affected"] = long_audience
    assert brief._affected_note(affected_story) == "A" * 150
    for invalid in (None, "", "TBD", "unknown", {"group": "families"}, ["families"], True, 123):
        affected_story["content"]["who_is_affected"] = invalid
        assert brief._affected_note(affected_story) == ""

    # v5 records can legitimately use semantic/nested score forms. Runtime safety
    # already hardens the main feed score, but the briefing's own fallback and
    # explanation paths must not reintroduce direct float() crashes.
    assert brief._importance_score(record("semantic", "discover", "HIGH")) == 80.0
    assert brief._importance_score(record("nested", "discover", {"score": "92"})) == 92.0
    original_feed_score = brief.feed_score
    brief.feed_score = lambda item: 50.0
    try:
        semantic_sparse = [
            record("semantic", "discover", "HIGH"),
            record("other", "reflection", "MEDIUM"),
            record("extra", "discover", {"score": "92"}),
        ]
        rows = brief.select_daily_brief_rows(
            semantic_sparse,
            saved_update_predicate=lambda item: False,
            relevance_fn=lambda item: 50,
        )
        assert len(rows) == 3
        assert {item["id"] for _, item in rows} == {"semantic", "other", "extra"}
    finally:
        brief.feed_score = original_feed_score

    assert brief.select_daily_brief_rows([], saved_update_predicate=lambda item: False, relevance_fn=relevance) == []
    assert brief.select_saved_updates([], saved_update_predicate=lambda item: True, relevance_fn=relevance) == []
    print("ALAM daily briefing selection regression checks passed")


if __name__ == "__main__":
    main()
