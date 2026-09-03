"""Regression tests for ALAM Saved review state and collection organization."""

from pathlib import Path
from types import SimpleNamespace

import alam_core
import alam_saved_views as saved_views
from alam_local_state import _advance_saved_snapshot, _sid
from alam_saved_views import (
    DEFAULT_COLLECTION,
    _change_preview,
    _collection_key,
    _decode_collection_cookie,
    _normalize_collection,
)


def test_saved_snapshot_advances_monotonically():
    profile = {"b": {}}
    story_id = "story-123"
    assert _advance_saved_snapshot(profile, story_id, 100) is True
    assert profile["b"][_sid(story_id)] == 100
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
    assert _change_preview(record, [record]) == (
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


def test_saved_collection_normalization_is_backward_compatible():
    assert _normalize_collection("saved") == DEFAULT_COLLECTION
    assert _normalize_collection("Read Later") == DEFAULT_COLLECTION
    assert _normalize_collection("money") == "money"
    assert _normalize_collection("unexpected-value") == DEFAULT_COLLECTION


def test_saved_collection_cookie_rejects_bad_shape_and_normalizes_values():
    assert _decode_collection_cookie("[]") == {}
    story_key = _collection_key("story-9")
    decoded = _decode_collection_cookie(
        '{"%s":"Important","123456789abc":"not-a-real-collection"}' % story_key
    )
    assert decoded[story_key] == "important"
    assert decoded["123456789abc"] == DEFAULT_COLLECTION


def test_collection_cookie_uses_hashed_story_keys():
    key = _collection_key("a-very-long-stable-story-id")
    assert len(key) == 12
    assert "story" not in key


def test_saved_collection_database_domain_matches_product_vocabulary():
    """Durable account state must reject labels the browser cannot interpret."""
    migration = (
        Path(__file__).resolve().parents[1]
        / "supabase"
        / "migrations"
        / "017_saved_collection_domain.sql"
    ).read_text(encoding="utf-8")
    expected = {"saved", "read_later", "important", "money", "japan", "family", "ideas"}
    for value in expected:
        assert f"'{value}'" in migration
    assert "saved_articles_collection_domain_check" in migration
    assert "CHECK (collection IN" in migration
    assert "DROP TABLE" not in migration.upper()
    assert "DELETE FROM" not in migration.upper()


def test_failed_cloud_collection_write_cannot_revert_newer_browser_choice():
    """A stale successful read must not undo a collection move whose write is retrying."""
    story_id = "story-sync-failure"
    story_key = _collection_key(story_id)
    original_st = saved_views.st
    original_cloud_collections = saved_views._cloud_collections
    original_set_cloud_collection = saved_views._set_cloud_collection
    fake_st = SimpleNamespace(
        session_state={
            "alam_saved_collections_loaded": True,
            "alam_saved_collections": {story_key: "money"},
            saved_views.PENDING_COLLECTIONS_STATE: {story_id: "money"},
        }
    )
    try:
        saved_views.st = fake_st
        saved_views._cloud_collections = lambda saved_ids: ({story_id: DEFAULT_COLLECTION}, None)
        saved_views._set_cloud_collection = lambda sid, collection: (False, "retry pending")
        effective, error = saved_views._effective_collections([{"id": story_id}])
        assert effective[story_id] == "money"
        assert error == "retry pending"
        assert fake_st.session_state[saved_views.PENDING_COLLECTIONS_STATE][story_id] == "money"
    finally:
        saved_views.st = original_st
        saved_views._cloud_collections = original_cloud_collections
        saved_views._set_cloud_collection = original_set_cloud_collection


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
    print(f"{len(tests)} Saved-update/collection tests passed")
