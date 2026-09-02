"""Regression tests for view-aware cross-agent comment hydration."""

from alam_comment_scope import comment_scope_ids


def test_selected_story_uses_single_story_scope():
    records = [{"id": "story-a"}, {"id": "story-b"}, {"id": "story-c"}]
    assert comment_scope_ids(records, "story-b") == ["story-b"]


def test_feed_scope_preserves_unique_current_story_order():
    records = [
        {"id": "story-b"},
        {"id": "story-a"},
        {"id": "story-b"},
        {"id": None},
        {},
        {"id": "story-c"},
    ]
    assert comment_scope_ids(records) == ["story-b", "story-a", "story-c"]


def test_stale_selected_story_falls_back_to_feed_scope():
    records = [{"id": "story-a"}, {"id": "story-b"}]
    assert comment_scope_ids(records, "removed-story") == ["story-a", "story-b"]


def test_empty_feed_is_safe():
    assert comment_scope_ids([], "story-a") == []
    assert comment_scope_ids(None, None) == []


if __name__ == "__main__":
    test_selected_story_uses_single_story_scope()
    test_feed_scope_preserves_unique_current_story_order()
    test_stale_selected_story_falls_back_to_feed_scope()
    test_empty_feed_is_safe()
    print("ALAM comment scope regression tests passed")
