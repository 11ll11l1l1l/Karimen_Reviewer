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

from datetime import datetime, timezone

import streamlit as st

import alam_extras as extras
from alam_core import parse_dt
from alam_supabase import load_article_history, load_published_articles


# Current-feed stories must earn their place by being current. History is retained in
# the underlying data and remains available on detail routes; these TTLs only decide
# what can keep occupying the public/current feed.
DEFAULT_FEED_TTL_HOURS = 7 * 24
SHORT_LIVED_TTL_HOURS = 36
SHORT_LIVED_TERMS = (
    "typhoon",
    "台風",
    "weather",
    "heavy rain",
    "豪雨",
    "warning",
    "alert",
    "earthquake",
    "地震",
    "flood",
    "flooding",
    "landslide",
    "storm",
    "transport disruption",
    "train disruption",
    "today:",
)


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


def _expiry_datetime(record):
    """Return an explicit per-story expiry when one is supplied by ingestion."""
    if not isinstance(record, dict):
        return None
    content = record.get("content") if isinstance(record.get("content"), dict) else {}
    raw = record.get("expires_at") or content.get("expires_at")
    if not raw:
        return None
    try:
        value = parse_dt(raw)
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _is_short_lived(record):
    """Identify fast-changing safety/weather/transport stories that age in hours."""
    if not isinstance(record, dict):
        return False
    tags = record.get("tags") if isinstance(record.get("tags"), list) else []
    text = " ".join(
        [
            str(record.get("title") or ""),
            str(record.get("type") or ""),
            str(record.get("status") or ""),
            *[str(tag) for tag in tags],
        ]
    ).lower()
    return any(term in text for term in SHORT_LIVED_TERMS)


def record_expired_for_feed(record, now=None):
    """True when a story should leave the current feed but remain in history.

    Explicit ``expires_at`` wins. Otherwise rapidly changing alerts live for 36 hours
    and ordinary stories live for seven days. An ongoing subject can stay visible by
    publishing a fresh verified version instead of pinning an old article indefinitely.
    """
    if not isinstance(record, dict):
        return False
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    else:
        current = current.astimezone(timezone.utc)

    explicit_expiry = _expiry_datetime(record)
    if explicit_expiry is not None:
        return current >= explicit_expiry.astimezone(timezone.utc)

    raw_created = record.get("created_at")
    if not raw_created:
        return False
    try:
        created = parse_dt(raw_created)
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        age_hours = max(0.0, (current - created.astimezone(timezone.utc)).total_seconds() / 3600.0)
    except Exception:
        # Do not silently delete malformed legacy content; validation can flag it.
        return False

    ttl = SHORT_LIVED_TTL_HOURS if _is_short_lived(record) else DEFAULT_FEED_TTL_HOURS
    return age_hours > ttl


def filter_current_feed_records(records, selected_story=None):
    """Remove expired feed cards while preserving a selected/deep-linked story."""
    selected_id = str(selected_story or "").strip()
    kept = []
    expired = 0
    for record in list(records or []):
        if selected_id and str((record or {}).get("id") or "") == selected_id:
            kept.append(record)
            continue
        if record_expired_for_feed(record):
            expired += 1
            continue
        kept.append(record)
    st.session_state["alam_expired_feed_count"] = expired
    return kept


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
    selected_story = st.session_state.get("selected_story")
    source_scope = selected_source_scope(selected_story)
    supabase_records, supabase_error = load_published_articles(source_article_ids=source_scope)
    if supabase_records:
        st.session_state["alam_content_source"] = "supabase"
        st.session_state.pop("alam_supabase_content_error", None)
        return filter_current_feed_records(supabase_records, selected_story)

    if supabase_error:
        st.session_state["alam_supabase_content_error"] = supabase_error
    else:
        st.session_state.pop("alam_supabase_content_error", None)

    # Reuse the mature cached fallback loader rather than introducing a second local
    # file contract. It includes local history by design; expiry only filters the
    # current feed view and never deletes the local audit/history files.
    return filter_current_feed_records(extras.load_article_records(), selected_story)


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
