import json
import random
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import streamlit as st

from alam_core import *
from alam_personas import PERSONAS, comments_for_story, persona_for_comment


def render_brand(records):
    latest = max((parse_dt(r.get("created_at")) for r in records), default=None)
    updated = age_label(latest) if latest else "waiting"
    st.markdown(
        f'<div class="alam-brand"><div class="alam-logo">ALAM '
        f'<span>Ano\'ng bago. Bakit mahalaga. Ano\'ng gagawin.</span></div>'
        f'<div class="live-pill"><span class="live-dot"></span> Updated {esc(updated)}</div></div>',
        unsafe_allow_html=True,
    )


def card_html(record):
    meta = category_meta(record)
    counts = claim_counts(record)
    total, strong = source_quality(record)
    pills = []
    for kind in ("FACT", "INFERENCE", "ASSUMPTION", "ESTIMATE"):
        if counts[kind]:
            label, color, bg, _ = CLAIM_META[kind]
            pills.append(
                f'<span class="claim-dot" style="color:{color};background:{bg}">'
                f'{label} {counts[kind]}</span>'
            )
    if not pills:
        pills.append(
            '<span class="claim-dot" style="color:#667085;background:#F0F2F5">'
            'UNCLASSIFIED LEGACY RECORD</span>'
        )
    so_what = summarize_so_what(record)
    so_html = (
        f'<div class="so-what"><strong>So what?</strong> {esc(so_what)}</div>'
        if so_what
        else ""
    )
    source_word = "source" if total == 1 else "sources"
    return (
        f'<div class="story-card">'
        f'<div class="story-accent" style="background:{meta["accent"]}"></div>'
        f'<div class="story-label" style="background:{meta["soft"]};color:{meta["accent"]}">'
        f'{esc(type_label(record))}</div>'
        f'<div class="story-title">{esc(record.get("title"))}</div>'
        f'<div class="story-summary">{esc(record.get("summary", ""))}</div>'
        f'{so_html}'
        f'<div class="claim-mini'>{"".join(pills)}</div>'
        f'<div class="story-meta" style="margin-top:10px">'
        f'<span>Importance {int(record.get("importance", 0) or 0)}</span>'
        f'<span>Confidence {int(record.get("confidence", 0) or 0)}%</span>'
        f'<span>{total} {source_word} · {strong} primary/official</span>'
        f'<span>{esc(age_label(record.get("created_at")))}</span>'
        f'</div></div>'
    )


def render_card(record, key, manager=None):
    st.markdown(card_html(record), unsafe_allow_html=True)
    a, b = st.columns([3, 2])
    with a:
        if st.button("Basahin →", key=f"read_{key}", use_container_width=True):
            st.session_state["selected_story"] = str(record["id"])
            st.rerun()
    with b:
        label = "✓ Binabantayan" if is_followed(record["id"]) else "+ Bantayan"
        if st.button(label, key=f"follow_{key}", use_container_width=True):
            toggle_follow(record["id"], manager)
            st.rerun()


def render_since(records):
    ref = st.session_state.get("visit_reference")
    first = ref is None or ref.year <= 1970
    if first:
        ref = datetime.now(timezone.utc) - timedelta(hours=24)
    changed = [
        r for r in records
        if parse_dt(r.get("created_at")).astimezone(timezone.utc) > ref.astimezone(timezone.utc)
    ]
    counts = {k: sum(r.get("_category") == k for r in changed) for k in CATEGORY_META}
    st.markdown(
        f'<div class="section-eyebrow">'
        f'{"First visit: last 24h" if first else "Since you were gone"}</div>'
        f'<div class="metric-strip">'
        f'<div class="metric-mini"><div class="metric-value">{len(changed)}</div>'
        f'<div class="metric-label">meaningful updates</div></div>'
        f'<div class="metric-mini"><div class="metric-value">{counts["practical"]}</div>'
        f'<div class="metric-label">practical / risk</div></div>'
        f'<div class="metric-mini"><div class="metric-value">{counts["reflection"]}</div>'
        f'<div class="metric-label">reflections</div></div>'
        f'<div class="metric-mini"><div class="metric-value">{counts["trend"]}</div>'
        f'<div class="metric-label">trend updates</div></div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_pulse(records):
    st.markdown(
        '<div class="section-eyebrow">ALAM Pulse</div>'
        '<div class="section-title">Gaano ka-active ang signals ngayon?</div>',
        unsafe_allow_html=True,
    )
    cols = st.columns(4)
    scores = {}
    for col, key in zip(cols, CATEGORY_META):
        subset = sorted(
            [r for r in records if r.get("_category") == key],
            key=feed_score,
            reverse=True,
        )[:5]
        score = (
            int(
                sum(
                    .55 * float(r.get("importance", 50) or 50)
                    + .45 * freshness_score(r.get("created_at"))
                    for r in subset
                ) / len(subset)
            )
            if subset else 0
        )
        scores[key] = score
        meta = CATEGORY_META[key]
        state = "Active" if score >= 70 else "Moving" if score >= 50 else "Quiet"
        with col:
            st.markdown(
                f'<div class="pulse-card"><div class="pulse-row">'
                f'<strong>{meta["emoji"]} {meta["label"]}</strong>'
                f'<span>{score} · {state}</span></div>'
                f'<div class="pulse-bar-bg"><div class="pulse-bar" '
                f'style="width:{score}%;background:{meta["accent"]}"></div></div></div>',
                unsafe_allow_html=True,
            )
    if scores:
        strongest = max(scores, key=scores.get)
        st.caption(
            f"Pinakamalakas na signal: {CATEGORY_META[strongest]['label']} "
            f"({scores[strongest]}/100). Activity/importance signal ito, hindi danger score."
        )


def render_today(all_records, records, manager=None):
    if not records:
        st.info("Wala pang intelligence records.")
        return
    render_since(records)
    render_pulse(records)
    top = max(records, key=feed_score)
    recent = [
        r for r in records
        if parse_dt(r.get("created_at")) > datetime.now(timezone.utc) - timedelta(hours=24)
    ]
    signal = (
        min(
            100,
            int(
                sum(float(r.get("importance", 50) or 50) for r in recent)
                / max(1, len(recent))
                + min(20, len(recent) * 2)
            ),
        )
        if recent else 0
    )
    st.markdown(
        f'<div class="hero"><div class="hero-kicker">Today\'s signal · {signal}/100</div>'
        f'<div class="hero-title">{esc(top.get("title"))}</div>'
        f'<div class="hero-copy">{esc(top.get("summary", ""))}</div></div>',
        unsafe_allow_html=True,
    )
    if st.button("Basahin ang top story →", key="hero"):
        st.session_state["selected_story"] = str(top["id"])
        st.rerun()

    st.markdown(
        '<div class="section-eyebrow">Intelligence map</div>'
        '<div class="section-title">Apat na paraan para maintindihan ang mundo.</div>',
        unsafe_allow_html=True,
    )
    cols = st.columns(4)
    for col, key in zip(cols, CATEGORY_META):
        meta = CATEGORY_META[key]
        count = sum(r.get("_category") == key for r in records)
        with col:
            st.markdown(
                f'<div class="category-tile"><div class="category-icon">{meta["emoji"]}</div>'
                f'<div class="category-name">{meta["label"]}</div>'
                f'<div class="category-q">{meta["question"]}</div>'
                f'<div class="category-count" style="color:{meta["accent"]}">{count} live topics</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    growing = [
        r for r in records
        if r.get("_category") == "trend"
        and str((r.get("content") or {}).get("direction", "")).upper() == "ACCELERATING"
        and 45 <= int((r.get("content") or {}).get("current_strength", r.get("importance", 0)) or 0) < 85
    ]
    if growing:
        st.markdown(
            '<div class="section-eyebrow">Quietly becoming important</div>'
            '<div class="section-title">Hindi pa headline — pero lumalakas ang signal.</div>',
            unsafe_allow_html=True,
        )
        cols = st.columns(2)
        for i, r in enumerate(growing[:4]):
            with cols[i % 2]:
                render_card(r, f"quiet_{i}", manager)

    mode = st.radio(
        "Catch-up",
        ["5 minutes lang ako", "May oras ako", "Surprise me"],
        horizontal=True,
        label_visibility="collapsed",
    )
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
        picks = [random.Random(datetime.now().strftime("%Y-%m-%d-%H")).choice(pool)]

    st.markdown('<div class="section-eyebrow">Para sa’yo ngayon</div>', unsafe_allow_html=True)
    cols = st.columns(2)
    for i, r in enumerate(picks):
        with cols[i % 2]:
            render_card(r, f"today_{i}", manager)


def render_category(records, category, manager=None):
    meta = CATEGORY_META[category]
    copy = {
        "discover": "Fresh developments na worth knowing — hindi basta trending lang.",
        "practical": "Tipid, safety, risk at Japan life advice na may totoong action.",
        "reflection": "Psychology, philosophy at modern Christian life — mas malalim kaysa headline.",
        "trend": "Patterns, predictions at signals na lumalakas, humihina, o bumabaliktad.",
    }[category]
    st.markdown(
        f'<div class="hero" style="padding-top:32px;padding-bottom:32px">'
        f'<div class="hero-kicker" style="color:{meta["accent"]}">{meta["emoji"]} {meta["label"]}</div>'
        f'<div class="hero-title" style="font-size:clamp(2rem,4vw,3.5rem)">{esc(meta["question"])}</div>'
        f'<div class="hero-copy">{esc(copy)}</div></div>',
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
    for i, r in enumerate(subset):
        with cols[i % 2]:
            render_card(r, f"{category}_{i}", manager)


def render_action_center(records, manager=None):
    subset = [r for r in records if r.get("_category") == "practical"]
    st.markdown(
        '<div class="hero" style="padding-top:32px;padding-bottom:32px">'
        '<div class="hero-kicker" style="color:#087D5B">🛡️ ACTION CENTER</div>'
        '<div class="hero-title" style="font-size:clamp(2rem,4vw,3.4rem)">'
        'Ano ang dapat gawin, iwasan, o bantayan?</div>'
        '<div class="hero-copy">Hindi lahat ng balita kailangan ng action. Dito lang ang may practical consequence.</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    actions = defaultdict(int)
    for r in subset:
        actions[str((r.get("content") or {}).get("action", "WATCH")).upper()] += 1
    st.markdown(
        f'<div class="metric-strip">'
        f'<div class="metric-mini"><div class="metric-value">{actions.get("DO NOW",0)+actions.get("PREPARE",0)+actions.get("APPLY",0)}</div><div class="metric-label">do / prepare now</div></div>'
        f'<div class="metric-mini"><div class="metric-value">{actions.get("AVOID",0)}</div><div class="metric-label">avoid</div></div>'
        f'<div class="metric-mini"><div class="metric-value">{actions.get("WATCH",0)+actions.get("WAIT",0)}</div><div class="metric-label">watch / wait</div></div>'
        f'<div class="metric-mini"><div class="metric-value">{len(subset)}</div><div class="metric-label">total practical items</div></div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    cols = st.columns(2)
    for i, r in enumerate(sorted(subset, key=feed_score, reverse=True)):
        with cols[i % 2]:
            render_card(r, f"action_{i}", manager)
            c = r.get("content") or {}
            saving = c.get("estimated_saving_yen") or parse_yen(c.get("financial_impact"))
            minutes = c.get("time_minutes")
            travel = c.get("travel_minutes", 0) or 0
            if saving and minutes:
                try:
                    hourly = float(saving) / max(1, float(minutes) + float(travel)) * 60
                    verdict = "SULIT" if hourly >= 1500 else "MAYBE" if hourly >= 800 else "SKIP kung extra trip/effort"
                    st.caption(f"Sulit ba? ~¥{hourly:,.0f}/hour effort value → {verdict}")
                except Exception:
                    pass


def render_prediction_lab(records):
    predictions = [
        r for r in records
        if r.get("_category") == "trend"
        and (
            str(r.get("type", "")).lower() in {"prediction", "correction"}
            or (r.get("content") or {}).get("current_probability") is not None
        )
    ]
    st.markdown(
        '<div class="hero" style="padding-top:32px;padding-bottom:32px">'
        '<div class="hero-kicker" style="color:#C95E19">🔮 PREDICTION LAB</div>'
        '<div class="hero-title" style="font-size:clamp(2rem,4vw,3.4rem)">'
        'Track the forecast. Keep the mistakes.</div>'
        '<div class="hero-copy">Hindi tinatago ang maling prediction. Calibration ang goal.</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    statuses = defaultdict(int)
    for r in predictions:
        statuses[str((r.get("content") or {}).get("status", r.get("status", "OPEN"))).upper()] += 1
    st.markdown(
        f'<div class="metric-strip">'
        f'<div class="metric-mini"><div class="metric-value">{statuses.get("CONFIRMED",0)}</div><div class="metric-label">confirmed</div></div>'
        f'<div class="metric-mini"><div class="metric-value">{statuses.get("PARTLY_CONFIRMED",0)}</div><div class="metric-label">partly correct</div></div>'
        f'<div class="metric-mini"><div class="metric-value">{statuses.get("WRONG",0)}</div><div class="metric-label">wrong</div></div>'
        f'<div class="metric-mini"><div class="metric-value">{sum(v for k,v in statuses.items() if k in {"OPEN","STRENGTHENING","WEAKENING"})}</div><div class="metric-label">open</div></div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    if not predictions:
        st.info("Wala pang prediction ledger.")
        return
    for i, r in enumerate(sorted(predictions, key=lambda x: parse_dt(x.get("created_at")), reverse=True)):
        c = r.get("content") or {}
        p = percent_value(c.get("current_probability", c.get("initial_probability", 0)))
        status = str(c.get("status", r.get("status", "OPEN"))).upper()
        st.markdown(
            f'<div class="story-card" style="margin-bottom:10px">'
            f'<div class="story-title">{esc(c.get("statement") or r.get("title"))}</div>'
            f'<div class="kicker-row"><span class="small-muted">{esc(status)}</span><strong>{p:.0f}%</strong></div>'
            f'<div class="trend-bar-bg"><div class="trend-bar" style="width:{p}%;background:#C95E19"></div></div>'
            f'<div class="story-summary" style="margin-top:10px">{esc(r.get("summary",""))}</div></div>',
            unsafe_allow_html=True,
        )
        if st.button("Open prediction →", key=f"pred_{i}"):
            st.session_state["selected_story"] = str(r["id"])
            st.rerun()


def render_following(records, manager=None):
    followed = set(st.session_state.get("followed_stories", []))
    subset = [r for r in records if str(r.get("id")) in followed]
    st.markdown(
        '<div class="hero" style="padding-top:32px;padding-bottom:32px">'
        '<div class="hero-kicker">👁️ FOLLOWING</div>'
        '<div class="hero-title" style="font-size:clamp(2rem,4vw,3.4rem)">Mga story na binabantayan mo.</div>'
        '<div class="hero-copy">Kapag may material update sa same story ID, makikita rito ang latest state.</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    if not subset:
        st.info('Wala ka pang binabantayang topic. Tap "+ Bantayan" sa isang story.')
        return
    cols = st.columns(2)
    for i, r in enumerate(subset):
        with cols[i % 2]:
            render_card(r, f"following_{i}", manager)


def render_claims(record):
    st.markdown("#### Fact check layer")
    st.caption("FACT = source-backed. INFERENCE / ESTIMATE / ASSUMPTION are explicitly separate.")
    claims = get_claims(record)
    if not claims:
        st.warning("Legacy/unclassified record. Huwag i-assume na fact ang prose; check the sources.")
        return
    for c in claims:
        kind = c["kind"]
        label, color, bg, meaning = CLAIM_META[kind]
        refs = c.get("source_refs") or []
        if isinstance(refs, str):
            refs = [refs]
        ref_text = f" · source refs {', '.join(map(str, refs))}" if refs else ""
        st.markdown(
            f'<div class="claim-box"><span class="claim-label" style="color:{color};background:{bg}">'
            f'{label}</span> <span class="small-muted">{esc(c.get("basis") or meaning)}{esc(ref_text)}</span>'
            f'<div class="claim-text" style="margin-top:6px">{esc(c.get("text",""))}</div></div>',
            unsafe_allow_html=True,
        )


def render_sources(record):
    st.markdown("#### Sources")
    sources = record.get("sources") or []
    if not sources:
        st.error("Walang attached source. Treat factual claims as unverified.")
        return
    for i, s in enumerate(sources, start=1):
        url = s.get("url") or ""
        link = f'<a href="{esc(url)}" target="_blank">Open source ↗</a>' if urlparse(url).scheme in {"http","https"} else ""
        st.markdown(
            f'<div class="source-card"><div class="source-type">[{i}] {esc(str(s.get("source_type") or "other").upper())}</div>'
            f'<div class="source-title">{esc(s.get("publisher") or "Source")} — {esc(s.get("title") or "")}</div>'
            f'<div class="source-meta">{esc(s.get("published_at") or "date not supplied")} · {link}</div></div>',
            unsafe_allow_html=True,
        )


def render_pr_vs_reality(record):
    c = record.get("content") or {}
    pr = c.get("pr_vs_reality") or {}
    official = pr.get("official_claim") or c.get("official_framing")
    evidence = pr.get("evidence_says") or c.get("evidence_check")
    verdict = pr.get("verdict") or c.get("alam_verdict")
    if not official and not evidence and not verdict:
        return
    st.markdown("#### PR vs Reality")
    st.markdown(
        f'<div class="pr-box"><div class="pr-cell"><div class="pr-head">What they say</div>'
        f'<div>{esc(official or "No formal claim captured.")}</div></div>'
        f'<div class="pr-cell"><div class="pr-head">What the evidence says</div>'
        f'<div>{format_value(evidence or "Evidence comparison not supplied.")}</div></div></div>',
        unsafe_allow_html=True,
    )
    if verdict:
        st.markdown(f'<div class="verdict"><strong>ALAM verdict</strong><br>{esc(verdict)}</div>', unsafe_allow_html=True)


def render_timeline(all_records, record):
    versions = story_versions(all_records, record["id"])
    if len(versions) <= 1:
        return
    st.markdown("#### Story timeline — ano talaga ang nagbago?")
    parts = ['<div class="timeline">']
    for item in versions:
        c = item.get("content") or {}
        change = c.get("change_summary") or {}
        if isinstance(change, dict) and (change.get("previous") or change.get("now")):
            text = f'Dati: {change.get("previous") or "—"} → Ngayon: {change.get("now") or "—"}'
        else:
            text = item.get("summary", "")
        parts.append(
            f'<div class="timeline-item"><div class="timeline-date">{parse_dt(item.get("created_at")).strftime("%Y-%m-%d %H:%M")}</div>'
            f'<div class="timeline-title">Confidence {int(item.get("confidence",0) or 0)}% · Importance {int(item.get("importance",0) or 0)}</div>'
            f'<div class="timeline-change">{esc(text)}</div></div>'
        )
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


def render_comments(record, comments):
    thread = comments_for_story(comments, record["id"])
    st.markdown("#### 💬 ALAM Comment Lounge")
    st.caption(
        "AI editorial personas ito, hindi real people. Binabasa nila ang article at comments above bago mag-comment. "
        "Humor is allowed; bagong factual claims still need evidence."
    )
    if not thread:
        st.info("Wala pang panel comment sa story na ito. Future agent runs can pick it up.")
    by_id = {str(c.get("id")): c for c in thread}
    for c in thread:
        persona = persona_for_comment(c)
        parent = by_id.get(str(c.get("reply_to"))) if c.get("reply_to") else None
        parent_text = f' replying to {persona_for_comment(parent)["name"]}' if parent else ""
        indent = 22 if parent else 0
        st.markdown(
            f'<div class="claim-box" style="margin-left:{indent}px">'
            f'<div><strong>{persona["emoji"]} {esc(persona["name"])}</strong> '
            f'<span class="small-muted">· {esc(persona["role"])} · {esc(age_label(c.get("created_at")))}{esc(parent_text)}</span></div>'
            f'<div class="claim-text" style="margin-top:6px">{esc(c.get("body",""))}</div></div>',
            unsafe_allow_html=True,
        )
        if c.get("article_source_refs"):
            st.caption(f"Article source refs used: {', '.join(map(str, c['article_source_refs']))}")
        if c.get("sources"):
            with st.expander(f"Sources for {persona['name']}'s comment"):
                for s in c["sources"]:
                    if urlparse(s.get("url") or "").scheme in {"http","https"}:
                        st.markdown(f"- [{s.get('publisher','Source')} — {s.get('title','')}]({s.get('url')})")
                    else:
                        st.markdown(f"- {s.get('publisher','Source')} — {s.get('title','')}")
    st.markdown("**The cast**")
    cast_cols = st.columns(4)
    for col, (agent, pair) in zip(cast_cols, PERSONAS.items()):
        with col:
            st.markdown(
                f"**{CATEGORY_META[agent]['emoji']} {CATEGORY_META[agent]['label']}**  \n"
                f"{pair[0]['emoji']} {pair[0]['name']} vs {pair[1]['emoji']} {pair[1]['name']}"
            )


def render_reflection_interaction(record):
    c = record.get("content") or {}
    questions = c.get("questions") or []
    if not questions:
        return
    st.markdown("#### Argue With Me")
    lead = questions[1] if len(questions) > 1 else questions[0]
    st.markdown(f"**{lead}**")
    answer = st.radio("Ano ang instinctive answer mo?", ["Agree", "Unsure", "Disagree"], horizontal=True, key=f"argue_{record['id']}")
    if st.button("Show the strongest other side", key=f"reveal_{record['id']}"):
        st.session_state[f"reveal_{record['id']}"] = True
    if st.session_state.get(f"reveal_{record['id']}"):
        st.info(f"Strongest challenge: {c.get('secular_challenge') or 'No opposing argument supplied.'}")
        st.success(f"Strongest Christian response: {c.get('christian_response') or 'No response supplied.'}")
        st.caption(f"Your first instinct: {answer}. Hindi ito score — tension test ito.")
    st.markdown("**Tatlong tanong:**")
    for q in questions[:3]:
        st.markdown(f"- {q}")


def render_detail(all_records, record, comments, manager=None):
    if st.button("← Balik"):
        st.session_state.pop("selected_story", None)
        st.rerun()
    meta = category_meta(record)
    total, strong = source_quality(record)
    st.markdown(
        f'<div class="detail-shell"><div class="story-label" style="background:{meta["soft"]};color:{meta["accent"]}">{esc(type_label(record))}</div>'
        f'<div class="detail-title">{esc(record.get("title"))}</div>'
        f'<div class="detail-summary">{esc(record.get("summary",""))}</div>'
        f'<div class="story-meta" style="margin-top:16px"><span>Importance {int(record.get("importance",0) or 0)}</span>'
        f'<span>Confidence {int(record.get("confidence",0) or 0)}%</span><span>{total} sources · {strong} primary/official</span>'
        f'<span>{esc(age_label(record.get("created_at")))}</span></div></div>',
        unsafe_allow_html=True,
    )
    a, b = st.columns([3, 1])
    with a:
        level = st.radio("Reading depth", ["⚡ 30 sec", "📖 2 min", "🧠 Deep"], horizontal=True, key=f"reading_{record['id']}")
    with b:
        if st.button("✓ Binabantayan" if is_followed(record["id"]) else "+ Bantayan", use_container_width=True, key=f"detail_follow_{record['id']}"):
            toggle_follow(record["id"], manager)
            st.rerun()
    simple = level.split(" ", 1)[1]
    if simple != "Deep":
        st.markdown(f'<div class="reading-box">{esc(reading_text(record, simple)).replace(chr(10), "<br>")}</div>', unsafe_allow_html=True)
        render_claims(record)
        render_sources(record)
        render_comments(record, comments)
        return

    if record.get("why_it_matters"):
        st.markdown(
            f'<div class="detail-section"><div class="detail-heading">Bakit mahalaga</div>'
            f'<div class="detail-body">{esc(record.get("why_it_matters"))}</div></div>',
            unsafe_allow_html=True,
        )
    render_pr_vs_reality(record)
    render_claims(record)
    c = record.get("content") or {}
    skip = {
        "usefulness","novelty","history","reading_levels","pr_vs_reality","facts","inferences","assumptions",
        "estimates","change_summary","estimated_saving_yen","time_minutes","travel_minutes","official_framing",
        "evidence_check","alam_verdict","questions","what_would_change_mind",
    }
    for key, value in c.items():
        if key in skip or value in ("", None, [], {}):
            continue
        st.markdown(
            f'<div class="detail-section"><div class="detail-heading">{esc(FIELD_LABELS.get(key, key.replace("_"," ").title()))}</div>'
            f'<div class="detail-body">{format_value(value)}</div></div>',
            unsafe_allow_html=True,
        )
    mind = c.get("what_would_change_mind") or c.get("what_next")
    if mind:
        st.markdown(f'<div class="mind-change"><strong>What would change our mind?</strong><br>{esc(mind)}</div>', unsafe_allow_html=True)
    if record.get("_category") == "reflection":
        render_reflection_interaction(record)
    render_timeline(all_records, record)
    history = c.get("history")
    if isinstance(history, list) and history:
        st.markdown("#### Galaw ng signal")
        for p in history[-10:]:
            value = max(0, min(100, int(p.get("value", 0) or 0)))
            st.markdown(
                f'<div style="margin:10px 0"><div class="kicker-row"><span class="small-muted">{esc(p.get("label",""))}</span><strong>{value}%</strong></div>'
                f'<div class="trend-bar-bg"><div class="trend-bar" style="width:{value}%;background:{meta["accent"]}"></div></div></div>',
                unsafe_allow_html=True,
            )
    render_sources(record)
    render_comments(record, comments)


def render_footer(all_records, records, comments):
    live = [r for r in records if not r.get("demo")]
    st.markdown("---")
    st.caption(
        f"ALAM • {len(records)} current topics • {len(all_records)} historical records • "
        f"{len(comments)} persona comments • {len(live)} live topics. "
        "FACT labels require source support; analysis is explicitly separated."
    )
