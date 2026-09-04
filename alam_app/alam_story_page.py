"""Mobile-first article page orchestration for ALAM.ph.

The reader page answers the decision questions first, then provides teaching,
connected intelligence, panel reasoning, evidence, and deep analysis. Enhancements
must degrade safely when Supabase/local records lack optional metadata.
"""

from __future__ import annotations

import re

import streamlit as st

import alam_action_checklist as action_checklist
import alam_evidence_views as evidence_views
import alam_intelligence as intelligence
import alam_learning_views as learning_views
import alam_local_state as localstate
import alam_mobile_views as mobile
import alam_related_views as related_views
from alam_core import age_label, category_meta, esc, is_followed, source_quality, summarize_so_what, type_label
from alam_views import _render_claims, _render_pr_vs_reality, _render_timeline


STORY_PAGE_CSS = r"""
<style>
.story-answer-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px;margin:10px 0 12px}
.story-answer-card{background:rgba(255,255,255,.94);border:1px solid rgba(23,32,42,.09);border-radius:17px;padding:13px 14px;min-height:116px}
.story-answer-label{font-size:.65rem;font-weight:950;letter-spacing:.075em;text-transform:uppercase;color:#667085;margin-bottom:6px}.story-answer-value{font-size:.88rem;line-height:1.48;color:#344054}.story-answer-value strong{color:#17202A}
.story-evidence-strong{color:#087D5B}.story-evidence-good{color:#2F6FB0}.story-evidence-early{color:#C95E19}.story-evidence-weak{color:#B42318}
.story-action-snapshot{border:1px solid rgba(8,125,91,.14);background:rgba(8,125,91,.045);border-radius:17px;padding:13px 14px;margin:9px 0 12px}.story-action-snapshot-title{font-size:.70rem;font-weight:950;letter-spacing:.065em;text-transform:uppercase;color:#087454;margin-bottom:8px}.story-action-snapshot-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px}.story-action-snapshot-item{font-size:.80rem;line-height:1.44;color:#344054}.story-action-snapshot-item b{display:block;font-size:.64rem;letter-spacing:.05em;text-transform:uppercase;color:#667085;margin-bottom:3px}.story-action-tradeoffs{border-top:1px solid rgba(8,125,91,.12);margin-top:10px;padding-top:10px}.story-action-tradeoffs-title{font-size:.64rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase;color:#667085;margin-bottom:6px}.story-action-tradeoffs-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px}.story-action-tradeoff{font-size:.78rem;line-height:1.42;color:#344054}.story-action-tradeoff b{display:block;font-size:.63rem;letter-spacing:.045em;text-transform:uppercase;color:#667085;margin-bottom:3px}
.story-change-shell{border:1px solid rgba(89,104,242,.15);background:#F7F8FF;border-radius:17px;padding:13px 14px;margin:9px 0 12px}.story-change-title{font-size:.72rem;font-weight:950;letter-spacing:.065em;text-transform:uppercase;color:#5968F2;margin-bottom:8px}.story-change-grid{display:grid;grid-template-columns:1fr auto 1fr;gap:10px;align-items:start}.story-change-block{font-size:.82rem;line-height:1.46;color:#344054}.story-change-block b{display:block;color:#17202A;margin-bottom:3px}.story-change-arrow{color:#98A2B3;font-weight:900;padding-top:17px}.story-change-why{border-top:1px solid rgba(89,104,242,.12);margin-top:9px;padding-top:9px;font-size:.82rem;line-height:1.45;color:#344054}
.story-disagreement-note{border:1px solid #F5D995;background:#FFF7E8;border-radius:14px;padding:9px 11px;margin:8px 0 12px;font-size:.80rem;line-height:1.42;color:#6B4D16}.story-saved-update{border:1px solid rgba(89,104,242,.17);background:#EEF0FF;color:#4854C8;border-radius:14px;padding:9px 11px;margin:8px 0;font-size:.79rem;line-height:1.42}.story-view-label{font-size:.70rem;font-weight:900;color:#667085;margin:12px 0 6px}
@media(max-width:760px){.story-answer-grid,.story-action-snapshot-grid,.story-action-tradeoffs-grid{grid-template-columns:1fr}.story-answer-card{min-height:auto}.story-change-grid{grid-template-columns:1fr}.story-change-arrow{transform:rotate(90deg);text-align:center;padding:0}.story-view-label{margin-top:10px}}
</style>
"""


SCORE_LABELS = {
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


def _score_value(value, default=0.0):
    """Normalize valid ALAM v5 score shapes before article-detail rendering."""
    if value is None:
        return float(default)
    if isinstance(value, bool):
        return 100.0 if value else 0.0
    if isinstance(value, (int, float)):
        return max(0.0, min(100.0, float(value)))
    if isinstance(value, dict):
        for key in ("score", "value", "percent", "percentage", "rating"):
            if key in value:
                return _score_value(value.get(key), default)
        return float(default)
    text = str(value).strip().upper()
    if text in SCORE_LABELS:
        return SCORE_LABELS[text]
    match = re.search(r"-?\d+(?:\.\d+)?", text.replace(",", ""))
    if not match:
        return float(default)
    try:
        return max(0.0, min(100.0, float(match.group(0))))
    except ValueError:
        return float(default)


def _compact(value, limit=360):
    text = str(value or "").strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _action_answer(record):
    content = record.get("content") if isinstance(record.get("content"), dict) else {}
    action = str(content.get("action") or "").strip().upper()
    recommendation = content.get("recommendation") or content.get("what_to_do") or content.get("next_step") or content.get("practical_guidelines")
    if action and recommendation:
        return f"{action}: {_compact(recommendation, 260)}"
    if action:
        return action
    if recommendation:
        return _compact(recommendation, 280)
    return "No immediate action stated. Keep watching the evidence."


def _why_answer(record):
    return _compact(record.get("why_it_matters") or summarize_so_what(record) or record.get("summary") or "The record does not yet state a separate impact conclusion.", 320)


def _safe_action_fact(value, limit):
    """Normalize only explicit scalar action metadata; structured/placeholder values fail closed."""
    if not isinstance(value, str):
        return ""
    text = " ".join(value.split()).strip()
    if not text or text.lower() in {"none", "n/a", "na", "not applicable", "unknown", "tbd"}:
        return ""
    return _compact(text, limit)


def _practical_action_snapshot(record):
    """Return article-supplied decision context without inferring eligibility or urgency."""
    if str(record.get("_category") or record.get("category") or "").lower() != "practical":
        return []
    content = record.get("content") if isinstance(record.get("content"), dict) else {}
    candidates = (
        ("Affected", content.get("who_is_affected"), 220),
        ("Deadline / timing", content.get("deadline") or content.get("when"), 180),
        ("If ignored", content.get("risk_if_ignored"), 240),
    )
    return [(label, text) for label, value, limit in candidates if (text := _safe_action_fact(value, limit))]


def _practical_action_tradeoffs(record):
    """Expose explicit cost/benefit/effort metadata without calculating a recommendation."""
    if str(record.get("_category") or record.get("category") or "").lower() != "practical":
        return []
    content = record.get("content") if isinstance(record.get("content"), dict) else {}
    candidates = (
        ("Potential benefit", content.get("potential_benefit"), 200),
        ("Downside", content.get("downside"), 200),
        ("Effort / cost", content.get("effort") or content.get("financial_impact"), 180),
    )
    return [(label, text) for label, value, limit in candidates if (text := _safe_action_fact(value, limit))]


def _render_action_snapshot(record):
    items = _practical_action_snapshot(record)
    tradeoffs = _practical_action_tradeoffs(record)
    if not items and not tradeoffs:
        return
    cards = "".join(f"<div class='story-action-snapshot-item'><b>{esc(label)}</b>{esc(value)}</div>" for label, value in items)
    tradeoff_html = ""
    if tradeoffs:
        tradeoff_cards = "".join(f"<div class='story-action-tradeoff'><b>{esc(label)}</b>{esc(value)}</div>" for label, value in tradeoffs)
        tradeoff_html = f"<div class='story-action-tradeoffs'><div class='story-action-tradeoffs-title'>Tradeoffs before committing</div><div class='story-action-tradeoffs-grid'>{tradeoff_cards}</div></div>"
    st.markdown(f"<div class='story-action-snapshot'><div class='story-action-snapshot-title'>Before you act</div><div class='story-action-snapshot-grid'>{cards}</div>{tradeoff_html}</div>", unsafe_allow_html=True)


def _render_answer_grid(record, all_records):
    health, evidence = intelligence.evidence_health(record)
    lifecycle = intelligence.story_lifecycle(record, all_records)
    relevance = intelligence.personal_relevance(record)
    health_class = {"STRONG":"story-evidence-strong","GOOD":"story-evidence-good","EARLY":"story-evidence-early","WEAK":"story-evidence-weak"}.get(health, "")
    st.markdown(
        "<div class='story-answer-grid'>"
        "<div class='story-answer-card'><div class='story-answer-label'>Why it matters</div>" f"<div class='story-answer-value'>{esc(_why_answer(record))}</div></div>"
        "<div class='story-answer-card'><div class='story-answer-label'>What to do</div>" f"<div class='story-answer-value'>{esc(_action_answer(record))}</div></div>"
        "<div class='story-answer-card'><div class='story-answer-label'>Evidence</div>" f"<div class='story-answer-value'><strong class='{health_class}'>{esc(health)}</strong> · {esc(lifecycle)}<br>{esc(evidence)}<br><span class='small-muted'>Relevance {relevance}/100</span></div></div></div>",
        unsafe_allow_html=True,
    )


def _render_change(record, all_records):
    change = intelligence.change_snapshot(record, all_records)
    if not change:
        return
    content = record.get("content") if isinstance(record.get("content"), dict) else {}
    supplied = content.get("change_summary") if isinstance(content.get("change_summary"), dict) else {}
    why = supplied.get("why_change_matters") or supplied.get("what_this_means")
    why_html = f"<div class='story-change-why'><strong>What this means:</strong> {esc(_compact(why, 380))}</div>" if why else ""
    st.markdown("<div class='story-change-shell'><div class='story-change-title'>What changed</div><div class='story-change-grid'>" f"<div class='story-change-block'><b>Before</b>{esc(_compact(change[0],330))}</div><div class='story-change-arrow'>→</div><div class='story-change-block'><b>Now</b>{esc(_compact(change[1],330))}</div></div>{why_html}</div>", unsafe_allow_html=True)


def _render_disagreement_signal(record, comments):
    disagreement = intelligence.disagreement_signal(record, comments)
    if disagreement:
        st.markdown("<div class='story-disagreement-note'>" f"⚡ <strong>Panel disagreement: {esc(disagreement[0])}</strong> — {esc(disagreement[1])}. Open <strong>Panel</strong> below to read the actual reasoning; ALAM does not flatten this into a forced consensus.</div>", unsafe_allow_html=True)


def render_story_page(all_records, record, comments, manager=None):
    """Render a complete story page in decision-first reading order."""
    if st.button("← Balik", key="back_detail"):
        st.session_state.pop("selected_story", None)
        st.rerun()

    confidence_raw = record.get("confidence") if record.get("confidence") is not None else record.get("confidence_score")
    importance_raw = record.get("importance") if record.get("importance") is not None else record.get("importance_score")
    confidence = _score_value(confidence_raw, 0.0)
    normalized_record = dict(record)
    normalized_record["confidence"] = confidence
    normalized_record["importance"] = _score_value(importance_raw, 50.0)

    meta = category_meta(record)
    total, strong = source_quality(record)
    tags = " · ".join(str(x) for x in record.get("tags", [])[:5])
    st.markdown("<div class='detail-shell'><div class='story-topline'>" f"<div class='story-label' style='margin:0;background:{meta['soft']};color:{meta['accent']}'>{esc(type_label(record))}</div><div class='story-age'>{esc(age_label(record.get('created_at')))}</div></div>" f"<div class='detail-title'>{esc(record.get('title',''))}</div><div class='detail-summary'>{esc(record.get('summary',''))}</div><div class='story-meta' style='margin-top:14px'><span>{confidence:g}% confidence</span><span>{total} sources</span><span>{strong} primary/official</span><span>{esc(tags)}</span></div></div>", unsafe_allow_html=True)

    if localstate.saved_has_update(record):
        st.markdown("<div class='story-saved-update'><strong>Updated since you saved this.</strong> This stable story ID now points to a newer ALAM version than the one captured when you saved it.</div>", unsafe_allow_html=True)

    label = "✓ Binabantayan" if is_followed(record["id"]) else "+ Bantayan"
    if st.button(label, key=f"detail_follow_story_{record['id']}", use_container_width=True):
        localstate.toggle_saved(record, manager)
        st.rerun()

    _render_answer_grid(normalized_record, all_records)
    _render_action_snapshot(record)
    action_checklist.render_action_checklist(record, manager)
    _render_change(record, all_records)
    _render_disagreement_signal(record, comments)
    learning_views.render_learning_section(record)

    related_views.render_related_stories(record, all_records)

    st.markdown("<div class='story-view-label'>More ways to explore this story</div>", unsafe_allow_html=True)
    mode = st.segmented_control("View", ["⚡ 30 sec", "🗣 Panel", "🧾 Evidence", "🧠 Deep"], default="⚡ 30 sec", key=f"detail_mode_{record['id']}", label_visibility="collapsed", width="stretch")
    if mode == "🗣 Panel":
        mobile._render_panel(record, comments)
    elif mode == "🧾 Evidence":
        evidence_views.render_evidence(record, all_records, _render_pr_vs_reality, _render_claims, _render_timeline)
    elif mode == "🧠 Deep":
        mobile._render_deep(record, all_records, comments)
    else:
        mobile._render_30sec(record)