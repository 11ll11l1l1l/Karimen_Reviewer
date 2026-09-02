"""Supabase-enhanced intelligence views for ALAM.

These views are additive: when Supabase data is absent or migration is incomplete,
they quietly fall back to the existing record-derived UI instead of breaking ALAM.
"""

from __future__ import annotations

import html

import streamlit as st

from alam_core import parse_dt
from alam_personas import comments_for_story, persona_for_comment
from alam_supabase import load_article_relationships, load_public_predictions


def _esc(value):
    return html.escape(str(value if value is not None else ""))


def _compact(value, limit=260):
    text = str(value or "").strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def render_change_summary(record):
    content = record.get("content") if isinstance(record.get("content"), dict) else {}
    change = content.get("change_summary") if isinstance(content.get("change_summary"), dict) else None
    if not change:
        return
    previous = change.get("previous")
    now = change.get("now")
    why = change.get("why_change_matters")
    if not any((previous, now, why)):
        return

    st.markdown("#### What changed")
    cols = st.columns(2)
    with cols[0]:
        st.markdown("**Before**")
        st.write(previous or "No previous material conclusion recorded.")
    with cols[1]:
        st.markdown("**Now**")
        st.write(now or "Current evidence changed the story.")
    if why:
        st.info(str(why))


def render_disagreement(record, comments):
    thread = comments_for_story(comments or [], record.get("id"))
    if not thread:
        return
    challenged = [c for c in thread if str(c.get("stance") or "").upper() == "CHALLENGE"]
    supporting = [c for c in thread if str(c.get("stance") or "").upper() in {"SUPPORT", "MIXED"}]
    if not challenged:
        return

    st.markdown("#### Agents disagree")
    st.caption("ALAM keeps material disagreement visible instead of forcing one synthetic consensus.")
    chosen = (challenged[:2] + supporting[:1])[:3]
    for comment in chosen:
        persona = persona_for_comment(comment)
        stance = str(comment.get("stance") or "MIXED").upper()
        st.markdown(
            f"**{_esc(persona.get('emoji'))} {_esc(persona.get('name'))} · {_esc(stance)}**  \n"
            f"{_esc(_compact(comment.get('body'), 420))}"
        )


def render_story_connections(record, current_records):
    if st.session_state.get("alam_content_source") != "supabase":
        return
    rows, error = load_article_relationships([record.get("id")])
    if error or not rows:
        return
    records_by_id = {str(r.get("id")): r for r in current_records}
    related = []
    current_id = str(record.get("id"))
    for row in rows:
        other_id = str(row.get("to_article_id")) if str(row.get("from_article_id")) == current_id else str(row.get("from_article_id"))
        other = records_by_id.get(other_id)
        if not other:
            continue
        related.append((float(row.get("strength") or 0), row, other))
    if not related:
        return

    st.markdown("#### Connect the dots")
    for index, (_, relation, other) in enumerate(sorted(related, key=lambda x: x[0], reverse=True)[:4]):
        explanation = relation.get("explanation") or relation.get("relationship") or "Related ALAM signal"
        st.markdown(f"**{_esc(other.get('title'))}**  \n{_esc(_compact(explanation, 260))}")
        if st.button("Open related story →", key=f"db_related_{record.get('id')}_{index}", use_container_width=True):
            st.session_state["selected_story"] = str(other.get("id"))
            st.rerun()


def render_connect_the_dots(records):
    if st.session_state.get("alam_content_source") != "supabase" or len(records) < 2:
        return
    ids = [r.get("id") for r in records if r.get("id")]
    relationships, error = load_article_relationships(ids)
    if error or not relationships:
        return

    records_by_id = {str(r.get("id")): r for r in records}
    usable = []
    for row in relationships:
        left = records_by_id.get(str(row.get("from_article_id")))
        right = records_by_id.get(str(row.get("to_article_id")))
        if not left or not right:
            continue
        usable.append((float(row.get("strength") or 0), row, left, right))
    if not usable:
        return

    st.markdown("#### Connect the Dots")
    st.caption("Structural overlaps between ALAM stories. Shared signals are not automatically treated as causal relationships.")
    for strength, row, left, right in sorted(usable, key=lambda x: x[0], reverse=True)[:8]:
        pct = max(0, min(100, int(round(strength * 100))))
        with st.expander(f"{left.get('title')} ↔ {right.get('title')}"):
            st.write(row.get("explanation") or row.get("relationship") or "Related signal")
            st.caption(f"Connection strength: {pct}% · relationship: {row.get('relationship')}")


def _status_label(status):
    value = str(status or "open").lower()
    return {
        "open": "OPEN",
        "correct": "CORRECT",
        "partially_correct": "PARTLY CORRECT",
        "incorrect": "INCORRECT",
        "unresolved": "UNRESOLVED",
    }.get(value, value.upper())


def render_prediction_lab(records, fallback_renderer):
    """Prefer the durable DB ledger; fall back to the legacy record-derived ledger."""
    if st.session_state.get("alam_content_source") != "supabase":
        fallback_renderer(records)
        return

    predictions, error = load_public_predictions()
    if error or not predictions:
        fallback_renderer(records)
        return

    st.markdown(
        '<div class="hero mobile-hero"><div class="hero-kicker" style="color:#C95E19">🔮 PREDICTIONS</div>'
        '<div class="hero-title">Track the forecast. Keep the mistakes.</div>'
        '<div class="hero-copy">Durable Supabase ledger: open calls, resolved calls, and misses stay visible.</div></div>',
        unsafe_allow_html=True,
    )

    resolved = [p for p in predictions if str(p.get("status")) != "open"]
    correct = [p for p in resolved if str(p.get("status")) == "correct"]
    partial = [p for p in resolved if str(p.get("status")) == "partially_correct"]
    if resolved:
        score = (len(correct) + 0.5 * len(partial)) / len(resolved) * 100
        st.caption(f"Resolved forecast score: {score:.0f}% across {len(resolved)} resolved predictions. Partial = 0.5 credit.")

    records_by_id = {str(r.get("id")): r for r in records}
    for index, prediction in enumerate(predictions):
        status = _status_label(prediction.get("status"))
        confidence = prediction.get("confidence")
        horizon = prediction.get("horizon")
        created = parse_dt(prediction.get("created_at"))
        meta = [status]
        if confidence is not None:
            try:
                meta.append(f"{float(confidence):.0f}%")
            except (TypeError, ValueError):
                pass
        if horizon:
            meta.append(str(horizon))
        st.markdown(
            f"**{_esc(prediction.get('claim'))}**  \n"
            f"{_esc(' · '.join(meta))} · {created.date().isoformat()}"
        )
        if prediction.get("resolution_notes"):
            st.caption(str(prediction.get("resolution_notes")))
        linked = records_by_id.get(str(prediction.get("article_id")))
        if linked and st.button("Open source story →", key=f"db_prediction_{index}", use_container_width=True):
            st.session_state["selected_story"] = str(linked.get("id"))
            st.rerun()
        st.divider()
