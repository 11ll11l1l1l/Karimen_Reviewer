"""Network-free regression checks for ALAM's optional Auth account boundary."""

import ast
import inspect
from pathlib import Path

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


def main():
    auth_source = inspect.getsource(alam_auth)
    client_source = inspect.getsource(alam_auth.get_auth_client)
    settings_source = inspect.getsource(alam_auth.render_account_settings)
    runtime_source = inspect.getsource(alam_runtime_safety._install_account_settings_hook)

    assert "st.cache_resource" not in _decorator_names(client_source)
    assert "get_supabase_public" not in client_source
    assert 'st.session_state["alam_auth_client"]' in client_source
    assert "SUPABASE_SERVICE_ROLE_KEY" not in auth_source
    assert "SUPABASE_PUBLISHABLE_KEY" in auth_source
    assert "verify_otp" in auth_source
    assert "alam_link_current_account" in auth_source
    assert "Anonymous ALAM" in settings_source or "browser-only ALAM" in settings_source
    assert "render_account_settings" in runtime_source

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
