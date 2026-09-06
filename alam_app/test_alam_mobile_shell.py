from pathlib import Path

import alam_mobile_shell as shell


def test_mobile_shell_integrity():
    cookie = shell.COOKIE_GUARD_CSS
    mobile = shell.MOBILE_SHELL_CSS

    # Must match the real extra_streamlit_components.CookieManager key created in
    # alam_core.init_browser_state(). A stale selector silently restores blank space.
    assert ".st-key-alam_cookie_manager" in cookie
    assert ".st-key-alam_cookie_host" not in cookie
    assert "height:1px!important" in cookie
    assert "pointer-events:none!important" in cookie

    assert "padding-bottom:6.25rem!important" in mobile
    assert "bottom:calc(.55rem + env(safe-area-inset-bottom, 0px))!important" in mobile
    assert ".alam-time-header" in mobile and "min-height:82px!important" in mobile
    assert ".wisdom-strip" in mobile
    assert ".wisdom-line,.wisdom-verse" in mobile
    assert "height:auto!important" in mobile
    assert "max-height:none!important" in mobile
    assert "overflow:visible!important" in mobile
    assert ".wisdom-verse:nth-of-type(n+2){display:none!important}" not in mobile
    assert ".intel-brief-copy,.intel-mini{display:none!important}" in mobile
    assert ".today-action-card:has(.today-empty){display:none!important}" in mobile

    entrypoint = Path(__file__).with_name("streamlit_app.py").read_text(encoding="utf-8")
    core = Path(__file__).with_name("alam_core.py").read_text(encoding="utf-8")
    assert 'stx.CookieManager(key="alam_cookie_manager")' in core
    assert "import alam_mobile_shell as mobile_shell" in entrypoint
    assert "mobile_shell.install_mobile_shell()" in entrypoint
    assert "install_cookie_guard()" in Path(__file__).with_name("alam_mobile_shell.py").read_text(
        encoding="utf-8"
    )
    assert entrypoint.index("intelligence.init_preferences()") < entrypoint.index(
        "mobile_shell.install_mobile_shell()"
    )


def main():
    test_mobile_shell_integrity()
    print("ALAM mobile shell regression test passed")


if __name__ == "__main__":
    main()
