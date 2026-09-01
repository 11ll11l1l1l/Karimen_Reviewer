import json
import random
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import streamlit as st

from alam_core import (
    CATEGORY_META, CLAIM_META, FIELD_LABELS, age_label, category_meta,
    claim_counts, esc, feed_score, format_value, freshness_score,
    get_claims, is_followed, parse_dt, parse_yen, percent_value,
    reading_text, source_quality, story_versions, summarize_so_what,
    toggle_follow, type_label,
)
from alam_personas import PERSONAS, comments_for_story, persona_for_comment


def render_brand(records):
    latest = max((parse_dt(r.get("created_at")) for r in records), default=None)
    updated = age_label(latest) if latest else "waiting for first update"
    st.markdown(
        '<div class="alam-brand"><div class="alam-logo">ALAM '
        "<span>Ano'ng bago. Bakit mahalaga. Ano'ng gagawin.</span></div>"
        '<div class="live-pill"><span class="live-dot"></span> Updated '
        + esc(updated) + '</div></div>',
        unsafe_allow_html=True,
    )


def _claim_pills(record):
    counts = claim_counts(record)
    pills = []
    for kind in ("FACT", "INFERENCE", "ESTIMATE", "ASSUMPTION"):
        if counts[kind]:
            label, color, bg, _ = CLAIM_META[kind]
            pills.append(
                f'<span class="claim-dot" style="color:{color};background:{bg}">{label} {counts[kind]}</span>'
            )
    if not pills:
        pills.append('<span class="claim-dot" style="color:#667085;background:#F0F2F5">UNCLASSIFIED LEGACY RECORD</span>')
    return "".join(pills)


def _card_html(record):
    meta = category_meta(record)
    total, strong = source_quality(record)
    source_word = "source" if total == 1 else "sources"
    so_what = summarize_so_what(record)
    so_html = '<div class="so-what"><strong>So what?</strong> ' + esc(so_what) + '</div>' if so_what else ''
    return (
        '<div class="story-card">'
        f'<div class="story-accent" style="background:{meta["accent"]}"></div>'
        f'<div class="story-label" style="background:{meta["soft"]};color:{meta["accent"]}">{esc(type_label(record))}</div>'
        f'<div class="story-title">{esc(record.get("title", "Untitled"))}</div>'
        f'<div class="story-summary">{esc(record.get("summary", ""))}</div>'
        + so_html
        + f'<div class="claim-mini">{_claim_pills(record)}</div>'
        + '<div class="story-meta" style="margin-top:10px">'
        + f'<span>Importance {int(record.get("importance", 0) or 0)}</span>'
        + f'<span>Confidence {int(record.get("confidence", 0) or 0)}%</span>'
        + f'<span>{total} {source_word} · {strong} primary/official</span>'
        + f'<span>{esc(age_label(record.get("created_at")))}</span>'
        + '</div></div>'
    )


def _open_story(record):
    st.session_state["selected_story"] = str(record["id"])
    st.rerun()


def render_card(record, key, manager=None):
    st.markdown(_card_html(record), unsafe_allow_html=True)
    left, right = st.columns([3, 2])
    with left:
        if st.button("Basahin →", key=f"read_{key}", use_container_width=True):
            _open_story(record)
    with right:
        label = "✓ Binabantayan" if is_followed(record["id"]) else "+ Bantayan"
        if st.button(label, key=f"follow_{key}", use_container_width=True):
            toggle_follow(record["id"], manager)
            st.rerun()


def _render_since(records):
    ref = st.session_state.get("visit_reference")
    first = ref is None or getattr(ref, "year", 1970) <= 1970
    if first:
        ref = datetime.now(timezone.utc) - timedelta(hours=24)
    changed = [r for r in records if parse_dt(r.get("created_at")).astimezone(timezone.utc) > ref.astimezone(timezone.utc)]
    counts = {key: sum(1 for r in changed if r.get("_category") == key) for key in CATEGORY_META}
    label = "First visit: last 24h" if first else "Since you were gone"
    st.markdown(
        f'<div class="section-eyebrow">{esc(label)}</div><div class="metric-strip">'
        f'<div class="metric-mini"><div class="metric-value">{len(changed)}</div><div class="metric-label">meaningful updates</div></div>'
        f'<div class="metric-mini"><div class="metric-value">{counts["practical"]}</div><div class="metric-label">practical / risk</div></div>'
        f'<div class="metric-mini"><div class="metric-value">{counts["reflection"]}</div><div class="metric-label">reflections</div></div>'
        f'<div class="metric-mini"><div class="metric-value">{counts["trend"]}</div><div class="metric-label">trend updates</div></div></div>',
        unsafe_allow_html=True,
    )


def _pulse_score(records, category):
    subset = sorted([r for r in records if r.get("_category") == category], key=feed_score, reverse=True)[:5]
    if not subset:
        return 0
    values = [0.55 * float(r.get("importance", 50) or 50) + 0.45 * freshness_score(r.get("created_at")) for r in subset]
    return max(0, min(100, int(sum(values) / len(values))))


def _render_pulse(records):
    st.markdown('<div class="section-eyebrow">ALAM Pulse</div><div class="section-title">Gaano ka-active ang signals ngayon?</div>', unsafe_allow_html=True)
    cols = st.columns(4)
    scores = {}
    for col, key in zip(cols, CATEGORY_META):
        meta = CATEGORY_META[key]
        score = _pulse_score(records, key)
        scores[key] = score
        state = "Active" if score >= 70 else "Moving" if score >= 50 else "Quiet"
        with col:
            st.markdown(
                f'<div class="pulse-card"><div class="pulse-row"><strong>{meta["emoji"]} {esc(meta["label"])}</strong><span>{score} · {state}</span></div>'
                f'<div class="pulse-bar-bg"><div class="pulse-bar" style="width:{score}%;background:{meta["accent"]}"></div></div></div>',
                unsafe_allow_html=True,
            )
    if scores:
        strongest = max(scores, key=scores.get)
        st.caption(f"Pinakamalakas na signal: {CATEGORY_META[strongest]['label']} ({scores[strongest]}/100). Activity/importance signal ito, hindi danger score.")


def render_today(all_records, records, manager=None):
    if not records:
        st.info("Wala pang intelligence records.")
        return
    _render_since(records)
    _render_pulse(records)
    top = max(records, key=feed_score)
    recent = [r for r in records if parse_dt(r.get("created_at")) > datetime.now(timezone.utc) - timedelta(hours=24)]
    signal = min(100, int(sum(float(r.get("importance", 50) or 50) for r in recent) / len(recent) + min(20, len(recent) * 2))) if recent else 0
    st.markdown(
        '<div class="hero">'
        f'<div class="hero-kicker">Today\'s signal · {signal}/100</div>'
        f'<div class="hero-title">{esc(top.get("title", ""))}</div>'
        f'<div class="hero-copy">{esc(top.get("summary", ""))}</div></div>',
        unsafe_allow_html=True,
    )
    if st.button("Basahin ang top story →", key="hero_story"):
        _open_story(top)

    st.markdown('<div class="section-eyebrow">Intelligence map</div><div class="section-title">Apat na paraan para maintindihan ang mundo.</div>', unsafe_allow_html=True)
    cols = st.columns(4)
    for col, key in zip(cols, CATEGORY_META):
        meta = CATEGORY_META[key]
        count = sum(1 for r in records if r.get("_category") == key)
        with col:
            st.markdown(
                f'<div class="category-tile"><div class="category-icon">{meta["emoji"]}</div><div class="category-name">{esc(meta["label"])}</div>'
                f'<div class="category-q">{esc(meta["question"])}</div><div class="category-count" style="color:{meta["accent"]}">{count} live topics</div></div>',
                unsafe_allow_html=True,
            )

    growing = [r for r in records if r.get("_category") == "trend" and str((r.get("content") or {}).get("direction", "")).upper() == "ACCELERATING" and 45 <= int((r.get("content") or {}).get("current_strength", r.get("importance", 0)) or 0) < 85]
    if growing:
        st.markdown('<div class="section-eyebrow">Quietly becoming important</div><div class="section-title">Hindi pa headline — pero lumalakas ang signal.</div>', unsafe_allow_html=True)
        cols = st.columns(2)
        for i, record in enumerate(growing[:4]):
            with cols[i % 2]:
                render_card(record, f"quiet_{i}", manager)

    mode = st.radio("Catch-up", ["5 minutes lang ako", "May oras ako", "Surprise me"], horizontal=True, label_visibility="collapsed", key="today_mode")
    if mode == "5 minutes lang ako":
        picks = []
        for category in CATEGORY_META:
            subset = [r for r in records if r.get("_category") == category]
            if subset:
                picks.append(max(subset, key=feed_score))
    elif mode == "May oras ako":
        picks = sorted(records, key=feed_score, reverse=True)[:8]
    else:
        pool = sorted(records, key=feed_score, reverse=True)[:min(15, len(records))]
        picks = [random.Random(datetime.now().strftime("%Y-%m-%d-%H")).choice(pool)] if pool else []

    st.markdown('<div class="section-eyebrow">Para sa’yo ngayon</div>', unsafe_allow_html=True)
    cols = st.columns(2)
    for i, record in enumerate(picks):
        with cols[i % 2]:
            render_card(record, f"today_{i}", manager)


def render_category(records, category, manager=None):
    meta = CATEGORY_META[category]
    descriptions = {
        "discover": "Fresh developments na worth knowing — hindi basta trending lang.",
        "practical": "Tipid, safety, risk at Japan life advice na may totoong action.",
        "reflection": "Psychology, philosophy at modern Christian life — mas malalim kaysa headline.",
        "trend": "Patterns, predictions at signals na lumalakas, humihina, o bumabaliktad.",
    }
    st.markdown(
        f'<div class="hero" style="padding-top:32px;padding-bottom:32px"><div class="hero-kicker" style="color:{meta["accent"]}">{meta["emoji"]} {esc(meta["label"])}</div>'
        f'<div class="hero-title" style="font-size:clamp(2rem,4vw,3.5rem)">{esc(meta["question"])}</div><div class="hero-copy">{esc(descriptions[category])}</div></div>',
        unsafe_allow_html=True,
    )
    search = st.text_input("Hanapin", placeholder="Search topics, Japan, AI, money, faith…", key=f"search_{category}")
    subset = [r for r in records if r.get("_category") == category]
    if search:
        q = search.lower().strip()
        subset = [r for r in subset if q in json.dumps(r, ensure_ascii=False).lower()]
    if not subset:
        st.markdown('<div class="empty-box">Walang matching items ngayon.</div>', unsafe_allow_html=True)
        return
    if category == "trend":
        subset.sort(key=lambda r: (r.get("content") or {}).get("current_strength", r.get("importance", 0)), reverse=True)
    else:
        subset.sort(key=feed_score, reverse=True)
    cols = st.columns(2)
    for i, record in enumerate(subset):
        with cols[i % 2]:
            render_card(record, f"{category}_{i}", manager)


def render_action_center(records, manager=None):
    subset = [r for r in records if r.get("_category") == "practical"]
    st.markdown('<div class="hero" style="padding-top:32px;padding-bottom:32px"><div class="hero-kicker" style="color:#087D5B">🛡️ ACTION CENTER</div><div class="hero-title" style="font-size:clamp(2rem,4vw,3.4rem)">Ano ang dapat gawin, iwasan, o bantayan?</div><div class="hero-copy">Hindi lahat ng balita kailangan ng action. Dito lang ang may practical consequence.</div></div>', unsafe_allow_html=True)
    actions = defaultdict(int)
    for record in subset:
        actions[str((record.get("content") or {}).get("action", "WATCH")).upper()] += 1
    st.markdown(
        f'<div class="metric-strip"><div class="metric-mini"><div class="metric-value">{actions.get("DO NOW", 0) + actions.get("PREPARE", 0) + actions.get("APPLY", 0)}</div><div class="metric-label">do / prepare now</div></div>'
        f'<div class="metric-mini"><div class="metric-value">{actions.get("AVOID", 0)}</div><div class="metric-label">avoid</div></div>'
        f'<div class="metric-mini"><div class="metric-value">{actions.get("WATCH", 0) + actions.get("WAIT", 0)}</div><div class="metric-label">watch / wait</div></div>'
        f'<div class="metric-mini"><div class="metric-value">{len(subset)}</div><div class="metric-label">total practical items</div></div></div>',
        unsafe_allow_html=True,
    )
    cols = st.columns(2)
    for i, record in enumerate(sorted(subset, key=feed_score, reverse=True)):
        with cols[i % 2]:
            render_card(record, f"action_{i}", manager)
            content = record.get("content") or {}
            saving = content.get("estimated_saving_yen") or parse_yen(content.get("financial_impact"))
            minutes = content.get("time_minutes")
            travel = content.get("travel_minutes", 0) or 0
            if saving and minutes:
                try:
                    hourly = float(saving) / max(1, float(minutes) + float(travel)) * 60
                    verdict = "SULIT" if hourly >= 1500 else "MAYBE" if hourly >= 800 else "SKIP kung extra trip/effort"
                    st.caption(f"Sulit ba? ~¥{hourly:,.0f}/hour effort value → {verdict}")
                except (TypeError, ValueError):
                    pass


def render_prediction_lab(records):
    predictions = []
    for record in records:
        content = record.get("content") or {}
        is_prediction = str(record.get("type", "")).lower() in {"prediction", "correction"}
        if record.get("_category") == "trend" and (is_prediction or content.get("current_probability") is not None):
            predictions.append(record)
    st.markdown('<div class="hero" style="padding-top:32px;padding-bottom:32px"><div class="hero-kicker" style="color:#C95E19">🔮 PREDICTION LAB</div><div class="hero-title" style="font-size:clamp(2rem,4vw,3.4rem)">Track the forecast. Keep the mistakes.</div><div class="hero-copy">Hindi tinatago ang maling prediction. Calibration at self-correction ang goal.</div></div>', unsafe_allow_html=True)
    if not predictions:
        st.markdown('<div class="empty-box">Wala pang prediction ledger. Agent 5 will add one only when evidence supports a real forecast.</div>', unsafe_allow_html=True)
        return
    for i, record in enumerate(sorted(predictions, key=lambda r: parse_dt(r.get("created_at")), reverse=True)):
        content = record.get("content") or {}
        probability = percent_value(content.get("current_probability", content.get("initial_probability", 0)))
        status = str(content.get("status", record.get("status", "OPEN"))).upper()
        statement = content.get("statement") or record.get("title", "")
        st.markdown(
            f'<div class="story-card" style="margin-bottom:10px"><div class="story-title">{esc(statement)}</div><div class="kicker-row"><span class="small-muted">{esc(status)}</span><strong>{probability:.0f}%</strong></div>'
            f'<div class="trend-bar-bg"><div class="trend-bar" style="width:{probability}%;background:#C95E19"></div></div><div class="story-summary" style="margin-top:10px">{esc(record.get("summary", ""))}</div></div>',
            unsafe_allow_html=True,
        )
        if st.button("Open prediction →", key=f"prediction_{i}"):
            _open_story(record)


def render_following(records, manager=None):
    subset = [r for r in records if is_followed(r.get("id"))]
    st.markdown('<div class="hero" style="padding-top:32px;padding-bottom:32px"><div class="hero-kicker">👁️ FOLLOWING</div><div class="hero-title" style="font-size:clamp(2rem,4vw,3.4rem)">Mga story na binabantayan mo.</div><div class="hero-copy">Material updates sa same story ID appear here.</div></div>', unsafe_allow_html=True)
    if not subset:
        st.markdown('<div class="empty-box">Wala ka pang binabantayang topic. Tap “+ Bantayan” sa kahit anong story.</div>', unsafe_allow_html=True)
        return
    cols = st.columns(2)
    for i, record in enumerate(subset):
        with cols[i % 2]:
            render_card(record, f"following_{i}", manager)


def _render_reading_levels(record):
    level = st.radio("Reading depth", ["⚡ 30 sec", "📖 2 min", "🧠 Deep"], horizontal=True, key=f"reading_{record['id']}")
    mode = level.split(" ", 1)[1]
    if mode == "Deep":
        return True
    safe = esc(reading_text(record, mode)).replace("\n", "<br>")
    st.markdown(f'<div class="reading-box">{safe}</div>', unsafe_allow_html=True)
    return False


def _render_claims(record):
    st.markdown("#### Fact check layer")
    st.caption("FACT = directly sourced. INFERENCE = reasoned conclusion. ESTIMATE = calculated/reported estimate. ASSUMPTION = working assumption.")
    claims = get_claims(record)
    if not claims:
        st.warning("Legacy/unclassified record ito. Huwag i-assume na fact ang prose; check the sources below.")
        return
    for claim in claims:
        kind = claim.get("kind", "OPINION")
        if kind not in CLAIM_META:
            kind = "OPINION"
        label, color, bg, meaning = CLAIM_META[kind]
        refs = claim.get("source_refs") or claim.get("sources") or []
        if isinstance(refs, str):
            refs = [refs]
        refs_text = " · Source refs: " + ", ".join(str(x) for x in refs) if refs else ""
        basis = claim.get("basis") or meaning
        st.markdown(
            f'<div class="claim-box"><span class="claim-label" style="color:{color};background:{bg}">{label}</span> <span class="small-muted">{esc(basis + refs_text)}</span><div class="claim-text">{esc(claim.get("text", ""))}</div></div>',
            unsafe_allow_html=True,
        )


def _render_sources(record):
    st.markdown("#### Sources")
    sources = record.get("sources") or []
    if not sources:
        st.error("Walang source na naka-attach. Treat factual claims as unverified.")
        return
    for idx, source in enumerate(sources, start=1):
        publisher = source.get("publisher") or "Source"
        title = source.get("title") or publisher
        source_type = str(source.get("source_type") or "other").upper()
        published = source.get("published_at") or "date not supplied"
        url = source.get("url") or ""
        open_link = f' · <a href="{esc(url)}" target="_blank">Open source ↗</a>' if urlparse(url).scheme in {"http", "https"} else ""
        st.markdown(
            f'<div class="source-card"><div class="source-type">[{idx}] {esc(source_type)}</div><div class="source-title">{esc(publisher)} — {esc(title)}</div><div class="source-meta">Published/updated: {esc(published)}{open_link}</div></div>',
            unsafe_allow_html=True,
        )


def _render_pr_vs_reality(record):
    content = record.get("content") or {}
    payload = content.get("pr_vs_reality") or {}
    if not isinstance(payload, dict):
        payload = {}
    official = payload.get("official_claim") or content.get("official_framing")
    evidence = payload.get("evidence_says") or content.get("evidence_check")
    verdict = payload.get("verdict") or content.get("alam_verdict")
    if not any((official, evidence, verdict)):
        return
    verdict_html = f'<div class="verdict"><strong>ALAM verdict:</strong> {esc(verdict)}</div>' if verdict else ""
    st.markdown("#### PR vs Reality")
    st.markdown(
        f'<div class="pr-box"><div class="pr-cell"><div class="pr-head">What they say</div>{esc(official or "No formal PR/official claim captured.")}</div>'
        f'<div class="pr-cell"><div class="pr-head">What the evidence says</div>{format_value(evidence or "Evidence comparison not supplied.")}</div></div>{verdict_html}',
        unsafe_allow_html=True,
    )


def _render_timeline(all_records, record):
    versions = story_versions(all_records, record["id"])
    if len(versions) <= 1:
        return
    st.markdown("#### Story timeline — ano talaga ang nagbago?")
    parts = ['<div class="timeline">']
    for item in versions:
        content = item.get("content") or {}
        change = content.get("change_summary")
        if isinstance(change, dict):
            change_text = f"Dati: {change.get('previous') or '—'} → Ngayon: {change.get('now') or '—'}"
        else:
            change_text = str(change) if change else item.get("summary", "")
        dt = parse_dt(item.get("created_at")).strftime("%Y-%m-%d %H:%M")
        parts.append(
            f'<div class="timeline-item"><div class="timeline-date">{esc(dt)}</div><div class="timeline-title">Confidence {int(item.get("confidence", 0) or 0)}% · Importance {int(item.get("importance", 0) or 0)}</div><div class="timeline-change">{esc(change_text)}</div></div>'
        )
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


def _render_comments(record, comments):
    thread = comments_for_story(comments, record["id"])
    st.markdown("#### 💬 ALAM Comment Lounge")
    st.caption("Fictional AI editorial personas ito. They read the article and prior comments, then argue from deliberately different viewpoints.")
    if not thread:
        st.info("Tahimik pa ang lounge. Agents only comment when they have something new to add.")
    else:
        by_id = {str(c.get("id")): c for c in thread}
        for comment in thread:
            persona = persona_for_comment(comment)
            reply = by_id.get(str(comment.get("reply_to") or ""))
            reply_line = ""
            if reply:
                reply_persona = persona_for_comment(reply)
                reply_line = f"<div class='small-muted'>↳ replying to {esc(reply_persona['emoji'] + ' ' + reply_persona['name'])}</div>"
            article_refs = comment.get("article_source_refs") or []
            if isinstance(article_refs, str):
                article_refs = [article_refs]
            refs_line = "<div class='small-muted'>Uses article sources: " + esc(", ".join(str(x) for x in article_refs)) + "</div>" if article_refs else ""
            st.markdown(
                f'<div class="source-card"><div class="source-title">{esc(persona["emoji"] + " " + persona["name"])} <span class="small-muted">— {esc(persona.get("role", "Editorial Persona"))}</span></div>{reply_line}'
                f'<div class="detail-body" style="margin-top:6px">{esc(comment.get("body", ""))}</div>{refs_line}<div class="source-meta">{esc(age_label(comment.get("created_at")))}</div></div>',
                unsafe_allow_html=True,
            )
    st.markdown("**Meet the opposing voices**")
    cols = st.columns(4)
    for col, category in zip(cols, ("discover", "practical", "reflection", "trend")):
        with col:
            for persona in PERSONAS.get(category, []):
                st.caption(f"{persona['emoji']} **{persona['name']}** — {persona['role']}")


def _render_reflection_interaction(record):
    content = record.get("content") or {}
    questions = content.get("questions") or []
    if not isinstance(questions, list) or not questions:
        return
    st.markdown("#### Argue With Me")
    lead = questions[1] if len(questions) > 1 else questions[0]
    stance = st.radio(str(lead), ["Agree", "Unsure", "Disagree"], horizontal=True, key=f"stance_{record['id']}")
    if st.button("Show the strongest other side", key=f"other_{record['id']}"):
        st.session_state[f"show_other_{record['id']}"] = True
    if st.session_state.get(f"show_other_{record['id']}"):
        st.info(f"Strongest challenge: {content.get('secular_challenge') or 'No opposing argument supplied.'}")
        st.success(f"Strongest Christian response: {content.get('christian_response') or 'No Christian response supplied.'}")
        st.caption(f"Initial stance: {stance}. Walang score dito; tension ang point.")


def render_detail(all_records, record, comments, manager=None):
    if st.button("← Balik", key="back_detail"):
        st.session_state.pop("selected_story", None)
        st.rerun()
    meta = category_meta(record)
    total, strong = source_quality(record)
    tags = " · ".join(str(x) for x in record.get("tags", [])[:6])
    st.markdown(
        f'<div class="detail-shell"><div class="story-label" style="background:{meta["soft"]};color:{meta["accent"]}">{esc(type_label(record))}</div>'
        f'<div class="detail-title">{esc(record.get("title", ""))}</div><div class="detail-summary">{esc(record.get("summary", ""))}</div><div class="story-meta" style="margin-top:16px">'
        f'<span>Importance {int(record.get("importance", 0) or 0)}</span><span>Confidence {int(record.get("confidence", 0) or 0)}%</span><span>{total} sources · {strong} primary/official</span><span>{esc(age_label(record.get("created_at")))}</span><span>{esc(tags)}</span></div></div>',
        unsafe_allow_html=True,
    )
    left, right = st.columns([2, 1])
    with left:
        deep = _render_reading_levels(record)
    with right:
        label = "✓ Binabantayan" if is_followed(record["id"]) else "+ Bantayan ang story"
        if st.button(label, key=f"detail_follow_{record['id']}", use_container_width=True):
            toggle_follow(record["id"], manager)
            st.rerun()
    if not deep:
        _render_claims(record)
        _render_sources(record)
        _render_comments(record, comments)
        return
    if record.get("why_it_matters"):
        st.markdown(f'<div class="detail-section"><div class="detail-heading">Bakit mahalaga</div><div class="detail-body">{esc(record.get("why_it_matters"))}</div></div>', unsafe_allow_html=True)
    _render_pr_vs_reality(record)
    _render_claims(record)
    content = record.get("content") or {}
    skip = {"usefulness", "novelty", "history", "reading_levels", "pr_vs_reality", "facts", "inferences", "assumptions", "estimates", "change_summary", "estimated_saving_yen", "time_minutes", "travel_minutes", "official_framing", "evidence_check", "alam_verdict", "what_would_change_mind"}
    for key, value in content.items():
        if key in skip or value in ("", None, [], {}):
            continue
        if key == "questions" and record.get("_category") == "reflection":
            continue
        heading = FIELD_LABELS.get(key, key.replace("_", " ").title())
        st.markdown(f'<div class="detail-section"><div class="detail-heading">{esc(heading)}</div><div class="detail-body">{format_value(value)}</div></div>', unsafe_allow_html=True)
    mind_change = content.get("what_would_change_mind") or content.get("what_next")
    if mind_change:
        st.markdown(f'<div class="mind-change"><strong>What would change our mind?</strong><br>{esc(mind_change)}</div>', unsafe_allow_html=True)
    if record.get("_category") == "reflection":
        _render_reflection_interaction(record)
    _render_timeline(all_records, record)
    history = content.get("history")
    if isinstance(history, list) and history:
        st.markdown("#### Galaw ng signal")
        for point in history[-10:]:
            value = max(0, min(100, int(point.get("value", 0) or 0)))
            st.markdown(f'<div style="margin:10px 0"><div class="kicker-row"><span class="small-muted">{esc(point.get("label", ""))}</span><strong>{value}%</strong></div><div class="trend-bar-bg"><div class="trend-bar" style="width:{value}%;background:{meta["accent"]}"></div></div></div>', unsafe_allow_html=True)
    _render_sources(record)
    _render_comments(record, comments)


def render_footer(all_records, records, comments):
    live = [r for r in records if not r.get("demo")]
    st.markdown("---")
    st.caption(f"ALAM • {len(records)} current topics • {len(all_records)} historical records • {len(live)} live current records • {len(comments)} persona comments. FACT labels require source support; inference and assumptions are shown separately.")
