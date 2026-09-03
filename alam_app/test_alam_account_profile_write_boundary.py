"""Regression guard for the authenticated account-profile write boundary."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "026_lock_account_profile_writes_to_rpc.sql"
AUTH = ROOT / "alam_app" / "alam_auth.py"


def test_account_profile_mutations_are_rpc_only():
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "revoke insert, update, delete on table public.account_profiles from authenticated" in sql
    assert "grant select on table public.account_profiles to authenticated" in sql
    assert "revoke all privileges on table public.account_profiles from anon" in sql

    # RLS protects rows, but primary_visitor_id is part of the identity bridge and must
    # never become browser-writable independently of account_visitor_links.
    for forbidden in (
        "grant insert on table public.account_profiles to authenticated",
        "grant update on table public.account_profiles to authenticated",
        "grant delete on table public.account_profiles to authenticated",
        "grant select, insert",
    ):
        assert forbidden not in sql


def test_browser_account_flow_does_not_directly_mutate_profiles():
    source = AUTH.read_text(encoding="utf-8")
    assert '.table("account_profiles")' not in source
    assert '"alam_link_current_account"' in source


def test_account_profile_write_lock_is_replay_safe_and_non_destructive():
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    assert "alter table public.account_profiles enable row level security" in sql
    for destructive in ("drop table", "truncate table", "delete from"):
        assert destructive not in sql
