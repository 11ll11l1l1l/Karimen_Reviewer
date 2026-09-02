"""Route-aware article loading for latency-sensitive ALAM detail pages.

The public feed needs current articles immediately, while a selected story needs only
that story's version history and normalized evidence rows. Keeping these boundaries
outside rendering prevents a single mobile tap from hydrating every historical version
or every ``article_sources`` row before the reader can see the selected article.

Local/GitHub fallback intentionally keeps its existing full-record behavior. The
fallback is a migration/recovery path backed by local files, so narrowing its scan
would add complexity without reducing a network query.
"""

from __future__ import annotations

import streamlit as st

import alam_extras as extras
from alam_core import parse_dt
from alam_supabase import load_article_history, load_published_articles


def selected_history_ids(article_id):
    """Return the one stable story ID a detail route is allowed to hydrate.

    Keeping this tiny policy pure makes the performance boundary testable without a
    live database. Empty/invalid selections return no IDs rather than accidentally
    widening into the full feed.
    """
    story_id = str(article_id or "").strip()
    return [story_id] if story_id else []


def selected_source_scope(article_id):
    """Return the normalized-evidence scope for the current route.

    ``None`` means no active detail selection and deliberately preserves full-feed
    source hydration. A stable selected ID becomes a one-item tuple so Streamlit's
    cached Supabase loader has a deterministic, hashable route key. A stale ID is
    still scoped during the cheap selection probe; if it proves invalid, the caller
    falls back to the established fully hydrated feed path.
    """
    story_id = str(article_id or "").strip()
    return (story_id,) if story_id else None


def _dedupe_current_from_history(current_records, history_records):
    """Combine current rows with history without duplicating the current version.

    Ingestion also stores the current article in ``article_versions``. Matching on
    stable story ID plus normalized creation time preserves older versions while
    preventing the same current version from appearing twice in timelines.
    """
    current_keys = {
        (str(record.get("id")), parse_dt(record.get("created_at")).isoformat())
        for record in current_records
    }
    older = [
        record
        for record in history_records
        if (str(record.get("id")), parse_dt(record.get("created_at")).isoformat()) not in current_keys
    ]
    return sorted(older + list(current_records), key=lambda r: parse_dt(r.get("created_at")), reverse=True)


def load_current_article_records():
    """Load current Supabase articles with route-appropriate source hydration.

    On ordinary feed/list routes, normalized sources are hydrated for every current
    story exactly as before. When ``selected_story`` is already present on a rerun,
    only that stable ID requests normalized ``article_sources`` rows; the current
    article JSON payload is still loaded for all stories so selection validation and
    related-story lookup remain intact.

    ``load_published_articles`` is cached by the data layer, while this wrapper stays
    uncached because its session-state side effects must run on every Streamlit rerun.
    """
    source_scope = selected_source_scope(st.session_state.get("selected_story"))
    supabase_records, supabase_error = load_published_articles(source_article_ids=source_scope)
    if supabase_records:
        st.session_state["alam_content_source"] = "supabase"
        st.session_state.pop("alam_supabase_content_error", None)
        return supabase_records

    if supabase_error:
        st.session_state["alam_supabase_content_error"] = supabase_error
    else:
        st.session_state.pop("alam_supabase_content_error", None)

    # Reuse the mature cached fallback loader rather than introducing a second local
    # file contract. It includes local history by design; latest_by_story still picks
    # the current rows for feed selection.
    return extras.load_article_records()


def load_selected_article_records(article_id):
    """Return all current rows plus history for one valid selected story only.

    If Supabase is unavailable, preserve the existing local migration fallback in
    full. If selected-history hydration fails, keep the current article readable and
    surface the history error through existing Settings diagnostics rather than
    hiding the failure behind an empty timeline.
    """
    current_records = load_current_article_records()
    if st.session_state.get("alam_content_source") != "supabase":
        return current_records

    history_ids = selected_history_ids(article_id)
    if not history_ids:
        return current_records

    history, history_error = load_article_history(history_ids)
    if history_error:
        st.session_state["alam_supabase_history_error"] = history_error
        history = []
    else:
        st.session_state.pop("alam_supabase_history_error", None)

    return _dedupe_current_from_history(current_records, history)