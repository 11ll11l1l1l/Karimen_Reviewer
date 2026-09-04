from pathlib import Path


ROOT = Path(__file__).resolve().parent
MIGRATION = ROOT.parent / "supabase" / "migrations" / "030_harden_public_default_privileges.sql"


def test_future_application_owned_public_objects_fail_closed_for_browser_roles():
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "alter default privileges for role postgres in schema public" in sql
    assert "revoke all on tables from anon, authenticated" in sql
    assert "revoke all on sequences from anon, authenticated" in sql
    assert "revoke execute on functions from public, anon, authenticated" in sql

    # Provider-owned supabase_admin defaults are not mutable from project migrations.
    # Keep the migration scoped to the owner that creates ALAM application objects.
    assert "alter default privileges for role supabase_admin" not in sql

    # Browser access to future durable state/RPCs must be an explicit opt-in in the
    # migration that creates the object, never an ambient default privilege.
    assert "grant all on tables to anon" not in sql
    assert "grant all on tables to authenticated" not in sql
    assert "grant execute on functions to public" not in sql


def test_default_privilege_hardening_is_non_destructive():
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    for destructive in (
        "drop table",
        "truncate",
        "delete from",
        "update public.",
        "alter table",
        "revoke all on all tables",
        "revoke execute on all functions",
    ):
        assert destructive not in sql
