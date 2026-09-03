from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "027_minimize_anonymous_identity_metadata.sql"
IDENTITY = ROOT / "alam_app" / "alam_identity.py"


def test_registration_rpc_minimizes_client_metadata():
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    assert "create or replace function public.alam_register_device" in sql
    assert "security definer" in sql
    assert "set search_path = ''" in sql
    assert "'identity_model'" in sql
    assert "'app'" in sql
    assert "jsonb_strip_nulls" in sql
    assert "values (v_name, v_metadata)" in sql
    assert "p_session_id" in sql and "120" in sql
    assert "grant execute on function public.alam_register_device" in sql
    assert " to anon, authenticated" in sql


def test_identity_rpc_cannot_persist_fingerprinting_keys():
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    # p_metadata is accepted for backward-compatible clients, but only explicit keys
    # may cross the SECURITY DEFINER boundary into durable visitor state.
    assert "values (v_name, coalesce(p_metadata" not in sql
    assert "coalesce(p_metadata, '{}'::jsonb)" not in sql
    assert "user_agent" not in sql
    assert "ip_address" not in sql


def test_application_identity_contract_remains_random_uuid_based():
    source = IDENTITY.read_text(encoding="utf-8")
    assert 'DEVICE_STORAGE_KEY = "alam_device_id_v2"' in source
    assert "uuid.uuid4()" in source
    assert "fingerprint" in source.lower()
