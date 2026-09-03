from alam_related_views import related_story_candidates


def _story(story_id, tags, category="discover", importance=70):
    return {
        "id": story_id,
        "title": story_id,
        "tags": tags,
        "_category": category,
        "importance": importance,
        "confidence": 80,
        "created_at": "2026-09-03T10:00:00+09:00",
        "content": {},
    }


def test_related_stories_require_shared_validated_signal():
    base = _story("base", ["yen", "household"])
    linked = _story("linked", ["yen", "boj"], "reflection", 90)
    unrelated = _story("unrelated", ["semiconductor", "robot"], "discover", 99)
    rows = related_story_candidates(base, [base, unrelated, linked])
    assert [row[2]["id"] for row in rows] == ["linked"]
    assert rows[0][3] == ["yen"]


def test_explicit_connection_tags_work_without_title_inference():
    base = _story("base", [])
    base["content"] = {"connection_tags": ["rate-normalization"]}
    linked = _story("linked", [])
    linked["content"] = {"connection_tags": ["rate-normalization", "mortgages"]}
    rows = related_story_candidates(base, [base, linked])
    assert len(rows) == 1
    assert rows[0][3] == ["rate-normalization"]


def test_zero_and_one_story_states_are_safe():
    base = _story("base", ["yen"])
    assert related_story_candidates(base, []) == []
    assert related_story_candidates(base, [base]) == []
