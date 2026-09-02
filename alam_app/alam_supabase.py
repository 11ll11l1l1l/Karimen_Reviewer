"""Supabase data access for ALAM.

The app deliberately treats Supabase as the preferred source of truth while keeping
local JSON as a temporary migration fallback. Public clients are read-only by policy;
agent/admin writes must use trusted server-side credentials outside the Streamlit UI.
"""

import re
from datetime import datetime, timezone

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


def _article_row_to_record(row):
    """Convert a Supabase article row into ALAM's existing article data contract."""
    if not isinstance(row, dict):
        return None
    payload = row.get("record") if isinstance(row.get("record"), dict) else {}
    record = dict(payload)

    # Typed database columns win over duplicated JSON values. This lets ALAM evolve
    # queryable fields without breaking old agent payloads stored in `record`.
    for key in (
        "id", "story_key", "category", "title", "summary", "status",
        "published_at", "created_at", "updated_at", "image_url", "image_type",
        "importance_score", "confidence_score", "novelty_score", "urgency",
    ):
        if row.get(key) is not None:
            record[key] = row.get(key)

    if not record.get("id") or not record.get("title"):
        return None

    category = str(record.get("category") or record.get("_category") or "").strip().lower()
    category_aliases = {
        "adaptive_discovery": "discover",
        "discovery": "discover",
        "practical_living": "practical",
        "practical_living_safety": "practical",
        "daily_reflection": "reflection",
        "market": "reflection",
        "interest_culture": "trend",
        "culture": "trend",
    }
    category = category_aliases.get(category, category)
    record["_category"] = category
    record["_path"] = f"supabase://articles/{record['id']}"
    record["_record_key"] = f"supabase::{record['id']}"
    record["_storage"] = "supabase"
    return record


@st.cache_data(ttl=45, show_spinner=False)
def load_published_articles(limit=500):
    """Read current published ALAM articles from Supabase.

    Returns ``(records, error)``. An empty list with ``error is None`` means the
    table is healthy but currently has no published content. Callers may choose a
    temporary local fallback while migration is in progress.
    """
    try:
        client = get_supabase_public()
        response = (
            client.table("articles")
            .select(
                "id,story_key,category,title,summary,status,published_at,created_at,"
                "updated_at,image_url,image_type,importance_score,confidence_score,"
                "novelty_score,urgency,record"
            )
            .eq("status", "published")
            .order("published_at", desc=True)
            .limit(int(limit))
            .execute()
        )
        records = []
        for row in response.data or []:
            record = _article_row_to_record(row)
            if record:
                records.append(record)
        return records, None
    except Exception as exc:
        return [], _safe_error(exc)


@st.cache_data(ttl=45, show_spinner=False)
def load_article_sources(article_ids):
    """Return public source rows grouped by article id."""
    ids = [str(x) for x in article_ids if x]
    if not ids:
        return {}, None
    try:
        client = get_supabase_public()
        response = (
            client.table("article_sources")
            .select("article_id,url,publisher,published_at,source_type,is_primary,reliability")
            .in_("article_id", ids[:500])
            .order("is_primary", desc=True)
            .execute()
        )
        grouped = {}
        for row in response.data or []:
            grouped.setdefault(str(row.get("article_id")), []).append(row)
        return grouped, None
    except Exception as exc:
        return {}, _safe_error(exc)


@st.cache_data(ttl=30, show_spinner=False)
def load_agent_comments(article_ids):
    """Return published cross-agent perspectives grouped by article id."""
    ids = [str(x) for x in article_ids if x]
    if not ids:
        return {}, None
    try:
        client = get_supabase_public()
        response = (
            client.table("agent_comments")
            .select("id,article_id,agent_id,stance,comment,created_at")
            .in_("article_id", ids[:500])
            .eq("status", "published")
            .order("created_at", desc=False)
            .execute()
        )
        grouped = {}
        for row in response.data or []:
            grouped.setdefault(str(row.get("article_id")), []).append(row)
        return grouped, None
    except Exception as exc:
        return {}, _safe_error(exc)


def database_now_iso():
    """UTC timestamp helper used by trusted ingestion tooling."""
    return datetime.now(timezone.utc).isoformat()
