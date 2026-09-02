"""Privacy-preserving anonymous identity and interaction telemetry for ALAM.

ALAM remembers a browser by a random UUID stored in a long-lived cookie. Returning
sessions read that cookie from Streamlit's native initial-request context first, which
avoids custom-component initialization races. The existing CookieManager is used only
for writes/fallback reads. ALAM never attempts hardware/browser fingerprinting and does
not store IP addresses for recognition. The public Supabase key can only call narrow
SECURITY DEFINER RPCs; visitor tables remain closed to direct public reads/writes under
RLS.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import streamlit as st

from alam_supabase import _safe_error, get_supabase_public

DEVICE_COOKIE = "alam_device_id_v1"
COOKIE_DAYS = 730
COOKIE_MAX_AGE = COOKIE_DAYS * 24 * 60 * 60
WELCOME_ART = Path(__file__).resolve().parent / "assets" / "alam_welcome.svg"

# Only structured controls are mirrored automatically. Free-text/search fields are
# intentionally excluded even though the user asked for interaction history: future
# personalization needs behavioral signals, not an accidental collection of typed text.
TRACKED_WIDGET_PREFIXES = (
    "main_nav",
    "more_nav",
    "today_mode",
    "detail_mode_",
    "interest_",
    "alert_",
    "feedback_",
)


def _new_uuid() -> str:
    return str(uuid.uuid4())


def _valid_device_id(value) -> str | None:
    """Return a canonical UUID string or None for malformed/untrusted cookie values."""
    try:
        return str(uuid.UUID(str(value).strip()))
    except (ValueError, TypeError, AttributeError):
        return None


def _device_metadata() -> dict:
    """Return coarse device context without collecting IP or fingerprint attributes."""
    metadata = {"identity_model": "random_cookie_uuid", "app": "alam_streamlit"}
    try:
        headers = st.context.headers
        user_agent = str(headers.get("User-Agent") or "").strip()
        if user_agent:
            metadata["user_agent"] = user_agent[:500]
    except Exception:
        pass
    return metadata


def _request_cookie_get() -> str | None:
    """Read the cookie synchronously from the browser's initial Streamlit request."""
    try:
        return _valid_device_id(st.context.cookies.get(DEVICE_COOKIE))
    except Exception:
        return None


def _cookie_get(manager) -> str | None:
    """Prefer native request cookies; fall back to the legacy component cache."""
    native = _request_cookie_get()
    if native:
        return native
    if manager is None:
        return None
    try:
        return _valid_device_id(manager.get(cookie=DEVICE_COOKIE))
    except Exception:
        return None


def _cookie_set(manager, device_id: str) -> bool:
    """Best-effort persistent device cookie write.

    The first render can occur before the custom CookieManager frontend has mounted,
    so callers intentionally repeat this write after successful onboarding.
    """
    canonical = _valid_device_id(device_id)
    if manager is None or not canonical:
        return False
    try:
        manager.set(
            DEVICE_COOKIE,
            canonical,
            expires_at=datetime.now() + timedelta(days=COOKIE_DAYS),
            max_age=COOKIE_MAX_AGE,
            same_site="lax",
            path="/",
            key="set_alam_device_id",
        )
        return True
    except Exception:
        return False


def _lookup(device_id: str):
    try:
        response = get_supabase_public().rpc(
            "alam_lookup_device", {"p_device_id": device_id}
        ).execute()
        rows = list(response.data or [])
        return (rows[0] if rows else None), None
    except Exception as exc:
        return None, _safe_error(exc)


def _register(device_id: str, name: str, session_id: str):
    try:
        response = get_supabase_public().rpc(
            "alam_register_device",
            {
                "p_device_id": device_id,
                "p_display_name": name,
                "p_session_id": session_id,
                "p_metadata": _device_metadata(),
            },
        ).execute()
        rows = list(response.data or [])
        return (rows[0] if rows else None), None
    except Exception as exc:
        return None, _safe_error(exc)


def init_identity(manager=None) -> dict:
    """Resolve this browser to a visitor profile if one already exists."""
    st.session_state.setdefault("alam_session_id", _new_uuid())
    if st.session_state.get("alam_identity_initialized"):
        return dict(st.session_state.get("alam_visitor") or {})

    # On a brand-new Streamlit session, st.context.cookies contains the cookies from
    # the initial HTTP/WebSocket request immediately. This is substantially more
    # reliable than waiting for the third-party CookieManager component to hydrate.
    device_id = _valid_device_id(st.session_state.get("alam_device_id")) or _cookie_get(manager)
    if not device_id:
        device_id = _new_uuid()
        # This first write is opportunistic. The authoritative persistence write is
        # repeated after onboarding submission, once the cookie component is mounted.
        _cookie_set(manager, device_id)
    st.session_state["alam_device_id"] = device_id

    visitor, error = _lookup(device_id)
    st.session_state["alam_identity_error"] = error
    st.session_state["alam_visitor"] = dict(visitor or {})
    st.session_state["alam_identity_initialized"] = True
    return dict(visitor or {})


def current_visitor() -> dict:
    return dict(st.session_state.get("alam_visitor") or {})


def display_name() -> str:
    return str(current_visitor().get("display_name") or "").strip()


def is_recognized() -> bool:
    return bool(current_visitor().get("visitor_id") and display_name())


def log_event(event_name: str, article_id: str | None = None, properties: dict | None = None) -> bool:
    """Best-effort public event logging through the constrained Supabase RPC."""
    device_id = _valid_device_id(st.session_state.get("alam_device_id"))
    if not device_id or not is_recognized():
        return False
    try:
        get_supabase_public().rpc(
            "alam_log_event",
            {
                "p_device_id": device_id,
                "p_session_id": str(st.session_state.get("alam_session_id") or "")[:120],
                "p_event_name": str(event_name or "")[:64],
                "p_article_id": str(article_id) if article_id else None,
                "p_properties": dict(properties or {}),
            },
        ).execute()
        return True
    except Exception:
        # Telemetry must never block reading. Production diagnostics can inspect RPC
        # health separately; do not surface noisy event failures to ordinary readers.
        return False


def _welcome_copy() -> None:
    st.markdown(
        """
        <div style="text-align:center;max-width:760px;margin:0 auto 10px">
          <div style="font-size:.76rem;font-weight:900;letter-spacing:.1em;color:#5968F2;text-transform:uppercase">Welcome to ALAM</div>
          <div style="font-size:clamp(2rem,6vw,4rem);font-weight:950;letter-spacing:-.05em;line-height:1.02;margin:8px 0 10px">Know what matters. Understand why. Know what to do.</div>
          <div style="font-size:1rem;line-height:1.6;color:#667085">ALAM turns verified developments into clear explanations, learning takeaways, and practical next steps. Tell us what to call you once and this browser will be recognized on future visits.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_onboarding(manager=None) -> bool:
    """Render first-visit onboarding. Return True only when the visitor is recognized."""
    init_identity(manager)
    if is_recognized():
        # Refresh the persistent cookie during a normal mounted render. This repairs
        # older ALAM sessions whose first-render cookie write was lost.
        _cookie_set(manager, str(st.session_state.get("alam_device_id") or ""))
        return True

    if WELCOME_ART.exists():
        st.image(str(WELCOME_ART), use_container_width=True)
    _welcome_copy()

    with st.form("alam_welcome_form", border=False):
        name = st.text_input(
            "What should ALAM call you?",
            placeholder="Your name",
            max_chars=80,
            key="alam_onboarding_name",
        )
        st.caption(
            "We remember this browser using a random device ID. No hardware fingerprinting and no IP address is stored for recognition."
        )
        submitted = st.form_submit_button("Enter ALAM →", use_container_width=True, type="primary")

    if submitted:
        clean = str(name or "").strip()
        if not clean:
            st.warning("Please enter a name so ALAM knows how to greet you.")
            return False
        device_id = _valid_device_id(st.session_state.get("alam_device_id")) or _new_uuid()
        st.session_state["alam_device_id"] = device_id
        profile, error = _register(
            device_id,
            clean,
            str(st.session_state.get("alam_session_id")),
        )
        if profile:
            # Important: repeat the cookie write here. By the time a human has typed a
            # name and submitted the form, the CookieManager component is mounted, so
            # this write reliably survives browser refreshes/new Streamlit sessions.
            persisted = _cookie_set(manager, device_id)
            st.session_state["alam_device_cookie_persisted"] = persisted
            st.session_state["alam_visitor"] = dict(profile)
            st.session_state["alam_identity_error"] = None
            log_event("onboarding_completed", properties={"returning_device": False})
            st.rerun()
        st.error("ALAM could not save this device profile yet. " + str(error or "Please retry."))
    elif st.session_state.get("alam_identity_error"):
        st.caption("Personalization is temporarily unavailable; ALAM will retry when this page reloads.")
    return False


def render_returning_greeting() -> None:
    name = display_name()
    if not name:
        return
    st.markdown(
        f"<div style='font-size:.82rem;color:#667085;margin:-4px 0 6px'>Welcome back, <strong>{name}</strong>.</div>",
        unsafe_allow_html=True,
    )


def log_session_open_once() -> None:
    if st.session_state.get("alam_session_open_logged") or not is_recognized():
        return
    if log_event("app_open", properties={"recognized_device": True}):
        st.session_state["alam_session_open_logged"] = True


def log_navigation(page: str, section: str = "main") -> None:
    """Deduplicate navigation events within one session."""
    value = str(page or "")
    key = f"{section}:{value}"
    if st.session_state.get("alam_last_navigation") == key:
        return
    if log_event("navigation", properties={"section": section, "page": value[:80]}):
        st.session_state["alam_last_navigation"] = key


def log_story_open(record: dict) -> None:
    article_id = str(record.get("id") or "").strip()
    if not article_id:
        return
    log_event(
        "article_open",
        article_id=article_id,
        properties={
            "category": str(record.get("_category") or record.get("category") or "")[:40],
            "type": str(record.get("type") or "")[:50],
        },
    )


def track_widget_changes() -> None:
    """Log safe structured UI-control changes for future personalization models."""
    if not is_recognized():
        return
    previous = dict(st.session_state.get("alam_widget_snapshot") or {})
    current = {}
    for key, value in list(st.session_state.items()):
        text_key = str(key)
        if not text_key.startswith(TRACKED_WIDGET_PREFIXES):
            continue
        if isinstance(value, (str, int, float, bool)):
            current[text_key] = value
            if text_key in previous and previous[text_key] != value:
                # Button False resets are not useful behavior; the True click is.
                if not (isinstance(value, bool) and value is False):
                    log_event(
                        "ui_control_changed",
                        properties={"control": text_key[:100], "value": str(value)[:120]},
                    )
    st.session_state["alam_widget_snapshot"] = current
