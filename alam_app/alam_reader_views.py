from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import json

import streamlit as st

import alam_intelligence as intelligence
import alam_local_state as localstate
from alam_core import feed_score, parse_dt, source_quality, story_versions


LENS_LABEL = {
    "discover": "Discover",
    "practical": "Practical",
    "reflection": "Market",
    "trend": "Trend",
}


def _open_story(record):
    st.session_state["selected_story"] = str(record.get("id"))
    st.rerun()


def _rank(record):
    return (intelligence.personal_relevance(record), feed_score(record))


def render_inbox(records, all_records, manager=None):
    unread = [r for r in records if localstate.is_unread(r)]
    changed = [r for r in unread if intelligence.change_snapshot(r, all_records)]
    actionable = [r for r in unread if intelligence._actionable(r)]
    unread.sort(key=_rank, reverse=True)
    changed.sort(key=_rank, reverse=True)
    actionable.sort(key=_rank, reverse=True)

    st.markdown(
        f"<div class='reader-inbox'><div><strong>📥 Intelligence inbox</strong><br>"
        f"<span>{len(unread)} unread · {len(changed)} materially changed · {len(actionable)} actionable</span></div></div>",
        unsafe_allow_html=True,
    )
    if not unread:
        st.caption("Caught up. New versions will become unread again when a story materially changes.")
        return

    mode = st.segmented_control(
        "Inbox",
        ["Unread", "Changed", "Actionable"],
        default="Unread",
        key="reader_inbox_mode",
        label_visibility="collapsed",
        width="stretch",
    )
    pool = unread if mode == "Unread" else changed if mode == "Changed" else actionable
    for i, record in enumerate(pool[:5]):
        lifecycle = intelligence.story_lifecycle(record, all_records)
        relevance = intelligence.personal_relevance(record)
        change = intelligence.change_snapshot(record, all_records)
        c1, c2 = st.columns([5, 1])
        with c1:
            st.markdown(f"**{record.get('title','')}**")
            if change and mode != "Actionable":
                st.caption(f"Changed · {change[1][:150]}")
            else:
                st.caption(f"{LENS_LABEL.get(record.get('_category'),'ALAM')} · {lifecycle} · relevance {relevance}/100")
        with c2:
            if st.button("Open", key=f"inbox_open_{i}_{record.get('id')}", use_container_width=True):
                _open_story(record)
    if len(pool) > 5:
        st.caption(f"+ {len(pool) - 5} more in this view")
    if st.button("Mark current stories read", key="inbox_mark_all", use_container_width=True):
        localstate.mark_all_read(records, manager)
        st.rerun()


def render_detail_reader_controls(record, manager=None):
    localstate.mark_read(record, manager)
    localstate.render_story_controls(record, intelligence.interest_hits(record), manager)


def _prediction_status(record):
    c = record.get("content") or {}
    candidates = [c.get("prediction_status"), c.get("status")]
    pred = c.get("prediction")
    if isinstance(pred, dict):
        candidates.insert(0, pred.get("status"))
    for value in candidates:
        status = str(value or "").upper().replace(" ", "_")
        if status in {"OPEN", "STRENGTHENING", "WEAKENING", "CONFIRMED", "PARTLY_CONFIRMED", "WRONG", "EXPIRED"}:
            return status
    return ""


def _audit_metrics(all_records, comments):
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    recent = [r for r in all_records if parse_dt(r.get("created_at")).astimezone(timezone.utc) >= cutoff]
    by_lens = defaultdict(list)
    for record in recent:
        by_lens[str(record.get("_category") or "discover")].append(record)
    comment_counts = Counter(str(c.get("agent") or "") for c in (comments or []))

    rows = []
    for lens in ("discover", "practical", "reflection", "trend"):
        items = by_lens.get(lens, [])
        facts = 0
        sourced_facts = 0
        sources = 0
        strong_sources = 0
        stories = set()
        changed = 0
        for record in items:
            stories.add(str(record.get("id")))
            total, strong = source_quality(record)
            sources += total
            strong_sources += strong
            claims = record.get("claims") or []
            for claim in claims:
                if isinstance(claim, dict) and str(claim.get("kind", "")).upper() == "FACT":
                    facts += 1
                    sourced_facts += bool(claim.get("source_refs"))
            if len(story_versions(all_records, record.get("id"))) > 1 and intelligence.change_snapshot(record, all_records):
                changed += 1
        rows.append({
            "lens": LENS_LABEL[lens],
            "stories": len(stories),
            "records": len(items),
            "strong_source_pct": round(100 * strong_sources / sources) if sources else 0,
            "fact_sourced_pct": round(100 * sourced_facts / facts) if facts else 100,
            "material_updates": changed,
            "comments": comment_counts.get(lens, 0),
        })
    return rows


def render_agent_audit(records, all_records, comments):
    st.markdown(
        "<div class='hero mobile-hero'><div class='hero-kicker'>🧪 ALAM AUDIT</div>"
        "<div class='hero-title'>Can the agents earn your trust?</div>"
        "<div class='hero-copy'>Measured evidence discipline and prediction outcomes from ALAM's own archive. No invented overall trust score.</div></div>",
        unsafe_allow_html=True,
    )
    rows = _audit_metrics(all_records, comments)
    cols = st.columns(2, wrap=True)
    for i, row in enumerate(rows):
        with cols[i % 2]:
            st.markdown(
                f"<div class='reader-audit-card'><div class='reader-audit-title'>{row['lens']}</div>"
                f"<div class='reader-audit-grid'><div><b>{row['stories']}</b><span>stories / 30d</span></div>"
                f"<div><b>{row['strong_source_pct']}%</b><span>primary-quality sources</span></div>"
                f"<div><b>{row['fact_sourced_pct']}%</b><span>FACT claims sourced</span></div>"
                f"<div><b>{row['material_updates']}</b><span>material updates</span></div></div></div>",
                unsafe_allow_html=True,
            )

    latest = {}
    for record in sorted(records, key=lambda r: parse_dt(r.get("created_at"))):
        latest[str(record.get("id"))] = record
    predictions = []
    for record in latest.values():
        status = _prediction_status(record)
        c = record.get("content") or {}
        if status or str(record.get("type", "")).lower() in {"prediction", "correction"} or "current_probability" in c:
            predictions.append((status or "OPEN", record))
    if predictions:
        counts = Counter(status for status, _ in predictions)
        resolved = counts["CONFIRMED"] + counts["PARTLY_CONFIRMED"] + counts["WRONG"]
        outcome_score = None
        if resolved:
            outcome_score = round(100 * (counts["CONFIRMED"] + 0.5 * counts["PARTLY_CONFIRMED"]) / resolved)
        st.markdown("#### Prediction scoreboard")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Confirmed", counts["CONFIRMED"])
        c2.metric("Partly", counts["PARTLY_CONFIRMED"])
        c3.metric("Wrong", counts["WRONG"])
        c4.metric("Open", counts["OPEN"] + counts["STRENGTHENING"] + counts["WEAKENING"])
        if outcome_score is not None:
            st.caption(f"Resolved outcome score: {outcome_score}/100. This is a simple accountability score, not statistical calibration or a probability-forecast Brier score.")
        wrong = [r for status, r in predictions if status == "WRONG"]
        if wrong:
            with st.expander("Show misses"):
                for record in wrong[:10]:
                    st.markdown(f"- **{record.get('title','')}**")
    else:
        st.info("No resolved prediction ledger entries yet. The scoreboard will populate as Trend closes forecasts.")

    changed = [r for r in records if intelligence.change_snapshot(r, all_records)]
    resolved = [r for r in records if intelligence.story_lifecycle(r, all_records) == "RESOLVED"]
    if changed or resolved:
        st.markdown("#### Accountability trail")
        st.caption(f"{len(changed)} current stories have a material change trail · {len(resolved)} are resolved")


def _briefing_markdown(records, all_records):
    ranked = sorted(records, key=_rank, reverse=True)
    lines = [
        "# ALAM Offline Briefing",
        "",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "## Today in 3 lines",
    ]
    for label, record in intelligence.daily_three(records):
        lines.extend([f"### {label} — {record.get('title','')}", str(record.get("summary") or record.get("why_it_matters") or ""), ""])
    lines.append("## Priority intelligence")
    for record in ranked[:12]:
        health, evidence = intelligence.evidence_health(record)
        lines.extend([
            f"### {record.get('title','')}",
            str(record.get("summary") or ""),
            f"- Lens: {LENS_LABEL.get(record.get('_category'),'ALAM')}",
            f"- Lifecycle: {intelligence.story_lifecycle(record, all_records)}",
            f"- Relevance: {intelligence.personal_relevance(record)}/100",
            f"- Evidence: {health} — {evidence}",
            "",
        ])
    return "\n".join(lines)


def render_offline_pack(records, all_records):
    st.markdown("#### Offline briefing pack")
    st.caption("Useful while traveling: save a clean snapshot of the current briefing before you lose connectivity.")
    payload = _briefing_markdown(records, all_records)
    st.download_button(
        "Download current briefing (.md)",
        data=payload,
        file_name="alam_offline_briefing.md",
        mime="text/markdown",
        use_container_width=True,
    )
    compact = [{k: r.get(k) for k in ("id", "created_at", "type", "title", "summary", "why_it_matters", "importance", "confidence", "status", "tags", "geography", "sources", "claims", "content")} for r in records[:50]]
    st.download_button(
        "Download current intelligence data (.json)",
        data=json.dumps(compact, ensure_ascii=False, indent=2),
        file_name="alam_current_intelligence.json",
        mime="application/json",
        use_container_width=True,
    )


def render_local_profile(records, manager=None):
    localstate.render_profile_tools(manager)
    muted = [r for r in records if localstate.is_muted(r)]
    if muted:
        with st.expander(f"Muted stories ({len(muted)})"):
            for i, record in enumerate(muted):
                c1, c2 = st.columns([5, 1])
                c1.markdown(f"**{record.get('title','')}**")
                if c2.button("Unmute", key=f"unmute_{i}_{record.get('id')}"):
                    localstate.toggle_muted(record, manager)
                    st.rerun()


READER_CSS = r"""
<style>
.reader-inbox{border:1px solid rgba(89,104,242,.16);background:rgba(244,245,255,.78);border-radius:16px;padding:10px 13px;margin:9px 0 8px;font-size:.82rem}.reader-inbox span{color:#667085}.reader-audit-card{background:rgba(255,255,255,.9);border:1px solid rgba(23,32,42,.09);border-radius:18px;padding:14px;margin:5px 0 10px}.reader-audit-title{font-weight:950;font-size:1.02rem;margin-bottom:9px}.reader-audit-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}.reader-audit-grid div{background:#F7F8FA;border-radius:12px;padding:9px}.reader-audit-grid b{display:block;font-size:1.05rem}.reader-audit-grid span{display:block;font-size:.65rem;color:#98A2B3;margin-top:2px}
@media(max-width:760px){.reader-audit-grid{grid-template-columns:1fr 1fr}}
</style>
"""
