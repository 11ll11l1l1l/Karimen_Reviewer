import json
import math
import random
import html
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import streamlit as st

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"

st.set_page_config(
    page_title="ALAM — Ano'ng bago. Bakit mahalaga.",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="collapsed",
)

CATEGORY_META = {
    "discover": {
        "emoji": "🔭",
        "label": "Discover",
        "question": "Ano'ng bago?",
        "accent": "#5B6CFF",
        "soft": "#EEF0FF",
    },
    "practical": {
        "emoji": "🛡️",
        "label": "Practical",
        "question": "May dapat ba akong gawin?",
        "accent": "#0B8F67",
        "soft": "#E8F7F1",
    },
    "reflection": {
        "emoji": "🧠",
        "label": "Reflect",
        "question": "Ano'ng ibig sabihin nito?",
        "accent": "#8C5BD7",
        "soft": "#F3ECFC",
    },
    "trend": {
        "emoji": "📈",
        "label": "Trends",
        "question": "Saan papunta ito?",
        "accent": "#D66A22",
        "soft": "#FFF0E5",
    },
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
}

CSS = """
<style>
:root {
    --bg: #F7F6F2;
    --ink: #17202A;
    --muted: #667085;
    --card: rgba(255,255,255,.92);
    --line: rgba(23,32,42,.09);
    --shadow: 0 12px 35px rgba(23,32,42,.07);
}
html, body, [class*="css"] {
    font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
.stApp {
    background:
      radial-gradient(circle at 8% 0%, rgba(91,108,255,.09), transparent 28rem),
      radial-gradient(circle at 92% 5%, rgba(11,143,103,.08), transparent 26rem),
      var(--bg);
    color: var(--ink);
}
.block-container {
    max-width: 1180px;
    padding-top: 1.25rem;
    padding-bottom: 5rem;
}
header[data-testid="stHeader"] { background: transparent; }
#MainMenu, footer { visibility: hidden; }

.alam-brand {
    display:flex; align-items:center; justify-content:space-between;
    gap:16px; padding: 10px 2px 20px;
}
.alam-logo {
    font-size: 2rem; font-weight: 900; letter-spacing: -0.06em;
}
.alam-logo span {
    display:inline-block; margin-left:.45rem; font-size:.82rem; font-weight:700;
    letter-spacing:0; color:#667085; vertical-align:middle;
}
.hero {
    border:1px solid rgba(23,32,42,.07);
    border-radius:28px;
    padding: clamp(24px, 4vw, 52px);
    background:
      linear-gradient(135deg, rgba(255,255,255,.96), rgba(255,255,255,.82)),
      linear-gradient(120deg, #EEF0FF, #E8F7F1);
    box-shadow: var(--shadow);
    overflow:hidden;
    position:relative;
    margin-bottom:22px;
}
.hero:after {
    content:"";
    position:absolute; width:240px; height:240px; right:-70px; top:-90px;
    border-radius:50%; background:linear-gradient(135deg, rgba(91,108,255,.18), rgba(11,143,103,.15));
    filter:blur(2px);
}
.hero-kicker {
    font-size:.78rem; font-weight:850; letter-spacing:.08em; text-transform:uppercase;
    color:#5B6CFF; margin-bottom:10px;
}
.hero-title {
    font-size:clamp(2rem, 5vw, 4.6rem);
    line-height:.98; letter-spacing:-.055em; font-weight:950; max-width:830px;
    margin:0 0 16px;
}
.hero-copy {
    font-size:clamp(1rem, 1.8vw, 1.25rem);
    line-height:1.55; color:#475467; max-width:760px;
}
.live-pill {
    display:inline-flex; align-items:center; gap:7px;
    border-radius:999px; padding:7px 11px; background:rgba(11,143,103,.10);
    color:#087454; font-size:.78rem; font-weight:800;
}
.live-dot { width:8px; height:8px; border-radius:50%; background:#0B8F67; box-shadow:0 0 0 5px rgba(11,143,103,.11); }

.section-eyebrow {
    font-size:.74rem; font-weight:850; letter-spacing:.08em; text-transform:uppercase;
    color:#98A2B3; margin:26px 0 8px;
}
.section-title {
    font-size:clamp(1.45rem, 2.5vw, 2rem); font-weight:900; letter-spacing:-.035em;
    margin:0 0 12px;
}
.story-card {
    background:var(--card); border:1px solid var(--line); border-radius:22px;
    padding:21px 21px 17px; box-shadow:0 7px 24px rgba(23,32,42,.045);
    transition: transform .18s ease, box-shadow .18s ease;
    height:100%;
    position:relative;
    overflow:hidden;
}
.story-card:hover { transform:translateY(-2px); box-shadow:0 14px 34px rgba(23,32,42,.08); }
.story-accent { position:absolute; top:0; left:0; right:0; height:4px; }
.story-label {
    display:inline-block; border-radius:999px; padding:5px 9px;
    font-size:.7rem; font-weight:850; letter-spacing:.035em; margin-bottom:13px;
}
.story-title {
    font-size:1.22rem; line-height:1.18; letter-spacing:-.025em; font-weight:880;
    margin:0 0 9px;
}
.story-summary { color:#475467; line-height:1.55; font-size:.93rem; margin-bottom:15px; }
.story-meta { color:#98A2B3; font-size:.75rem; display:flex; gap:10px; flex-wrap:wrap; }
.so-what {
    margin-top:14px; padding:12px 14px; border-radius:15px;
    background:#F7F8FA; color:#344054; font-size:.84rem; line-height:1.45;
}
.category-tile {
    border-radius:21px; padding:19px; border:1px solid var(--line); background:rgba(255,255,255,.74);
    min-height:155px;
}
.category-icon { font-size:1.45rem; margin-bottom:13px; }
.category-name { font-size:1.04rem; font-weight:880; letter-spacing:-.02em; }
.category-q { color:#667085; font-size:.86rem; line-height:1.45; margin-top:4px; }
.category-count { margin-top:17px; font-size:.78rem; font-weight:800; }

.metric-strip {
    display:grid; grid-template-columns:repeat(4, 1fr); gap:10px; margin:6px 0 20px;
}
.metric-mini {
    background:rgba(255,255,255,.72); border:1px solid var(--line); border-radius:17px;
    padding:13px 15px;
}
.metric-value { font-size:1.15rem; font-weight:900; }
.metric-label { font-size:.72rem; color:#98A2B3; margin-top:2px; }

.detail-shell {
    background:rgba(255,255,255,.9); border:1px solid var(--line); border-radius:26px;
    padding:clamp(22px,4vw,44px); box-shadow:var(--shadow); margin:12px 0 22px;
}
.detail-title {
    font-size:clamp(1.8rem,4vw,3.1rem); line-height:1.03; letter-spacing:-.045em;
    font-weight:950; margin:10px 0 14px;
}
.detail-summary { font-size:1.07rem; color:#475467; line-height:1.65; }
.detail-section {
    margin:20px 0; padding-top:18px; border-top:1px solid var(--line);
}
.detail-heading { font-size:.78rem; font-weight:900; letter-spacing:.07em; text-transform:uppercase; color:#667085; margin-bottom:7px; }
.detail-body { color:#344054; line-height:1.68; }
.demo-banner {
    border-radius:16px; padding:11px 14px; background:#FFF7E8; color:#815900;
    border:1px solid #F5D995; font-size:.83rem; margin:6px 0 18px;
}
.empty-box {
    border:1px dashed rgba(23,32,42,.18); border-radius:20px; padding:34px 22px; text-align:center;
    color:#667085; background:rgba(255,255,255,.45);
}
.trend-bar-bg { width:100%; height:9px; border-radius:99px; background:#EEF0F3; overflow:hidden; margin-top:8px; }
.trend-bar { height:100%; border-radius:99px; }
.kicker-row { display:flex; align-items:center; justify-content:space-between; gap:10px; flex-wrap:wrap; }
.small-muted { color:#98A2B3; font-size:.77rem; }

div[data-testid="stRadio"] > div { gap:.3rem; }
div[data-testid="stRadio"] label {
    background:rgba(255,255,255,.72); border:1px solid var(--line);
    padding:.46rem .78rem; border-radius:999px; margin-right:.25rem;
}
div[data-testid="stRadio"] label:has(input:checked) {
    background:#17202A; color:white; border-color:#17202A;
}
.stButton > button {
    border-radius:13px !important;
    border:1px solid rgba(23,32,42,.11) !important;
    font-weight:800 !important;
}
.stButton > button:hover {
    border-color:#17202A !important;
}
div[data-testid="stTextInput"] input, div[data-testid="stMultiSelect"] {
    border-radius:14px;
}
@media (max-width: 760px) {
    .block-container { padding-left:1rem; padding-right:1rem; }
    .metric-strip { grid-template-columns:repeat(2, 1fr); }
    .hero { border-radius:22px; }
    .alam-logo span { display:block; margin:.12rem 0 0; }
}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


def esc(value):
    return html.escape(str(value if value is not None else ""))


def normalize_category(record):
    raw = str(record.get("agent", "")).lower() + " " + str(record.get("type", "")).lower()
    if "practical" in raw or "risk" in raw or "saving" in raw:
        return "practical"
    if "reflection" in raw or "reflect" in raw or "psychology" in raw:
        return "reflection"
    if "trend" in raw or "prediction" in raw:
        return "trend"
    return "discover"


def parse_dt(value):
    if not value:
        return datetime(1970, 1, 1, tzinfo=timezone.utc)
    try:
        text = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return datetime(1970, 1, 1, tzinfo=timezone.utc)


def age_label(value):
    dt = parse_dt(value)
    now = datetime.now(timezone.utc)
    hours = max(0, (now - dt.astimezone(timezone.utc)).total_seconds() / 3600)
    if hours < 1:
        return "bagong update"
    if hours < 24:
        return f"{int(hours)}h ago"
    days = int(hours / 24)
    if days == 1:
        return "kahapon"
    if days < 7:
        return f"{days} days ago"
    return dt.strftime("%b %d")


def freshness_score(value):
    dt = parse_dt(value)
    hours = max(0, (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds() / 3600)
    return max(0, 100 * math.exp(-hours / 42))


def feed_score(record):
    importance = float(record.get("importance", 50) or 50)
    confidence = float(record.get("confidence", 50) or 50)
    content = record.get("content") or {}
    usefulness = float(content.get("usefulness", record.get("usefulness", 55)) or 55)
    novelty = float(content.get("novelty", record.get("novelty", 55)) or 55)
    return (
        0.35 * importance
        + 0.20 * freshness_score(record.get("created_at"))
        + 0.15 * usefulness
        + 0.10 * confidence
        + 0.10 * novelty
        + 10
    )


@st.cache_data(ttl=60)
def load_records():
    records = []
    if not DATA_DIR.exists():
        return records
    for path in sorted(DATA_DIR.rglob("*.json")):
        if path.name.startswith("_"):
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            batch = payload if isinstance(payload, list) else [payload]
            for item in batch:
                if not isinstance(item, dict):
                    continue
                if not item.get("id") or not item.get("title"):
                    continue
                item["_path"] = str(path.relative_to(APP_DIR))
                item["_category"] = normalize_category(item)
                records.append(item)
        except Exception:
            continue

    deduped = {}
    for item in records:
        rid = str(item.get("id"))
        existing = deduped.get(rid)
        if existing is None or parse_dt(item.get("created_at")) >= parse_dt(existing.get("created_at")):
            deduped[rid] = item

    output = list(deduped.values())
    output.sort(key=lambda x: parse_dt(x.get("created_at")), reverse=True)
    return output


def category_meta(record):
    return CATEGORY_META.get(record.get("_category", "discover"), CATEGORY_META["discover"])


def type_label(record):
    return TYPE_LABELS.get(str(record.get("type", "")).lower(), TYPE_LABELS.get(record.get("_category"), "🔭 UPDATE"))


def render_brand(records):
    latest = max((parse_dt(r.get("created_at")) for r in records), default=None)
    latest_text = age_label(latest.isoformat()) if latest else "waiting for first update"
    st.markdown(
        f"""
        <div class="alam-brand">
          <div class="alam-logo">ALAM <span>Ano'ng bago. Bakit mahalaga. Ano'ng gagawin.</span></div>
          <div class="live-pill"><span class="live-dot"></span> Updated {esc(latest_text)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_category_tiles(records):
    cols = st.columns(4)
    for col, key in zip(cols, ["discover", "practical", "reflection", "trend"]):
        meta = CATEGORY_META[key]
        count = sum(1 for r in records if r.get("_category") == key)
        with col:
            st.markdown(
                f"""
                <div class="category-tile">
                  <div class="category-icon">{meta['emoji']}</div>
                  <div class="category-name">{esc(meta['label'])}</div>
                  <div class="category-q">{esc(meta['question'])}</div>
                  <div class="category-count" style="color:{meta['accent']}">{count} item{'s' if count != 1 else ''}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def summarize_so_what(record):
    content = record.get("content") or {}
    for key in ("action", "recommendation", "potential_benefit", "watch_next", "modern_christian_life"):
        value = content.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return record.get("why_it_matters") or ""


def story_card_html(record):
    meta = category_meta(record)
    title = esc(record.get("title", "Untitled"))
    summary = esc(record.get("summary", ""))
    importance = int(record.get("importance", 0) or 0)
    confidence = int(record.get("confidence", 0) or 0)
    tag = esc(type_label(record))
    so_what = esc(summarize_so_what(record))
    demo = " • DEMO" if record.get("demo") else ""
    so_what_html = f'<div class="so-what"><strong>So what?</strong> {so_what}</div>' if so_what else ""
    return f"""
    <div class="story-card">
      <div class="story-accent" style="background:{meta['accent']}"></div>
      <div class="story-label" style="background:{meta['soft']};color:{meta['accent']}">{tag}</div>
      <div class="story-title">{title}</div>
      <div class="story-summary">{summary}</div>
      {so_what_html}
      <div class="story-meta">
        <span>Importance {importance}</span>
        <span>Confidence {confidence}%</span>
        <span>{esc(age_label(record.get('created_at')))}{demo}</span>
      </div>
    </div>
    """


def set_selected(record_id):
    st.session_state["selected_story"] = record_id


def render_story_card(record, key_prefix="card"):
    st.markdown(story_card_html(record), unsafe_allow_html=True)
    if st.button("Basahin →", key=f"{key_prefix}_{record['id']}", use_container_width=True):
        set_selected(record["id"])
        st.rerun()


def format_value(value):
    if isinstance(value, list):
        items = "".join(f"<li>{esc(v)}</li>" for v in value)
        return f"<ul>{items}</ul>"
    if isinstance(value, dict):
        parts = []
        for k, v in value.items():
            parts.append(f"<strong>{esc(str(k).replace('_',' ').title())}:</strong> {esc(v)}")
        return "<br>".join(parts)
    return esc(value)


def render_detail(record):
    meta = category_meta(record)
    if st.button("← Balik", key="back_detail"):
        st.session_state.pop("selected_story", None)
        st.rerun()

    tags = " · ".join(record.get("tags", [])[:5])
    demo = " · DEMO CONTENT" if record.get("demo") else ""
    st.markdown(
        f"""
        <div class="detail-shell">
          <div class="story-label" style="background:{meta['soft']};color:{meta['accent']}">{esc(type_label(record))}</div>
          <div class="detail-title">{esc(record.get('title'))}</div>
          <div class="detail-summary">{esc(record.get('summary', ''))}</div>
          <div class="story-meta" style="margin-top:16px">
            <span>Importance {int(record.get('importance', 0) or 0)}</span>
            <span>Confidence {int(record.get('confidence', 0) or 0)}%</span>
            <span>{esc(age_label(record.get('created_at')))}</span>
            <span>{esc(tags)}{demo}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    why = record.get("why_it_matters")
    if why:
        st.markdown(
            f"""
            <div class="detail-section">
              <div class="detail-heading">Bakit mahalaga</div>
              <div class="detail-body">{esc(why)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    content = record.get("content") or {}
    reserved = {"usefulness", "novelty", "history"}
    for key, value in content.items():
        if key in reserved or value in ("", None, [], {}):
            continue
        heading = FIELD_LABELS.get(key, key.replace("_", " ").title())
        st.markdown(
            f"""
            <div class="detail-section">
              <div class="detail-heading">{esc(heading)}</div>
              <div class="detail-body">{format_value(value)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    history = content.get("history")
    if isinstance(history, list) and history:
        st.markdown("#### Galaw ng signal")
        for point in history[-8:]:
            label = esc(point.get("label", ""))
            value = max(0, min(100, int(point.get("value", 0) or 0)))
            st.markdown(
                f"""
                <div style="margin:10px 0">
                  <div class="kicker-row"><span class="small-muted">{label}</span><strong>{value}%</strong></div>
                  <div class="trend-bar-bg"><div class="trend-bar" style="width:{value}%;background:{meta['accent']}"></div></div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    sources = record.get("sources") or []
    if sources:
        st.markdown("#### Sources")
        for source in sources:
            publisher = source.get("publisher") or "Source"
            title = source.get("title") or publisher
            url = source.get("url") or ""
            parsed = urlparse(url)
            if parsed.scheme in {"http", "https"}:
                st.markdown(f"- [{publisher} — {title}]({url})")
            else:
                st.markdown(f"- {publisher} — {title}")


def top_by_category(records, category):
    subset = [r for r in records if r.get("_category") == category]
    return max(subset, key=feed_score) if subset else None


def render_today(records):
    if not records:
        st.markdown('<div class="empty-box">Wala pang intelligence records. Ready na ang app kapag may unang agent update.</div>', unsafe_allow_html=True)
        return

    top_story = max(records, key=feed_score)
    st.markdown(
        f"""
        <div class="hero">
          <div class="hero-kicker">Here's what matters ngayon</div>
          <div class="hero-title">{esc(top_story.get('title'))}</div>
          <div class="hero-copy">{esc(top_story.get('summary',''))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Basahin ang top story →", key="hero_read"):
        set_selected(top_story["id"])
        st.rerun()

    st.markdown('<div class="section-eyebrow">Your intelligence map</div><div class="section-title">Apat na paraan para maintindihan ang mundo.</div>', unsafe_allow_html=True)
    render_category_tiles(records)

    mode = st.radio(
        "Catch-up mode",
        ["5 minutes lang ako", "May oras ako", "Surprise me"],
        horizontal=True,
        label_visibility="collapsed",
        key="today_mode",
    )

    st.markdown('<div class="section-eyebrow">Para sa’yo ngayon</div>', unsafe_allow_html=True)

    if mode == "5 minutes lang ako":
        picks = [top_by_category(records, c) for c in ["discover", "practical", "reflection", "trend"]]
        picks = [p for p in picks if p]
        cols = st.columns(2)
        for i, item in enumerate(picks):
            with cols[i % 2]:
                render_story_card(item, "quick")
    elif mode == "May oras ako":
        picks = sorted(records, key=feed_score, reverse=True)[:8]
        cols = st.columns(2)
        for i, item in enumerate(picks):
            with cols[i % 2]:
                render_story_card(item, "deep")
    else:
        seed = datetime.now().strftime("%Y-%m-%d-%H")
        rng = random.Random(seed)
        pool = sorted(records, key=lambda r: (r.get("demo", False), -feed_score(r)))
        pick = rng.choice(pool[: max(1, min(12, len(pool)))])
        render_story_card(pick, "surprise")


def filter_records(records, category):
    subset = [r for r in records if r.get("_category") == category]
    search = st.text_input("Hanapin", placeholder="Search topics, Japan, AI, money, faith…", key=f"search_{category}")
    all_tags = sorted({tag for r in subset for tag in r.get("tags", [])})
    selected_tags = st.multiselect("Filter by topic", all_tags, key=f"tags_{category}") if all_tags else []

    if search:
        q = search.lower().strip()
        subset = [
            r for r in subset
            if q in json.dumps(r, ensure_ascii=False).lower()
        ]
    if selected_tags:
        subset = [r for r in subset if set(selected_tags).intersection(r.get("tags", []))]
    return subset


def render_category_page(records, category):
    meta = CATEGORY_META[category]
    st.markdown(
        f"""
        <div class="hero" style="padding-top:32px;padding-bottom:32px">
          <div class="hero-kicker" style="color:{meta['accent']}">{meta['emoji']} {esc(meta['label'])}</div>
          <div class="hero-title" style="font-size:clamp(2rem,4vw,3.5rem)">{esc(meta['question'])}</div>
          <div class="hero-copy">
            {esc({
                'discover': "Fresh developments na worth knowing — hindi basta trending lang.",
                'practical': "Tipid, safety, risk at Japan life advice na may totoong action.",
                'reflection': "Current events, psychology, philosophy at Christian life — mas malalim kaysa headline.",
                'trend': "Patterns, predictions at mga signal na unti-unting lumalakas o humihina.",
            }[category])}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    subset = filter_records(records, category)
    if not subset:
        st.markdown('<div class="empty-box">Walang matching items ngayon. Mas okay ang tahimik kaysa filler.</div>', unsafe_allow_html=True)
        return

    if category == "trend":
        subset.sort(key=lambda r: (r.get("content") or {}).get("current_strength", r.get("importance", 0)), reverse=True)
    else:
        subset.sort(key=feed_score, reverse=True)

    cols = st.columns(2)
    for i, item in enumerate(subset):
        with cols[i % 2]:
            render_story_card(item, f"{category}_card")


def render_footer(records):
    live = [r for r in records if not r.get("demo")]
    st.markdown("---")
    st.caption(
        f"ALAM • {len(records)} records loaded"
        + (f" • {len(live)} live" if live else " • demo mode")
        + " • GitHub ang data layer; scheduled agents ang intelligence engine."
    )


records = load_records()
render_brand(records)

if records and all(r.get("demo") for r in records):
    st.markdown(
        '<div class="demo-banner"><strong>Prototype mode:</strong> Sample content muna ito para makita ang actual experience. Kapag nagsimula nang mag-push ang agents, automatic na babasahin ng app ang live JSON records.</div>',
        unsafe_allow_html=True,
    )

selected_id = st.session_state.get("selected_story")
selected = next((r for r in records if r.get("id") == selected_id), None)

if selected:
    render_detail(selected)
else:
    page = st.radio(
        "Navigation",
        ["Today", "Discover", "Practical", "Reflect", "Trends"],
        horizontal=True,
        label_visibility="collapsed",
        key="main_nav",
    )

    if page == "Today":
        render_today(records)
    elif page == "Discover":
        render_category_page(records, "discover")
    elif page == "Practical":
        render_category_page(records, "practical")
    elif page == "Reflect":
        render_category_page(records, "reflection")
    else:
        render_category_page(records, "trend")

render_footer(records)
