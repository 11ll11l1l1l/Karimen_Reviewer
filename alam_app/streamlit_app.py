import html
import json
import math
import random
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import streamlit as st

try:
    import extra_streamlit_components as stx
except Exception:
    stx = None

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"

st.set_page_config(
    page_title="ALAM — Ano'ng bago. Bakit mahalaga.",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="collapsed",
)

CATEGORY_META = {
    "discover": {"emoji": "🔭", "label": "Discover", "question": "Ano'ng bago?", "accent": "#5968F2", "soft": "#EEF0FF"},
    "practical": {"emoji": "🛡️", "label": "Practical", "question": "May dapat ba akong gawin?", "accent": "#087D5B", "soft": "#E9F7F2"},
    "reflection": {"emoji": "🧠", "label": "Reflect", "question": "Ano'ng ibig sabihin nito?", "accent": "#8254C7", "soft": "#F2ECFB"},
    "trend": {"emoji": "📈", "label": "Trends", "question": "Saan papunta ito?", "accent": "#C95E19", "soft": "#FFF0E6"},
}

TYPE_LABELS = {
    "important": "🔥 MAHALAGA",
    "saving": "💸 TIPID ALERT",
    "risk": "⚠️ INGAT",
    "reflection": "🤔 PAG-ISIPAN",
    "watch": "👀 WATCH LANG MUNA",
    "trend": "📈 LUMALAKAS",
    "prediction": "🔮 PREDICTION",
    "correction": "❌ MALI TAYO",
    "technology": "🤖 TECH",
    "japan": "🇯🇵 JAPAN",
    "discovery": "🔭 WORTH KNOWING",
    "policy": "🏛️ POLICY",
    "safety": "🛡️ SAFETY",
}

FIELD_LABELS = {
    "what_happened": "Ano'ng nangyari",
    "whats_new": "Ano'ng bago",
    "why_it_matters": "Bakit mahalaga",
    "skeptical_view": "Pero teka",
    "what_next": "Ano ang susunod na bantayan",
    "recommendation": "Bottom line",
    "who_is_affected": "Sino ang apektado",
    "when": "Kailan",
    "financial_impact": "Impact sa pera",
    "risk_if_ignored": "Risk kung i-ignore",
    "action": "Gawin",
    "deadline": "Deadline",
    "effort": "Effort",
    "potential_benefit": "Potential benefit",
    "downside": "Catch / downside",
    "human_problem": "Human problem",
    "psychology": "Psychology",
    "philosophical_conflict": "Philosophical conflict",
    "christian_analysis": "Christian perspective",
    "secular_challenge": "Strongest challenge",
    "christian_response": "Christian response",
    "modern_christian_life": "Sa modern Christian life",
    "questions": "Mga tanong na pag-isipan",
    "current_strength": "Current strength",
    "previous_strength": "Previous strength",
    "direction": "Direction",
    "evidence_for": "Evidence for",
    "evidence_against": "Evidence against",
    "connection": "Bakit posibleng connected",
    "alternative_explanation": "Alternative explanation",
    "watch_next": "Ano ang bantayan",
    "implications": "Possible implications",
    "statement": "Prediction",
    "current_probability": "Current probability",
    "initial_probability": "Initial probability",
    "status": "Status",
    "what_would_change_mind": "Ano ang magpapabago sa conclusion",
}

CLAIM_META = {
    "FACT": ("FACT", "#087D5B", "#E9F7F2", "Directly supported by cited evidence"),
    "INFERENCE": ("INFERENCE", "#B35B14", "#FFF0E6", "Reasoned conclusion from evidence"),
    "ASSUMPTION": ("ASSUMPTION", "#A03C64", "#FCECF3", "Working assumption; not established fact"),
    "ESTIMATE": ("ESTIMATE", "#3F68B2", "#EAF0FB", "Calculated or reported estimate"),
    "OPINION": ("ANALYSIS", "#5F6673", "#F0F2F5", "Interpretation, not a factual claim"),
}

CSS = """
<style>
:root{--bg:#F5F4F0;--ink:#17202A;--muted:#667085;--card:rgba(255,255,255,.94);--line:rgba(23,32,42,.09);--shadow:0 14px 42px rgba(23,32,42,.075)}
html,body,[class*="css"]{font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
.stApp{background:radial-gradient(circle at 5% 0%,rgba(89,104,242,.10),transparent 29rem),radial-gradient(circle at 95% 2%,rgba(8,125,91,.09),transparent 27rem),var(--bg);color:var(--ink)}
.block-container{max-width:1180px;padding-top:1.05rem;padding-bottom:5rem}header[data-testid="stHeader"]{background:transparent}#MainMenu,footer{visibility:hidden}
.alam-brand{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:8px 2px 16px}.alam-logo{font-size:2.1rem;font-weight:950;letter-spacing:-.065em}.alam-logo span{display:inline-block;margin-left:.48rem;font-size:.78rem;font-weight:750;letter-spacing:0;color:#667085;vertical-align:middle}
.live-pill{display:inline-flex;align-items:center;gap:7px;border-radius:999px;padding:7px 11px;background:rgba(8,125,91,.10);color:#087454;font-size:.76rem;font-weight:850}.live-dot{width:8px;height:8px;border-radius:50%;background:#087D5B;box-shadow:0 0 0 5px rgba(8,125,91,.11)}
.hero{border:1px solid rgba(23,32,42,.07);border-radius:30px;padding:clamp(25px,4vw,52px);background:linear-gradient(135deg,rgba(255,255,255,.98),rgba(255,255,255,.84)),linear-gradient(120deg,#EEF0FF,#E9F7F2);box-shadow:var(--shadow);overflow:hidden;position:relative;margin-bottom:20px}.hero:after{content:"";position:absolute;width:260px;height:260px;right:-75px;top:-100px;border-radius:50%;background:linear-gradient(135deg,rgba(89,104,242,.18),rgba(8,125,91,.14))}.hero-kicker{font-size:.75rem;font-weight:900;letter-spacing:.09em;text-transform:uppercase;color:#5968F2;margin-bottom:10px}.hero-title{font-size:clamp(2rem,5vw,4.5rem);line-height:.98;letter-spacing:-.055em;font-weight:950;max-width:850px;margin:0 0 15px}.hero-copy{font-size:clamp(1rem,1.8vw,1.2rem);line-height:1.55;color:#475467;max-width:800px}
.section-eyebrow{font-size:.72rem;font-weight:900;letter-spacing:.09em;text-transform:uppercase;color:#98A2B3;margin:25px 0 7px}.section-title{font-size:clamp(1.45rem,2.5vw,2.05rem);font-weight:930;letter-spacing:-.038em;margin:0 0 12px}
.story-card{background:var(--card);border:1px solid var(--line);border-radius:23px;padding:21px 21px 17px;box-shadow:0 8px 26px rgba(23,32,42,.05);height:100%;position:relative;overflow:hidden;transition:transform .18s ease,box-shadow .18s ease}.story-card:hover{transform:translateY(-2px);box-shadow:0 15px 36px rgba(23,32,42,.085)}.story-accent{position:absolute;top:0;left:0;right:0;height:4px}.story-label{display:inline-block;border-radius:999px;padding:5px 9px;font-size:.69rem;font-weight:900;letter-spacing:.035em;margin-bottom:13px}.story-title{font-size:1.22rem;line-height:1.18;letter-spacing:-.026em;font-weight:900;margin:0 0 9px}.story-summary{color:#475467;line-height:1.55;font-size:.93rem;margin-bottom:14px}.story-meta{color:#98A2B3;font-size:.73rem;display:flex;gap:9px;flex-wrap:wrap}.so-what{margin-top:13px;padding:11px 13px;border-radius:14px;background:#F7F8FA;color:#344054;font-size:.83rem;line-height:1.45}
.claim-mini{display:inline-flex;gap:5px;align-items:center;margin-top:10px;flex-wrap:wrap}.claim-dot{font-size:.64rem;font-weight:900;padding:4px 7px;border-radius:999px}
.category-tile{border-radius:21px;padding:19px;border:1px solid var(--line);background:rgba(255,255,255,.76);min-height:154px}.category-icon{font-size:1.45rem;margin-bottom:12px}.category-name{font-size:1.04rem;font-weight:900;letter-spacing:-.02em}.category-q{color:#667085;font-size:.85rem;line-height:1.45;margin-top:4px}.category-count{margin-top:16px;font-size:.77rem;font-weight:850}
.metric-strip{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:6px 0 20px}.metric-mini{background:rgba(255,255,255,.78);border:1px solid var(--line);border-radius:17px;padding:13px 15px}.metric-value{font-size:1.16rem;font-weight:930}.metric-label{font-size:.71rem;color:#98A2B3;margin-top:2px}
.pulse-card{background:rgba(255,255,255,.78);border:1px solid var(--line);border-radius:18px;padding:14px 15px;margin-bottom:9px}.pulse-row{display:flex;justify-content:space-between;gap:12px;align-items:center;font-size:.86rem}.pulse-bar-bg{height:7px;border-radius:99px;background:#ECEFF2;overflow:hidden;margin-top:8px}.pulse-bar{height:100%;border-radius:99px}
.detail-shell{background:rgba(255,255,255,.94);border:1px solid var(--line);border-radius:28px;padding:clamp(22px,4vw,44px);box-shadow:var(--shadow);margin:10px 0 18px}.detail-title{font-size:clamp(1.8rem,4vw,3.15rem);line-height:1.03;letter-spacing:-.046em;font-weight:950;margin:10px 0 14px}.detail-summary{font-size:1.06rem;color:#475467;line-height:1.65}.detail-section{margin:20px 0;padding-top:18px;border-top:1px solid var(--line)}.detail-heading{font-size:.75rem;font-weight:900;letter-spacing:.075em;text-transform:uppercase;color:#667085;margin-bottom:7px}.detail-body{color:#344054;line-height:1.68}
.claim-box{border-radius:16px;padding:13px 14px;border:1px solid var(--line);margin:9px 0;background:white}.claim-head{display:flex;align-items:center;gap:9px;flex-wrap:wrap;margin-bottom:5px}.claim-label{font-size:.67rem;font-weight:950;padding:4px 7px;border-radius:999px}.claim-text{line-height:1.55;color:#344054;font-size:.91rem}.claim-basis{font-size:.73rem;color:#98A2B3;margin-top:5px}
.source-card{border:1px solid var(--line);border-radius:15px;background:rgba(255,255,255,.82);padding:12px 13px;margin:7px 0}.source-type{font-size:.63rem;font-weight:900;text-transform:uppercase;color:#667085}.source-title{font-size:.87rem;font-weight:800;margin-top:3px}.source-meta{font-size:.71rem;color:#98A2B3;margin-top:4px}
.pr-box{display:grid;grid-template-columns:1fr 1fr;gap:10px}.pr-cell{border-radius:17px;padding:15px;border:1px solid var(--line);background:rgba(255,255,255,.8)}.pr-head{font-size:.68rem;font-weight:950;letter-spacing:.07em;text-transform:uppercase;color:#667085;margin-bottom:5px}.verdict{margin-top:10px;border-radius:17px;padding:15px;background:#17202A;color:white}.verdict small{display:block;color:#C9D0D8;font-size:.67rem;font-weight:900;letter-spacing:.08em;text-transform:uppercase;margin-bottom:4px}
.timeline{border-left:2px solid #D8DDE5;margin:10px 0 10px 7px;padding-left:18px}.timeline-item{position:relative;margin:0 0 19px}.timeline-item:before{content:"";position:absolute;width:10px;height:10px;border-radius:50%;background:#5968F2;left:-24px;top:5px;border:3px solid #F5F4F0}.timeline-date{font-size:.69rem;font-weight:900;color:#98A2B3;text-transform:uppercase}.timeline-title{font-size:.92rem;font-weight:850;margin-top:2px}.timeline-change{font-size:.82rem;color:#667085;margin-top:3px;line-height:1.45}
.demo-banner{border-radius:16px;padding:11px 14px;background:#FFF7E8;color:#815900;border:1px solid #F5D995;font-size:.82rem;margin:6px 0 18px}.empty-box{border:1px dashed rgba(23,32,42,.18);border-radius:20px;padding:34px 22px;text-align:center;color:#667085;background:rgba(255,255,255,.45)}
.trend-bar-bg{width:100%;height:9px;border-radius:99px;background:#EEF0F3;overflow:hidden;margin-top:8px}.trend-bar{height:100%;border-radius:99px}.kicker-row{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap}.small-muted{color:#98A2B3;font-size:.76rem}.reading-box{border-radius:18px;background:rgba(255,255,255,.8);border:1px solid var(--line);padding:16px 17px;line-height:1.65;color:#344054}.mind-change{border-radius:17px;background:#F1F3F7;border:1px solid var(--line);padding:15px 16px;color:#344054;line-height:1.55}
div[data-testid="stRadio"]>div{gap:.3rem}div[data-testid="stRadio"] label{background:rgba(255,255,255,.74);border:1px solid var(--line);padding:.45rem .75rem;border-radius:999px;margin-right:.22rem}div[data-testid="stRadio"] label:has(input:checked){background:#17202A;color:white;border-color:#17202A}.stButton>button{border-radius:13px!important;border:1px solid rgba(23,32,42,.11)!important;font-weight:850!important}.stButton>button:hover{border-color:#17202A!important}div[data-testid="stTextInput"] input,div[data-testid="stMultiSelect"],div[data-testid="stSelectbox"]{border-radius:14px}
@media(max-width:760px){.block-container{padding-left:1rem;padding-right:1rem}.metric-strip{grid-template-columns:repeat(2,1fr)}.pr-box{grid-template-columns:1fr}.hero{border-radius:23px}.alam-logo span{display:block;margin:.12rem 0 0}.story-card{border-radius:20px}}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


def esc(value):
    return html.escape(str(value if value is not None else ""))


def normalize_category(record):
    raw = f"{record.get('agent', '')} {record.get('type', '')}".lower()
    if any(x in raw for x in ("practical", "risk", "saving", "safety")):
        return "practical"
    if any(x in raw for x in ("reflection", "reflect", "psychology")):
        return "reflection"
    if any(x in raw for x in ("trend", "prediction", "correction")):
        return "trend"
    return "discover"


def parse_dt(value):
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not value:
        return datetime(1970, 1, 1, tzinfo=timezone.utc)
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return datetime(1970, 1, 1, tzinfo=timezone.utc)


def age_label(value):
    dt = parse_dt(value)
    hours = max(0, (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds() / 3600)
    if hours < 1:
        return f"{max(1,int(hours*60))}m ago"
    if hours < 24:
        return f"{int(hours)}h ago"
    days = int(hours / 24)
    if days == 1:
        return "kahapon"
    if days < 7:
        return f"{days} days ago"
    return dt.strftime("%b %d")


def freshness_score(value):
    hours = max(0, (datetime.now(timezone.utc) - parse_dt(value).astimezone(timezone.utc)).total_seconds() / 3600)
    return max(0.0, 100.0 * math.exp(-hours / 42.0))


def feed_score(record):
    content = record.get("content") or {}
    importance = float(record.get("importance", 50) or 50)
    confidence = float(record.get("confidence", 50) or 50)
    usefulness = float(content.get("usefulness", record.get("usefulness", 55)) or 55)
    novelty = float(content.get("novelty", record.get("novelty", 55)) or 55)
    source_bonus = min(8.0, len(record.get("sources") or []) * 2.0)
    return 0.35*importance + 0.20*freshness_score(record.get("created_at")) + 0.15*usefulness + 0.10*confidence + 0.10*novelty + 10 + source_bonus


def read_json_file(path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, list) else [payload]


@st.cache_data(ttl=60)
def load_all_records():
    records = []
    if not DATA_DIR.exists():
        return records
    for path in sorted(DATA_DIR.rglob("*.json")):
        if path.name.startswith("_"):
            continue
        try:
            for idx, item in enumerate(read_json_file(path)):
                if not isinstance(item, dict) or not item.get("id") or not item.get("title"):
                    continue
                copy = dict(item)
                copy["_path"] = str(path.relative_to(APP_DIR))
                copy["_category"] = normalize_category(copy)
                copy["_record_key"] = f"{path.relative_to(APP_DIR)}::{idx}"
                records.append(copy)
        except Exception:
            continue
    records.sort(key=lambda r: parse_dt(r.get("created_at")), reverse=True)
    return records


def latest_by_story(records):
    latest = {}
    for record in sorted(records, key=lambda r: parse_dt(r.get("created_at"))):
        latest[str(record.get("id"))] = record
    return sorted(latest.values(), key=lambda r: parse_dt(r.get("created_at")), reverse=True)


def story_versions(all_records, story_id):
    return sorted([r for r in all_records if str(r.get("id")) == str(story_id)], key=lambda r: parse_dt(r.get("created_at")))


def category_meta(record):
    return CATEGORY_META.get(record.get("_category", "discover"), CATEGORY_META["discover"])


def type_label(record):
    return TYPE_LABELS.get(str(record.get("type", "")).lower(), f"{category_meta(record)['emoji']} UPDATE")


def get_claims(record):
    claims = record.get("claims")
    if isinstance(claims, list):
        clean = []
        for claim in claims:
            if isinstance(claim, dict) and claim.get("text"):
                kind = str(claim.get("kind") or claim.get("label") or "OPINION").upper()
                if kind not in CLAIM_META:
                    kind = "OPINION"
                clean.append({**claim, "kind": kind})
        return clean
    clean = []
    for key, kind in (("facts","FACT"),("inferences","INFERENCE"),("assumptions","ASSUMPTION"),("estimates","ESTIMATE")):
        values = (record.get("content") or {}).get(key)
        if isinstance(values, str): values = [values]
        if isinstance(values, list): clean.extend({"kind":kind,"text":str(v)} for v in values if v)
    return clean


def claim_counts(record):
    counts = defaultdict(int)
    for c in get_claims(record): counts[c["kind"]] += 1
    return counts


def source_quality(record):
    sources = record.get("sources") or []
    strong = sum(1 for s in sources if str(s.get("source_type","")).lower() in {"official","primary","research","filing"})
    return len(sources), strong


def summarize_so_what(record):
    content = record.get("content") or {}
    for key in ("action","recommendation","potential_benefit","watch_next","modern_christian_life"):
        value = content.get(key)
        if isinstance(value,str) and value.strip(): return value.strip()
    return record.get("why_it_matters") or ""


def get_reading_text(record, level):
    content = record.get("content") or {}
    reading = content.get("reading_levels") or record.get("reading_levels") or {}
    aliases = {"30 sec":("30_sec","thirty_second","quick"),"2 min":("2_min","two_minute","medium"),"Deep":("deep","deep_dive")}
    for key in aliases[level]:
        value = reading.get(key) if isinstance(reading,dict) else None
        if isinstance(value,str) and value.strip(): return value.strip()
    if level == "30 sec": return " ".join(x for x in [record.get("summary",""),summarize_so_what(record)] if x)
    if level == "2 min":
        pieces = [record.get("summary",""),record.get("why_it_matters","")]
        for key in ("whats_new","skeptical_view","recommendation","action","what_next"):
            value = content.get(key)
            if isinstance(value,str): pieces.append(value)
        return "\n\n".join(dict.fromkeys(x.strip() for x in pieces if x and x.strip()))
    return ""


def format_value(value):
    if isinstance(value,list): return "<ul>"+"".join(f"<li>{esc(v)}</li>" for v in value)+"</ul>"
    if isinstance(value,dict): return "<br>".join(f"<strong>{esc(str(k).replace('_',' ').title())}:</strong> {esc(v)}" for k,v in value.items())
    return esc(value)


def render_brand(records):
    latest = max((parse_dt(r.get("created_at")) for r in records),default=None)
    latest_text = age_label(latest) if latest else "waiting for first update"
    st.markdown(f'<div class="alam-brand"><div class="alam-logo">ALAM <span>Ano\'ng bago. Bakit mahalaga. Ano\'ng gagawin.</span></div><div class="live-pill"><span class="live-dot"></span> Updated {esc(latest_text)}</div></div>',unsafe_allow_html=True)


def story_card_html(record):
    meta = category_meta(record); counts = claim_counts(record); total_sources,strong_sources = source_quality(record)
    pills = []
    for kind in ("FACT","INFERENCE","ASSUMPTION","ESTIMATE"):
        if counts[kind]:
            label,color,bg,_ = CLAIM_META[kind]; pills.append(f'<span class="claim-dot" style="color:{color};background:{bg}">{label} {counts[kind]}</span>')
    claims_html = f'<div class="claim-mini">{"".join(pills)}</div>' if pills else '<div class="claim-mini"><span class="claim-dot" style="color:#667085;background:#F0F2F5">UNCLASSIFIED LEGACY RECORD</span></div>'
    so_what = summarize_so_what(record); demo = " • DEMO" if record.get("demo") else ""
    return f'<div class="story-card"><div class="story-accent" style="background:{meta["accent"]}"></div><div class="story-label" style="background:{meta["soft"]};color:{meta["accent"]}">{esc(type_label(record))}</div><div class="story-title">{esc(record.get("title","Untitled"))}</div><div class="story-summary">{esc(record.get("summary",""))}</div>{f"<div class=\"so-what\"><strong>So what?</strong> {esc(so_what)}</div>" if so_what else ""}{claims_html}<div class="story-meta" style="margin-top:10px"><span>Importance {int(record.get("importance",0) or 0)}</span><span>Confidence {int(record.get("confidence",0) or 0)}%</span><span>{total_sources} source{"s" if total_sources != 1 else ""} · {strong_sources} primary/official</span><span>{esc(age_label(record.get("created_at")))}{demo}</span></div></div>'


def select_story(story_id): st.session_state["selected_story"] = str(story_id)


def render_story_card(record,key_prefix="card",followable=False):
    st.markdown(story_card_html(record),unsafe_allow_html=True)
    cols = st.columns([3,2]) if followable else [1]
    with cols[0]:
        if st.button("Basahin →",key=f"{key_prefix}_read_{record['_record_key']}",use_container_width=True): select_story(record["id"]); st.rerun()
    if followable:
        with cols[1]:
            followed = is_followed(record["id"])
            if st.button("✓ Binabantayan" if followed else "+ Bantayan",key=f"{key_prefix}_follow_{record['_record_key']}",use_container_width=True): toggle_follow(record["id"]); st.rerun()


def render_category_tiles(records):
    cols = st.columns(4)
    for col,key in zip(cols,CATEGORY_META):
        meta=CATEGORY_META[key]; count=sum(1 for r in records if r.get("_category")==key)
        with col: st.markdown(f'<div class="category-tile"><div class="category-icon">{meta["emoji"]}</div><div class="category-name">{esc(meta["label"])}</div><div class="category-q">{esc(meta["question"])}</div><div class="category-count" style="color:{meta["accent"]}">{count} live topic{"s" if count != 1 else ""}</div></div>',unsafe_allow_html=True)


def pulse_score(records,category):
    subset=sorted([r for r in records if r.get("_category")==category],key=feed_score,reverse=True)[:5]
    if not subset:return 0
    return int(sum(.55*float(r.get("importance",50) or 50)+.45*freshness_score(r.get("created_at")) for r in subset)/len(subset))


def render_pulse(records):
    st.markdown('<div class="section-eyebrow">ALAM Pulse</div><div class="section-title">Gaano ka-active ang signals ngayon?</div>',unsafe_allow_html=True)
    cols=st.columns(4); scores={}
    for col,key in zip(cols,CATEGORY_META):
        score=pulse_score(records,key); scores[key]=score; meta=CATEGORY_META[key]; state="Active" if score>=70 else "Moving" if score>=50 else "Quiet"
        with col: st.markdown(f'<div class="pulse-card"><div class="pulse-row"><strong>{meta["emoji"]} {meta["label"]}</strong><span>{score} · {state}</span></div><div class="pulse-bar-bg"><div class="pulse-bar" style="width:{score}%;background:{meta["accent"]}"></div></div></div>',unsafe_allow_html=True)
    if scores:
        strongest=max(scores,key=scores.get); st.caption(f"Pinakamalakas na signal ngayon: {CATEGORY_META[strongest]['label']} ({scores[strongest]}/100). Hindi ito danger score; activity + importance signal lang.")


def init_cookie_state():
    if "followed_stories" not in st.session_state: st.session_state["followed_stories"]=[]
    if "visit_reference" not in st.session_state: st.session_state["visit_reference"]=None
    if stx is None:return None
    try:
        manager=stx.CookieManager(key="alam_cookie_manager")
        if not st.session_state.get("cookie_loaded"):
            raw_followed=manager.get(cookie="alam_followed")
            if raw_followed:
                try:
                    parsed=json.loads(raw_followed)
                    if isinstance(parsed,list): st.session_state["followed_stories"]=[str(x) for x in parsed]
                except Exception: pass
            raw_last=manager.get(cookie="alam_last_visit")
            if raw_last: st.session_state["visit_reference"]=parse_dt(raw_last)
            st.session_state["cookie_loaded"]=True
        return manager
    except Exception:return None


def is_followed(story_id): return str(story_id) in set(st.session_state.get("followed_stories",[]))


def persist_followed():
    manager=st.session_state.get("cookie_manager")
    if manager:
        try: manager.set("alam_followed",json.dumps(st.session_state.get("followed_stories",[])),expires_at=datetime.now()+timedelta(days=365),key="set_followed")
        except Exception: pass


def toggle_follow(story_id):
    sid=str(story_id); current=list(st.session_state.get("followed_stories",[]))
    current=[x for x in current if x!=sid] if sid in current else current+[sid]
    st.session_state["followed_stories"]=current; persist_followed()


def mark_visit_for_next_time():
    if st.session_state.get("visit_marked"):return
    manager=st.session_state.get("cookie_manager")
    if manager:
        try: manager.set("alam_last_visit",datetime.now(timezone.utc).isoformat(),expires_at=datetime.now()+timedelta(days=365),key="set_last_visit")
        except Exception: pass
    st.session_state["visit_marked"]=True


def render_since_you_were_gone(records):
    ref=st.session_state.get("visit_reference"); first_visit=ref is None or ref.year<=1970
    if first_visit: ref=datetime.now(timezone.utc)-timedelta(hours=24)
    changed=[r for r in records if parse_dt(r.get("created_at")).astimezone(timezone.utc)>ref.astimezone(timezone.utc)]
    counts={key:sum(1 for r in changed if r.get("_category")==key) for key in CATEGORY_META}; label="First visit: ito ang nagbago sa last 24h" if first_visit else "Since you were gone"
    st.markdown(f'<div class="section-eyebrow">{esc(label)}</div>',unsafe_allow_html=True)
    st.markdown("<div class='metric-strip'>"+"".join([f'<div class="metric-mini"><div class="metric-value">{len(changed)}</div><div class="metric-label">meaningful updates</div></div>',f'<div class="metric-mini"><div class="metric-value">{counts["practical"]}</div><div class="metric-label">practical / risk</div></div>',f'<div class="metric-mini"><div class="metric-value">{counts["reflection"]}</div><div class="metric-label">new reflections</div></div>',f'<div class="metric-mini"><div class="metric-value">{counts["trend"]}</div><div class="metric-label">trend updates</div></div>'])+"</div>",unsafe_allow_html=True)


def render_claim_ledger(record):
    claims=get_claims(record); st.markdown("#### Fact check layer"); st.caption("Dito malinaw kung alin ang sourced fact, inference, estimate, o assumption. Confidence score ≠ fact status.")
    if not claims: st.warning("Legacy/unclassified record ito. Hindi namin ia-assume na fact ang prose. Basahin ang sources sa ibaba bago gamitin bilang factual claim."); return
    for claim in claims:
        kind=claim["kind"]; label,color,bg,meaning=CLAIM_META[kind]; refs=claim.get("source_refs") or claim.get("sources") or []
        if isinstance(refs,str): refs=[refs]
        basis=claim.get("basis") or meaning; ref_text=f" · Source refs: {', '.join(map(str,refs))}" if refs else ""
        st.markdown(f'<div class="claim-box"><div class="claim-head"><span class="claim-label" style="color:{color};background:{bg}">{label}</span><span class="small-muted">{esc(basis)}{esc(ref_text)}</span></div><div class="claim-text">{esc(claim.get("text",""))}</div></div>',unsafe_allow_html=True)


def render_sources(record):
    sources=record.get("sources") or []; st.markdown("#### Sources")
    if not sources: st.error("Walang source na naka-attach sa record na ito. Treat factual claims as unverified until sourced."); return
    for idx,source in enumerate(sources,start=1):
        publisher=source.get("publisher") or "Source"; title=source.get("title") or publisher; url=source.get("url") or ""; stype=str(source.get("source_type") or "other").upper(); published=source.get("published_at") or "date not supplied"; safe_link=""
        if urlparse(url).scheme in {"http","https"}: safe_link=f'<a href="{esc(url)}" target="_blank">Open source ↗</a>'
        st.markdown(f'<div class="source-card"><div class="source-type">[{idx}] {esc(stype)}</div><div class="source-title">{esc(publisher)} — {esc(title)}</div><div class="source-meta">Published/updated: {esc(published)} · {safe_link}</div></div>',unsafe_allow_html=True)


def render_pr_vs_reality(record):
    content=record.get("content") or {}; pr=content.get("pr_vs_reality") or {}; official=pr.get("official_claim") or content.get("official_framing"); evidence=pr.get("evidence_says") or content.get("evidence_check"); verdict=pr.get("verdict") or content.get("alam_verdict")
    if not official and not evidence and not verdict:return
    st.markdown("#### PR vs Reality")
    st.markdown(f'<div class="pr-box"><div class="pr-cell"><div class="pr-head">What they say</div><div>{esc(official or "No formal PR/official claim captured.")}</div></div><div class="pr-cell"><div class="pr-head">What the evidence says</div><div>{format_value(evidence or "Evidence comparison not supplied.")}</div></div></div>{f"<div class=\"verdict\"><small>ALAM verdict</small>{esc(verdict)}</div>" if verdict else ""}',unsafe_allow_html=True)


def render_reading_levels(record):
    level=st.radio("Reading depth",["⚡ 30 sec","📖 2 min","🧠 Deep"],horizontal=True,key=f"reading_{record['id']}"); simple=level.split(" ",1)[1]
    if simple!="Deep": st.markdown(f'<div class="reading-box">{esc(get_reading_text(record,simple)).replace(chr(10),"<br>")}</div>',unsafe_allow_html=True); return False
    return True


def render_timeline(all_records,record):
    versions=story_versions(all_records,record["id"])
    if len(versions)<=1:return
    st.markdown("#### Story timeline — ano talaga ang nagbago?"); parts=['<div class="timeline">']
    for item in versions:
        content=item.get("content") or {}; change=content.get("change_summary") or {}
        if isinstance(change,dict):
            previous=change.get("previous"); now=change.get("now"); change_text=f"Dati: {previous or '—'} → Ngayon: {now or '—'}" if previous or now else item.get("summary","")
        else: change_text=str(change) if change else item.get("summary","")
        parts.append(f'<div class="timeline-item"><div class="timeline-date">{esc(parse_dt(item.get("created_at")).strftime("%Y-%m-%d %H:%M"))}</div><div class="timeline-title">Confidence {int(item.get("confidence",0) or 0)}% · Importance {int(item.get("importance",0) or 0)}</div><div class="timeline-change">{esc(change_text)}</div></div>')
    parts.append("</div>"); st.markdown("".join(parts),unsafe_allow_html=True)


def render_reflection_interaction(record):
    content=record.get("content") or {}; questions=content.get("questions") or []
    if not questions:return
    st.markdown("#### Argue With Me"); lead=questions[1] if len(questions)>1 else questions[0]; st.markdown(f"**{lead}**"); answer=st.radio("Ano ang instinctive answer mo?",["Agree","Unsure","Disagree"],horizontal=True,key=f"argue_{record['id']}")
    if st.button("Show the strongest other side",key=f"reveal_{record['id']}"): st.session_state[f"reveal_{record['id']}"]=True
    if st.session_state.get(f"reveal_{record['id']}"):
        st.info(f"Strongest challenge: {content.get('secular_challenge') or 'No opposing argument supplied.'}"); st.success(f"Strongest Christian response: {content.get('christian_response') or 'No Christian response supplied.'}"); st.caption(f"Your initial stance: {answer}. The point is not to score you; it's to expose the strongest tension.")
    st.markdown("**Tatlong tanong na pag-isipan:**")
    for q in questions[:3]: st.markdown(f"- {q}")


def render_detail(all_records,record):
    if st.button("← Balik",key="back_detail"): st.session_state.pop("selected_story",None); st.rerun()
    meta=category_meta(record); tags=" · ".join(record.get("tags",[])[:6]); total_sources,strong_sources=source_quality(record)
    st.markdown(f'<div class="detail-shell"><div class="story-label" style="background:{meta["soft"]};color:{meta["accent"]}">{esc(type_label(record))}</div><div class="detail-title">{esc(record.get("title"))}</div><div class="detail-summary">{esc(record.get("summary",""))}</div><div class="story-meta" style="margin-top:16px"><span>Importance {int(record.get("importance",0) or 0)}</span><span>Confidence {int(record.get("confidence",0) or 0)}%</span><span>{total_sources} sources · {strong_sources} primary/official</span><span>{esc(age_label(record.get("created_at")))}</span><span>{esc(tags)}</span></div></div>',unsafe_allow_html=True)
    cols=st.columns([2,1])
    with cols[0]: deep=render_reading_levels(record)
    with cols[1]:
        followed=is_followed(record["id"])
        if st.button("✓ Binabantayan" if followed else "+ Bantayan ang story",key=f"detail_follow_{record['id']}",use_container_width=True): toggle_follow(record["id"]); st.rerun()
    if not deep: render_claim_ledger(record); render_sources(record); return
    if record.get("why_it_matters"): st.markdown(f'<div class="detail-section"><div class="detail-heading">Bakit mahalaga</div><div class="detail-body">{esc(record.get("why_it_matters"))}</div></div>',unsafe_allow_html=True)
    render_pr_vs_reality(record); render_claim_ledger(record); content=record.get("content") or {}
    skip={"usefulness","novelty","history","reading_levels","pr_vs_reality","facts","inferences","assumptions","estimates","change_summary","estimated_saving_yen","time_minutes","travel_minutes","official_framing","evidence_check","alam_verdict"}
    for key,value in content.items():
        if key in skip or value in ("",None,[],{}): continue
        if key=="questions" and record.get("_category")=="reflection": continue
        heading=FIELD_LABELS.get(key,key.replace("_"," ").title()); st.markdown(f'<div class="detail-section"><div class="detail-heading">{esc(heading)}</div><div class="detail-body">{format_value(value)}</div></div>',unsafe_allow_html=True)
    mind_change=content.get("what_would_change_mind") or content.get("what_next")
    if mind_change: st.markdown(f'<div class="mind-change"><strong>What would change our mind?</strong><br>{esc(mind_change)}</div>',unsafe_allow_html=True)
    if record.get("_category")=="reflection": render_reflection_interaction(record)
    render_timeline(all_records,record)
    history=content.get("history")
    if isinstance(history,list) and history:
        st.markdown("#### Galaw ng signal")
        for point in history[-10:]:
            value=max(0,min(100,int(point.get("value",0) or 0))); st.markdown(f'<div style="margin:10px 0"><div class="kicker-row"><span class="small-muted">{esc(point.get("label",""))}</span><strong>{value}%</strong></div><div class="trend-bar-bg"><div class="trend-bar" style="width:{value}%;background:{meta["accent"]}"></div></div></div>',unsafe_allow_html=True)
    render_sources(record)


def top_by_category(records,category):
    subset=[r for r in records if r.get("_category")==category]; return max(subset,key=feed_score) if subset else None


def daily_signal_score(records):
    recent=[r for r in records if parse_dt(r.get("created_at"))>datetime.now(timezone.utc)-timedelta(hours=24)]
    if not recent:return 0
    return min(100,int(sum(min(100,float(r.get("importance",50) or 50)) for r in recent)/max(1,len(recent))+min(20,len(recent)*2)))


def render_today(all_records,records):
    if not records: st.markdown('<div class="empty-box">Wala pang intelligence records. Ready na ang app kapag may unang agent update.</div>',unsafe_allow_html=True); return
    render_since_you_were_gone(records); render_pulse(records); top_story=max(records,key=feed_score); signal=daily_signal_score(records); signal_text="BUSIER THAN NORMAL" if signal>=75 else "ACTIVE" if signal>=55 else "NORMAL"
    st.markdown(f'<div class="hero"><div class="hero-kicker">Today\'s signal · {signal}/100 · {signal_text}</div><div class="hero-title">{esc(top_story.get("title"))}</div><div class="hero-copy">{esc(top_story.get("summary",""))}</div></div>',unsafe_allow_html=True)
    if st.button("Basahin ang top story →",key="hero_read"): select_story(top_story["id"]); st.rerun()
    st.markdown('<div class="section-eyebrow">Your intelligence map</div><div class="section-title">Apat na paraan para maintindihan ang mundo.</div>',unsafe_allow_html=True); render_category_tiles(records)
    growing=[r for r in records if r.get("_category")=="trend" and str((r.get("content") or {}).get("direction","")).upper()=="ACCELERATING" and 45<=int((r.get("content") or {}).get("current_strength",r.get("importance",0)) or 0)<85]
    if growing:
        st.markdown('<div class="section-eyebrow">Quietly becoming important</div><div class="section-title">Hindi pa headline — pero lumalakas ang signal.</div>',unsafe_allow_html=True); cols=st.columns(2)
        for i,item in enumerate(sorted(growing,key=lambda r:(r.get("content") or {}).get("current_strength",0),reverse=True)[:4]):
            with cols[i%2]: render_story_card(item,"quiet",True)
    mode=st.radio("Catch-up mode",["5 minutes lang ako","May oras ako","Surprise me"],horizontal=True,label_visibility="collapsed",key="today_mode"); st.markdown('<div class="section-eyebrow">Para sa’yo ngayon</div>',unsafe_allow_html=True)
    if mode=="5 minutes lang ako": picks=[p for p in [top_by_category(records,c) for c in CATEGORY_META] if p]
    elif mode=="May oras ako": picks=sorted(records,key=feed_score,reverse=True)[:8]
    else:
        rng=random.Random(datetime.now().strftime("%Y-%m-%d-%H")); pool=sorted(records,key=feed_score,reverse=True)[:max(1,min(15,len(records)))]; picks=[rng.choice(pool)]
    cols=st.columns(2)
    for i,item in enumerate(picks):
        with cols[i%2]: render_story_card(item,f"today_{i}",True)


def filter_records(records,category):
    subset=[r for r in records if r.get("_category")==category]; search=st.text_input("Hanapin",placeholder="Search topics, Japan, AI, money, faith…",key=f"search_{category}"); all_tags=sorted({str(tag) for r in subset for tag in r.get("tags",[])}); selected_tags=st.multiselect("Filter by topic",all_tags,key=f"tags_{category}") if all_tags else []
    if search:
        q=search.lower().strip(); subset=[r for r in subset if q in json.dumps(r,ensure_ascii=False).lower()]
    if selected_tags: subset=[r for r in subset if set(selected_tags).intersection(map(str,r.get("tags",[])))]
    return subset


def render_category_page(records,category):
    meta=CATEGORY_META[category]; copy={"discover":"Fresh developments na worth knowing — hindi basta trending lang.","practical":"Tipid, safety, risk at Japan life advice na may totoong action.","reflection":"Current events, psychology, philosophy at Christian life — mas malalim kaysa headline.","trend":"Patterns, predictions at mga signal na unti-unting lumalakas o humihina."}[category]
    st.markdown(f'<div class="hero" style="padding-top:32px;padding-bottom:32px"><div class="hero-kicker" style="color:{meta["accent"]}">{meta["emoji"]} {meta["label"]}</div><div class="hero-title" style="font-size:clamp(2rem,4vw,3.5rem)">{esc(meta["question"])}</div><div class="hero-copy">{esc(copy)}</div></div>',unsafe_allow_html=True)
    subset=filter_records(records,category)
    if not subset: st.markdown('<div class="empty-box">Walang matching items ngayon. Mas okay ang tahimik kaysa filler.</div>',unsafe_allow_html=True); return
    subset.sort(key=(lambda r:(r.get("content") or {}).get("current_strength",r.get("importance",0))) if category=="trend" else feed_score,reverse=True); cols=st.columns(2)
    for i,item in enumerate(subset):
        with cols[i%2]: render_story_card(item,f"{category}_{i}",True)


def parse_yen(value):
    if isinstance(value,(int,float)): return float(value)
    if not isinstance(value,str): return None
    nums=[float(x.replace(",","")) for x in re.findall(r"\d[\d,]*(?:\.\d+)?",value)]
    return sum(nums)/len(nums) if nums else None


def render_action_center(records):
    subset=[r for r in records if r.get("_category")=="practical"]; st.markdown('<div class="hero" style="padding-top:32px;padding-bottom:32px"><div class="hero-kicker" style="color:#087D5B">🛡️ ACTION CENTER</div><div class="hero-title" style="font-size:clamp(2rem,4vw,3.4rem)">Ano ang dapat gawin, iwasan, o bantayan?</div><div class="hero-copy">Hindi lahat ng balita kailangan ng action. Dito lang ang may practical consequence.</div></div>',unsafe_allow_html=True); actions=defaultdict(int)
    for r in subset: actions[str((r.get("content") or {}).get("action","WATCH")).upper()]+=1
    st.markdown("<div class='metric-strip'>"+"".join([f'<div class="metric-mini"><div class="metric-value">{actions.get("DO NOW",0)+actions.get("APPLY",0)+actions.get("PREPARE",0)}</div><div class="metric-label">do / prepare now</div></div>',f'<div class="metric-mini"><div class="metric-value">{actions.get("AVOID",0)}</div><div class="metric-label">avoid</div></div>',f'<div class="metric-mini"><div class="metric-value">{actions.get("WATCH",0)+actions.get("WAIT",0)}</div><div class="metric-label">watch / wait</div></div>',f'<div class="metric-mini"><div class="metric-value">{len(subset)}</div><div class="metric-label">total practical items</div></div>'])+"</div>",unsafe_allow_html=True)
    choice=st.selectbox("Show",["ALL","DO NOW / PREPARE","AVOID","WATCH / WAIT","BUY / APPLY"])
    def matches(r):
        a=str((r.get("content") or {}).get("action","WATCH")).upper()
        if choice=="ALL":return True
        if choice=="DO NOW / PREPARE":return a in {"DO NOW","PREPARE"}
        if choice=="AVOID":return a=="AVOID"
        if choice=="WATCH / WAIT":return a in {"WATCH","WAIT","IGNORE"}
        return a in {"BUY","APPLY"}
    shown=[r for r in subset if matches(r)]; cols=st.columns(2)
    for i,item in enumerate(shown):
        with cols[i%2]:
            render_story_card(item,f"action_{i}",True); content=item.get("content") or {}; saving=content.get("estimated_saving_yen") or parse_yen(content.get("financial_impact")); minutes=content.get("time_minutes"); travel=content.get("travel_minutes",0) or 0
            if saving and minutes:
                try:
                    hourly=float(saving)/max(1,float(minutes)+float(travel))*60; verdict="SULIT" if hourly>=1500 else "MAYBE" if hourly>=800 else "SKIP kung extra trip/effort"; st.caption(f"Sulit ba? ~¥{hourly:,.0f}/hour equivalent effort value → {verdict}")
                except Exception: pass


def percent_value(value):
    if isinstance(value,(int,float)): return max(0,min(100,float(value)))
    if isinstance(value,str):
        m=re.search(r"\d+(?:\.\d+)?",value); return max(0,min(100,float(m.group()))) if m else 0
    return 0


def render_prediction_lab(records):
    predictions=[r for r in records if r.get("_category")=="trend" and (str(r.get("type","")).lower() in {"prediction","correction"} or (r.get("content") or {}).get("current_probability") is not None)]; st.markdown('<div class="hero" style="padding-top:32px;padding-bottom:32px"><div class="hero-kicker" style="color:#C95E19">🔮 PREDICTION LAB</div><div class="hero-title" style="font-size:clamp(2rem,4vw,3.4rem)">Track the forecast. Keep the mistakes.</div><div class="hero-copy">Hindi tinatago ang maling prediction. Calibration at self-correction ang goal, hindi pagiging mukhang laging tama.</div></div>',unsafe_allow_html=True); statuses=defaultdict(int)
    for r in predictions: statuses[str((r.get("content") or {}).get("status",r.get("status","OPEN"))).upper()]+=1
    st.markdown("<div class='metric-strip'>"+"".join([f'<div class="metric-mini"><div class="metric-value">{statuses.get("CONFIRMED",0)}</div><div class="metric-label">confirmed</div></div>',f'<div class="metric-mini"><div class="metric-value">{statuses.get("PARTLY_CONFIRMED",0)}</div><div class="metric-label">partly correct</div></div>',f'<div class="metric-mini"><div class="metric-value">{statuses.get("WRONG",0)}</div><div class="metric-label">wrong</div></div>',f'<div class="metric-mini"><div class="metric-value">{sum(v for k,v in statuses.items() if k in {"OPEN","STRENGTHENING","WEAKENING"})}</div><div class="metric-label">still open</div></div>'])+"</div>",unsafe_allow_html=True)
    if not predictions: st.markdown('<div class="empty-box">Wala pang prediction ledger. Agent 5 will add one only when evidence supports a real forecast.</div>',unsafe_allow_html=True); return
    for idx,r in enumerate(sorted(predictions,key=lambda x:parse_dt(x.get("created_at")),reverse=True)):
        content=r.get("content") or {}; p=percent_value(content.get("current_probability",content.get("initial_probability",0))); status=str(content.get("status",r.get("status","OPEN"))).upper(); st.markdown(f'<div class="story-card" style="margin-bottom:10px"><div class="story-title">{esc(content.get("statement") or r.get("title"))}</div><div class="kicker-row"><span class="small-muted">{esc(status)}</span><strong>{p:.0f}%</strong></div><div class="trend-bar-bg"><div class="trend-bar" style="width:{p}%;background:#C95E19"></div></div><div class="story-summary" style="margin-top:10px">{esc(r.get("summary",""))}</div></div>',unsafe_allow_html=True)
        if st.button("Open prediction →",key=f"pred_{idx}"): select_story(r["id"]); st.rerun()


def render_following(records):
    followed=set(st.session_state.get("followed_stories",[])); subset=[r for r in records if str(r.get("id")) in followed]; st.markdown('<div class="hero" style="padding-top:32px;padding-bottom:32px"><div class="hero-kicker">👁️ FOLLOWING</div><div class="hero-title" style="font-size:clamp(2rem,4vw,3.4rem)">Mga story na binabantayan mo.</div><div class="hero-copy">Kapag may material update sa same stable story ID, makikita rito ang latest state at timeline.</div></div>',unsafe_allow_html=True)
    if not subset: st.markdown('<div class="empty-box">Wala ka pang binabantayang topic. Tap “+ Bantayan” sa kahit anong story.</div>',unsafe_allow_html=True); return
    cols=st.columns(2)
    for i,item in enumerate(subset):
        with cols[i%2]: render_story_card(item,f"following_{i}",True)


def render_footer(all_records,records):
    live=[r for r in records if not r.get("demo")]; st.markdown("---"); st.caption(f"ALAM • {len(records)} current topics • {len(all_records)} historical records • {len(live)} live current records. GitHub = data layer; scheduled agents = intelligence engine. FACT labels require source support; INFERENCE/ASSUMPTION are shown separately.")


all_records=load_all_records(); records=latest_by_story(all_records); manager=init_cookie_state(); st.session_state["cookie_manager"]=manager; render_brand(records)
if records and all(r.get("demo") for r in records): st.markdown('<div class="demo-banner"><strong>Prototype mode:</strong> Sample content muna ito. Live agent records automatically replace/augment this feed as they are committed to GitHub.</div>',unsafe_allow_html=True)
selected_id=st.session_state.get("selected_story"); selected=next((r for r in records if str(r.get("id"))==str(selected_id)),None)
if selected: render_detail(all_records,selected)
else:
    page=st.radio("Navigation",["Today","Discover","Action Center","Reflect","Trends","Predictions","Following"],horizontal=True,label_visibility="collapsed",key="main_nav")
    if page=="Today": render_today(all_records,records)
    elif page=="Discover": render_category_page(records,"discover")
    elif page=="Action Center": render_action_center(records)
    elif page=="Reflect": render_category_page(records,"reflection")
    elif page=="Trends": render_category_page(records,"trend")
    elif page=="Predictions": render_prediction_lab(records)
    else: render_following(records)
mark_visit_for_next_time(); render_footer(all_records,records)
