"""Decision-first Today page for ALAM.ph.

ALAM accumulated several individually useful Today widgets over time: alert matches,
a three-line brief, an inbox, an urgent strip, a top-story hero and a second briefing.
Rendered together they compete for the same first-screen attention. This module gives
Today one information architecture instead:

    Today in 3 lines -> Do Now -> Prepare -> Avoid -> Watch -> Discover

The full Action Center, Search, Market and Trend pages still exist for deeper browsing.
Today's job is prioritization, not exhaustive navigation.
"""

from __future__ import annotations

import streamlit as st

import alam_intelligence as intelligence
import alam_local_state as localstate
from alam_core import age_label, esc, feed_score


TODAY_CSS = r"""
<style>
.today-priority-title{font-size:1.15rem;font-weight:950;letter-spacing:-.025em;margin:18px 0 4px}
.today-priority-copy{font-size:.77rem;line-height:1.45;color:#667085;margin-bottom:9px}
.today-action-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:9px;margin:7px 0 16px}
.today-action-card{background:rgba(255,255,255,.94);border:1px solid rgba(23,32,42,.09);border-radius:17px;padding:13px;min-width:0}
.today-action-card.do{border-top:4px solid #087D5B}.today-action-card.prepare{border-top:4px solid #5968F2}.today-action-card.avoid{border-top:4px solid #B42318}.today-action-card.watch{border-top:4px solid #C95E19}
.today-action-kicker{font-size:.63rem;font-weight:950;letter-spacing:.07em;text-transform:uppercase;color:#667085}
.today-action-head{font-size:.91rem;line-height:1.25;font-weight:900;margin-top:5px;color:#17202A}
.today-action-body{font-size:.78rem;line-height:1.43;color:#475467;margin-top:6px}
.today-action-meta{font-size:.64rem;color:#98A2B3;margin-top:8px}
.today-empty{font-size:.76rem;line-height:1.4;color:#98A2B3;margin-top:7px}
.today-discover-head{display:flex;align-items:end;justify-content:space-between;gap:10px;margin:20px 0 8px}.today-discover-head strong{font-size:1.2rem}.today-discover-head span{font-size:.72rem;color:#98A2B3}
.today-caught-up{border:1px solid rgba(8,125,91,.13);background:rgba(8,125,91,.07);border-radius:14px;padding:9px 11px;margin:8px 0 12px;font-size:.76rem;line-height:1.4;color:#087454}
@media(max-width:900px){.today-action-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:560px){.today-action-grid{grid-template-columns:1fr}.today-action-card{padding:12px}.today-priority-title{font-size:1.05rem}.today-discover-head{align-items:flex-start;flex-direction:column;gap:2px}}
</style>
"""

ACTION_LANES = (
    ("DO NOW", "do", {"DO NOW", "APPLY", "BUY"}),
    ("PREPARE", "prepare", {"PREPARE"}),
    ("AVOID", "avoid", {"AVOID"}),
    ("WATCH", "watch", {"WATCH", "WAIT"}),
)


def _action(record):
    content = record.get("content") if isinstance(record.get("content"), dict) else {}
    return str(content.get("action") or "").strip().upper()


def _action_copy(record):
    content = record.get("content") if isinstance(record.get("content"), dict) else {}
    value = (
        content.get("recommendation")
        or content.get("risk_if_ignored")
        or content.get("what_to_do")
        or content.get("potential_benefit")
        or record.get("why_it_matters")
        or record.get("summary")
        or ""
    )
    text = str(value).strip()
    return text if len(text) <= 170 else text[:169].rstrip() + "…"


def _rank(record):
    return (intelligence.personal_relevance(record), feed_score(record))


def _pick_lane(records, allowed_actions):
    candidates = [
        record for record in records
        if record.get("_category") == "practical" and _action(record) in allowed_actions
    ]
    return max(candidates, key=_rank) if candidates else None


def _open_story(record):
    st.session_state["selected_story"] = str(record.get("id"))
    st.rerun()


def _render_action_priorities(records):
    st.markdown('<div class="today-priority-title">What needs your attention?</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="today-priority-copy">Action signals are separated by intent so an urgent warning does not get buried beside a low-pressure watch item.</div>',
        unsafe_allow_html=True,
    )

    selected = []
    cards = []
    for label, css_class, allowed in ACTION_LANES:
        record = _pick_lane(records, allowed)
        selected.append((label, record))
        if record:
            cards.append(
                f'<div class="today-action-card {css_class}">'
                f'<div class="today-action-kicker">{esc(label)}</div>'
                f'<div class="today-action-head">{esc(record.get("title", ""))}</div>'
                f'<div class="today-action-body">{esc(_action_copy(record))}</div>'
                f'<div class="today-action-meta">Relevance {intelligence.personal_relevance(record)}/100 · {esc(age_label(record.get("created_at")))}</div>'
                '</div>'
            )
        else:
            cards.append(
                f'<div class="today-action-card {css_class}">'
                f'<div class="today-action-kicker">{esc(label)}</div>'
                '<div class="today-empty">No current verified item in this lane.</div>'
                '</div>'
            )
    st.markdown('<div class="today-action-grid">' + "".join(cards) + '</div>', unsafe_allow_html=True)

    # Streamlit HTML cards are deliberately non-clickable so they remain accessible
    # and predictable. Only lanes that contain a story get a native button/tap target.
    active = [(label, record) for label, record in selected if record]
    if active:
        button_cols = st.columns(len(active))
        for col, (label, record) in zip(button_cols, active):
            if col.button(f"Open {label.title()} →", key=f"today_lane_{label}_{record.get('id')}", use_container_width=True):
                _open_story(record)


def _discover_pool(records, action_ids):
    """Choose useful non-duplicate discovery cards after action priorities.

    High relevance leads, but at least one non-personalized high-importance item can
    still surface because ranking uses ALAM's shared feed score as the second term.
    This avoids turning Today into a narrow filter bubble.
    """
    pool = [record for record in records if str(record.get("id")) not in action_ids]
    pool.sort(key=_rank, reverse=True)
    return pool[:6]


def render_today(records, all_records, comments, manager, views, reader):
    if not records:
        st.info("Wala pang verified intelligence records.")
        return

    # An alert match is exceptional enough to stay above the normal hierarchy, but
    # it is rendered only when the user's explicit alert rules are satisfied.
    intelligence.render_alert_ribbon(records, all_records)
    intelligence.render_daily_brief(records, all_records)

    action_picks = []
    for _, _, allowed in ACTION_LANES:
        record = _pick_lane(records, allowed)
        if record:
            action_picks.append(record)
    _render_action_priorities(records)

    # Inbox follows the immediate decision lanes: unread/material-change information
    # matters, but should not push Do Now/Avoid items below the first screen.
    reader.render_inbox(records, all_records, manager)

    unread_count = sum(1 for record in records if localstate.is_unread(record))
    if unread_count == 0:
        st.markdown(
            '<div class="today-caught-up"><strong>Caught up.</strong> Saved or existing stories will become unread again when a newer material version arrives.</div>',
            unsafe_allow_html=True,
        )

    action_ids = {str(record.get("id")) for record in action_picks}
    discovery = _discover_pool(records, action_ids)
    st.markdown(
        '<div class="today-discover-head"><strong>Discover</strong><span>Useful signals beyond the immediate action queue</span></div>',
        unsafe_allow_html=True,
    )
    if not discovery:
        st.caption("No additional current stories after the action queue.")
        return

    cols = st.columns(2, wrap=True)
    for index, record in enumerate(discovery):
        with cols[index % 2]:
            views.render_card(record, f"today_priority_{index}", manager, comments)
