"""Regression guard for account-state Data API privileges."""
from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "supabase"
    / "migrations"
    / "020_harden_account_state_grants.sql"
)


def test_account_state_grants_are_least_privilege():
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "revoke all privileges on table public.account_profiles from authenticated" in sql
    assert "grant select, insert, update, delete on table public.account_profiles to authenticated" in sql
    assert "revoke all privileges on table public.account_visitor_links from authenticated" in sql
    assert "grant select on table public.account_visitor_links to authenticated" in sql

    # Durable account identity must never regain table-level capabilities that RLS does
    # not meaningfully constrain, especially TRUNCATE.
    for forbidden in ("grant truncate", "grant trigger", "grant references"):
        assert forbidden not in sql


def test_account_grant_migration_is_replay_safe_and_non_destructive():
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    assert "alter table public.account_profiles enable row level security" in sql
    assert "alter table public.account_visitor_links enable row level security" in sql
    for destructive in ("drop table", "truncate table", "delete from"):
        assert destructive not in sql
