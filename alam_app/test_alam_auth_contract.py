"""Network-free regression checks for ALAM's optional Auth account boundary."""

import ast
import inspect
from pathlib import Path
from types import SimpleNamespace

import alam_auth
import alam_runtime_safety


def _decorator_names(function_source: str) -> set[str]:
    """Return syntactic decorator names without matching explanatory docstrings."""
    node = ast.parse(function_source).body[0]
    names = set()
    for decorator in getattr(node, "decorator_list", []):
        try:
            names.add(ast.unparse(decorator))
        except Exception:
            names.add("<unknown>")
    return names


def _called_names(function_source: str) -> set[str]:
    """Return actual call targets so comments/docstrings cannot fool safety checks."""
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
    """A UI identity summary must never outlive its session-bound Auth client."""
    original_st = alam_auth.st
    fake_state = {
        "alam_account": {"user_id": "stale-user", "email": "stale@example.com"}
    }
    alam_auth.st = SimpleNamespace(session_state=fake_state)
    try:
        assert alam_auth.refresh_account() == {}
        assert "alam_account" not in fake_state
    finally:
        alam_auth.st = original_st


def main():
    auth_source = inspect.getsource(alam_auth)
    client_source = inspect.getsource(alam_auth.get_auth_client)
    settings_source = inspect.getsource(alam_auth.render_account_settings)
    runtime_source = inspect.getsource(alam_runtime_safety._install_account_settings_hook)

    assert "st.cache_resource" not in _decorator_names(client_source)
    client_calls = _called_names(client_source)
    assert not any(name == "get_supabase_public" or name.endswith(".get_supabase_public") for name in client_calls)
    assert 'st.session_state["alam_auth_client"]' in client_source
    assert "SUPABASE_SERVICE_ROLE_KEY" not in auth_source
    assert "SUPABASE_PUBLISHABLE_KEY" in auth_source
    assert "verify_otp" in auth_source
    assert "alam_link_current_account" in auth_source
    assert "Anonymous ALAM" in settings_source or "browser-only ALAM" in settings_source
    assert "render_account_settings" in runtime_source
    _assert_stale_account_fails_closed()

    migration = (
        Path(__file__).resolve().parents[1]
        / "supabase"
        / "migrations"
        / "010_account_identity_bridge.sql"
    ).read_text(encoding="utf-8")
    assert "auth.uid()" in migration
    assert "security definer" in migration.lower()
    assert "revoke all on function public.alam_link_current_account(uuid) from public" in migration.lower()
    assert "grant execute on function public.alam_link_current_account(uuid) to authenticated" in migration.lower()
    assert "unique (visitor_id)" in migration.lower()

    print("ALAM optional Auth account contract checks passed")


if __name__ == "__main__":
    main()
