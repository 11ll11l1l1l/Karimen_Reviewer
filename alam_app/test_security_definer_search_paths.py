"""Regression guard for ALAM SECURITY DEFINER RPC search-path hardening."""
from pathlib import Path
import re


MIGRATION = Path(__file__).resolve().parents[1] / "supabase" / "migrations" / "018_harden_security_definer_search_paths.sql"

EXPECTED_SIGNATURES = (
    "public.alam_lookup_device(uuid)",
    "public.alam_register_device(uuid, text, text, jsonb)",
    "public.alam_log_event(uuid, text, text, text, jsonb)",
    "public.alam_link_current_account(uuid)",
    "public.alam_public_sync_health()",
)


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_exposed_security_definer_rpcs_get_empty_search_path():
    sql = _sql()
    for signature in EXPECTED_SIGNATURES:
        pattern = rf"alter\s+function\s+{re.escape(signature.lower())}\s+set\s+search_path\s*=\s*''\s*;"
        assert re.search(pattern, sql, flags=re.MULTILINE), signature


def test_search_path_hardening_is_non_destructive_and_replay_safe():
    sql = _sql()
    assert "drop function" not in sql
    assert "drop table" not in sql
    assert "delete from" not in sql
    assert "truncate" not in sql
    assert "create or replace function" not in sql
