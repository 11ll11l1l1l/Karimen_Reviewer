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
    assert [label for label, _ in rows] == ["DO", "WATCH", "KNOW"] or [label for label, _ in rows] == ["DO", "WATCH", "KNOW"]
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

    assert brief.select_daily_brief_rows([], saved_update_predicate=lambda item: False, relevance_fn=relevance) == []
    print("ALAM daily briefing selection regression checks passed")


if __name__ == "__main__":
    main()
