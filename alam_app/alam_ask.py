"""Grounded question-answering over ALAM's already-validated article corpus.

This first Ask ALAM release is intentionally retrieval-first rather than a free-form
chatbot. It never answers a factual question from model memory: every displayed answer
sentence is selected from a validated ALAM record already loaded by the application
(preferably from Supabase, with the existing GitHub/local recovery fallback).

That boundary is deliberate. A later LLM synthesis layer may sit on top of the ranked
records, but it must preserve source citations/refusal behavior instead of silently
inventing an answer when the corpus is weak.
"""

from __future__ import annotations

import json
import re
from collections import OrderedDict

import streamlit as st


CATEGORY_LABELS = {
    "discover": "Discover",
    "practical": "Action",
    "reflection": "Market",
    "trend": "Trends",
}

# Small multilingual/topic expansion improves ordinary Taglish queries without making
# retrieval opaque. These aliases only add literal corpus search terms; they never add
# facts or generate an answer.
ALIASES = {
    "visa": ("immigration", "residence", "在留", "renewal"),
    "renew": ("renewal", "residence", "在留"),
    "pr": ("permanent residence", "永住"),
    "tax": ("tax", "year-end", "deduction", "税", "扶養"),
    "dependent": ("dependent", "扶養", "spouse", "relative"),
    "earthquake": ("earthquake", "seismic", "plate", "地震"),
    "quake": ("earthquake", "seismic", "plate", "地震"),
    "nisa": ("nisa", "investment", "fund"),
    "yen": ("yen", "jpy", "円", "usd/jpy"),
    "market": ("market", "nikkei", "topix", "jgb", "usd/jpy"),
    "scam": ("scam", "fraud", "詐欺"),
    "benefit": ("benefit", "allowance", "support", "給付", "手当"),
}

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "can", "do", "does", "for",
    "from", "how", "i", "in", "is", "it", "me", "my", "of", "on", "or",
    "should", "the", "this", "to", "what", "when", "where", "which", "who",
    "why", "with", "yung", "ang", "ano", "ba", "ko", "mo", "sa", "ng",
}

TOKEN_RE = re.compile(r"[a-z0-9]+(?:[./-][a-z0-9]+)*|[\u3040-\u30ff\u3400-\u9fff]+", re.I)

ASK_CSS = r"""
<style>
.ask-shell{padding:16px 17px;margin:8px 0 14px;border:1px solid rgba(23,32,42,.09);border-radius:18px;background:rgba(255,255,255,.72)}
.ask-kicker{font-size:.68rem;font-weight:850;letter-spacing:.08em;text-transform:uppercase;color:#667085}
.ask-answer{font-size:1.02rem;line-height:1.55;font-weight:720;color:#273142;margin-top:7px}
.ask-meta{font-size:.72rem;color:#667085;margin-top:8px;line-height:1.4}
.ask-lens{padding:10px 11px;border:1px solid rgba(23,32,42,.08);border-radius:14px;margin:7px 0;background:rgba(255,255,255,.58)}
.ask-lens strong{font-size:.78rem}.ask-lens span{font-size:.78rem;color:#475467;line-height:1.45}
@media(max-width:760px){.ask-shell{padding:13px 13px;border-radius:16px}.ask-answer{font-size:.94rem}}
</style>
"""


def _flat_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):
        return str(value)


def _search_fields(record: dict) -> dict[str, str]:
    """Return weighted literal search fields; no generated semantic content."""
    return {
        "title": str(record.get("title") or "").lower(),
        "tags": " ".join(str(x) for x in (record.get("tags") or [])).lower(),
        "summary": " ".join(
            [str(record.get("summary") or ""), str(record.get("why_it_matters") or "")]
        ).lower(),
        "body": " ".join(
            [
                _flat_text(record.get("content")),
                _flat_text(record.get("claims")),
                _flat_text(record.get("geography")),
            ]
        ).lower(),
    }


def _base_terms(query: str) -> list[str]:
    tokens = [token.lower() for token in TOKEN_RE.findall(str(query or ""))]
    return [token for token in tokens if len(token) > 1 and token not in STOPWORDS]


def query_terms(query: str) -> list[str]:
    """Return stable, deduplicated literal terms plus conservative topic aliases."""
    ordered: OrderedDict[str, None] = OrderedDict()
    for token in _base_terms(query):
        ordered[token] = None
        for alias in ALIASES.get(token, ()):
            ordered[alias.lower()] = None
    return list(ordered)


def relevance_score(record: dict, query: str) -> float:
    """Score a record using explainable literal overlap, not hidden model similarity."""
    terms = query_terms(query)
    if not terms:
        return 0.0

    fields = _search_fields(record)
    phrase = str(query or "").strip().lower()
    score = 0.0
    matched_core = 0
    core = set(_base_terms(query))

    if len(phrase) >= 4:
        if phrase in fields["title"]:
            score += 10.0
        elif phrase in fields["summary"]:
            score += 5.0
        elif phrase in fields["body"]:
            score += 2.0

    for term in terms:
        hit = False
        if term in fields["title"]:
            score += 5.0
            hit = True
        if term in fields["tags"]:
            score += 3.5
            hit = True
        if term in fields["summary"]:
            score += 2.5
            hit = True
        if term in fields["body"]:
            score += 1.0
            hit = True
        if hit and term in core:
            matched_core += 1

    # At least one literal user term must match. Alias-only matches are useful for
    # expansion but are not strong enough to manufacture relevance on their own.
    if core and matched_core == 0:
        return 0.0

    if score <= 0:
        return 0.0

    # Tiny quality tie-breakers can order two equally relevant records, but can never
    # make an irrelevant high-importance story match the question.
    try:
        importance = float(record.get("importance") or record.get("importance_score") or 0)
    except (TypeError, ValueError):
        importance = 0.0
    try:
        confidence = float(record.get("confidence") or record.get("confidence_score") or 0)
    except (TypeError, ValueError):
        confidence = 0.0
    score += min(max(importance, 0.0), 100.0) / 100.0
    score += min(max(confidence, 0.0), 100.0) / 200.0
    return round(score, 4)


def rank_records(records, query: str, limit: int = 8) -> list[tuple[float, dict]]:
    ranked = []
    for record in records or []:
        if not isinstance(record, dict) or not record.get("id"):
            continue
        score = relevance_score(record, query)
        if score > 0:
            ranked.append((score, record))
    ranked.sort(key=lambda item: (-item[0], str(item[1].get("id") or "")))
    return ranked[: max(1, int(limit))]


def grounded_answer(record: dict) -> str:
    """Select the best existing reader-facing sentence from one validated record."""
    content = record.get("content") if isinstance(record.get("content"), dict) else {}
    reading = content.get("reading_levels") if isinstance(content.get("reading_levels"), dict) else {}
    short = reading.get("30 sec") if isinstance(reading.get("30 sec"), dict) else {}
    candidates = (
        content.get("key_message"),
        short.get("bottom_line"),
        short.get("what_happened"),
        record.get("summary"),
    )
    for candidate in candidates:
        text = str(candidate or "").strip()
        if text:
            return text
    return ""


def grounded_next_step(record: dict) -> str:
    """Select an action/watch sentence that already exists in the record."""
    content = record.get("content") if isinstance(record.get("content"), dict) else {}
    reading = content.get("reading_levels") if isinstance(content.get("reading_levels"), dict) else {}
    short = reading.get("30 sec") if isinstance(reading.get("30 sec"), dict) else {}
    action_plan = content.get("action_plan") if isinstance(content.get("action_plan"), dict) else {}
    candidates = (
        short.get("what_to_do_watch"),
        content.get("recommendation"),
        action_plan.get("goal"),
        content.get("what_next"),
    )
    for candidate in candidates:
        text = str(candidate or "").strip()
        if text:
            return text
    return ""


def _record_lens(record: dict) -> str:
    return CATEGORY_LABELS.get(str(record.get("_category") or record.get("category") or ""), "ALAM")


def _compact_record_line(record: dict) -> str:
    text = grounded_answer(record) or str(record.get("summary") or "").strip()
    if len(text) > 240:
        text = text[:237].rstrip() + "..."
    return text


def render_ask_alam(records, comments, manager, views) -> None:
    """Render retrieval-grounded Ask ALAM plus the matching source-story cards."""
    st.markdown(ASK_CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="hero mobile-hero"><div class="hero-kicker">✦ ASK ALAM · GROUNDED BETA</div>'
        '<div class="hero-title">Ask the verified corpus.</div>'
        '<div class="hero-copy">ALAM answers only when its screened agent records support the question. '
        'No model-memory fallback.</div></div>',
        unsafe_allow_html=True,
    )

    source_mode = str(st.session_state.get("alam_content_source") or "").strip()
    source_label = "live Supabase corpus" if source_mode == "supabase" else "validated audit fallback"
    st.caption(
        f"Evidence source: {source_label}. Your question text is used locally for retrieval and is not stored by this feature."
    )

    query = st.text_input(
        "Ask ALAM",
        placeholder="e.g. What changes for my visa renewal in October?",
        key="alam_ask_query",
    )
    lenses = st.multiselect(
        "Agent lenses",
        ["Discover", "Action", "Market", "Trends"],
        default=[],
        placeholder="All verified lenses",
        key="alam_ask_lenses",
    )
    category_by_label = {value: key for key, value in CATEGORY_LABELS.items()}
    allowed = {category_by_label[label] for label in lenses if label in category_by_label}
    pool = [
        record for record in (records or [])
        if not allowed or str(record.get("_category") or record.get("category") or "") in allowed
    ]

    if not str(query or "").strip():
        st.info(
            "Try a real question about Japan paperwork, household money, safety, markets, technology, or a topic ALAM has already researched."
        )
        return

    ranked = rank_records(pool, query, limit=8)
    if not ranked:
        st.warning(
            "INSUFFICIENT ALAM EVIDENCE — I found no screened current record that directly supports this question. "
            "Try broader wording or wait for the research agents to cover it."
        )
        return

    top_score, top = ranked[0]
    answer = grounded_answer(top)
    if not answer:
        st.warning("A relevant record exists, but it has no safe reader-facing answer sentence to reuse yet.")
        return

    confidence = top.get("confidence") or top.get("confidence_score")
    importance = top.get("importance") or top.get("importance_score")
    meta = [f"{_record_lens(top)} agent", f"retrieval score {top_score:.1f}"]
    if confidence is not None:
        meta.append(f"record confidence {confidence}/100")
    if importance is not None:
        meta.append(f"importance {importance}/100")

    st.markdown(
        '<div class="ask-shell">'
        '<div class="ask-kicker">Grounded answer</div>'
        f'<div class="ask-answer">{_escape(answer)}</div>'
        f'<div class="ask-meta">{" · ".join(_escape(x) for x in meta)}</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    next_step = grounded_next_step(top)
    if next_step:
        st.markdown("**What to do / watch**")
        st.write(next_step)

    # Surface the strongest record from each matched lens so the user can see whether
    # multiple specialized agents independently have relevant evidence. No artificial
    # disagreement is generated when a lens has nothing useful to add.
    by_lens: OrderedDict[str, dict] = OrderedDict()
    for _, record in ranked:
        lens = _record_lens(record)
        if lens not in by_lens:
            by_lens[lens] = record
    if len(by_lens) > 1:
        st.markdown("**Cross-agent evidence**")
        for lens, record in by_lens.items():
            st.markdown(
                f'<div class="ask-lens"><strong>{_escape(lens)}</strong><br>'
                f'<span>{_escape(_compact_record_line(record))}</span></div>',
                unsafe_allow_html=True,
            )

    st.markdown("**Open the evidence**")
    cols = st.columns(2, wrap=True)
    for index, (_, record) in enumerate(ranked[:6]):
        with cols[index % 2]:
            views.render_card(record, f"ask_alam_{index}", manager, comments)

    st.caption(
        "Ask ALAM currently performs deterministic evidence retrieval and refuses unsupported answers. "
        "A generative synthesis layer can be added later only if it cites these records and preserves the same refusal boundary."
    )


def _escape(value) -> str:
    """Escape tiny user/record snippets used in ALAM's controlled HTML cards."""
    text = str(value or "")
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )
