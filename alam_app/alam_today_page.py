"""Decision-first Today page for ALAM.ph.

Today prioritizes a concise briefing, actionable lanes, inbox state, and a deliberately
balanced discovery shelf. The discovery shelf is personalized without becoming a
single-topic filter bubble: when the corpus permits it, one high-value story from a
category outside the reader's leading personalized picks is reserved as a perspective
stretch.
"""
from __future__ import annotations

from collections import Counter
import streamlit as st

import alam_daily_brief as daily_brief
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
.today-stretch{border:1px solid rgba(89,104,242,.14);background:rgba(89,104,242,.06);border-radius:14px;padding:9px 11px;margin:7px 0 10px;font-size:.74rem;line-height:1.4;color:#475467}.today-stretch strong{color:#3949ab}
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
    value = content.get("recommendation") or content.get("risk_if_ignored") or content.get("what_to_do") or content.get("potential_benefit") or record.get("why_it_matters") or record.get("summary") or ""
    text = str(value).strip()
    return text if len(text) <= 170 else text[:169].rstrip() + "…"


def _rank(record):
    return (intelligence.personal_relevance(record), feed_score(record))


def _pick_lane(records, allowed_actions):
    candidates = [record for record in records if record.get("_category") == "practical" and _action(record) in allowed_actions]
    return max(candidates, key=_rank) if candidates else None


def _open_story(record):
    st.session_state["selected_story"] = str(record.get("id"))
    st.rerun()


def _render_action_priorities(records):
    st.markdown('<div class="today-priority-title">What needs your attention?</div>', unsafe_allow_html=True)
    st.markdown('<div class="today-priority-copy">Action signals are separated by intent so an urgent warning does not get buried beside a low-pressure watch item.</div>', unsafe_allow_html=True)
    selected, cards = [], []
    for label, css_class, allowed in ACTION_LANES:
        record = _pick_lane(records, allowed)
        selected.append((label, record))
        if record:
            cards.append(f'<div class="today-action-card {css_class}"><div class="today-action-kicker">{esc(label)}</div><div class="today-action-head">{esc(record.get("title", ""))}</div><div class="today-action-body">{esc(_action_copy(record))}</div><div class="today-action-meta">Relevance {intelligence.personal_relevance(record)}/100 · {esc(age_label(record.get("created_at")))}</div></div>')
        else:
            cards.append(f'<div class="today-action-card {css_class}"><div class="today-action-kicker">{esc(label)}</div><div class="today-empty">No current verified item in this lane.</div></div>')
    st.markdown('<div class="today-action-grid">' + "".join(cards) + '</div>', unsafe_allow_html=True)
    active = [(label, record) for label, record in selected if record]
    if active:
        button_cols = st.columns(len(active))
        for col, (label, record) in zip(button_cols, active):
            if col.button(f"Open {label.title()} →", key=f"today_lane_{label}_{record.get('id')}", use_container_width=True):
                _open_story(record)


def _category(record):
    return str(record.get("_category") or record.get("category") or "other")


def _discover_pool(records, action_ids, limit=6):
    """Return personalized discovery plus one explainable perspective-stretch slot.

    Personal relevance still drives the shelf. If the first picks collapse into too
    few categories while another category has a strong current story, reserve the
    final slot for the highest shared-feed-score story from an unrepresented category.
    This is deterministic, uses only validated records, and never lowers the shelf
    below the available corpus just to manufacture diversity.
    """
    pool = [record for record in records if str(record.get("id")) not in action_ids]
    pool.sort(key=_rank, reverse=True)
    limit = max(1, int(limit))
    chosen = pool[:limit]
    if len(chosen) < 2:
        return chosen, None

    represented = {_category(record) for record in chosen[:-1]}
    alternatives = [record for record in pool if record not in chosen and _category(record) not in represented]
    if not alternatives:
        return chosen, None

    counts = Counter(_category(record) for record in chosen)
    if len(counts) >= min(3, len({_category(record) for record in pool})):
        return chosen, None

    stretch = max(alternatives, key=lambda record: (feed_score(record), intelligence.personal_relevance(record)))
    chosen[-1] = stretch
    return chosen, stretch


def render_today(records, all_records, comments, manager, views, reader):
    if not records:
        st.info("Wala pang verified intelligence records.")
        return
    intelligence.render_alert_ribbon(records, all_records)
    daily_brief.render_daily_brief(records, all_records)

    action_picks = []
    for _, _, allowed in ACTION_LANES:
        record = _pick_lane(records, allowed)
        if record:
            action_picks.append(record)
    _render_action_priorities(records)
    reader.render_inbox(records, all_records, manager)

    unread_count = sum(1 for record in records if localstate.is_unread(record))
    if unread_count == 0:
        st.markdown('<div class="today-caught-up"><strong>Caught up.</strong> Saved or existing stories will become unread again when a newer material version arrives.</div>', unsafe_allow_html=True)

    action_ids = {str(record.get("id")) for record in action_picks}
    discovery, stretch = _discover_pool(records, action_ids)
    st.markdown('<div class="today-discover-head"><strong>Discover</strong><span>Useful signals beyond the immediate action queue</span></div>', unsafe_allow_html=True)
    if stretch:
        st.markdown(f'<div class="today-stretch"><strong>Perspective stretch:</strong> one verified {esc(_category(stretch).title())} story is included outside the leading personalized mix, so Today does not become a closed filter bubble.</div>', unsafe_allow_html=True)
    if not discovery:
        st.caption("No additional current stories after the action queue.")
        return
    cols = st.columns(2, wrap=True)
    for index, record in enumerate(discovery):
        with cols[index % 2]:
            views.render_card(record, f"today_priority_{index}", manager, comments)
