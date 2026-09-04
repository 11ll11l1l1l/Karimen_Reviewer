"""Focused regression checks for Today's bounded additional-deadline queue."""

import alam_daily_brief as brief


def story(story_id, deadline=None, action="APPLY", relevance=50):
    content = {"action": action}
    if deadline is not None:
        content["deadline"] = deadline
    return {"id": story_id, "_category": "practical", "importance": relevance, "confidence": 80, "title": story_id, "summary": story_id, "content": content}


def main():
    high = story("high", "2026-10-01", "PREPARE", 90)
    low = story("low", "Apply by October 15", "APPLY", 70)
    no_deadline = story("none", None, "DO NOW", 99)
    malformed = story("bad", {"date": "2026-09-05"}, "APPLY", 99)
    duplicate = dict(high)
    scores = {"high": 96, "low": 70, "none": 99, "bad": 99}
    relevance = lambda item: scores.get(item["id"], 50)

    queued = brief.select_deadline_actions(
        [low, no_deadline, high, malformed, duplicate],
        exclude_ids={"low"},
        relevance_fn=relevance,
        limit=2,
    )
    assert [item["id"] for item in queued] == ["high"]
    assert [item["id"] for item in brief.select_deadline_actions([low, high], relevance_fn=relevance, limit=1)] == ["high"]
    assert brief.select_deadline_actions([no_deadline, malformed], relevance_fn=relevance) == []
    assert brief.select_deadline_actions([], relevance_fn=relevance) == []
    assert brief.select_deadline_actions([high], relevance_fn=relevance, limit=0) == []
    print("ALAM Today additional deadline queue checks passed")


if __name__ == "__main__":
    main()
