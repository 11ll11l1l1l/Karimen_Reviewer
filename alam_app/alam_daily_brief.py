"""Compact, explainable Today briefing selection for ALAM.ph.

The briefing is deliberately deterministic and retrieval-only: it selects from the
already validated ALAM record set and never generates article claims. Saved-story
material changes get first-class return value, while action and cross-lens diversity
keep the three slots useful without turning personalization into a filter bubble.
"""

from __future__ import annotations

import re
from html import escape

import streamlit as st

import alam_intelligence as intelligence
import alam_local_state as localstate
from alam_core import feed_score


ACTIONABLE = {"DO NOW", "APPLY", "AVOID", "PREPARE", "BUY", "WAIT"}
WATCH_CATEGORIES = {"trend", "reflection"}
IMPORTANCE_LABELS = {
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


def _story_id(record):
    return str(record.get("id") or "")


def _actionable(record):
    return str((record.get("content") or {}).get("action") or "").strip().upper() in ACTIONABLE


def _importance_score(record):
    """Normalize loose importance values so Today never crashes on valid v5 labels."""
    value = record.get("importance")
    if isinstance(value, bool):
        return 100.0 if value else 0.0
    if isinstance(value, (int, float)):
        return max(0.0, min(100.0, float(value)))
    if isinstance(value, dict):
        for key in ("score", "value", "percent", "percentage", "rating"):
            if key in value:
                return _importance_score({"importance": value.get(key)})
        return 0.0
    text = str(value or "").strip().upper()
    if text in IMPORTANCE_LABELS:
        return IMPORTANCE_LABELS[text]
    match = re.search(r"-?\d+(?:\.\d+)?", text.replace(",", ""))
    if not match:
        return 0.0
    try:
        return max(0.0, min(100.0, float(match.group(0))))
    except ValueError:
        return 0.0


def _rank(record, relevance_fn):
    return (int(relevance_fn(record)), float(feed_score(record)))


def _best(records, predicate, relevance_fn, used_ids):
    candidates = [
        record
        for record in records
        if _story_id(record) not in used_ids and predicate(record)
    ]
    return max(candidates, key=lambda record: _rank(record, relevance_fn)) if candidates else None


def _balanced_fallback(records, relevance_fn, used_ids, used_categories):
    """Fill a missing slot without blindly repeating the reader's strongest lane.

    Category novelty and public importance lead this fallback before personalized
    relevance. It therefore acts as a small anti-filter-bubble guard only when a
    normal KNOW/DO/WATCH slot is unavailable; it never displaces a saved material
    update or a verified actionable item.
    """
    candidates = [record for record in records if _story_id(record) not in used_ids]
    if not candidates:
        return None

    def score(record):
        category = str(record.get("_category") or "")
        novel = 1 if category and category not in used_categories else 0
        importance = _importance_score(record)
        return (novel, importance, int(relevance_fn(record)), float(feed_score(record)))

    return max(candidates, key=score)


def select_saved_updates(records, *, saved_update_predicate=None, relevance_fn=None, limit=3):
    """Return the strongest unique Saved stories with material updates.

    This is a return-value queue, not another recommendation surface. It reuses the
    same material-change predicate as Saved/Today, deduplicates stable story IDs, and
    ranks only among changed Saved stories. No unseen or merely old story is promoted
    into the queue just to fill space.
    """
    if not records:
        return []
    try:
        limit = max(0, int(limit))
    except (TypeError, ValueError):
        limit = 3
    if limit == 0:
        return []

    saved_update_predicate = saved_update_predicate or localstate.saved_has_update
    relevance_fn = relevance_fn or intelligence.personal_relevance
    candidates = [record for record in records if saved_update_predicate(record)]
    candidates.sort(key=lambda record: _rank(record, relevance_fn), reverse=True)

    selected = []
    used_ids = set()
    for record in candidates:
        story_id = _story_id(record)
        if not story_id or story_id in used_ids:
            continue
        selected.append(record)
        used_ids.add(story_id)
        if len(selected) >= limit:
            break
    return selected


def select_daily_brief_rows(records, *, saved_update_predicate=None, relevance_fn=None):
    """Return up to three unique ``(label, record)`` briefing rows.

    Selection order is intentionally product-driven rather than a generic top-three:
    a changed Saved story is a reason to return, an actionable Practical item is a
    reason to act, and KNOW/WATCH maintain breadth. When no Saved update exists the
    familiar KNOW -> DO -> WATCH structure is preserved.
    """
    if not records:
        return []

    saved_update_predicate = saved_update_predicate or localstate.saved_has_update
    relevance_fn = relevance_fn or intelligence.personal_relevance
    ranked = sorted(records, key=lambda record: _rank(record, relevance_fn), reverse=True)
    saved_update = _best(ranked, saved_update_predicate, relevance_fn, set())

    desired = []
    if saved_update:
        desired.append(("REVIEW", lambda record: _story_id(record) == _story_id(saved_update)))
        desired.append(("DO", lambda record: record.get("_category") == "practical" and _actionable(record)))
        desired.append(("WATCH", lambda record: record.get("_category") in WATCH_CATEGORIES))
        desired.append(("KNOW", lambda record: record.get("_category") == "discover"))
    else:
        desired.extend(
            [
                ("KNOW", lambda record: record.get("_category") == "discover"),
                ("DO", lambda record: record.get("_category") == "practical" and _actionable(record)),
                ("WATCH", lambda record: record.get("_category") in WATCH_CATEGORIES),
            ]
        )

    rows = []
    used_ids = set()
    for label, predicate in desired:
        record = _best(ranked, predicate, relevance_fn, used_ids)
        if not record:
            continue
        rows.append((label, record))
        used_ids.add(_story_id(record))
        if len(rows) == 3:
            return rows

    while len(rows) < 3:
        categories = {str(record.get("_category") or "") for _, record in rows}
        record = _balanced_fallback(ranked, relevance_fn, used_ids, categories)
        if not record:
            break
        rows.append(("KNOW", record))
        used_ids.add(_story_id(record))
    return rows


def _why_selected(label, record):
    if label == "REVIEW":
        return "Saved story changed since your last review"
    hits = intelligence.interest_hits(record)
    prefs = st.session_state.get("alam_interest_preferences") or intelligence.DEFAULT_INTERESTS
    enabled_hits = [name for name in hits if prefs.get(name)]
    if label == "DO":
        if enabled_hits:
            return f"Actionable now · matches {enabled_hits[0]}"
        return "Actionable verified item"
    if enabled_hits:
        return f"Matches {enabled_hits[0]}"
    if _importance_score(record) >= 80:
        return "High-importance signal kept for balance"
    return "Useful signal outside your immediate action queue"


def _brief_copy(label, record, all_records):
    content = record.get("content") or {}
    if label == "REVIEW":
        change = intelligence.change_snapshot(record, all_records)
        if change:
            return change[1]
    if label == "DO":
        return content.get("recommendation") or content.get("what_to_do") or content.get("action")
    return record.get("summary") or record.get("why_it_matters")


def _brief_open_label(label):
    """Keep the three-line brief scannable while giving every line a clear next step."""
    return {
        "REVIEW": "Review update",
        "DO": "Open action",
        "WATCH": "Open watch",
        "KNOW": "Open story",
    }.get(str(label or "").upper(), "Open story")


def _open_story(record):
    st.session_state["selected_story"] = _story_id(record)
    st.rerun()


def _render_saved_change_queue(records, all_records, primary_review=None, limit=3):
    """Expose additional material Saved changes that cannot fit the 3-line brief."""
    updates = select_saved_updates(records, limit=limit)
    primary_id = _story_id(primary_review or {})
    remaining = [record for record in updates if _story_id(record) != primary_id]
    if not remaining:
        return

    st.markdown("<div class='intel-title'>More Saved changes</div>", unsafe_allow_html=True)
    st.caption("Material updates since your last review. Open the changed evidence before relying on an older takeaway.")
    for record in remaining:
        change = intelligence.change_snapshot(record, all_records)
        change_copy = str(change[1] if change else "A newer material version is available.")[:180]
        st.markdown(
            "<div class='intel-brief-card'>"
            "<div class='intel-kicker'>SAVED UPDATE</div>"
            f"<div class='intel-brief-head'>{escape(str(record.get('title') or ''))}</div>"
            f"<div class='intel-brief-copy'>{escape(change_copy)}</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        title = str(record.get("title") or "Changed Saved story").strip()
        button_title = title if len(title) <= 64 else title[:63].rstrip() + "…"
        if st.button(
            f"Review update · {button_title} →",
            key=f"today_saved_update_{_story_id(record)}",
            use_container_width=True,
        ):
            _open_story(record)


def render_daily_brief(records, all_records):
    rows = select_daily_brief_rows(records)
    if not rows:
        return

    st.markdown("<div class='intel-title'>Today in 3 lines</div>", unsafe_allow_html=True)
    html = ["<div class='intel-brief-grid'>"]
    for label, record in rows:
        copy = str(_brief_copy(label, record, all_records) or "")[:190]
        reason = _why_selected(label, record)
        lifecycle = intelligence.story_lifecycle(record, all_records)
        relevance = intelligence.personal_relevance(record)
        html.append(
            "<div class='intel-brief-card'>"
            f"<div class='intel-kicker'>{escape(label)}</div>"
            f"<div class='intel-brief-head'>{escape(str(record.get('title') or ''))}</div>"
            f"<div class='intel-brief-copy'>{escape(copy)}</div>"
            f"<div class='intel-mini'>{escape(reason)} · Relevance {relevance}/100 · {escape(lifecycle)}</div>"
            "</div>"
        )
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)

    # The brief previously explained three decisions but only the Saved REVIEW row
    # could be opened from this module. Full-width controls keep all three decisions
    # reachable with one mobile tap without making the HTML cards themselves depend
    # on brittle Streamlit DOM/link behavior.
    for label, record in rows:
        title = str(record.get("title") or "Story").strip()
        button_title = title if len(title) <= 52 else title[:51].rstrip() + "…"
        if st.button(
            f"{_brief_open_label(label)} · {button_title} →",
            key=f"today_brief_open_{label.lower()}_{_story_id(record)}",
            use_container_width=True,
        ):
            _open_story(record)

    review = next((record for label, record in rows if label == "REVIEW"), None)
    _render_saved_change_queue(records, all_records, primary_review=review)
