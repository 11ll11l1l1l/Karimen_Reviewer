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
    "VERY HIGH": 90.0, "HIGH": 80.0, "MEDIUM-HIGH": 70.0, "MED-HIGH": 70.0,
    "MEDIUM": 55.0, "MED": 55.0, "LOW-MEDIUM": 40.0, "LOW": 30.0, "VERY LOW": 15.0,
}


def _story_id(record):
    return str(record.get("id") or "")


def _actionable(record):
    return str((record.get("content") or {}).get("action") or "").strip().upper() in ACTIONABLE


def _action_label(record):
    """Expose the validated decision verb instead of flattening every action to DO."""
    action = str((record.get("content") or {}).get("action") or "").strip().upper()
    return action if action in ACTIONABLE else "DO"


def _display_label(label, record):
    return _action_label(record) if str(label or "").upper() == "DO" else str(label or "").upper()


def _deadline_note(record):
    """Return only an explicitly published Practical deadline; never derive one."""
    content = record.get("content") or {}
    value = content.get("deadline")
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return ""
    text = " ".join(str(value).split()).strip()
    if not text or text.lower() in {"none", "n/a", "na", "not applicable", "unknown", "tbd"}:
        return ""
    return text[:96]


def _affected_note(record):
    """Expose only the article's explicit affected-audience statement.

    Practical stories are required to answer who is affected, but Today must never
    infer eligibility from a reader profile or from article prose. Structured or
    placeholder values therefore fail closed and the published text is display-capped.
    """
    content = record.get("content") or {}
    value = content.get("who_is_affected")
    if not isinstance(value, str):
        return ""
    text = " ".join(value.split()).strip()
    if not text or text.lower() in {"none", "n/a", "na", "not applicable", "unknown", "tbd"}:
        return ""
    return text[:150]


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
    candidates = [record for record in records if _story_id(record) not in used_ids and predicate(record)]
    return max(candidates, key=lambda record: _rank(record, relevance_fn)) if candidates else None


def _balanced_fallback(records, relevance_fn, used_ids, used_categories):
    candidates = [record for record in records if _story_id(record) not in used_ids]
    if not candidates:
        return None
    def score(record):
        category = str(record.get("_category") or "")
        return (1 if category and category not in used_categories else 0, _importance_score(record), int(relevance_fn(record)), float(feed_score(record)))
    return max(candidates, key=score)


def select_saved_updates(records, *, saved_update_predicate=None, relevance_fn=None, limit=3):
    """Return the strongest unique Saved stories with material updates."""
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
    selected, used_ids = [], set()
    for record in candidates:
        story_id = _story_id(record)
        if not story_id or story_id in used_ids:
            continue
        selected.append(record); used_ids.add(story_id)
        if len(selected) >= limit:
            break
    return selected


def select_deadline_actions(records, *, exclude_ids=None, relevance_fn=None, limit=2):
    """Return a bounded queue of validated actions that explicitly publish deadlines.

    This intentionally does not parse, compare, or manufacture urgency from deadline
    prose. The queue exists to prevent a second relevant deadline from disappearing
    behind Today's three-slot diversity constraint; ranking stays on existing relevance.
    """
    if not records:
        return []
    try:
        limit = max(0, int(limit))
    except (TypeError, ValueError):
        limit = 2
    if limit == 0:
        return []
    excluded = {str(value) for value in (exclude_ids or set()) if str(value)}
    relevance_fn = relevance_fn or intelligence.personal_relevance
    candidates = [r for r in records if _story_id(r) not in excluded and r.get("_category") == "practical" and _actionable(r) and _deadline_note(r)]
    candidates.sort(key=lambda record: _rank(record, relevance_fn), reverse=True)
    selected, used_ids = [], set()
    for record in candidates:
        story_id = _story_id(record)
        if not story_id or story_id in used_ids:
            continue
        selected.append(record); used_ids.add(story_id)
        if len(selected) >= limit:
            break
    return selected


def select_daily_brief_rows(records, *, saved_update_predicate=None, relevance_fn=None):
    if not records:
        return []
    saved_update_predicate = saved_update_predicate or localstate.saved_has_update
    relevance_fn = relevance_fn or intelligence.personal_relevance
    ranked = sorted(records, key=lambda record: _rank(record, relevance_fn), reverse=True)
    saved_update = _best(ranked, saved_update_predicate, relevance_fn, set())
    desired = []
    if saved_update:
        desired.extend([("REVIEW", lambda r: _story_id(r) == _story_id(saved_update)), ("DO", lambda r: r.get("_category") == "practical" and _actionable(r)), ("WATCH", lambda r: r.get("_category") in WATCH_CATEGORIES), ("KNOW", lambda r: r.get("_category") == "discover")])
    else:
        desired.extend([("KNOW", lambda r: r.get("_category") == "discover"), ("DO", lambda r: r.get("_category") == "practical" and _actionable(r)), ("WATCH", lambda r: r.get("_category") in WATCH_CATEGORIES)])
    rows, used_ids = [], set()
    for label, predicate in desired:
        record = _best(ranked, predicate, relevance_fn, used_ids)
        if not record:
            continue
        rows.append((label, record)); used_ids.add(_story_id(record))
        if len(rows) == 3:
            return rows
    while len(rows) < 3:
        categories = {str(record.get("_category") or "") for _, record in rows}
        record = _balanced_fallback(ranked, relevance_fn, used_ids, categories)
        if not record:
            break
        rows.append(("KNOW", record)); used_ids.add(_story_id(record))
    return rows


def _why_selected(label, record):
    if label == "REVIEW":
        return "Saved story changed since your last review"
    hits = intelligence.interest_hits(record)
    prefs = st.session_state.get("alam_interest_preferences") or intelligence.DEFAULT_INTERESTS
    enabled_hits = [name for name in hits if prefs.get(name)]
    if label == "DO":
        return f"{_action_label(record).title()} · matches {enabled_hits[0]}" if enabled_hits else f"Verified action · {_action_label(record).title()}"
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


def _brief_open_label(label, record=None):
    if str(label or "").upper() == "DO":
        return {"DO NOW":"Open now","APPLY":"Open application","AVOID":"Open what to avoid","PREPARE":"Open preparation","BUY":"Open buying guidance","WAIT":"Open why to wait"}.get(_action_label(record or {}), "Open action")
    return {"REVIEW":"Review update","WATCH":"Open watch","KNOW":"Open story"}.get(str(label or "").upper(), "Open story")


def _open_story(record):
    st.session_state["selected_story"] = _story_id(record)
    st.rerun()


def _render_saved_change_queue(records, all_records, primary_review=None, limit=3):
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
        st.markdown("<div class='intel-brief-card'><div class='intel-kicker'>SAVED UPDATE</div>" f"<div class='intel-brief-head'>{escape(str(record.get('title') or ''))}</div>" f"<div class='intel-brief-copy'>{escape(change_copy)}</div></div>", unsafe_allow_html=True)
        title = str(record.get("title") or "Changed Saved story").strip(); button_title = title if len(title) <= 64 else title[:63].rstrip() + "…"
        if st.button(f"Review update · {button_title} →", key=f"today_saved_update_{_story_id(record)}", use_container_width=True):
            _open_story(record)


def _render_deadline_queue(records, brief_rows, limit=2):
    """Keep additional explicit deadlines visible without expanding the 3-line brief."""
    used_ids = {_story_id(record) for _, record in brief_rows}
    items = select_deadline_actions(records, exclude_ids=used_ids, limit=limit)
    if not items:
        return
    st.markdown("<div class='intel-title'>More action deadlines</div>", unsafe_allow_html=True)
    st.caption("Other validated actions with an explicit published deadline. ALAM is not inferring urgency or reordering dates from prose.")
    for record in items:
        deadline = _deadline_note(record)
        affected = _affected_note(record)
        affected_html = f"<div class='intel-mini'>Affected · {escape(affected)}</div>" if affected else ""
        st.markdown("<div class='intel-brief-card'>" f"<div class='intel-kicker'>{escape(_action_label(record))}</div>" f"<div class='intel-brief-head'>{escape(str(record.get('title') or ''))}</div>" f"<div class='intel-mini'><strong>Deadline · {escape(deadline)}</strong></div>{affected_html}</div>", unsafe_allow_html=True)
        title = str(record.get("title") or "Action").strip(); button_title = title if len(title) <= 58 else title[:57].rstrip() + "…"
        if st.button(f"{_brief_open_label('DO', record)} · {button_title} →", key=f"today_deadline_{_story_id(record)}", use_container_width=True):
            _open_story(record)


def render_daily_brief(records, all_records):
    rows = select_daily_brief_rows(records)
    if not rows:
        return
    st.markdown("<div class='intel-title'>Today in 3 lines</div>", unsafe_allow_html=True)
    html = ["<div class='intel-brief-grid'>"]
    for label, record in rows:
        copy = str(_brief_copy(label, record, all_records) or "")[:190]
        reason = _why_selected(label, record); lifecycle = intelligence.story_lifecycle(record, all_records); relevance = intelligence.personal_relevance(record)
        display_label = _display_label(label, record); deadline = _deadline_note(record) if label == "DO" else ""; affected = _affected_note(record) if label == "DO" else ""
        deadline_html = f"<div class='intel-mini'><strong>Deadline · {escape(deadline)}</strong></div>" if deadline else ""
        affected_html = f"<div class='intel-mini'>Affected · {escape(affected)}</div>" if affected else ""
        html.append("<div class='intel-brief-card'>" f"<div class='intel-kicker'>{escape(display_label)}</div>" f"<div class='intel-brief-head'>{escape(str(record.get('title') or ''))}</div>" f"<div class='intel-brief-copy'>{escape(copy)}</div>{deadline_html}{affected_html}" f"<div class='intel-mini'>{escape(reason)} · Relevance {relevance}/100 · {escape(lifecycle)}</div></div>")
    html.append("</div>"); st.markdown("".join(html), unsafe_allow_html=True)
    for label, record in rows:
        title = str(record.get("title") or "Story").strip(); button_title = title if len(title) <= 52 else title[:51].rstrip() + "…"
        if st.button(f"{_brief_open_label(label, record)} · {button_title} →", key=f"today_brief_open_{label.lower()}_{_story_id(record)}", use_container_width=True):
            _open_story(record)
    review = next((record for label, record in rows if label == "REVIEW"), None)
    _render_saved_change_queue(records, all_records, primary_review=review)
    _render_deadline_queue(records, rows)
