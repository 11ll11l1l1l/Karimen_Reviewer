import alam_mobile_shell as shell


def main():
    cookie = shell.COOKIE_GUARD_CSS
    mobile = shell.MOBILE_SHELL_CSS

    assert ".st-key-alam_cookie_host" in cookie
    assert "height:1px!important" in cookie
    assert "pointer-events:none!important" in cookie

    assert "padding-bottom:6.25rem!important" in mobile
    assert "bottom:calc(.55rem + env(safe-area-inset-bottom, 0px))!important" in mobile
    assert ".alam-time-header" in mobile and "min-height:82px!important" in mobile
    assert ".wisdom-strip" in mobile
    assert ".intel-brief-copy,.intel-mini{display:none!important}" in mobile
    assert ".today-action-card:has(.today-empty){display:none!important}" in mobile

    print("ALAM mobile shell regression test passed")


if __name__ == "__main__":
    main()
