"""Regression checks for route-aware article history hydration."""

from alam_article_scope import _dedupe_current_from_history, selected_history_ids


def _record(article_id, created_at, title):
    return {"id": article_id, "created_at": created_at, "title": title}


def main():
    assert selected_history_ids("story-a") == ["story-a"]
    assert selected_history_ids(123) == ["123"]
    assert selected_history_ids("") == []
    assert selected_history_ids(None) == []

    current = [
        _record("story-a", "2026-09-03T01:00:00+00:00", "A now"),
        _record("story-b", "2026-09-03T02:00:00+00:00", "B now"),
    ]
    selected_history = [
        _record("story-a", "2026-09-02T01:00:00+00:00", "A before"),
        # Supabase article_versions also contains the current version; it must not
        # duplicate the current article in detail timelines.
        _record("story-a", "2026-09-03T01:00:00+00:00", "A now"),
    ]
    merged = _dedupe_current_from_history(current, selected_history)

    assert len(merged) == 3
    assert [row["title"] for row in merged].count("A now") == 1
    assert any(row["title"] == "A before" for row in merged)
    assert any(row["title"] == "B now" for row in merged)
    assert not any(row["id"] == "story-b" and row["title"] != "B now" for row in merged)

    print("ALAM article history scope regression checks passed")


if __name__ == "__main__":
    main()
