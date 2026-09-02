"""Small, read-only Supabase connection helpers for ALAM."""

import re

import streamlit as st

try:
    from supabase import create_client
except ModuleNotFoundError:
    create_client = None


@st.cache_resource
def get_supabase_public():
    """Return ALAM's public Supabase client using Streamlit Secrets."""
    if create_client is None:
        raise RuntimeError("Supabase Python package is not installed in this deployment yet.")

    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_PUBLISHABLE_KEY"]
    except KeyError as exc:
        raise RuntimeError(f"Missing Streamlit secret: {exc.args[0]}") from exc

    if not str(url).strip() or not str(key).strip():
        raise RuntimeError("Supabase Streamlit secrets are empty.")

    return create_client(str(url).strip(), str(key).strip())


def _safe_error(exc):
    """Return a useful error message without ever displaying an API key."""
    text = str(exc) or exc.__class__.__name__
    text = re.sub(r"sb_(?:publishable|secret)_[A-Za-z0-9._-]+", "[hidden-key]", text)
    text = re.sub(r"eyJ[A-Za-z0-9._-]+", "[hidden-token]", text)
    return text[:240]


@st.cache_data(ttl=60, show_spinner=False)
def check_supabase_connection():
    """Perform a harmless SELECT against ALAM's agents table."""
    try:
        client = get_supabase_public()
        client.table("agents").select("id").limit(1).execute()
        return True, "Supabase connected"
    except Exception as exc:
        return False, _safe_error(exc)
