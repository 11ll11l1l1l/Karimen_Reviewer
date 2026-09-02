import re
import sys

import streamlit as st

import alam_core
import alam_mobile_shell


def numeric_score(value, default=50.0):
    """Convert loose ALAM score fields into a safe 0-100 number.

    New records occasionally carry semantic values such as HIGH/MEDIUM/LOW or
    nested score objects. Ranking should degrade gracefully instead of taking the
    entire Streamlit app down.
    """
    if value is None or value == "":
        return float(default)
    if isinstance(value, bool):
        return 100.0 if value else 0.0
    if isinstance(value, (int, float)):
        return max(0.0, min(100.0, float(value)))
    if isinstance(value, dict):
        for key in ("score", "value", "percent", "percentage", "rating"):
            if key in value:
                return numeric_score(value.get(key), default)
        return float(default)
    text = str(value).strip().upper()
    semantic = {
        "VERY HIGH": 90.0,
        "HIGH": 80.0,
        "MEDIUM-HIGH": 70.0,
        "MED-HIGH": 70.0,
        "MEDIUM": 55.0,
        "MED": 55.0,
        "LOW-MEDIUM": 40.0,
        "LOW": 30.0,
        "VERY LOW": 15.0,
    }
    if text in semantic:
        return semantic[text]
    match = re.search(r"-?\d+(?:\.\d+)?", text.replace(",", ""))
    if not match:
        return float(default)
    try:
        return max(0.0, min(100.0, float(match.group(0))))
    except (TypeError, ValueError):
        return float(default)


def safe_feed_score(record):
    record = record if isinstance(record, dict) else {}
    content = record.get("content")
    content = content if isinstance(content, dict) else {}
    sources = record.get("sources")
    source_count = len(sources) if isinstance(sources, list) else 0
    return (
        0.35 * numeric_score(record.get("importance"), 50)
        + 0.20 * alam_core.freshness_score(record.get("created_at"))
        + 0.15 * numeric_score(content.get("usefulness"), 55)
        + 0.10 * numeric_score(record.get("confidence"), 50)
        + 0.10 * numeric_score(content.get("novelty"), 55)
        + 10
        + min(8, source_count * 2)
    )


def _install_cookie_layout_guard():
    """Keep CookieManager functional without allowing its iframe to move the page.

    ``extra_streamlit_components.CookieManager`` is iframe-backed. On some mobile
    browsers its first render briefly reserves a large default iframe height, causing
    ALAM's brand to jump upward only after the component settles. Wrapping the manager
    in a keyed, visually collapsed host keeps the iframe alive for cookie I/O while
    taking it out of normal document flow.
    """
    if alam_core.stx is None:
        return
    current = getattr(alam_core.stx, "CookieManager", None)
    if current is None or getattr(current, "_alam_layout_guard", False):
        return

    original = current

    def guarded_cookie_manager(*args, **kwargs):
        alam_mobile_shell.install_cookie_guard()
        with st.container(key="alam_cookie_host"):
            return original(*args, **kwargs)

    guarded_cookie_manager._alam_layout_guard = True
    alam_core.stx.CookieManager = guarded_cookie_manager


def _install_mobile_shell_hooks():
    """Apply compact mobile chrome through modules already called by streamlit_app."""
    extras = sys.modules.get("alam_extras")
    if extras is not None:
        current = getattr(extras, "install_extras_css", None)
        if current is not None and not getattr(current, "_alam_mobile_shell", False):
            original = current

            def install_extras_and_mobile_shell():
                original()
                alam_mobile_shell.install_mobile_shell()

            install_extras_and_mobile_shell._alam_mobile_shell = True
            extras.install_extras_css = install_extras_and_mobile_shell

    readiness = sys.modules.get("alam_readiness")
    if readiness is not None:
        readiness.render_runtime_status = alam_mobile_shell.render_runtime_status


def install_runtime_safety():
    """Install score hardening plus startup-safe mobile shell guards.

    This installer intentionally patches existing call sites instead of duplicating
    business logic in ``streamlit_app.py``. The public feed/data contracts therefore
    remain unchanged while the mobile shell can be repaired independently.
    """
    alam_core.feed_score = safe_feed_score
    for name, module in list(sys.modules.items()):
        if not name.startswith("alam_") or module is None:
            continue
        if hasattr(module, "feed_score"):
            setattr(module, "feed_score", safe_feed_score)

    _install_cookie_layout_guard()
    _install_mobile_shell_hooks()
