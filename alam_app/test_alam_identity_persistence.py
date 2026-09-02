"""Regression checks for ALAM browser/device recognition.

This test stays network-free. It proves the identity layer reads device identity from
Streamlit's native request cookies, never uses a component read fallback, writes the
long-lived cookie only when explicitly asked, and reuses one CookieManager instance per
Streamlit session.
"""

import inspect
from types import SimpleNamespace

import alam_core as core
import alam_identity as identity


class FakeCookies(dict):
    pass


class FakeManager:
    def __init__(self, value=None):
        self.value = value
        self.calls = []
        self.get_calls = []

    def get(self, cookie):
        self.get_calls.append(cookie)
        return self.value

    def set(self, *args, **kwargs):
        self.calls.append((args, kwargs))


class FakeStx:
    def __init__(self):
        self.created = 0
        self.manager = FakeManager()

    def CookieManager(self, key):
        self.created += 1
        return self.manager


def main():
    original_identity_st = identity.st
    original_core_st = core.st
    original_core_stx = core.stx
    try:
        native_id = "805b1bcf-943e-4e07-9c3f-5bef33ac18b8"
        legacy_component_id = "15ca5b5f-5ddb-49f1-a793-636f5f5e91c4"

        identity.st = SimpleNamespace(
            context=SimpleNamespace(cookies=FakeCookies({identity.DEVICE_COOKIE: native_id}))
        )
        manager = FakeManager(legacy_component_id)
        assert identity._cookie_get(manager) == native_id
        assert manager.get_calls == [], "Device recognition must not depend on an async component read."

        identity.st = SimpleNamespace(context=SimpleNamespace(cookies=FakeCookies()))
        assert identity._cookie_get(manager) is None
        assert manager.get_calls == [], "Missing native cookies must not trigger a component read/rerun."

        assert identity._valid_device_id("not-a-uuid") is None
        assert identity._valid_device_id(native_id) == native_id

        writer = FakeManager()
        assert identity._cookie_set(writer, native_id, key="confirm_alam_device_id") is True
        assert len(writer.calls) == 1
        args, kwargs = writer.calls[0]
        assert args[0] == identity.DEVICE_COOKIE
        assert args[1] == native_id
        assert kwargs["path"] == "/"
        assert kwargs["same_site"] == "lax"
        assert kwargs["max_age"] == identity.COOKIE_MAX_AGE
        assert kwargs["key"] == "confirm_alam_device_id"
        assert identity.COOKIE_DAYS >= 365

        onboarding_source = inspect.getsource(identity.render_onboarding)
        assert "refresh_alam_device_id" not in onboarding_source
        assert onboarding_source.count("_cookie_set(") == 1, (
            "Returning visitors must not rewrite the device cookie on every render."
        )

        fake_stx = FakeStx()
        fake_state = {}
        core.st = SimpleNamespace(
            session_state=fake_state,
            context=SimpleNamespace(cookies=FakeCookies()),
        )
        core.stx = fake_stx
        first = core.init_browser_state()
        second = core.init_browser_state()
        assert first is second is fake_stx.manager
        assert fake_stx.created == 1, "CookieManager must be created once per Streamlit session."

        print("ALAM identity persistence regression checks passed")
    finally:
        identity.st = original_identity_st
        core.st = original_core_st
        core.stx = original_core_stx


if __name__ == "__main__":
    main()
