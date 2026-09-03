from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IDENTITY = ROOT / "alam_app" / "alam_identity.py"
MIGRATION = ROOT / "supabase" / "migrations" / "009_lock_app_events_to_rpc.sql"


def test_browser_telemetry_uses_validated_rpc_only():
    text = IDENTITY.read_text(encoding="utf-8").lower()
    assert '"alam_log_event"' in text
    assert '.table("app_events")' not in text
    assert ".table('app_events')" not in text
    assert '.from_("app_events")' not in text
    assert ".from_('app_events')" not in text


def test_migration_closes_direct_app_event_write_boundary():
    text = MIGRATION.read_text(encoding="utf-8").lower()
    assert "revoke insert on table public.app_events from anon, authenticated" in text
    assert "revoke usage, select on sequence public.app_events_id_seq from anon, authenticated" in text
    assert 'drop policy if exists "anon inserts anonymous app events" on public.app_events' in text
    assert 'drop policy if exists "users insert own app events" on public.app_events' in text
