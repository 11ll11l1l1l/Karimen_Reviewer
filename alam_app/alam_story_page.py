"""Mobile-first article page orchestration for ALAM.ph.

The original reader accumulated useful features over time, but many of them rendered
*after* the reader had already chosen a detail mode. That forced a user to hunt for
four basic answers: why this matters, whether action is needed, what changed, and
how strong the evidence is. This module deliberately owns the page-level information
architecture while reusing the existing evidence, panel, and deep-reading renderers.

Keeping orchestration here instead of adding another CSS/logic layer inside
``alam_mobile_views`` also reduces the risk of regressions in feed/card rendering.
"""

from __future__ import annotations

import streamlit as st

import alam_intelligence as intelligence
import alam_local_state as localstate
import alam_mobile_views as mobile
from alam_core import (
    age_label,
    category_meta,
    esc,
    is_followed,
    source_quality,
    summarize_so_what,
    type_label,
)
from alam_views import _render_claims, _render_pr_vs_reality, _render_sources, _render_timeline


STORY_PAGE_CSS = r"""
<style>
.story-answer-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px;margin:10px 0 12px}
.story-answer-card{background:rgba(255,255,255,.94);border:1px solid rgba(23,32,42,.09);border-radius:17px;padding:13px 14px;min-height:116px}
.story-answer-label{font-size:.65rem;font-weight:950;letter-spacing:.075em;text-transform:uppercase;color:#667085;margin-bottom:6px}
.story-answer-value{font-size:.88rem;line-height:1.48;color:#344054}
.story-answer-value strong{color:#17202A}
.story-evidence-strong{color:#087D5B}.story-evidence-good{color:#2F6FB0}.story-evidence-early{color:#C95E19}.story-evidence-weak{color:#B42318}
.story-change-shell{border:1px solid rgba(89,104,242,.15);background:#F7F8FF;border-radius:17px;padding:13px 14px;margin:9px 0 12px}
.story-change-title{font-size:.72rem;font-weight:950;letter-spacing:.065em;text-transform:uppercase;color:#5968F2;margin-bottom:8px}
.story-change-grid{display:grid;grid-template-columns:1fr auto 1fr;gap:10px;align-items:start}
.story-change-block{font-size:.82rem;line-height:1.46;color:#344054}.story-change-block b{display:block;color:#17202A;margin-bottom:3px}
.story-change-arrow{color:#98A2B3;font-weight:900;padding-top:17px}
.story-change-why{border-top:1px solid rgba(89,104,242,.12);margin-top:9px;padding-top:9px;font-size:.82rem;line-height:1.45;color:#344054}
.story-disagreement-note{border:1px solid #F5D995;background:#FFF7E8;border-radius:14px;padding:9px 11px;margin:8px 0 12px;font-size:.80rem;line-height:1.42;color:#6B4D16}
.story-saved-update{border:1px solid rgba(89,104,242,.17);background:#EEF0FF;color:#4854C8;border-radius:14px;padding:9px 11px;margin:8px 0;font-size:.79rem;line-height:1.42}
.story-view-label{font-size:.70rem;font-weight:900;color:#667085;margin:12px 0 6px}
@media(max-width:760px){.story-answer-grid{grid-template-columns:1fr}.story-answer-card{min-height:auto}.story-change-grid{grid-template-columns:1fr}.story-change-arrow{transform:rotate(90deg);text-align:center;padding:0}.story-view-label{margin-top:10px}}
</style>
"""


def _compact(value, limit=360):
    text = str(value or "").strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _action_answer(record):
    """Return a concise action answer without inventing advice absent from the record."""
    content = record.get("content") if isinstance(record.get("content"), dict) else {}
    action = str(content.get("action") or "").strip().upper()
    recommendation = (
        content.get("recommendation")
        or content.get("what_to_do")
        or content.get("next_step")
        or content.get("practical_guidelines")
    )
    if action and recommendation:
        return f"{action}: {_compact(recommendation, 260)}"
    if action:
        return action
    if recommendation:
        return _compact(recommendation, 280)
    # A neutral watch state is safer than synthesizing a call to action from a
    # descriptive story. The full analysis can still explain implications below.
    return "No immediate action stated. Keep watching the evidence."


def _why_answer(record):
    return _compact(
        record.get("why_it_matters")
        or summarize_so_what(record)
        or record.get("summary")
        or "The record does not yet state a separate impact conclusion.",
        320,
    )


def _render_answer_grid(record, all_records):
    health, evidence = intelligence.evidence_health(record)
    lifecycle = intelligence.story_lifecycle(record, all_records)
    relevance = intelligence.personal_relevance(record)
    health_class = {
        "STRONG": "story-evidence-strong",
        "GOOD": "story-evidence-good",
        "EARLY": "story-evidence-early",
        "WEAK": "story-evidence-weak",
    }.get(health, "")

    # These three cards intentionally answer different questions. Avoid collapsing
    # them into a generic metadata strip: on a phone, users need the implication and
    # action before they decide whether the article deserves a deeper read.
    st.markdown(
        "<div class='story-answer-grid'>"
        "<div class='story-answer-card'><div class='story-answer-label'>Why it matters</div>"
        f"<div class='story-answer-value'>{esc(_why_answer(record))}</div></div>"
        "<div class='story-answer-card'><div class='story-answer-label'>What to do</div>"
        f"<div class='story-answer-value'>{esc(_action_answer(record))}</div></div>"
        "<div class='story-answer-card'><div class='story-answer-label'>Evidence</div>"
        f"<div class='story-answer-value'><strong class='{health_class}'>{esc(health)}</strong> · {esc(lifecycle)}<br>"
        f"{esc(evidence)}<br><span class='small-muted'>Relevance {relevance}/100</span></div></div>"
        "</div>",
        unsafe_allow_html=True,
    )


def _render_change(record, all_records):
    change = intelligence.change_snapshot(record, all_records)
    if not change:
        return
    content = record.get("content") if isinstance(record.get("content"), dict) else {}
    supplied = content.get("change_summary") if isinstance(content.get("change_summary"), dict) else {}
    why = supplied.get("why_change_matters") or supplied.get("what_this_means")
    why_html = (
        f"<div class='story-change-why'><strong>What this means:</strong> {esc(_compact(why, 380))}</div>"
        if why else ""
    )
    st.markdown(
        "<div class='story-change-shell'><div class='story-change-title'>What changed</div>"
        "<div class='story-change-grid'>"
        f"<div class='story-change-block'><b>Before</b>{esc(_compact(change[0], 330))}</div>"
        "<div class='story-change-arrow'>→</div>"
        f"<div class='story-change-block'><b>Now</b>{esc(_compact(change[1], 330))}</div>"
        f"</div>{why_html}</div>",
        unsafe_allow_html=True,
    )


def _render_disagreement_signal(record, comments):
    disagreement = intelligence.disagreement_signal(record, comments)
    if not disagreement:
        return
    st.markdown(
        "<div class='story-disagreement-note'>"
        f"⚡ <strong>Panel disagreement: {esc(disagreement[0])}</strong> — {esc(disagreement[1])}. "
        "Open <strong>Panel</strong> below to read the actual reasoning; ALAM does not flatten this into a forced consensus."
        "</div>",
        unsafe_allow_html=True,
    )


def render_story_page(all_records, record, comments, manager=None):
    """Render a complete story page in decision-first reading order.

    The page works with either Supabase-hydrated records or the local JSON fallback
    because every derived element uses the stable ALAM v5 record contract. Missing
    history/comments simply remove the corresponding enhancement instead of turning
    a partial database migration into a broken reader.
    """
    if st.button("← Balik", key="back_detail"):
        st.session_state.pop("selected_story", None)
        st.rerun()

    meta = category_meta(record)
    total, strong = source_quality(record)
    tags = " · ".join(str(x) for x in record.get("tags", [])[:5])
    st.markdown(
        "<div class='detail-shell'>"
        "<div class='story-topline'>"
        f"<div class='story-label' style='margin:0;background:{meta['soft']};color:{meta['accent']}'>{esc(type_label(record))}</div>"
        f"<div class='story-age'>{esc(age_label(record.get('created_at')))}</div></div>"
        f"<div class='detail-title'>{esc(record.get('title',''))}</div>"
        f"<div class='detail-summary'>{esc(record.get('summary',''))}</div>"
        "<div class='story-meta' style='margin-top:14px'>"
        f"<span>{int(record.get('confidence',0) or 0)}% confidence</span>"
        f"<span>{total} sources</span><span>{strong} primary/official</span>"
        f"<span>{esc(tags)}</span></div></div>",
        unsafe_allow_html=True,
    )

    if localstate.saved_has_update(record):
        st.markdown(
            "<div class='story-saved-update'><strong>Updated since you saved this.</strong> "
            "This stable story ID now points to a newer ALAM version than the one captured when you saved it.</div>",
            unsafe_allow_html=True,
        )

    label = "✓ Binabantayan" if is_followed(record["id"]) else "+ Bantayan"
    if st.button(label, key=f"detail_follow_story_{record['id']}", use_container_width=True):
        # Save through the local-profile wrapper so ALAM records which exact material
        # version existed at save time. The legacy followed-ID cookie remains intact,
        # preserving backward compatibility with existing Saved sync codes.
        localstate.toggle_saved(record, manager)
        st.rerun()

    _render_answer_grid(record, all_records)
    _render_change(record, all_records)
    _render_disagreement_signal(record, comments)

    st.markdown("<div class='story-view-label'>Choose how deep you want to go</div>", unsafe_allow_html=True)
    mode = st.segmented_control(
        "View",
        ["⚡ 30 sec", "🗣 Panel", "🧾 Evidence", "🧠 Deep"],
        default="⚡ 30 sec",
        key=f"detail_mode_{record['id']}",
        label_visibility="collapsed",
        width="stretch",
    )
    if mode == "🗣 Panel":
        # The full-thread expander inside the existing panel preserves complete
        # substantive comments and reply relationships instead of forcing comments
        # into shallow one-line cards.
        mobile._render_panel(record, comments)
    elif mode == "🧾 Evidence":
        _render_pr_vs_reality(record)
        _render_claims(record)
        _render_timeline(all_records, record)
        _render_sources(record)
    elif mode == "🧠 Deep":
        mobile._render_deep(record, all_records, comments)
    else:
        mobile._render_30sec(record)
