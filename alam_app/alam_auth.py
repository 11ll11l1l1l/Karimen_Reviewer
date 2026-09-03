"""Optional per-browser Supabase Auth account flow for ALAM.

Anonymous ALAM use remains the default. Authenticated clients are created per Streamlit
session and are never cached globally: Supabase Auth mutates client session headers, so
a process-wide client could leak one reader's session into another reader's request.

Email OTP is used because it avoids passwords and keeps the token exchange in one
Streamlit session. The hosted Supabase project's Magic Link email template must use
``{{ .Token }}`` for this UI to receive a six-digit code.

A verified Supabase access/refresh token pair is persisted only in the browser's own
localStorage and restored with ``auth.set_session``. The storage bridge is rendered only
inside Settings, never above ALAM's compact mobile shell. Tokens are never logged,
placed in URLs, copied into the anonymous profile, or shared through a cached client.
"""

from __future__ import annotations

import json
import re

import streamlit as st

try:
    from streamlit_js_eval import streamlit_js_eval
except Exception:
    streamlit_js_eval = None

try:
    from supabase import create_client
except ModuleNotFoundError:
    create_client = None

from alam_identity import _valid_device_id
from alam_supabase import _safe_error

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
AUTH_STORAGE_KEY = "alam_auth_session_v1"


def _credentials() -> tuple[str, str]:
    try:
        url = str(st.secrets["SUPABASE_URL"]).strip()
        key = str(st.secrets["SUPABASE_PUBLISHABLE_KEY"]).strip()
    except KeyError as exc:
        raise RuntimeError(f"Missing Streamlit secret: {exc.args[0]}") from exc
    if not url or not key:
        raise RuntimeError("Supabase Streamlit secrets are empty.")
    return url, key


def get_auth_client():
    """Return a Supabase client private to this Streamlit browser/session.

    Do not replace this with ``@st.cache_resource`` or ``get_supabase_public()``.
    Supabase Auth stores access/refresh tokens on the client object after verification,
    so sharing the object process-wide is a cross-user session-isolation bug.
    """
    if create_client is None:
        raise RuntimeError("Supabase Python package is not installed in this deployment yet.")
    client = st.session_state.get("alam_auth_client")
    if client is None:
        url, key = _credentials()
        client = create_client(url, key)
        st.session_state["alam_auth_client"] = client
    return client


def account_summary() -> dict:
    return dict(st.session_state.get("alam_account") or {})


def is_signed_in() -> bool:
    return bool(account_summary().get("user_id"))


def _set_account_from_user(user) -> dict:
    if not user:
        st.session_state.pop("alam_account", None)
        return {}
    payload = {
        "user_id": str(getattr(user, "id", "") or ""),
        "email": str(getattr(user, "email", "") or ""),
    }
    if not payload["user_id"]:
        st.session_state.pop("alam_account", None)
        return {}
    st.session_state["alam_account"] = payload
    return payload


def _session_tokens(session) -> dict | None:
    """Extract only the token pair required by Supabase session restoration."""
    if not session:
        return None
    access = str(getattr(session, "access_token", "") or "").strip()
    refresh = str(getattr(session, "refresh_token", "") or "").strip()
    if not access or not refresh:
        return None
    return {"access_token": access, "refresh_token": refresh}


def _parse_persisted_session(raw) -> dict | None:
    """Validate browser storage without ever returning arbitrary stored fields."""
    if not raw:
        return None
    try:
        payload = json.loads(str(raw)) if not isinstance(raw, dict) else raw
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    access = str(payload.get("access_token") or "").strip()
    refresh = str(payload.get("refresh_token") or "").strip()
    if access.count(".") < 2 or len(access) < 40 or len(refresh) < 20:
        return None
    return {"access_token": access, "refresh_token": refresh}


def _auth_storage_expression(*, write_tokens: dict | None = None, clear: bool = False) -> str:
    """Read/write account tokens on the top-level ALAM origin when available."""
    key = json.dumps(AUTH_STORAGE_KEY)
    requested = json.dumps(write_tokens, separators=(",", ":")) if write_tokens else "null"
    clear_js = "true" if clear else "false"
    return (
        "(() => { try {"
        f"const k={key}; const requested={requested}; const clear={clear_js};"
        "let store=null; let scope='parent';"
        "try { store=window.parent.localStorage; store.getItem(k); } catch (_) {"
        "store=window.localStorage; scope='component';"
        "}"
        "if (clear) store.removeItem(k); else if (requested) store.setItem(k, JSON.stringify(requested));"
        "const stored=store.getItem(k);"
        "return JSON.stringify({ready:true,value:stored,error:null,scope:scope});"
        "} catch (e) {"
        "return JSON.stringify({ready:true,value:null,error:'storage_unavailable',scope:null});"
        "} })()"
    )


def _auth_storage_bridge() -> tuple[bool, dict | None, str | None]:
    """Hydrate or persist account tokens only when Settings renders the account panel."""
    if streamlit_js_eval is None:
        return True, None, "storage_component_unavailable"

    pending = _parse_persisted_session(st.session_state.get("alam_pending_auth_storage"))
    clear = bool(st.session_state.get("alam_clear_auth_storage"))
    try:
        raw = streamlit_js_eval(
            js_expressions=_auth_storage_expression(write_tokens=pending, clear=clear),
            want_output=True,
            key="alam_auth_storage_clear_v1" if clear else (
                "alam_auth_storage_write_v1" if pending else "alam_auth_storage_read_v1"
            ),
        )
    except Exception:
        return True, None, "storage_component_error"

    if raw is None:
        return False, None, None
    try:
        envelope = json.loads(str(raw))
    except Exception:
        return True, None, "invalid_storage_response"
    if not isinstance(envelope, dict):
        return True, None, "invalid_storage_response"

    if clear and envelope.get("ready"):
        st.session_state.pop("alam_clear_auth_storage", None)
        st.session_state.pop("alam_pending_auth_storage", None)
        return True, None, envelope.get("error")

    stored = _parse_persisted_session(envelope.get("value"))
    if pending and stored == pending:
        st.session_state.pop("alam_pending_auth_storage", None)
    return bool(envelope.get("ready", True)), stored, envelope.get("error")


def _queue_session_persistence(session) -> None:
    tokens = _session_tokens(session)
    if tokens:
        st.session_state["alam_pending_auth_storage"] = tokens
        st.session_state.pop("alam_clear_auth_storage", None)


def _restore_browser_session(stored_tokens: dict | None) -> dict:
    """Restore and verify a browser session, rotating persisted tokens when refreshed."""
    tokens = _parse_persisted_session(stored_tokens)
    if not tokens or st.session_state.get("alam_auth_client") is not None:
        return {}
    try:
        response = get_auth_client().auth.set_session(
            tokens["access_token"], tokens["refresh_token"]
        )
        _queue_session_persistence(getattr(response, "session", None))
        user = getattr(response, "user", None)
        if user is None:
            user_response = get_auth_client().auth.get_user()
            user = getattr(user_response, "user", None)
        return _set_account_from_user(user)
    except Exception:
        st.session_state.pop("alam_account", None)
        st.session_state.pop("alam_auth_client", None)
        st.session_state["alam_clear_auth_storage"] = True
        st.session_state.pop("alam_pending_auth_storage", None)
        return {}


def refresh_account() -> dict:
    """Verify the server-side Auth session; expired/revoked sessions fail closed."""
    if st.session_state.get("alam_auth_client") is None:
        st.session_state.pop("alam_account", None)
        return {}
    try:
        response = get_auth_client().auth.get_user()
        account = _set_account_from_user(getattr(response, "user", None))
        if account:
            current = get_auth_client().auth.get_session()
            _queue_session_persistence(current)
        return account
    except Exception:
        st.session_state.pop("alam_account", None)
        st.session_state.pop("alam_auth_client", None)
        st.session_state["alam_clear_auth_storage"] = True
        st.session_state.pop("alam_pending_auth_storage", None)
        return {}


def send_email_code(email: str) -> tuple[bool, str | None]:
    clean = str(email or "").strip().lower()
    if not EMAIL_RE.match(clean):
        return False, "Enter a valid email address."
    try:
        get_auth_client().auth.sign_in_with_otp(
            {"email": clean, "options": {"should_create_user": True}}
        )
        st.session_state["alam_auth_pending_email"] = clean
        return True, None
    except Exception as exc:
        return False, _safe_error(exc)


def _link_current_device() -> tuple[dict | None, str | None]:
    device_id = _valid_device_id(st.session_state.get("alam_device_id"))
    if not device_id:
        return None, "This browser identity is not ready yet."
    try:
        response = get_auth_client().rpc(
            "alam_link_current_account", {"p_device_id": device_id}
        ).execute()
        rows = list(response.data or [])
        return (rows[0] if rows else None), None
    except Exception as exc:
        return None, _safe_error(exc)


def verify_email_code(code: str) -> tuple[dict | None, str | None]:
    email = str(st.session_state.get("alam_auth_pending_email") or "").strip().lower()
    token = "".join(ch for ch in str(code or "") if ch.isdigit())
    if not email:
        return None, "Request a fresh email code first."
    if len(token) != 6:
        return None, "Enter the six-digit code from the ALAM sign-in email."
    try:
        response = get_auth_client().auth.verify_otp(
            {"email": email, "token": token, "type": "email"}
        )
        user = getattr(response, "user", None)
        account = _set_account_from_user(user)
        if not account:
            return None, "Supabase did not return an authenticated user session."
        _queue_session_persistence(getattr(response, "session", None))
        link, link_error = _link_current_device()
        if link_error:
            st.session_state["alam_account_link_error"] = link_error
        else:
            st.session_state.pop("alam_account_link_error", None)
            st.session_state["alam_account_link"] = dict(link or {})
        st.session_state.pop("alam_auth_pending_email", None)
        return account, None
    except Exception as exc:
        return None, _safe_error(exc)


def sign_out() -> None:
    client = st.session_state.get("alam_auth_client")
    if client is not None:
        try:
            client.auth.sign_out()
        except Exception:
            pass
    st.session_state["alam_clear_auth_storage"] = True
    for key in (
        "alam_auth_client",
        "alam_account",
        "alam_account_link",
        "alam_account_link_error",
        "alam_auth_pending_email",
        "alam_pending_auth_storage",
    ):
        st.session_state.pop(key, None)


def render_account_settings() -> None:
    """Render optional account controls without turning ALAM into a login wall."""
    st.markdown("### ALAM account")
    st.caption(
        "Optional. Your browser-only ALAM profile keeps working without an account. "
        "An account is for future cross-device Saved, preferences and reading state."
    )

    ready, stored_tokens, storage_error = _auth_storage_bridge()
    if ready and stored_tokens and st.session_state.get("alam_auth_client") is None:
        _restore_browser_session(stored_tokens)

    account = refresh_account()
    if account:
        email = account.get("email") or "Signed-in user"
        st.success(f"Signed in as {email}")
        if st.session_state.get("alam_account_link_error"):
            st.warning(
                "Your email session is active, but this browser's anonymous history has not been linked yet. "
                "ALAM will not overwrite either identity automatically."
            )
        else:
            st.caption("This browser identity is linked to your account without deleting anonymous history.")
        if storage_error:
            st.caption("This account is active for this visit, but this browser could not persist the session.")
        if st.button("Sign out", key="alam_account_sign_out", use_container_width=True):
            sign_out()
            st.rerun()
        return

    st.info(
        "Email-code sign-in is prepared in the app, but production activation depends on the Supabase Email template using a six-digit OTP token. Anonymous ALAM remains fully available meanwhile."
    )
    email = st.text_input(
        "Email",
        value=str(st.session_state.get("alam_auth_pending_email") or ""),
        placeholder="you@example.com",
        key="alam_account_email",
    )
    if st.button("Send sign-in code", key="alam_account_send_code", use_container_width=True):
        ok, error = send_email_code(email)
        if ok:
            st.success("Sign-in email requested. Enter the six-digit code below.")
        else:
            st.error(error or "Could not request a sign-in code.")

    if st.session_state.get("alam_auth_pending_email"):
        code = st.text_input(
            "Six-digit code", max_chars=6, placeholder="123456", key="alam_account_code"
        )
        if st.button(
            "Verify & link this browser",
            key="alam_account_verify_code",
            type="primary",
            use_container_width=True,
        ):
            account, error = verify_email_code(code)
            if account:
                st.rerun()
            else:
                st.error(error or "Could not verify that code.")
