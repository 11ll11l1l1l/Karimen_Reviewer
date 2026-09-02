"""Supabase data access for ALAM.

Supabase is the preferred durable source of truth. The public Streamlit client is
read-only for shared intelligence and may access only data allowed by RLS. Trusted
agent/admin writes belong in server-side ingestion tooling or Edge Functions.
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
    """Perform a harmless SELECT against ALAM's existing agents table."""
    try:
        client = get_supabase_public()
        client.table("agents").select("id").limit(1).execute()
        return True, "Supabase connected"
    except Exception as exc:
        return False, _safe_error(exc)


def _article_row_to_record(row):
    """Convert a typed Supabase article row into ALAM's v5 article contract."""
    if not isinstance(row, dict):
        return None
    payload = row.get("record") if isinstance(row.get("record"), dict) else {}
    record = dict(payload)

    # Queryable columns win where they represent the same v5 field. Database
    # publication state is intentionally kept separate from the agent lifecycle.
    for key in (
        "id", "story_key", "category", "title", "summary", "published_at",
        "created_at", "updated_at", "image_url", "image_type", "urgency",
    ):
        if row.get(key) is not None:
            record[key] = row.get(key)

    if row.get("importance_score") is not None:
        record["importance"] = row.get("importance_score")
    if row.get("confidence_score") is not None:
        record["confidence"] = row.get("confidence_score")
    if row.get("novelty_score") is not None:
        content = dict(record.get("content") or {})
        content.setdefault("novelty", row.get("novelty_score"))
        record["content"] = content

    lifecycle = row.get("lifecycle_status")
    if lifecycle:
        record["status"] = lifecycle
    record["_publication_status"] = row.get("status") or "published"

    if not record.get("id") or not record.get("title"):
        return None

    category = str(record.get("category") or record.get("_category") or record.get("agent") or "").strip().lower()
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
def load_article_sources(article_ids):
    """Return public source rows grouped by article id."""
    ids = [str(x) for x in article_ids if x]
    if not ids:
        return {}, None
    try:
        client = get_supabase_public()
        response = (
            client.table("article_sources")
            .select("article_id,url,publisher,title,published_at,source_type,is_primary,reliability,supports_claims")
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


@st.cache_data(ttl=45, show_spinner=False)
def load_published_articles(limit=500):
    """Read and hydrate current published ALAM articles from Supabase.

    Returns ``(records, error)``. Empty records with no error means the schema is
    healthy but not yet populated, allowing the app's migration fallback to remain.
    """
    try:
        client = get_supabase_public()
        response = (
            client.table("articles")
            .select(
                "id,story_key,category,title,summary,status,lifecycle_status,published_at,"
                "created_at,updated_at,image_url,image_type,importance_score,confidence_score,"
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

        if records:
            sources, source_error = load_article_sources([r.get("id") for r in records])
            if source_error is None:
                for record in records:
                    db_sources = sources.get(str(record.get("id")), [])
                    if db_sources:
                        # Keep the exact v5 source shape consumed by existing evidence UI.
                        record["sources"] = [
                            {
                                "publisher": s.get("publisher"),
                                "title": s.get("title"),
                                "url": s.get("url"),
                                "published_at": s.get("published_at"),
                                "source_type": s.get("source_type"),
                                "reliability": s.get("reliability"),
                                "is_primary": s.get("is_primary"),
                            }
                            for s in db_sources
                        ]
        return records, None
    except Exception as exc:
        return [], _safe_error(exc)


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
            .select("id,article_id,agent_id,persona_id,reply_to,stance,comment,record,created_at")
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


@st.cache_data(ttl=60, show_spinner=False)
def load_latest_wisdom_from_db():
    """Load the latest public daily wisdom entry from Supabase."""
    try:
        response = (
            get_supabase_public().table("wisdom_entries")
            .select("entry_date,based_on,question,verses,record,created_at")
            .order("entry_date", desc=True)
            .limit(1)
            .execute()
        )
        rows = list(response.data or [])
        if not rows:
            return None, None
        row = rows[0]
        payload = row.get("record") if isinstance(row.get("record"), dict) else {}
        item = dict(payload)
        item["date"] = str(row.get("entry_date"))
        item["based_on"] = row.get("based_on") or item.get("based_on")
        item["question"] = row.get("question") or item.get("question")
        item["verses"] = row.get("verses") or item.get("verses") or []
        return item, None
    except Exception as exc:
        return None, _safe_error(exc)


@st.cache_data(ttl=60, show_spinner=False)
def load_public_predictions(limit=200):
    """Load durable prediction accountability rows for the Predictions view."""
    try:
        response = (
            get_supabase_public().table("predictions")
            .select("id,article_id,agent_id,claim,horizon,confidence,status,resolution_notes,created_at,resolved_at")
            .order("created_at", desc=True)
            .limit(int(limit))
            .execute()
        )
        return list(response.data or []), None
    except Exception as exc:
        return [], _safe_error(exc)


@st.cache_data(ttl=60, show_spinner=False)
def load_article_relationships(article_ids, limit=500):
    """Load Connect-the-Dots relationships touching the supplied article IDs."""
    ids = [str(x) for x in article_ids if x]
    if not ids:
        return [], None
    try:
        client = get_supabase_public()
        left = (
            client.table("article_relationships")
            .select("from_article_id,to_article_id,relationship,strength,explanation,created_at")
            .in_("from_article_id", ids[:500])
            .limit(int(limit))
            .execute()
        )
        right = (
            client.table("article_relationships")
            .select("from_article_id,to_article_id,relationship,strength,explanation,created_at")
            .in_("to_article_id", ids[:500])
            .limit(int(limit))
            .execute()
        )
        unique = {}
        for row in list(left.data or []) + list(right.data or []):
            key = (row.get("from_article_id"), row.get("to_article_id"), row.get("relationship"))
            unique[key] = row
        return list(unique.values()), None
    except Exception as exc:
        return [], _safe_error(exc)


@st.cache_data(ttl=60, show_spinner=False)
def database_public_health():
    """Small read-only deployment diagnostic for Settings."""
    health = {"articles": None, "sources": None, "comments": None, "predictions": None, "wisdom": None}
    try:
        client = get_supabase_public()
        table_map = {
            "articles": "articles",
            "sources": "article_sources",
            "comments": "agent_comments",
            "predictions": "predictions",
            "wisdom": "wisdom_entries",
        }
        for label, table in table_map.items():
            response = client.table(table).select("*", count="exact").limit(1).execute()
            health[label] = getattr(response, "count", None)
        return health, None
    except Exception as exc:
        return health, _safe_error(exc)


def database_now_iso():
    """UTC timestamp helper used by trusted ingestion tooling."""
    return datetime.now(timezone.utc).isoformat()
