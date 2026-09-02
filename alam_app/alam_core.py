import html
import json
import math
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import streamlit as st

try:
    import extra_streamlit_components as stx
except Exception:
    stx = None

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"

CATEGORY_META = {
    "discover": {"emoji": "🔭", "label": "Discover", "question": "Ano'ng bago?", "accent": "#5968F2", "soft": "#EEF0FF"},
    "practical": {"emoji": "🛡️", "label": "Practical", "question": "May dapat ba akong gawin?", "accent": "#087D5B", "soft": "#E9F7F2"},
    "reflection": {"emoji": "🧠", "label": "Reflect", "question": "Ano'ng ibig sabihin nito?", "accent": "#8254C7", "soft": "#F2ECFB"},
    "trend": {"emoji": "📈", "label": "Trends", "question": "Saan papunta ito?", "accent": "#C95E19", "soft": "#FFF0E6"},
}

TYPE_LABELS = {
    "important": "🔥 MAHALAGA", "saving": "💸 TIPID ALERT", "risk": "⚠️ INGAT",
    "reflection": "🤔 PAG-ISIPAN", "watch": "👀 WATCH LANG MUNA", "trend": "📈 LUMALAKAS",
    "prediction": "🔮 PREDICTION", "correction": "❌ MALI TAYO", "technology": "🤖 TECH",
    "japan": "🇯🇵 JAPAN", "discovery": "🔭 WORTH KNOWING", "policy": "🏛️ POLICY", "safety": "🛡️ SAFETY",
}

FIELD_LABELS = {
    "what_happened": "Ano'ng nangyari", "whats_new": "Ano'ng bago", "why_it_matters": "Bakit mahalaga",
    "skeptical_view": "Pero teka", "what_next": "Ano ang susunod na bantayan", "recommendation": "Bottom line",
    "who_is_affected": "Sino ang apektado", "when": "Kailan", "financial_impact": "Impact sa pera",
    "risk_if_ignored": "Risk kung i-ignore", "action": "Gawin", "deadline": "Deadline", "effort": "Effort",
    "potential_benefit": "Potential benefit", "downside": "Catch / downside", "human_problem": "Human problem",
    "psychology": "Psychology", "philosophical_conflict": "Philosophical conflict", "christian_analysis": "Christian perspective",
    "secular_challenge": "Strongest challenge", "christian_response": "Christian response",
    "modern_christian_life": "Sa modern Christian life", "questions": "Mga tanong na pag-isipan",
    "current_strength": "Current strength", "previous_strength": "Previous strength", "direction": "Direction",
    "evidence_for": "Evidence for", "evidence_against": "Evidence against", "connection": "Bakit posibleng connected",
    "alternative_explanation": "Alternative explanation", "watch_next": "Ano ang bantayan", "implications": "Possible implications",
    "statement": "Prediction", "current_probability": "Current probability", "initial_probability": "Initial probability",
    "status": "Status", "what_would_change_mind": "Ano ang magpapabago sa conclusion",
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
:root{--bg:#F5F4F0;--ink:#17202A;--line:rgba(23,32,42,.09);--shadow:0 14px 42px rgba(23,32,42,.075)}
html,body,[class*="css"]{font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
.stApp{background:radial-gradient(circle at 5% 0%,rgba(89,104,242,.10),transparent 29rem),radial-gradient(circle at 95% 2%,rgba(8,125,91,.09),transparent 27rem),var(--bg);color:var(--ink)}
.block-container{max-width:1180px;padding-top:1.05rem;padding-bottom:5rem}header[data-testid="stHeader"]{background:transparent}#MainMenu,footer{visibility:hidden}
.alam-brand{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:8px 2px 16px}.alam-logo{font-size:2.1rem;font-weight:950;letter-spacing:-.065em}.alam-logo span{display:inline-block;margin-left:.48rem;font-size:.78rem;font-weight:750;letter-spacing:0;color:#667085}.live-pill{display:inline-flex;align-items:center;gap:7px;border-radius:999px;padding:7px 11px;background:rgba(8,125,91,.10);color:#087454;font-size:.76rem;font-weight:850}.live-dot{width:8px;height:8px;border-radius:50%;background:#087D5B;box-shadow:0 0 0 5px rgba(8,125,91,.11)}
.hero{border:1px solid rgba(23,32,42,.07);border-radius:30px;padding:clamp(25px,4vw,52px);background:linear-gradient(135deg,rgba(255,255,255,.98),rgba(255,255,255,.84)),linear-gradient(120deg,#EEF0FF,#E9F7F2);box-shadow:var(--shadow);overflow:hidden;position:relative;margin-bottom:20px}.hero:after{content:"";position:absolute;width:260px;height:260px;right:-75px;top:-100px;border-radius:50%;background:linear-gradient(135deg,rgba(89,104,242,.18),rgba(8,125,91,.14))}.hero-kicker{font-size:.75rem;font-weight:900;letter-spacing:.09em;text-transform:uppercase;color:#5968F2;margin-bottom:10px}.hero-title{font-size:clamp(2rem,5vw,4.5rem);line-height:.98;letter-spacing:-.055em;font-weight:950;max-width:850px;margin:0 0 15px}.hero-copy{font-size:clamp(1rem,1.8vw,1.2rem);line-height:1.55;color:#475467;max-width:800px}
.section-eyebrow{font-size:.72rem;font-weight:900;letter-spacing:.09em;text-transform:uppercase;color:#98A2B3;margin:25px 0 7px}.section-title{font-size:clamp(1.45rem,2.5vw,2.05rem);font-weight:930;letter-spacing:-.038em;margin:0 0 12px}
.story-card{background:rgba(255,255,255,.94);border:1px solid var(--line);border-radius:23px;padding:21px 21px 17px;box-shadow:0 8px 26px rgba(23,32,42,.05);height:100%;position:relative;overflow:hidden}.story-card:hover{transform:translateY(-2px);box-shadow:0 15px 36px rgba(23,32,42,.085)}.story-accent{position:absolute;top:0;left:0;right:0;height:4px}.story-label{display:inline-block;border-radius:999px;padding:5px 9px;font-size:.69rem;font-weight:900;letter-spacing:.035em;margin-bottom:13px}.story-title{font-size:1.22rem;line-height:1.18;letter-spacing:-.026em;font-weight:900;margin:0 0 9px}.story-summary{color:#475467;line-height:1.55;font-size:.93rem;margin-bottom:14px}.story-meta{color:#98A2B3;font-size:.73rem;display:flex;gap:9px;flex-wrap:wrap}.so-what{margin-top:13px;padding:11px 13px;border-radius:14px;background:#F7F8FA;color:#344054;font-size:.83rem;line-height:1.45}.claim-mini{display:flex;gap:5px;margin-top:10px;flex-wrap:wrap}.claim-dot{font-size:.64rem;font-weight:900;padding:4px 7px;border-radius:999px}
.category-tile,.metric-mini,.pulse-card,.claim-box,.source-card,.pr-cell,.reading-box,.mind-change{background:rgba(255,255,255,.82);border:1px solid var(--line);border-radius:18px}.category-tile{padding:19px;min-height:154px}.category-icon{font-size:1.45rem;margin-bottom:12px}.category-name{font-size:1.04rem;font-weight:900}.category-q{color:#667085;font-size:.85rem;margin-top:4px}.category-count{margin-top:16px;font-size:.77rem;font-weight:850}.metric-strip{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:6px 0 20px}.metric-mini{padding:13px 15px}.metric-value{font-size:1.16rem;font-weight:930}.metric-label{font-size:.71rem;color:#98A2B3}.pulse-card{padding:14px 15px;margin-bottom:9px}.pulse-row,.kicker-row{display:flex;justify-content:space-between;gap:10px;align-items:center}.pulse-bar-bg,.trend-bar-bg{height:8px;border-radius:99px;background:#ECEFF2;overflow:hidden;margin-top:8px}.pulse-bar,.trend-bar{height:100%;border-radius:99px}
.detail-shell{background:rgba(255,255,255,.94);border:1px solid var(--line);border-radius:28px;padding:clamp(22px,4vw,44px);box-shadow:var(--shadow);margin:10px 0 18px}.detail-title{font-size:clamp(1.8rem,4vw,3.15rem);line-height:1.03;letter-spacing:-.046em;font-weight:950;margin:10px 0 14px}.detail-summary{font-size:1.06rem;color:#475467;line-height:1.65}.detail-section{margin:20px 0;padding-top:18px;border-top:1px solid var(--line)}.detail-heading{font-size:.75rem;font-weight:900;letter-spacing:.075em;text-transform:uppercase;color:#667085;margin-bottom:7px}.detail-body{color:#344054;line-height:1.68}.claim-box,.source-card,.reading-box,.mind-change{padding:13px 14px;margin:8px 0}.claim-label{font-size:.67rem;font-weight:950;padding:4px 7px;border-radius:999px}.claim-text{line-height:1.55;color:#344054;font-size:.91rem}.small-muted,.source-meta{font-size:.72rem;color:#98A2B3}.source-type{font-size:.63rem;font-weight:900;color:#667085}.source-title{font-size:.87rem;font-weight:800;margin-top:3px}.pr-box{display:grid;grid-template-columns:1fr 1fr;gap:10px}.pr-cell{padding:15px}.pr-head{font-size:.68rem;font-weight:950;text-transform:uppercase;color:#667085}.verdict{margin-top:10px;border-radius:17px;padding:15px;background:#17202A;color:white}.timeline{border-left:2px solid #D8DDE5;margin:10px 0 10px 7px;padding-left:18px}.timeline-item{margin:0 0 19px}.timeline-date{font-size:.69rem;font-weight:900;color:#98A2B3}.timeline-title{font-size:.92rem;font-weight:850}.timeline-change{font-size:.82rem;color:#667085}.demo-banner{border-radius:16px;padding:11px 14px;background:#FFF7E8;color:#815900;border:1px solid #F5D995;font-size:.82rem;margin:6px 0 18px}.empty-box{border:1px dashed rgba(23,32,42,.18);border-radius:20px;padding:34px 22px;text-align:center;color:#667085;background:rgba(255,255,255,.45)}
div[data-testid="stRadio"]>div{gap:.3rem}div[data-testid="stRadio"] label{background:rgba(255,255,255,.74);border:1px solid var(--line);padding:.45rem .75rem;border-radius:999px}.stButton>button{border-radius:13px!important;font-weight:850!important}
@media(max-width:760px){.block-container{padding-left:1rem;padding-right:1rem}.metric-strip{grid-template-columns:repeat(2,1fr)}.pr-box{grid-template-columns:1fr}.alam-logo span{display:block;margin:.12rem 0 0}}
</style>
"""


def esc(value): return html.escape(str(value if value is not None else ""))

def normalize_category(record):
    raw = f"{record.get('agent', '')} {record.get('type', '')}".lower()
    if any(x in raw for x in ("practical", "risk", "saving", "safety")): return "practical"
    if any(x in raw for x in ("reflection", "reflect", "psychology")): return "reflection"
    if any(x in raw for x in ("trend", "prediction", "correction")): return "trend"
    return "discover"

def parse_dt(value):
    if isinstance(value, datetime): return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not value: return datetime(1970, 1, 1, tzinfo=timezone.utc)
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00")); return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception: return datetime(1970, 1, 1, tzinfo=timezone.utc)

def age_label(value):
    hours = max(0, (datetime.now(timezone.utc) - parse_dt(value).astimezone(timezone.utc)).total_seconds() / 3600)
    if hours < 1: return f"{max(1, int(hours * 60))}m ago"
    if hours < 24: return f"{int(hours)}h ago"
    days = int(hours / 24); return "kahapon" if days == 1 else f"{days} days ago" if days < 7 else parse_dt(value).strftime("%b %d")

def freshness_score(value):
    hours = max(0, (datetime.now(timezone.utc) - parse_dt(value).astimezone(timezone.utc)).total_seconds() / 3600); return 100 * math.exp(-hours / 42)

def feed_score(record):
    c = record.get("content") or {}
    return (0.35 * float(record.get("importance", 50) or 50) + 0.20 * freshness_score(record.get("created_at")) + 0.15 * float(c.get("usefulness", 55) or 55) + 0.10 * float(record.get("confidence", 50) or 50) + 0.10 * float(c.get("novelty", 55) or 55) + 10 + min(8, len(record.get("sources") or []) * 2))

@st.cache_data(ttl=60)
def load_all_records():
    records = []
    if not DATA_DIR.exists(): return records
    for path in sorted(DATA_DIR.rglob("*.json")):
        if path.name.startswith("_"): continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8")); batch = payload if isinstance(payload, list) else [payload]
            for idx, item in enumerate(batch):
                if not isinstance(item, dict) or not item.get("id") or not item.get("title"): continue
                item = dict(item); item["_path"] = str(path.relative_to(APP_DIR)); item["_category"] = normalize_category(item); item["_record_key"] = f"{item['_path']}::{idx}"; records.append(item)
        except Exception: continue
    return sorted(records, key=lambda r: parse_dt(r.get("created_at")), reverse=True)

def latest_by_story(records):
    latest = {}
    for r in sorted(records, key=lambda x: parse_dt(x.get("created_at"))): latest[str(r["id"])] = r
    return sorted(latest.values(), key=lambda r: parse_dt(r.get("created_at")), reverse=True)

def story_versions(records, story_id): return sorted([r for r in records if str(r.get("id")) == str(story_id)], key=lambda r: parse_dt(r.get("created_at")))
def category_meta(record): return CATEGORY_META.get(record.get("_category", "discover"), CATEGORY_META["discover"])
def type_label(record): return TYPE_LABELS.get(str(record.get("type", "")).lower(), f"{category_meta(record)['emoji']} UPDATE")

def get_claims(record):
    claims = record.get("claims")
    if isinstance(claims, list):
        out = []
        for c in claims:
            if isinstance(c, dict) and c.get("text"):
                kind = str(c.get("kind") or c.get("label") or "OPINION").upper(); out.append({**c, "kind": kind if kind in CLAIM_META else "OPINION"})
        return out
    out = []
    for key, kind in (("facts", "FACT"), ("inferences", "INFERENCE"), ("assumptions", "ASSUMPTION"), ("estimates", "ESTIMATE")):
        vals = (record.get("content") or {}).get(key); vals = [vals] if isinstance(vals, str) else vals
        if isinstance(vals, list): out.extend({"kind": kind, "text": str(v)} for v in vals if v)
    return out

def claim_counts(record):
    counts = defaultdict(int)
    for c in get_claims(record): counts[c["kind"]] += 1
    return counts

def source_quality(record):
    sources = record.get("sources") or []; strong = sum(str(s.get("source_type", "")).lower() in {"official", "primary", "research", "filing"} for s in sources); return len(sources), strong

def summarize_so_what(record):
    c = record.get("content") or {}
    for key in ("action", "recommendation", "potential_benefit", "watch_next", "modern_christian_life"):
        value = c.get(key)
        if isinstance(value, str) and value.strip(): return value.strip()
    return record.get("why_it_matters") or ""

def reading_text(record, level):
    c = record.get("content") or {}; reading = c.get("reading_levels") or {}; aliases = {"30 sec": ("30_sec", "quick"), "2 min": ("2_min", "medium")}
    for key in aliases.get(level, ()):
        value = reading.get(key)
        if isinstance(value, str) and value.strip(): return value.strip()
    if level == "30 sec": return " ".join(x for x in [record.get("summary", ""), summarize_so_what(record)] if x)
    parts = [record.get("summary", ""), record.get("why_it_matters", "")]
    for key in ("whats_new", "skeptical_view", "recommendation", "action", "what_next"):
        if isinstance(c.get(key), str): parts.append(c[key])
    return "\n\n".join(dict.fromkeys(x.strip() for x in parts if x and x.strip()))
def format_value(value):
    if isinstance(value, list): return "<ul>" + "".join(f"<li>{esc(v)}</li>" for v in value) + "</ul>"
    if isinstance(value, dict): return "<br>".join(f"<strong>{esc(str(k).replace('_', ' ').title())}:</strong> {esc(v)}" for k, v in value.items())
    return esc(value)
def parse_yen(value):
    if isinstance(value, (int, float)): return float(value)
    if not isinstance(value, str): return None
    nums = [float(x.replace(",", "")) for x in re.findall(r"\d[\d,]*(?:\.\d+)?", value)]; return sum(nums) / len(nums) if nums else None
def percent_value(value):
    if isinstance(value, (int, float)): return max(0, min(100, float(value)))
    if isinstance(value, str):
        m = re.search(r"\d+(?:\.\d+)?", value); return max(0, min(100, float(m.group()))) if m else 0
    return 0

def init_browser_state():
    st.session_state.setdefault("followed_stories", []); st.session_state.setdefault("visit_reference", None)
    if stx is None: return None
    try:
        manager = st.session_state.get("_alam_cookie_manager")
        if manager is None:
            manager = stx.CookieManager(key="alam_cookie_manager")
            st.session_state["_alam_cookie_manager"] = manager
        if not st.session_state.get("cookie_loaded"):
            cookies = {}
            try:
                cookies = dict(st.context.cookies)
            except Exception:
                pass
            raw = cookies.get("alam_followed") or manager.get(cookie="alam_followed")
            if raw:
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, list): st.session_state["followed_stories"] = [str(x) for x in parsed]
                except Exception: pass
            last = cookies.get("alam_last_visit") or manager.get(cookie="alam_last_visit")
            if last: st.session_state["visit_reference"] = parse_dt(last)
            st.session_state["cookie_loaded"] = True
        return manager
    except Exception: return None
def is_followed(story_id): return str(story_id) in set(st.session_state.get("followed_stories", []))
def toggle_follow(story_id, manager=None):
    sid = str(story_id); current = list(st.session_state.get("followed_stories", [])); current = [x for x in current if x != sid] if sid in current else current + [sid]; st.session_state["followed_stories"] = current
    if manager:
        try: manager.set("alam_followed", json.dumps(current), expires_at=datetime.now() + timedelta(days=365), key="set_followed")
        except Exception: pass
def mark_visit(manager=None):
    if st.session_state.get("visit_marked"): return
    if manager:
        try: manager.set("alam_last_visit", datetime.now(timezone.utc).isoformat(), expires_at=datetime.now() + timedelta(days=365), key="set_last_visit")
        except Exception: pass
    st.session_state["visit_marked"] = True