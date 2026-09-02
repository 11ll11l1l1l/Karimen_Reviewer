"""Deterministic regression tests for ALAM Supabase readiness classification."""

from datetime import datetime, timezone

from alam_supabase_health import classify_supabase_readiness, normalize_public_sync_health

NOW = datetime(2026, 9, 3, 0, 0, tzinfo=timezone.utc)


def _health(**overrides):
    base = {
        "last_sync_status": "success",
        "last_sync_started_at": "2026-09-02T23:54:00+00:00",
        "last_sync_finished_at": "2026-09-02T23:56:00+00:00",
        "stories_found": 4,
        "stories_published": 1,
        "stories_rejected": 0,
        "error_count": 0,
        "published_articles": 7,
        "latest_article_updated_at": "2026-09-02T23:50:00+00:00",
    }
    base.update(overrides)
    return base


def test_normalizer_accepts_postgrest_list_shape_and_numeric_strings():
    row = normalize_public_sync_health([
        {
            "last_sync_status": "success",
            "stories_found": "4",
            "stories_published": "2",
            "stories_rejected": "1",
            "error_count": "0",
            "published_articles": "9",
        }
    ])
    assert row["stories_found"] == 4
    assert row["stories_published"] == 2
    assert row["stories_rejected"] == 1
    assert row["error_count"] == 0
    assert row["published_articles"] == 9


def test_disconnected_outranks_other_state():
    state = classify_supabase_readiness(
        connected=False,
        content_source="local_fallback",
        sync_health=_health(last_sync_status="success"),
        now=NOW,
    )
    assert state.code == "disconnected"
    assert state.level == "error"
    assert state.ready is False


def test_missing_rpc_is_not_misreported_as_healthy():
    state = classify_supabase_readiness(
        connected=True,
        content_source="supabase",
        sync_health={},
        sync_health_error="function alam_public_sync_health does not exist",
        now=NOW,
    )
    assert state.code == "sync_health_unavailable"
    assert state.ready is False


def test_never_synchronized_is_distinct_from_empty_content():
    state = classify_supabase_readiness(
        connected=True,
        content_source="local_fallback",
        sync_health=_health(last_sync_status=None, last_sync_finished_at=None, published_articles=0),
        now=NOW,
    )
    assert state.code == "never_synchronized"
    assert state.ready is False


def test_failed_and_partial_syncs_remain_visible_even_if_rows_are_readable():
    failed = classify_supabase_readiness(
        connected=True,
        content_source="supabase",
        sync_health=_health(last_sync_status="failed"),
        now=NOW,
    )
    partial = classify_supabase_readiness(
        connected=True,
        content_source="supabase",
        sync_health=_health(last_sync_status="partial"),
        now=NOW,
    )
    assert failed.code == "sync_failed"
    assert failed.level == "error"
    assert failed.ready is False
    assert partial.code == "sync_partial"
    assert partial.level == "warning"
    assert partial.ready is False


def test_stale_success_is_not_declared_ready():
    state = classify_supabase_readiness(
        connected=True,
        content_source="supabase",
        sync_health=_health(last_sync_finished_at="2026-09-02T12:00:00+00:00"),
        stale_after_hours=6,
        now=NOW,
    )
    assert state.code == "sync_stale"
    assert state.ready is False
    assert state.sync_age_hours == 12.0


def test_successful_sync_but_local_reader_is_explicit_fallback():
    state = classify_supabase_readiness(
        connected=True,
        content_source="local_fallback",
        sync_health=_health(),
        now=NOW,
    )
    assert state.code == "local_fallback"
    assert state.ready is False


def test_synchronized_empty_database_can_be_operationally_healthy():
    state = classify_supabase_readiness(
        connected=True,
        content_source="supabase",
        sync_health=_health(published_articles=0),
        now=NOW,
    )
    assert state.code == "synchronized_empty"
    assert state.level == "info"
    assert state.ready is True


def test_recent_success_plus_supabase_feed_is_ready():
    state = classify_supabase_readiness(
        connected=True,
        content_source="supabase",
        sync_health=_health(),
        now=NOW,
    )
    assert state.code == "ready"
    assert state.level == "success"
    assert state.ready is True
    assert state.published_articles == 7
    assert round(state.sync_age_hours or -1, 3) == round(4 / 60, 3)


if __name__ == "__main__":
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
    print(f"Supabase readiness regression tests passed: {len(tests)}")
