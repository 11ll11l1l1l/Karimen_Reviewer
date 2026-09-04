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


def _assert_auth_project_guard_rejects_wrong_project():
    original_credentials = alam_auth._credentials
    alam_auth._credentials = lambda: (
        "https://zkfmgezvzugchcwppreq.supabase.co",
        "sb_publishable_test",
    )
    try:
        alam_runtime_safety._install_supabase_project_guard()
        try:
            alam_auth._credentials()
        except RuntimeError as exc:
            assert "unexpected Supabase project" in str(exc)
        else:
            raise AssertionError("Auth credentials accepted the retired Supabase project")
    finally:
        alam_auth._credentials = original_credentials


def _assert_sign_out_queues_browser_clear():
    original_st = alam_auth.st
    fake_state = {
        "alam_account": {"user_id": "u"},
        "alam_pending_auth_storage": {"x": "y"},
        "alam_account_state": {"saved": 4},
        "alam_account_state_user": "u",
    }
    fake_auth = SimpleNamespace(sign_out=lambda: None)
    fake_state["alam_auth_client"] = SimpleNamespace(auth=fake_auth)
    alam_auth.st = SimpleNamespace(session_state=fake_state)
    try:
        alam_auth.sign_out()
        assert fake_state["alam_clear_auth_storage"] is True
        assert "alam_auth_client" not in fake_state
        assert "alam_pending_auth_storage" not in fake_state
        assert "alam_account_state" not in fake_state
        assert "alam_account_state_user" not in fake_state
    finally:
        alam_auth.st = original_st


def _assert_auth_storage_readiness_is_normalized():
    original_st = alam_auth.st
    original_eval = alam_auth.streamlit_js_eval
    fake_state = {"alam_clear_auth_storage": True}
    alam_auth.st = SimpleNamespace(session_state=fake_state)
    try:
        # Legacy/component string booleans must not acknowledge a sign-out clear early.
        alam_auth.streamlit_js_eval = lambda **_kwargs: '{"ready":"false","value":null,"error":null}'
        ready, stored, error = alam_auth._auth_storage_bridge()
        assert ready is False and stored is None and error is None
        assert fake_state["alam_clear_auth_storage"] is True

        # A completed component render is not a successful storage mutation. If the
        # browser reports storage unavailable, the sign-out clear must remain queued so
        # a later Settings rerun can retry instead of leaving stale tokens persisted.
        alam_auth.streamlit_js_eval = lambda **_kwargs: '{"ready":true,"value":null,"error":"storage_unavailable"}'
        ready, stored, error = alam_auth._auth_storage_bridge()
        assert ready is True and stored is None and error == "storage_unavailable"
        assert fake_state["alam_clear_auth_storage"] is True

        alam_auth.streamlit_js_eval = lambda **_kwargs: '{"ready":"true","value":null,"error":null}'
        ready, stored, error = alam_auth._auth_storage_bridge()
        assert ready is True and stored is None and error is None
        assert "alam_clear_auth_storage" not in fake_state

        for encoded, expected in (("0", False), ("1", True)):
            alam_auth.streamlit_js_eval = (
                lambda value=encoded, **_kwargs: f'{{"ready":"{value}","value":null,"error":null}}'
            )
            assert alam_auth._auth_storage_bridge()[0] is expected
    finally:
        alam_auth.st = original_st
        alam_auth.streamlit_js_eval = original_eval


def _assert_saved_normalization_is_bounded_and_stable():
    values = ["story-a", "", "story-b", "story-a", None, " story-c "]
    assert alam_auth._normalized_saved_ids(values) == ["story-a", "story-b", "story-c"]
    many = [f"story-{index}" for index in range(alam_auth.MAX_ACCOUNT_SAVED_IMPORT + 20)]
    assert len(alam_auth._normalized_saved_ids(many)) == alam_auth.MAX_ACCOUNT_SAVED_IMPORT

    # Cloud state is additive, but an old browser-only ID that no longer exists in the
    # live article table must still remain in this session instead of being erased by sync.
    assert alam_auth._merged_session_saved_ids(
        ["cloud-story", "shared-story"],
        ["stale-browser-story", "shared-story"],
    ) == ["cloud-story", "shared-story", "stale-browser-story"]


def _assert_cloud_preferences_do_not_delete_local_history():
    original_st = alam_auth.st
    profile = {"r": {"hash-a": 1}, "m": ["hash-b"], "f": {"hash-c": ["MORE"]}, "s": {}}
    fake_state = {"alam_local_profile": profile}
    alam_auth.st = SimpleNamespace(session_state=fake_state)
    try:
        alam_auth._apply_cloud_preferences(
            {
                "interests": {"practical": True, "trend": False},
                "settings": {
                    "alert_min": 90,
                    "alert_action": True,
                    "alert_change": False,
                    "dark": True,
                },
            }
        )
        assert fake_state["alam_interest_preferences"] == {"practical": True, "trend": False}
        assert fake_state["alam_alert_min_importance"] == 90
        assert fake_state["alam_dark_mode"] is True
        assert profile["r"] == {"hash-a": 1}
        assert profile["m"] == ["hash-b"]
        assert profile["f"] == {"hash-c": ["MORE"]}
    finally:
        alam_auth.st = original_st


def _assert_cloud_preferences_normalize_legacy_or_malformed_scalars():
    original_st = alam_auth.st
    profile = {"r": {"keep": 1}, "m": [], "f": {}, "s": {}}
    fake_state = {"alam_local_profile": profile}
    alam_auth.st = SimpleNamespace(session_state=fake_state)
    try:
        alam_auth._apply_cloud_preferences(
            {
                "interests": {
                    "practical": "false",
                    "trend": "1",
                    "discover": {"unexpected": True},
                },
                "settings": {
                    "alert_min": {"broken": 100},
                    "alert_action": "false",
                    "alert_change": "0",
                    "dark": "true",
                },
            }
        )
        assert fake_state["alam_interest_preferences"] == {
            "practical": False,
            "trend": True,
            "discover": False,
        }
        assert fake_state["alam_alert_min_importance"] == 85
        assert fake_state["alam_alert_only_actionable"] is False
        assert fake_state["alam_alert_material_change"] is False
        assert fake_state["alam_dark_mode"] is True
        assert profile["r"] == {"keep": 1}
        assert profile["s"] == {
            "interests": {"practical": False, "trend": True, "discover": False},
            "alert_min": 85,
            "alert_action": False,
            "alert_change": False,
            "dark": True,
        }
    finally:
        alam_auth.st = original_st


def main():
    auth_source = inspect.getsource(alam_auth)
    client_source = inspect.getsource(alam_auth.get_auth_client)
    settings_source = inspect.getsource(alam_auth.render_account_settings)
    storage_source = inspect.getsource(alam_auth._auth_storage_expression)
    sync_source = inspect.getsource(alam_auth.synchronize_account_state)
    runtime_source = inspect.getsource(alam_runtime_safety._install_account_settings_hook)

    assert "st.cache_resource" not in _decorator_names(client_source)
    client_calls = _called_names(client_source)
    assert not any(name == "get_supabase_public" or name.endswith(".get_supabase_public") for name in client_calls)
    assert 'st.session_state["alam_auth_client"]' in client_source
    assert "SUPABASE_SERVICE_ROLE_KEY" not in auth_source
    assert "SUPABASE_PUBLISHABLE_KEY" in auth_source
    assert "verify_otp" in auth_source
    assert "alam_link_current_account" in auth_source
    assert "alam_import_current_device_reads" in sync_source
    assert 'table("saved_articles")' in sync_source
    assert 'table("user_preferences")' in sync_source
    assert "set_session" in auth_source
    assert "window.parent.localStorage" in storage_source
    assert "location.search" not in auth_source and "query_params" not in auth_source
    assert "render_account_settings" in runtime_source
    assert "browser-only alam" in settings_source.lower()
    assert "Sync this browser now" in settings_source
    assert "local_only_saved" in sync_source

    good = {
        "access_token": "a" * 45 + "." + "b" * 45 + "." + "c" * 45,
        "refresh_token": "refresh-token-123456789012345",
    }
    assert alam_auth._parse_persisted_session(good) == good
    assert alam_auth._parse_persisted_session({"access_token": "bad", "refresh_token": "short"}) is None
    assert alam_auth._parse_persisted_session("not-json") is None

    _assert_stale_account_fails_closed()
    _assert_restore_rotates_persisted_pair()
    _assert_auth_project_guard_rejects_wrong_project()
    _assert_sign_out_queues_browser_clear()
    _assert_auth_storage_readiness_is_normalized()
    _assert_saved_normalization_is_bounded_and_stable()
    _assert_cloud_preferences_do_not_delete_local_history()
    _assert_cloud_preferences_normalize_legacy_or_malformed_scalars()

    migration = (
        Path(__file__).resolve().parents[1] / "supabase" / "migrations" / "010_account_identity_bridge.sql"
    ).read_text(encoding="utf-8")
    assert "auth.uid()" in migration
    assert "security definer" in migration.lower()
    assert "revoke all on function public.alam_link_current_account(uuid) from public" in migration.lower()
    assert "grant execute on function public.alam_link_current_account(uuid) to authenticated" in migration.lower()
    assert "unique (visitor_id)" in migration.lower()

    history_migration = (
        Path(__file__).resolve().parents[1] / "supabase" / "migrations" / "012_account_state_history_bridge.sql"
    ).read_text(encoding="utf-8")
    lowered = history_migration.lower()
    assert "source_event_id" in lowered
    assert "article_reads_source_event_id_idx" in lowered
    assert "alam_import_current_device_reads" in lowered
    assert "auth.uid()" in lowered
    assert "on conflict do nothing" in lowered
    assert "revoke all on function public.alam_import_current_device_reads(uuid) from anon" in lowered
    assert "grant execute on function public.alam_import_current_device_reads(uuid) to authenticated" in lowered

    print("ALAM optional Auth account contract checks passed")


if __name__ == "__main__":
    main()
