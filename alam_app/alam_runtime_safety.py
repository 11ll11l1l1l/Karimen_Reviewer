import re
import sys

import streamlit as st

import alam_core
import alam_hybrid_feed
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


def _overlay_verified_audit(records, extras):
    """Add only GitHub versions missing from an otherwise live Supabase result."""
    if st.session_state.get("alam_content_source") != "supabase":
        return records
    local_loader = getattr(extras, "_load_local_article_records", None)
    if local_loader is None:
        return records
    audit_records = local_loader()
    merged, overlay_count = alam_hybrid_feed.merge_missing_audit_versions(records, audit_records)
    if overlay_count:
        st.session_state["alam_content_source"] = "hybrid_fallback"
        st.session_state["alam_audit_overlay_versions"] = int(overlay_count)
        return merged
    st.session_state.pop("alam_audit_overlay_versions", None)
    return records


def _install_hybrid_feed_hooks():
    """Keep verified hourly agent output visible while the trusted mirror lags.

    Both the fast current-feed loader and the mature full-history loader are wrapped.
    This matters because ``streamlit_app.py`` uses the former to resolve selections and
    the latter for normal list routes. The overlay activates only when Supabase itself
    returned content and GitHub contains a material version absent from that result.
    """
    extras = sys.modules.get("alam_extras")
    if extras is None:
        return

    full_loader = getattr(extras, "load_article_records", None)
    if full_loader is not None and not getattr(full_loader, "_alam_hybrid_overlay", False):
        original_full = full_loader

        def load_article_records_with_overlay(*args, **kwargs):
            records = original_full(*args, **kwargs)
            return _overlay_verified_audit(records, extras)

        load_article_records_with_overlay._alam_hybrid_overlay = True
        extras.load_article_records = load_article_records_with_overlay

    article_scope = sys.modules.get("alam_article_scope")
    current_loader = getattr(article_scope, "load_current_article_records", None) if article_scope else None
    if current_loader is not None and not getattr(current_loader, "_alam_hybrid_overlay", False):
        original_current = current_loader

        def load_current_article_records_with_overlay(*args, **kwargs):
            records = original_current(*args, **kwargs)
            return _overlay_verified_audit(records, extras)

        load_current_article_records_with_overlay._alam_hybrid_overlay = True
        article_scope.load_current_article_records = load_current_article_records_with_overlay


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
    """Install score hardening, sync continuity and startup-safe mobile shell guards.

    This installer intentionally patches existing call sites instead of duplicating
    business logic in ``streamlit_app.py``. The public data contracts therefore remain
    unchanged while cross-cutting reliability fixes can be applied independently.
    """
    alam_core.feed_score = safe_feed_score
    for name, module in list(sys.modules.items()):
        if not name.startswith("alam_") or module is None:
            continue
        if hasattr(module, "feed_score"):
            setattr(module, "feed_score", safe_feed_score)

    _install_cookie_layout_guard()
    _install_hybrid_feed_hooks()
    _install_mobile_shell_hooks()
