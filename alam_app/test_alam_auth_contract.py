"""Network-free regression checks for ALAM's optional Auth account boundary."""

import ast
import inspect
from pathlib import Path
from types import SimpleNamespace

import alam_auth
import alam_runtime_safety


def _decorator_names(function_source: str) -> set[str]:
    node = ast.parse(function_source).body[0]
    names = set()
    for decorator in getattr(node, "decorator_list", []):
        try:
            names.add(ast.unparse(decorator))
        except Exception:
            names.add("<unknown>")
    return names


def _called_names(function_source: str) -> set[str]:
    tree = ast.parse(function_source)
    names = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        try:
            names.add(ast.unparse(node.func))
        except Exception:
            if isinstance(node.func, ast.Name):
                names.add(node.func.id)
    return names


def _assert_stale_account_fails_closed():
    original_st = alam_auth.st
    fake_state = {"alam_account": {"user_id": "stale-user", "email": "stale@example.com"}}
    alam_auth.st = SimpleNamespace(session_state=fake_state)
    try:
        assert alam_auth.refresh_account() == {}
        assert "alam_account" not in fake_state
    finally:
        alam_auth.st = original_st


def _assert_restore_rotates_persisted_pair():
    original_st = alam_auth.st
    original_create_client = alam_auth.create_client
    user = SimpleNamespace(id="user-1", email="reader@example.com")
    rotated = SimpleNamespace(
        access_token="a" * 45 + "." + "b" * 45 + "." + "c" * 45,
        refresh_token="rotated-refresh-token-1234567890",
    )

    class FakeAuth:
        def __init__(self):
            self.set_calls = []

        def set_session(self, access, refresh):
            self.set_calls.append((access, refresh))
            return SimpleNamespace(session=rotated, user=user)

        def get_user(self):
            raise AssertionError("set_session already returned the verified user")

    fake_auth = FakeAuth()
    fake_client = SimpleNamespace(auth=fake_auth)
    fake_state = {}
    alam_auth.st = SimpleNamespace(
        session_state=fake_state,
        secrets={"SUPABASE_URL": "https://example.supabase.co", "SUPABASE_PUBLISHABLE_KEY": "sb_publishable_test"},
    )
    alam_auth.create_client = lambda *_args, **_kwargs: fake_client
    try:
        original = {
            "access_token": "x" * 45 + "." + "y" * 45 + "." + "z" * 45,
            "refresh_token": "original-refresh-token-123456789",
        }
        account = alam_auth._restore_browser_session(original)
        assert account["user_id"] == "user-1"
        assert fake_auth.set_calls == [(original["access_token"], original["refresh_token"])]
        assert fake_state["alam_pending_auth_storage"] == {
            "access_token": rotated.access_token,
            "refresh_token": rotated.refresh_token,
        }
    finally:
        alam_auth.st = original_st
        alam_auth.create_client = original_create_client


def _assert_sign_out_queues_browser_clear():
    original_st = alam_auth.st
    fake_state = {"alam_account": {"user_id": "u"}, "alam_pending_auth_storage": {"x": "y"}}
    fake_auth = SimpleNamespace(sign_out=lambda: None)
    fake_state["alam_auth_client"] = SimpleNamespace(auth=fake_auth)
    alam_auth.st = SimpleNamespace(session_state=fake_state)
    try:
        alam_auth.sign_out()
        assert fake_state["alam_clear_auth_storage"] is True
        assert "alam_auth_client" not in fake_state
        assert "alam_pending_auth_storage" not in fake_state
    finally:
        alam_auth.st = original_st


def main():
    auth_source = inspect.getsource(alam_auth)
    client_source = inspect.getsource(alam_auth.get_auth_client)
    settings_source = inspect.getsource(alam_auth.render_account_settings)
    storage_source = inspect.getsource(alam_auth._auth_storage_expression)
    runtime_source = inspect.getsource(alam_runtime_safety._install_account_settings_hook)

    assert "st.cache_resource" not in _decorator_names(client_source)
    client_calls = _called_names(client_source)
    assert not any(name == "get_supabase_public" or name.endswith(".get_supabase_public") for name in client_calls)
    assert 'st.session_state["alam_auth_client"]' in client_source
    assert "SUPABASE_SERVICE_ROLE_KEY" not in auth_source
    assert "SUPABASE_PUBLISHABLE_KEY" in auth_source
    assert "verify_otp" in auth_source
    assert "alam_link_current_account" in auth_source
    assert "set_session" in auth_source
    assert "window.parent.localStorage" in storage_source
    assert "location.search" not in auth_source and "query_params" not in auth_source
    assert "render_account_settings" in runtime_source
    assert "Anonymous ALAM" in settings_source or "browser-only ALAM" in settings_source

    good = {
        "access_token": "a" * 45 + "." + "b" * 45 + "." + "c" * 45,
        "refresh_token": "refresh-token-123456789012345",
    }
    assert alam_auth._parse_persisted_session(good) == good
    assert alam_auth._parse_persisted_session({"access_token": "bad", "refresh_token": "short"}) is None
    assert alam_auth._parse_persisted_session("not-json") is None

    _assert_stale_account_fails_closed()
    _assert_restore_rotates_persisted_pair()
    _assert_sign_out_queues_browser_clear()

    migration = (
        Path(__file__).resolve().parents[1] / "supabase" / "migrations" / "010_account_identity_bridge.sql"
    ).read_text(encoding="utf-8")
    assert "auth.uid()" in migration
    assert "security definer" in migration.lower()
    assert "revoke all on function public.alam_link_current_account(uuid) from public" in migration.lower()
    assert "grant execute on function public.alam_link_current_account(uuid) to authenticated" in migration.lower()
    assert "unique (visitor_id)" in migration.lower()

    print("ALAM optional Auth account contract checks passed")


if __name__ == "__main__":
    main()
