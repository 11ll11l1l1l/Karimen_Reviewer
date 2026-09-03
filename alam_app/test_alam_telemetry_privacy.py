from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "024_minimize_event_telemetry.sql"


def _migration_text() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_browser_event_taxonomy_is_explicitly_bounded():
    text = _migration_text()
    for event_name in (
        "app_open",
        "article_open",
        "navigation",
        "onboarding_completed",
        "ui_control_changed",
    ):
        assert f"'{event_name}'" in text
    assert "unsupported event name" in text


def test_event_properties_are_event_specific_and_privacy_minimized():
    text = _migration_text()
    for key in (
        "recognized_device",
        "category",
        "type",
        "page",
        "section",
        "returning_device",
        "control",
        "value",
    ):
        assert f"'{key}'" in text
    assert "jsonb_typeof(p_properties) <> 'object'" in text
    assert "jsonb_typeof(e.value) in ('string', 'number', 'boolean', 'null')" in text
    assert "octet_length(e.value::text) <= 160" in text


def test_event_rpc_keeps_hardened_privilege_boundary():
    text = _migration_text()
    assert "security definer" in text
    assert "set search_path = ''" in text
    assert "revoke all on function public.alam_log_event" in text
    assert "grant execute on function public.alam_log_event" in text
    assert "to anon, authenticated" in text


def test_article_telemetry_only_links_published_articles():
    text = _migration_text()
    assert "a.status = 'published'" in text


def test_telemetry_migration_is_non_destructive():
    text = _migration_text()
    assert "delete from" not in text
    assert "truncate" not in text
    assert "drop table" not in text
    assert "drop function" not in text
