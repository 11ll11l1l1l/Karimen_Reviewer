"""Regression guards for public sync-health telemetry drift detection."""

from pathlib import Path

from alam_supabase_health import classify_supabase_readiness

MIGRATION = Path(__file__).resolve().parents[1] / "supabase" / "migrations" / "019_detect_untracked_public_sync.sql"


def test_migration_detects_published_writes_without_canonical_sync_telemetry():
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    assert "agent_id = 'alam_supabase_sync'" in sql
    assert "when ls.started_at is null then true" in sql
    assert "'untracked'" in sql
    assert "newest_update > coalesce(ls.finished_at, ls.started_at) + interval '5 minutes'" in sql


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


def test_migration_preserves_security_boundary_and_is_non_destructive():
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    assert "security definer" in sql
    assert "set search_path = ''" in sql
    assert "revoke all on function public.alam_public_sync_health() from public" in sql
    assert "grant execute on function public.alam_public_sync_health() to anon, authenticated" in sql
    assert "delete from" not in sql
    assert "drop table" not in sql


if __name__ == "__main__":
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
    print(f"Public sync telemetry regression tests passed: {len(tests)}")
