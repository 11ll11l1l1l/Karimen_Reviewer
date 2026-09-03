"""Privacy-preserving anonymous identity and interaction telemetry for ALAM.

ALAM remembers a browser by a random UUID. The durable browser copy lives in
localStorage because component-written cookies are not reliably visible in every
Streamlit/browser deployment. A long-lived cookie remains a compatibility backup.
The UUID is random; ALAM does not fingerprint hardware and does not store IP addresses
for recognition. Shared visitor tables stay closed by RLS and are reached only through
narrow Supabase RPCs.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import streamlit as st

try:
    from streamlit_js_eval import streamlit_js_eval
except Exception:
    streamlit_js_eval = None

from alam_supabase import _safe_error, get_supabase_public

DEVICE_COOKIE = "alam_device_id_v1"
DEVICE_STORAGE_KEY = "alam_device_id_v2"
COOKIE_DAYS = 730
COOKIE_MAX_AGE = COOKIE_DAYS * 24 * 60 * 60
WELCOME_ART = Path(__file__).resolve().parent / "assets" / "alam_welcome.svg"

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
    try:
        return str(uuid.UUID(str(value).strip()))
    except (ValueError, TypeError, AttributeError):
        return None


def _device_metadata() -> dict:
    metadata = {"identity_model": "random_browser_uuid_v2", "app": "alam_streamlit"}
    try:
        headers = st.context.headers
        user_agent = str(headers.get("User-Agent") or "").strip()
        if user_agent:
            metadata["user_agent"] = user_agent[:500]
    except Exception:
        pass
    return metadata


def _request_cookie_get() -> str | None:
    try:
        return _valid_device_id(st.context.cookies.get(DEVICE_COOKIE))
    except Exception:
        return None


def _cookie_get(manager=None) -> str | None:
    # Never wait on CookieManager reads. Native request cookies are synchronous.
    return _request_cookie_get()


def _cookie_set(manager, device_id: str, *, key: str) -> bool:
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
            key=key,
        )
        return True
    except Exception:
        return False


def _storage_expression(write_value: str | None = None) -> str:
    """Return JS that always reports a ready sentinel once the component hydrates."""
    key = json.dumps(DEVICE_STORAGE_KEY)
    value = json.dumps(_valid_device_id(write_value)) if write_value else "null"
    return (
        "(() => { try {"
        f"const k={key}; const requested={value};"
        "if (requested) window.localStorage.setItem(k, requested);"
        "const stored=window.localStorage.getItem(k);"
        "return JSON.stringify({ready:true,value:stored,error:null});"
        "} catch (e) {"
        "return JSON.stringify({ready:true,value:null,error:'storage_unavailable'});"
        "} })()"
    )


def _parse_storage_result(raw) -> tuple[bool, str | None, str | None]:
    """Return (ready, device_id, error) from the browser component payload."""
    if raw is None:
        return False, None, None
    try:
        payload = json.loads(str(raw))
    except Exception:
        return True, None, "invalid_storage_response"
    if not isinstance(payload, dict):
        return True, None, "invalid_storage_response"
    return bool(payload.get("ready", True)), _valid_device_id(payload.get("value")), payload.get("error")


def _browser_storage_bridge() -> tuple[bool, str | None, str | None]:
    """Read/write the durable device UUID without making component reads authoritative.

    The call is made unconditionally near the top of onboarding. This avoids the known
    Streamlit custom-component failure mode where a component created only inside a
    button branch can disappear before its browser-side work completes.
    """
    if streamlit_js_eval is None:
        return True, None, "storage_component_unavailable"

    pending = _valid_device_id(st.session_state.get("alam_pending_device_storage"))
    try:
        raw = streamlit_js_eval(
            js_expressions=_storage_expression(pending),
            want_output=True,
            key="alam_device_storage_write_v2" if pending else "alam_device_storage_read_v2",
        )
    except Exception:
        return True, None, "storage_component_error"

    ready, stored, error = _parse_storage_result(raw)
    if ready and pending and stored == pending:
        st.session_state.pop("alam_pending_device_storage", None)
        st.session_state["alam_device_storage_persisted"] = True
    if ready:
        st.session_state["alam_device_storage_error"] = error
    return ready, stored, error


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


def init_identity(manager=None, *, storage_device_id: str | None = None) -> dict:
    """Resolve a browser identity using session -> localStorage -> native cookie."""
    st.session_state.setdefault("alam_session_id", _new_uuid())
    if st.session_state.get("alam_identity_initialized"):
        return dict(st.session_state.get("alam_visitor") or {})

    device_id = (
        _valid_device_id(st.session_state.get("alam_device_id"))
        or _valid_device_id(storage_device_id)
        or _cookie_get(manager)
    )
    if not device_id:
        # This UUID is session-only until onboarding succeeds. Registration then queues
        # durable localStorage + cookie writes before the next session can depend on it.
        device_id = _new_uuid()
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
    """Restore or register the anonymous browser identity."""
    storage_ready, storage_device_id, _ = _browser_storage_bridge()

    # On a fresh Streamlit session, do not mint a new UUID until localStorage has had
    # one hydration opportunity. Otherwise an existing browser identity can be replaced
    # simply because a custom component returned its initial None value.
    has_immediate_identity = bool(
        _valid_device_id(st.session_state.get("alam_device_id")) or _cookie_get(manager)
    )
    if not storage_ready and not has_immediate_identity:
        st.caption("Restoring this browser…")
        return False

    init_identity(manager, storage_device_id=storage_device_id)
    if is_recognized():
        # If an older browser was recognized only from the cookie, backfill the more
        # reliable localStorage copy once without rewriting it every render.
        device_id = _valid_device_id(st.session_state.get("alam_device_id"))
        if device_id and storage_ready and storage_device_id != device_id:
            st.session_state["alam_pending_device_storage"] = device_id
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
            "This is browser recognition, not an email/password account. ALAM stores a random browser ID locally; no hardware fingerprinting or IP address is used for recognition."
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
            # Queue durable localStorage persistence for the next unconditional bridge
            # render. CookieManager remains a compatibility backup only.
            st.session_state["alam_pending_device_storage"] = device_id
            st.session_state["alam_device_cookie_persisted"] = _cookie_set(
                manager,
                device_id,
                key="confirm_alam_device_id",
            )
            st.session_state["alam_visitor"] = dict(profile)
            st.session_state["alam_identity_error"] = None
            log_event("onboarding_completed", properties={"returning_device": False})
            st.rerun()
        st.error("ALAM could not save this browser profile yet. " + str(error or "Please retry."))
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
                if not (isinstance(value, bool) and value is False):
                    log_event(
                        "ui_control_changed",
                        properties={"control": text_key[:100], "value": str(value)[:120]},
                    )
    st.session_state["alam_widget_snapshot"] = current
