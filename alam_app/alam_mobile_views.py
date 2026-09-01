import json
import random
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import streamlit as st

from alam_core import (
    CATEGORY_META,
    FIELD_LABELS,
    age_label,
    category_meta,
    esc,
    feed_score,
    format_value,
    freshness_score,
    is_followed,
    parse_dt,
    parse_yen,
    percent_value,
    reading_text,
    source_quality,
    summarize_so_what,
    toggle_follow,
    type_label,
)
from alam_personas import PERSONAS, comments_for_story, persona_for_comment
from alam_views import (
    _render_claims,
    _render_pr_vs_reality,
    _render_reflection_interaction,
    _render_sources,
    _render_timeline,
)


MOBILE_CSS = r"""
<style>
:root{--mobile-card:rgba(255,255,255,.96);--mobile-muted:#667085;--mobile-border:rgba(23,32,42,.09)}
.block-container{max-width:1040px;padding-top:.65rem;padding-bottom:5.5rem}
.alam-brand{padding:5px 1px 10px}.alam-logo{font-size:1.85rem}.live-pill{white-space:nowrap}
.st-key-main_nav{position:sticky;top:.25rem;z-index:999;padding:.35rem .35rem .4rem;margin:0 -.35rem .65rem;border:1px solid rgba(23,32,42,.07);border-radius:18px;background:rgba(245,244,240,.92);backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px)}
.mobile-brief{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px;margin:4px 0 16px}.mobile-brief-card{background:var(--mobile-card);border:1px solid var(--mobile-border);border-radius:17px;padding:12px 13px}.mobile-brief-value{font-size:1.25rem;font-weight:950;letter-spacing:-.04em}.mobile-brief-label{font-size:.72rem;color:#98A2B3;margin-top:1px}
.urgent-strip{border:1px solid rgba(180,35,24,.16);background:#FFF3F1;border-radius:20px;padding:14px 16px;margin:4px 0 14px}.urgent-kicker{font-size:.69rem;font-weight:950;letter-spacing:.08em;color:#B42318;text-transform:uppercase}.urgent-title{font-size:1.05rem;font-weight:900;margin-top:3px}.urgent-copy{font-size:.84rem;line-height:1.45;color:#667085;margin-top:3px}
.hero.mobile-hero{padding:24px 24px 22px;border-radius:24px;margin-bottom:12px}.hero.mobile-hero .hero-title{font-size:clamp(1.75rem,4.8vw,3.3rem);line-height:1.02}.hero.mobile-hero .hero-copy{font-size:.98rem;line-height:1.5}
.story-card{border-radius:20px;padding:18px 18px 15px}.story-topline{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:10px}.story-age{font-size:.70rem;color:#98A2B3;font-weight:750;white-space:nowrap}.story-title{font-size:1.14rem;line-height:1.22}.story-summary{font-size:.90rem;line-height:1.5;margin-bottom:10px}.story-meta{font-size:.74rem;gap:8px}.story-status{display:inline-flex;gap:5px;flex-wrap:wrap;margin:5px 0 1px}.status-chip{font-size:.64rem;font-weight:950;padding:4px 7px;border-radius:999px;background:#EEF0FF;color:#4F5ED7}.status-chip.comment{background:#F2ECFB;color:#8254C7}.so-what{margin-top:10px;padding:10px 12px;font-size:.82rem}
.section-title{font-size:clamp(1.32rem,2.5vw,1.9rem)}.panel-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin:10px 0 14px}.panel-card{border:1px solid var(--mobile-border);background:var(--mobile-card);border-radius:18px;padding:14px}.panel-agent{font-size:.72rem;font-weight:950;color:#667085;text-transform:uppercase;letter-spacing:.05em}.panel-persona{font-size:.93rem;font-weight:900;margin-top:3px}.panel-body{font-size:.86rem;line-height:1.55;color:#344054;margin-top:7px}.panel-waiting{font-size:.83rem;color:#98A2B3;margin-top:7px}.panel-summary{background:#17202A;color:#fff;border-radius:18px;padding:13px 15px;margin:8px 0 12px;font-size:.83rem;line-height:1.45}
.detail-shell{border-radius:24px;padding:clamp(19px,4vw,34px);margin-top:6px}.detail-title{font-size:clamp(1.65rem,5.2vw,2.8rem)}.detail-summary{font-size:.98rem;line-height:1.55}.reading-box{font-size:.96rem;line-height:1.65;padding:15px}.mobile-bottomline{border-left:4px solid #5968F2;background:#F7F8FF;border-radius:14px;padding:12px 14px;margin:10px 0;font-size:.88rem;line-height:1.5;color:#344054}
.action-group{margin-top:21px}.action-heading{display:flex;align-items:center;gap:7px;font-weight:950;font-size:1.02rem;margin-bottom:8px}.action-sub{color:#98A2B3;font-size:.76rem;margin-top:-5px;margin-bottom:10px}
.stButton>button{min-height:44px!important;border-radius:14px!important}div[data-testid="stPills"] button,div[data-testid="stSegmentedControl"] button{min-height:42px}
@media(max-width:760px){.block-container{padding-left:.78rem;padding-right:.78rem;padding-top:.35rem}.alam-brand{align-items:flex-start;gap:8px}.alam-logo{font-size:1.62rem;letter-spacing:-.055em}.alam-logo span{font-size:.70rem;line-height:1.2}.live-pill{padding:6px 8px;font-size:.67rem}.mobile-brief{gap:6px}.mobile-brief-card{padding:10px 9px;border-radius:14px}.mobile-brief-value{font-size:1.05rem}.mobile-brief-label{font-size:.63rem;line-height:1.15}.hero.mobile-hero{padding:19px 17px 18px;border-radius:20px}.story-card{padding:16px 15px 14px;border-radius:18px}.story-title{font-size:1.08rem}.story-summary{font-size:.88rem}.story-meta{font-size:.72rem}.panel-grid{grid-template-columns:1fr}.detail-shell{padding:18px 16px;border-radius:19px}.detail-title{font-size:1.65rem;line-height:1.08}.metric-strip{grid-template-columns:repeat(2,1fr)}.category-tile{min-height:auto}.source-card,.claim-box,.reading-box,.mind-change{border-radius:15px}.section-eyebrow{margin-top:19px}.st-key-main_nav{top:.1rem;margin-left:-.2rem;margin-right:-.2rem}}
</style>
"""


def render_brand(records):
    latest = max((parse_dt(r.get("created_at")) for r in records), default=None)
    updated = age_label(latest) if latest else "waiting"
    st.markdown('<div class="alam-brand"><div class="alam-logo">ALAM <span>Ano\'ng bago. Bakit mahalaga. Ano\'ng gagawin.</span></div><div class="live-pill"><span class="live-dot"></span>' + esc(updated) + '</div></div>', unsafe_allow_html=True)


def _compact(text, limit=300):
    text = str(text or "").strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _open_story(record):
    st.session_state["selected_story"] = str(record["id"])
    st.rerun()


def _new_comment_count(comments, story_id):
    ref = st.session_state.get("visit_reference")
    if not comments or not ref:
        return 0
    return sum(1 for c in comments_for_story(comments, story_id) if parse_dt(c.get("created_at")).astimezone(timezone.utc) > ref.astimezone(timezone.utc))


def _card_html(record, comments=None):
    meta = category_meta(record)
    total, strong = source_quality(record)
    so_what = summarize_so_what(record)
    ref = st.session_state.get("visit_reference")
    chips = []
    if ref and parse_dt(record.get("created_at")).astimezone(timezone.utc) > ref.astimezone(timezone.utc):
        chips.append('<span class="status-chip">NEW</span>')
    new_comments = _new_comment_count(comments, record.get("id"))
    if new_comments:
        chips.append(f'<span class="status-chip comment">{new_comments} new comments</span>')
    status = '<div class="story-status">' + ''.join(chips) + '</div>' if chips else ''
    return ('<div class="story-card">' f'<div class="story-accent" style="background:{meta["accent"]}"></div><div class="story-topline"><div class="story-label" style="margin:0;background:{meta["soft"]};color:{meta["accent"]}">{esc(type_label(record))}</div><div class="story-age">{esc(age_label(record.get("created_at")))}</div></div>' + status + f'<div class="story-title">{esc(record.get("title", "Untitled"))}</div><div class="story-summary">{esc(_compact(record.get("summary")))}</div>' + (f'<div class="so-what"><strong>Why care:</strong> {esc(_compact(so_what, 210))}</div>' if so_what else '') + f'<div class="story-meta" style="margin-top:10px"><span>{int(record.get("confidence", 0) or 0)}% confidence</span><span>{total} sources</span>' + (f'<span>{strong} primary/official</span>' if strong else '') + '</div></div>')


def render_card(record, key, manager=None, comments=None):
    st.markdown(_card_html(record, comments), unsafe_allow_html=True)
    if st.button("Basahin →", key=f"read_{key}", use_container_width=True):
        _open_story(record)


def _render_urgent(records):
    urgent = [r for r in records if r.get("_category") == "practical" and str((r.get("content") or {}).get("action", "WATCH")).upper() in {"DO NOW", "AVOID", "PREPARE", "APPLY"}]
    if not urgent:
        return
    top = max(urgent, key=feed_score)
    action = str((top.get("content") or {}).get("action", "DO NOW")).upper()
    risk = (top.get("content") or {}).get("risk_if_ignored") or top.get("why_it_matters") or top.get("summary")
    st.markdown(f'<div class="urgent-strip"><div class="urgent-kicker">⚠ {esc(action)}</div><div class="urgent-title">{esc(top.get("title", ""))}</div><div class="urgent-copy">{esc(_compact(risk, 220))}</div></div>', unsafe_allow_html=True)
    if st.button("Open urgent item →", key="today_urgent", use_container_width=True):
        _open_story(top)


def _render_since(records, comments=None):
    ref = st.session_state.get("visit_reference")
    first = ref is None or getattr(ref, "year", 1970) <= 1970
    if first:
        ref = datetime.now(timezone.utc) - timedelta(hours=24)
    changed = [r for r in records if parse_dt(r.get("created_at")).astimezone(timezone.utc) > ref.astimezone(timezone.utc)]
    action_count = sum(1 for r in changed if r.get("_category") == "practical" and str((r.get("content") or {}).get("action", "WATCH")).upper() in {"DO NOW", "PREPARE", "APPLY", "AVOID"})
    new_comments = sum(1 for c in (comments or []) if parse_dt(c.get("created_at")).astimezone(timezone.utc) > ref.astimezone(timezone.utc))
    label = "Last 24h" if first else "Since last visit"
    st.markdown(f'<div class="section-eyebrow">{esc(label)}</div><div class="mobile-brief"><div class="mobile-brief-card"><div class="mobile-brief-value">{len(changed)}</div><div class="mobile-brief-label">meaningful updates</div></div><div class="mobile-brief-card"><div class="mobile-brief-value">{action_count}</div><div class="mobile-brief-label">need attention</div></div><div class="mobile-brief-card"><div class="mobile-brief-value">{new_comments}</div><div class="mobile-brief-label">new panel views</div></div></div>', unsafe_allow_html=True)


def _pulse_score(records, category):
    subset = sorted([r for r in records if r.get("_category") == category], key=feed_score, reverse=True)[:5]
    if not subset:
        return 0
    vals = [0.55 * float(r.get("importance", 50) or 50) + 0.45 * freshness_score(r.get("created_at")) for r in subset]
    return max(0, min(100, int(sum(vals) / len(vals))))


def render_today(all_records, records, comments=None, manager=None):
    if not records:
        st.info("Wala pang intelligence records.")
        return
    _render_urgent(records)
    top = max(records, key=feed_score)
    st.markdown(f'<div class="hero mobile-hero"><div class="hero-kicker">🔥 TOP STORY</div><div class="hero-title">{esc(top.get("title", ""))}</div><div class="hero-copy">{esc(_compact(top.get("summary"), 420))}</div></div>', unsafe_allow_html=True)
    if st.button("Basahin ang top story →", key="hero_story", use_container_width=True):
        _open_story(top)
    _render_since(records, comments)
    mode = st.segmented_control("Briefing depth", ["⚡ 5 min", "📚 More", "🎲 Surprise"], default="⚡ 5 min", key="today_mode_mobile", label_visibility="collapsed", width="stretch")
    if mode == "⚡ 5 min":
        picks = []
        for category in CATEGORY_META:
            subset = [r for r in records if r.get("_category") == category]
            if subset:
                picks.append(max(subset, key=feed_score))
    elif mode == "📚 More":
        picks = sorted(records, key=feed_score, reverse=True)[:8]
    else:
        pool = sorted(records, key=feed_score, reverse=True)[:min(15, len(records))]
        picks = [random.Random(datetime.now().strftime("%Y-%m-%d-%H")).choice(pool)] if pool else []
    st.markdown('<div class="section-eyebrow">Briefing</div><div class="section-title">Worth your attention ngayon</div>', unsafe_allow_html=True)
    cols = st.columns(2, wrap=True)
    for i, record in enumerate(picks):
        with cols[i % 2]:
            render_card(record, f"today_{i}", manager, comments)
    growing = [r for r in records if r.get("_category") == "trend" and str((r.get("content") or {}).get("direction", "")).upper() == "ACCELERATING" and 45 <= int((r.get("content") or {}).get("current_strength", r.get("importance", 0)) or 0) < 85]
    if growing:
        with st.expander("Quietly becoming important"):
            for i, record in enumerate(growing[:3]):
                render_card(record, f"quiet_{i}", manager, comments)
    with st.expander("Signal map · how active are the four lenses?"):
        for key in CATEGORY_META:
            meta = CATEGORY_META[key]
            score = _pulse_score(records, key)
            state = "Active" if score >= 70 else "Moving" if score >= 50 else "Quiet"
            st.markdown(f'<div class="pulse-card"><div class="pulse-row"><strong>{meta["emoji"]} {esc(meta["label"])}</strong><span>{score} · {state}</span></div><div class="pulse-bar-bg"><div class="pulse-bar" style="width:{score}%;background:{meta["accent"]}"></div></div></div>', unsafe_allow_html=True)


def render_category(records, category, manager=None, comments=None):
    meta = CATEGORY_META[category]
    descriptions = {"discover":"Fresh developments na worth knowing — hindi basta trending lang.","practical":"Tipid, safety, risk at Japan life advice na may totoong action.","reflection":"Psychology, philosophy at modern Christian life — mas malalim kaysa headline.","trend":"Patterns, predictions at signals na lumalakas, humihina, o bumabaliktad."}
    st.markdown(f'<div class="hero mobile-hero"><div class="hero-kicker" style="color:{meta["accent"]}">{meta["emoji"]} {esc(meta["label"])}</div><div class="hero-title">{esc(meta["question"])}</div><div class="hero-copy">{esc(descriptions[category])}</div></div>', unsafe_allow_html=True)
    search = st.text_input("Hanapin", placeholder="Search Japan, AI, money, faith…", key=f"search_{category}_mobile", type="search", label_visibility="collapsed")
    selected_filter = st.pills("Filter", ["All", "New", "High confidence", "Following"], default="All", required=True, key=f"filter_{category}_mobile", label_visibility="collapsed", width="stretch")
    subset = [r for r in records if r.get("_category") == category]
    if search:
        q = search.lower().strip(); subset = [r for r in subset if q in json.dumps(r, ensure_ascii=False).lower()]
    if selected_filter == "New":
        ref = st.session_state.get("visit_reference")
        if ref:
            subset = [r for r in subset if parse_dt(r.get("created_at")).astimezone(timezone.utc) > ref.astimezone(timezone.utc)]
    elif selected_filter == "High confidence":
        subset = [r for r in subset if int(r.get("confidence", 0) or 0) >= 85]
    elif selected_filter == "Following":
        subset = [r for r in subset if is_followed(r.get("id"))]
    if not subset:
        st.markdown('<div class="empty-box">Walang matching items ngayon.</div>', unsafe_allow_html=True); return
    subset.sort(key=(lambda r: (r.get("content") or {}).get("current_strength", r.get("importance", 0))) if category == "trend" else feed_score, reverse=True)
    cols = st.columns(2, wrap=True)
    for i, record in enumerate(subset):
        with cols[i % 2]: render_card(record, f"{category}_mobile_{i}", manager, comments)


def _action_bucket(record):
    action = str((record.get("content") or {}).get("action", "WATCH")).upper()
    if action in {"DO NOW", "APPLY"}: return "DO NOW"
    if action in {"PREPARE", "BUY"}: return "PREPARE"
    if action == "AVOID": return "AVOID"
    return "WATCH"


def render_action_center(records, manager=None, comments=None):
    subset = [r for r in records if r.get("_category") == "practical"]
    st.markdown('<div class="hero mobile-hero"><div class="hero-kicker" style="color:#087D5B">🛡️ ACTION</div><div class="hero-title">Ano ang kailangan mong gawin?</div><div class="hero-copy">Urgent muna, then prepare, avoid, at watch.</div></div>', unsafe_allow_html=True)
    groups = defaultdict(list)
    for r in subset: groups[_action_bucket(r)].append(r)
    meta = {"DO NOW":("🔴","Do now","May deadline, safety, or financial consequence."),"PREPARE":("🟠","Prepare","Hindi kailangan ngayon, pero magandang mauna."),"AVOID":("⛔","Avoid","May clear downside o unnecessary risk."),"WATCH":("🟡","Watch","Useful signal pero huwag muna kumilos.")}
    for bucket in ("DO NOW","PREPARE","AVOID","WATCH"):
        items = sorted(groups.get(bucket, []), key=feed_score, reverse=True)
        if not items: continue
        emoji,title,sub = meta[bucket]
        st.markdown(f'<div class="action-group"><div class="action-heading">{emoji} {esc(title)} <span class="small-muted">({len(items)})</span></div><div class="action-sub">{esc(sub)}</div></div>', unsafe_allow_html=True)
        cols = st.columns(2, wrap=True)
        for i, record in enumerate(items):
            with cols[i % 2]:
                render_card(record, f"action_mobile_{bucket}_{i}", manager, comments)
                c = record.get("content") or {}; saving = c.get("estimated_saving_yen") or parse_yen(c.get("financial_impact")); minutes = c.get("time_minutes"); travel = c.get("travel_minutes", 0) or 0
                if saving and minutes:
                    try:
                        hourly = float(saving) / max(1, float(minutes) + float(travel)) * 60
                        verdict = "SULIT" if hourly >= 1500 else "MAYBE" if hourly >= 800 else "LOW RETURN"
                        st.caption(f"Sulit ba? ~¥{hourly:,.0f}/hour effort → {verdict}")
                    except (TypeError, ValueError): pass


def render_prediction_lab(records):
    predictions=[]
    for r in records:
        c=r.get("content") or {}; is_prediction=str(r.get("type","")).lower() in {"prediction","correction"}
        if r.get("_category")=="trend" and (is_prediction or c.get("current_probability") is not None): predictions.append(r)
    st.markdown('<div class="hero mobile-hero"><div class="hero-kicker" style="color:#C95E19">🔮 PREDICTIONS</div><div class="hero-title">Track the forecast. Keep the mistakes.</div><div class="hero-copy">Calibration at self-correction ang goal.</div></div>', unsafe_allow_html=True)
    if not predictions:
        st.markdown('<div class="empty-box">Wala pang prediction ledger.</div>', unsafe_allow_html=True); return
    for i,r in enumerate(sorted(predictions,key=lambda x:parse_dt(x.get("created_at")),reverse=True)):
        c=r.get("content") or {}; p=percent_value(c.get("current_probability",c.get("initial_probability",0))); status=str(c.get("status",r.get("status","OPEN"))).upper(); statement=c.get("statement") or r.get("title","")
        st.markdown(f'<div class="story-card" style="margin-bottom:8px"><div class="story-topline"><span class="story-label" style="margin:0;background:#FFF0E6;color:#C95E19">{esc(status)}</span><span class="story-age">{esc(age_label(r.get("created_at")))}</span></div><div class="story-title">{esc(statement)}</div><div class="kicker-row"><span class="small-muted">Current probability</span><strong>{p:.0f}%</strong></div><div class="trend-bar-bg"><div class="trend-bar" style="width:{p}%;background:#C95E19"></div></div></div>', unsafe_allow_html=True)
        if st.button("Open prediction →",key=f"prediction_mobile_{i}",use_container_width=True): _open_story(r)


def render_following(records, manager=None, comments=None):
    subset=[r for r in records if is_followed(r.get("id"))]
    st.markdown('<div class="hero mobile-hero"><div class="hero-kicker">👁️ FOLLOWING</div><div class="hero-title">Mga story na binabantayan mo.</div><div class="hero-copy">Material updates stay easy to find here.</div></div>', unsafe_allow_html=True)
    if not subset:
        st.markdown('<div class="empty-box">Wala ka pang binabantayang topic. Open a story and tap “+ Bantayan”.</div>',unsafe_allow_html=True);return
    cols=st.columns(2,wrap=True)
    for i,r in enumerate(sorted(subset,key=feed_score,reverse=True)):
        with cols[i%2]: render_card(r,f"following_mobile_{i}",manager,comments)


def _agent_category(comment):
    raw=str(comment.get("agent") or "").lower()
    if "practical" in raw:return "practical"
    if "reflection" in raw or "reflect" in raw:return "reflection"
    if "trend" in raw:return "trend"
    return "discover"


def _render_full_thread(record, comments):
    thread=comments_for_story(comments,record["id"])
    if not thread:
        st.info("Tahimik pa ang panel. Agents comment only when useful.");return
    by_id={str(c.get("id")):c for c in thread}
    for c in thread:
        p=persona_for_comment(c); reply=by_id.get(str(c.get("reply_to") or "")); reply_line=""
        if reply:
            rp=persona_for_comment(reply); reply_line=f"<div class='small-muted'>↳ replying to {esc(rp['emoji']+' '+rp['name'])}</div>"
        st.markdown(f'<div class="source-card"><div class="source-title">{esc(p["emoji"]+" "+p["name"])} <span class="small-muted">— {esc(p.get("role","Editorial Persona"))}</span></div>{reply_line}<div class="detail-body" style="margin-top:6px">{esc(c.get("body",""))}</div><div class="source-meta">{esc(age_label(c.get("created_at")))}</div></div>',unsafe_allow_html=True)


def _render_panel(record, comments):
    thread=comments_for_story(comments,record["id"]); latest={}
    for c in thread: latest[_agent_category(c)]=c
    st.markdown("#### 🗣 ALAM Panel")
    st.markdown(f'<div class="panel-summary"><strong>{len(latest)}/4 lenses checked in.</strong> Same evidence, different jobs: novelty, practical consequence, human meaning, and pattern direction.</div>',unsafe_allow_html=True)
    cards=[]
    for category in ("discover","practical","reflection","trend"):
        meta=CATEGORY_META[category]; c=latest.get(category)
        if c:
            p=persona_for_comment(c); cards.append(f'<div class="panel-card"><div class="panel-agent">{meta["emoji"]} {esc(meta["label"])}</div><div class="panel-persona">{esc(p["emoji"]+" "+p["name"])}</div><div class="panel-body">{esc(c.get("body",""))}</div></div>')
        else: cards.append(f'<div class="panel-card"><div class="panel-agent">{meta["emoji"]} {esc(meta["label"])}</div><div class="panel-waiting">No useful panel comment yet.</div></div>')
    st.markdown('<div class="panel-grid">'+''.join(cards)+'</div>',unsafe_allow_html=True)
    with st.expander(f"Open full discussion · {len(thread)} comments"):
        _render_full_thread(record,comments)
        st.markdown("**Who are these voices?**")
        for category in ("discover","practical","reflection","trend"):
            names=" · ".join(f"{p['emoji']} {p['name']} — {p['role']}" for p in PERSONAS.get(category,[])); st.caption(f"{CATEGORY_META[category]['label']}: {names}")


def _render_30sec(record):
    text=reading_text(record,"30 sec") or record.get("summary","")
    st.markdown(f'<div class="reading-box">{esc(text).replace(chr(10),"<br>")}</div>',unsafe_allow_html=True)
    c=record.get("content") or {}; bottom=c.get("action") or record.get("why_it_matters") or c.get("recommendation") or summarize_so_what(record)
    if bottom: st.markdown(f'<div class="mobile-bottomline"><strong>Bottom line:</strong> {esc(_compact(bottom,360))}</div>',unsafe_allow_html=True)


def _render_deep(record, all_records, comments):
    if record.get("why_it_matters"):
        st.markdown(f'<div class="detail-section"><div class="detail-heading">Bakit mahalaga</div><div class="detail-body">{esc(record.get("why_it_matters"))}</div></div>',unsafe_allow_html=True)
    _render_pr_vs_reality(record); c=record.get("content") or {}
    skip={"usefulness","novelty","history","reading_levels","pr_vs_reality","facts","inferences","assumptions","estimates","change_summary","estimated_saving_yen","time_minutes","travel_minutes","official_framing","evidence_check","alam_verdict","what_would_change_mind"}
    for key,value in c.items():
        if key in skip or value in ("",None,[],{}):continue
        if key=="questions" and record.get("_category")=="reflection":continue
        heading=FIELD_LABELS.get(key,key.replace("_"," ").title()); st.markdown(f'<div class="detail-section"><div class="detail-heading">{esc(heading)}</div><div class="detail-body">{format_value(value)}</div></div>',unsafe_allow_html=True)
    mind=c.get("what_would_change_mind") or c.get("what_next")
    if mind: st.markdown(f'<div class="mind-change"><strong>What would change our mind?</strong><br>{esc(mind)}</div>',unsafe_allow_html=True)
    if record.get("_category")=="reflection": _render_reflection_interaction(record)
    _render_timeline(all_records,record)
    history=c.get("history")
    if isinstance(history,list) and history:
        meta=category_meta(record); st.markdown("#### Galaw ng signal")
        for point in history[-10:]:
            value=max(0,min(100,int(point.get("value",0) or 0))); st.markdown(f'<div style="margin:10px 0"><div class="kicker-row"><span class="small-muted">{esc(point.get("label",""))}</span><strong>{value}%</strong></div><div class="trend-bar-bg"><div class="trend-bar" style="width:{value}%;background:{meta["accent"]}"></div></div></div>',unsafe_allow_html=True)
    _render_claims(record); _render_sources(record); _render_panel(record,comments)


def render_detail(all_records, record, comments, manager=None):
    if st.button("← Balik",key="back_detail"):
        st.session_state.pop("selected_story",None); st.rerun()
    meta=category_meta(record); total,strong=source_quality(record); tags=" · ".join(str(x) for x in record.get("tags",[])[:5])
    st.markdown(f'<div class="detail-shell"><div class="story-topline"><div class="story-label" style="margin:0;background:{meta["soft"]};color:{meta["accent"]}">{esc(type_label(record))}</div><div class="story-age">{esc(age_label(record.get("created_at")))}</div></div><div class="detail-title">{esc(record.get("title",""))}</div><div class="detail-summary">{esc(record.get("summary",""))}</div><div class="story-meta" style="margin-top:14px"><span>{int(record.get("confidence",0) or 0)}% confidence</span><span>{total} sources</span><span>{strong} primary/official</span><span>{esc(tags)}</span></div></div>',unsafe_allow_html=True)
    label="✓ Binabantayan" if is_followed(record["id"]) else "+ Bantayan"
    if st.button(label,key=f"detail_follow_mobile_{record['id']}",use_container_width=True): toggle_follow(record["id"],manager); st.rerun()
    mode=st.segmented_control("View",["⚡ 30 sec","🗣 Panel","🧾 Evidence","🧠 Deep"],default="⚡ 30 sec",key=f"detail_mode_{record['id']}",label_visibility="collapsed",width="stretch")
    if mode=="🗣 Panel": _render_panel(record,comments)
    elif mode=="🧾 Evidence": _render_pr_vs_reality(record); _render_claims(record); _render_timeline(all_records,record); _render_sources(record)
    elif mode=="🧠 Deep": _render_deep(record,all_records,comments)
    else: _render_30sec(record)


def render_footer(all_records, records, comments):
    live=[r for r in records if not r.get("demo")]
    st.markdown("---"); st.caption(f"ALAM • {len(records)} current topics • {len(all_records)} historical records • {len(live)} live current records • {len(comments)} panel comments. FACT labels require source support; inference and assumptions stay separate.")
