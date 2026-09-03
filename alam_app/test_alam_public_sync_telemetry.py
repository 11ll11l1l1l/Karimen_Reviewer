"""Regression guard for public sync-health telemetry drift handling."""

from alam_supabase_health import classify_supabase_readiness


def test_untracked_health_can_never_be_declared_ready():
    state = classify_supabase_readiness(
        connected=True,
        content_source="supabase",
        sync_health={
            "last_sync_status": "untracked",
            "last_sync_started_at": None,
            "last_sync_finished_at": None,
            "published_articles": 36,
            "latest_article_updated_at": "2026-09-03T09:38:41+00:00",
        },
    )
    assert state.ready is False
    assert state.level == "warning"
    assert state.code == "sync_unknown_status"


if __name__ == "__main__":
    test_untracked_health_can_never_be_declared_ready()
    print("Public sync telemetry regression test passed")
