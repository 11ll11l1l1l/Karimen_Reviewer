from __future__ import annotations

import base64
import html
import json
import math
import random
import re
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

try:
    from supabase import create_client
except Exception:  # Online ranking stays optional if the package is unavailable.
    create_client = None

ROOT = Path(__file__).resolve().parent
DATA_FILE = ROOT / "data" / "questions.json"
MASCOT_FILE = ROOT / "assets" / "mascot.png"
SOUND_DIR = ROOT / "assets" / "sounds"
PROGRESS_VERSION = 4

st.set_page_config(
    page_title="A1 B1 Karimen Reviewer",
    page_icon="🚗",
    layout="centered",
    initial_sidebar_state="collapsed",
)


# ---------- Data ----------
@st.cache_data(show_spinner=False)
def load_data():
    doc = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    questions = doc["questions"]
    by_id = {q["id"]: q for q in questions}
    return doc["metadata"], questions, by_id


META, QUESTIONS, BY_ID = load_data()
BANK_OPTIONS = ["All", "A1", "B1"]
AVATARS = ["🚙", "🐶", "🐱", "🦊", "🐼", "🌸", "⭐", "🚦"]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def default_progress() -> dict:
    return {
        "version": PROGRESS_VERSION,
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
        "question_stats": {},
        "sessions": [],
    }


def legacy_id_to_current(qid: str) -> str | None:
    """Best-effort migration for progress files from older builds without retaining source-site labels."""
    if qid in BY_ID:
        return qid
    text = str(qid)
    # Older A1 IDs ended in 14/15/16-Qxxx.
    m = re.search(r"(?:^|[^0-9])(14|15|16)-?Q(\d{1,3})$", text, re.I)
    if m:
        candidate = f"A1-S{int(m.group(1)):02d}-Q{int(m.group(2)):03d}"
        if candidate in BY_ID:
            return candidate
    # Older B1 IDs ended in sNN_qNN, irrespective of their former prefix.
    m = re.search(r"s(\d{1,2})[_-]q(\d{1,3})$", text, re.I)
    if m and 1 <= int(m.group(1)) <= 10:
        candidate = f"B1-S{int(m.group(1)):02d}-Q{int(m.group(2)):03d}"
        if candidate in BY_ID:
            return candidate
    return None


def normalize_progress(raw: dict) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("Progress file is not a JSON object.")
    out = default_progress()
    stats = raw.get("question_stats", {})
    if isinstance(stats, dict):
        for old_qid, s in stats.items():
            qid = legacy_id_to_current(old_qid)
            if not qid or not isinstance(s, dict):
                continue
            attempts = max(0, int(s.get("attempts", 0) or 0))
            correct = max(0, min(attempts, int(s.get("correct", 0) or 0)))
            total_seconds = max(0.0, float(s.get("total_seconds", 0.0) or 0.0))
            existing = out["question_stats"].setdefault(
                qid,
                {"attempts": 0, "correct": 0, "wrong": 0, "streak": 0, "last_seen": None, "last_correct": None, "total_seconds": 0.0},
            )
            existing["attempts"] += attempts
            existing["correct"] += correct
            existing["wrong"] = existing["attempts"] - existing["correct"]
            existing["streak"] = max(existing["streak"], max(0, int(s.get("streak", 0) or 0)))
            existing["last_seen"] = s.get("last_seen") or existing["last_seen"]
            existing["last_correct"] = s.get("last_correct") or existing["last_correct"]
            existing["total_seconds"] += total_seconds
    sessions = raw.get("sessions", [])
    if isinstance(sessions, list):
        out["sessions"] = [x for x in sessions[-250:] if isinstance(x, dict)]
    out["created_at"] = raw.get("created_at") or out["created_at"]
    out["updated_at"] = utc_now_iso()
    return out


def init_state():
    defaults = {
        "progress": default_progress(),
        "nav": "Home",
        "review": None,
        "exam": None,
        "review_feedback": None,
        "review_started_at": time.time(),
        "show_japanese": False,
        "sound_on": True,
        "haptics_on": True,
        "player_name": "",
        "avatar": "🚙",
        "guest_code": uuid.uuid4().hex[:4].upper(),
        "last_import_hash": None,
        "online_error": None,
        "feedback_nonce": 0,
        "pending_fx": None,
        "theme": "Arcade",
        "seen_achievement_ids": set(),
        "achievements_ready": False,
        "achievement_toast": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_state()


# ---------- Soft mobile-first styling ----------
def inject_style():
    st.markdown(
        """
<style>
:root {
  --bg1:#e8f3ff; --bg2:#eef9ff; --bg3:#fff6e7;
  --ink:#20314d; --muted:#6780a6; --line:#d9e7fb; --card:#ffffff;
  --blue:#2b8cff; --sky:#64c4ff; --mint:#19d39a; --violet:#8a5bff; --orange:#ffab2d; --pink:#ff6fa8;
  --shadow:0 12px 30px rgba(54,82,130,.11); --shadow-soft:0 6px 18px rgba(54,82,130,.08);
  --radius:22px;
}
html, body, [class*="css"] { color:var(--ink); }
body { background: radial-gradient(circle at top left, #ffffff 0%, #f4fbff 35%, #fff6ea 100%); }
.stApp {
  background:
    radial-gradient(circle at 12% 12%, rgba(100,196,255,.18), transparent 22%),
    radial-gradient(circle at 88% 16%, rgba(255,171,45,.14), transparent 20%),
    radial-gradient(circle at 24% 88%, rgba(138,91,255,.11), transparent 19%),
    linear-gradient(180deg,var(--bg1) 0%,var(--bg2) 52%,var(--bg3) 100%);
}
.block-container { max-width:940px; padding-top:.75rem; padding-bottom:5rem; }
[data-testid="stHeader"] { background:rgba(245,250,255,.78); backdrop-filter:blur(10px); }
[data-testid="stToolbar"] { right: .6rem; }
.km-hero {
  position:relative; overflow:hidden;
  background: linear-gradient(135deg, #1f74ff 0%, #58a8ff 32%, #7fd9ff 60%, #ffd067 100%);
  border:1px solid rgba(255,255,255,.35); border-radius:28px; padding:1.05rem 1.05rem 1.1rem; margin:.15rem 0 .8rem;
  box-shadow:0 16px 36px rgba(36,90,181,.18);
}
.km-hero::before, .km-hero::after{content:"";position:absolute;border-radius:50%;background:rgba(255,255,255,.14);}
.km-hero::before{width:140px;height:140px;right:-15px;top:-25px;}
.km-hero::after{width:110px;height:110px;left:-20px;bottom:-28px;}
.km-title { font-size:clamp(1.75rem,8vw,2.75rem); font-weight:900; line-height:1.02; letter-spacing:-.04em; color:white; text-shadow:0 4px 16px rgba(11,47,117,.23); }
.km-subtitle { color:rgba(255,255,255,.93); margin-top:.42rem; line-height:1.45; font-weight:600; }
.km-badges{display:flex;gap:.42rem;flex-wrap:wrap;margin-top:.7rem;}
.km-badge{display:inline-flex;align-items:center;gap:.35rem;background:rgba(255,255,255,.2);color:white;border:1px solid rgba(255,255,255,.34);padding:.34rem .7rem;border-radius:999px;font-size:.78rem;font-weight:800;backdrop-filter: blur(6px);}
.km-card { background:rgba(255,255,255,.96); border:1px solid var(--line); border-radius:var(--radius); padding:1rem 1.05rem; margin:.55rem 0; box-shadow:var(--shadow-soft); }
.km-soft { background:linear-gradient(180deg,#ffffff,#f9fcff); }
.km-good { background:linear-gradient(180deg,#effff7,#ffffff); border-color:#b9efd6; }
.km-bad { background:linear-gradient(180deg,#fff3f4,#ffffff); border-color:#f2c6d1; }
.km-qno { font-size:.78rem; color:var(--muted); font-weight:850; letter-spacing:.05em; }
.km-question { font-size:clamp(1.14rem,4.3vw,1.48rem); line-height:1.58; font-weight:760; margin-top:.62rem; }
.km-japanese { font-size:.98rem; line-height:1.62; color:#60708b; margin-top:.78rem; padding-top:.68rem; border-top:1px dashed #dfeaf7; }
.km-pill { display:inline-block; background:#f6faff; border:1px solid #dce8f8; border-radius:999px; padding:.24rem .62rem; margin:.22rem .12rem .1rem 0; font-size:.78rem; color:#607089; font-weight:760; }
.km-small { font-size:.86rem; color:var(--muted); }
.km-divider { height:1px; background:var(--line); margin:.95rem 0; }
.km-mascot-line { display:flex; align-items:center; gap:.72rem; background:linear-gradient(180deg,#ffffff,#fbfdff); border:1px solid var(--line); border-radius:18px; padding:.78rem .9rem; margin:.55rem 0; box-shadow:var(--shadow-soft); }
.km-mascot-bubble { font-weight:760; line-height:1.42; }
.km-live-dot { display:inline-block;width:9px;height:9px;border-radius:50%;background:#2dcb79;margin-right:6px;box-shadow:0 0 0 4px rgba(45,203,121,.12); }
.km-rank { font-size:1.34rem;font-weight:900; }
.km-callout { padding:.85rem 1rem;border-radius:18px;background:linear-gradient(135deg,#fff7d8,#fff0ba);border:1px solid #f3dc84;color:#6d5311; box-shadow:var(--shadow-soft); }
.km-profile { background:linear-gradient(135deg,#253c91,#2d79ff 52%,#62c7ff 100%); border-radius:24px; padding:1rem; color:white; box-shadow:0 18px 36px rgba(34,78,170,.18); position:relative; overflow:hidden; }
.km-profile::after{content:"";position:absolute;right:-18px;top:-24px;width:120px;height:120px;background:rgba(255,255,255,.16);border-radius:50%;}
.km-profile-name{font-size:1.32rem;font-weight:900;line-height:1.08;}
.km-profile-sub{opacity:.92;font-weight:650;}
.km-xp{height:10px;background:rgba(255,255,255,.22);border-radius:999px;overflow:hidden;margin-top:.38rem;}
.km-xp-fill{height:100%;background:linear-gradient(90deg,#ffd25f,#fff7a8);border-radius:999px;}
.km-chip-row{display:flex;gap:.55rem;flex-wrap:wrap;margin-top:.75rem;}
.km-chip{background:rgba(255,255,255,.17);border:1px solid rgba(255,255,255,.28);padding:.45rem .7rem;border-radius:16px;font-size:.8rem;font-weight:760;min-width:85px;text-align:center;}
.km-grid4{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.78rem;}
.km-mode-card{position:relative;overflow:hidden;padding:1rem;border-radius:22px;color:white;min-height:148px;box-shadow:0 16px 28px rgba(66,92,140,.15);border:1px solid rgba(255,255,255,.18);}
.km-mode-card::before{content:"";position:absolute;right:-18px;bottom:-22px;width:96px;height:96px;border-radius:50%;background:rgba(255,255,255,.14);}
.km-mode-icon{font-size:1.7rem;margin-bottom:.28rem;}
.km-mode-title{font-size:1.22rem;font-weight:900;line-height:1.1;}
.km-mode-sub{font-size:.91rem;line-height:1.4;margin-top:.35rem;opacity:.96;font-weight:600;max-width:95%;}
.km-mode-blue{background:linear-gradient(135deg,#2c7df8,#5db6ff);}
.km-mode-green{background:linear-gradient(135deg,#0dc278,#57e38e);}
.km-mode-orange{background:linear-gradient(135deg,#ff9b19,#ffc043);}
.km-mode-violet{background:linear-gradient(135deg,#7151ff,#ab74ff);}
.km-mode-pink{background:linear-gradient(135deg,#ff5f94,#ff8dbc);}
.km-mode-cyan{background:linear-gradient(135deg,#12b6d8,#66dfff);}
.km-stat-band{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.72rem;margin-top:.5rem;}
.km-stat-card{background:rgba(255,255,255,.95);border:1px solid var(--line);border-radius:19px;padding:.85rem .85rem;box-shadow:var(--shadow-soft);text-align:center;}
.km-stat-label{font-size:.8rem;color:var(--muted);font-weight:760;}
.km-stat-value{font-size:1.4rem;font-weight:900;line-height:1.05;margin-top:.18rem;}
.km-panel-title{font-size:1.08rem;font-weight:900;margin:.2rem 0 .65rem;}
.km-top3{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.72rem;}
.km-podium{background:linear-gradient(180deg,#ffffff,#f7fbff);border:1px solid var(--line);border-radius:20px;padding:.9rem;text-align:center;box-shadow:var(--shadow-soft);}
.km-podium-rank{font-size:1.55rem;font-weight:900;line-height:1;}
.km-podium-name{font-weight:800;margin-top:.2rem;}
.km-podium-score{color:var(--blue);font-weight:900;margin-top:.25rem;}
.km-settings-box{background:linear-gradient(180deg,#ffffff,#f8fbff);border:1px solid var(--line);border-radius:18px;padding:.85rem 1rem;}
[data-testid="stMetric"] { background:rgba(255,255,255,.96); border:1px solid var(--line); border-radius:18px; padding:.7rem .75rem; box-shadow:var(--shadow-soft); }
[data-testid="stImage"] img { border-radius:18px; }
[data-testid="stRadio"] > div { gap:.35rem; flex-wrap:wrap; }
[data-testid="stRadio"] label { background:#f8fbff; border:1px solid #dce8f8; border-radius:999px; padding:.26rem .7rem; box-shadow:0 3px 10px rgba(67,94,141,.04); }
[data-baseweb="select"] > div, .stTextInput input, .stNumberInput input {
  border-radius:16px !important; border:1px solid #dce8f8 !important; background:#ffffff !important;
}
.stTextInput input, .stNumberInput input { min-height: 3rem; }
button[kind="primary"]{
  background:linear-gradient(135deg,#2b8cff,#66b7ff)!important; border:0!important; color:white!important;
}
div.stButton > button { min-height:3.2rem; border-radius:16px; font-weight:850; font-size:1rem; border:1px solid #dfe7f0; box-shadow:0 6px 14px rgba(65,90,120,.06); }
div.stButton > button:hover { transform:translateY(-1px); border-color:#bcd3f4; }
.stProgress > div > div > div { border-radius:999px; }
[data-testid="stFileUploader"] { border-radius:16px; }
label[data-testid="stWidgetLabel"] p{font-weight:760;color:#3b5173;}
@media(max-width:760px){
 .km-grid4{grid-template-columns:1fr;}
 .km-stat-band,.km-top3{grid-template-columns:1fr;}
 .block-container{padding-left:.72rem;padding-right:.72rem;padding-top:.48rem;}
 .km-hero{padding:.9rem;border-radius:22px;}
 .km-card{padding:.88rem;border-radius:18px;}
 .km-profile{padding:.9rem;border-radius:22px;}
 div.stButton > button{min-height:3.45rem;font-size:1.03rem;}
 [data-testid="column"]{min-width:0!important;}
}

.km-fx{position:relative;overflow:hidden;text-align:center;border-radius:24px;padding:1rem;margin:.65rem 0;box-shadow:0 14px 28px rgba(52,82,132,.12);animation:kmPop .36s cubic-bezier(.2,.9,.3,1.2);}
.km-fx-good{background:linear-gradient(135deg,#eafff4,#f8fffb);border:1px solid #aee9cd;}
.km-fx-bad{background:linear-gradient(135deg,#fff0f4,#fff8fa);border:1px solid #f0bdce;}
.km-fx-icon{font-size:2.15rem;animation:kmBounce .55s ease both;}
.km-fx-title{font-size:1.32rem;font-weight:900;margin-top:.15rem;}
.km-fx-sub{font-size:.9rem;color:var(--muted);font-weight:650;margin-top:.12rem;}
.km-fx-particles i{position:absolute;font-style:normal;font-size:.8rem;opacity:.72;left:calc(8% + (var(--i) * 14%));top:10%;animation:kmFloat calc(.8s + (var(--i)*.05s)) ease-out both;}
.km-mascot-pop{animation:kmBubble .35s cubic-bezier(.2,.9,.3,1.2);}
.km-badge-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.65rem;}
.km-badge-card{background:linear-gradient(180deg,#fff,#f8fbff);border:1px solid var(--line);border-radius:18px;padding:.75rem;text-align:center;box-shadow:var(--shadow-soft);min-height:112px;}
.km-badge-card.locked{filter:grayscale(.75);opacity:.48;box-shadow:none;}
.km-badge-icon{font-size:1.65rem}.km-badge-name{font-size:.88rem;font-weight:900;margin-top:.15rem}.km-badge-desc{font-size:.74rem;color:var(--muted);line-height:1.3;margin-top:.18rem;}
.km-result-hero{text-align:center;border-radius:28px;padding:1.15rem;margin:.5rem 0 1rem;background:linear-gradient(135deg,#2e87ff,#795dff 55%,#ffb53b);color:white;box-shadow:0 18px 36px rgba(58,82,177,.2);animation:kmPop .45s cubic-bezier(.2,.9,.3,1.2);}
.km-result-score{font-size:2.9rem;font-weight:950;line-height:1}.km-result-title{font-size:1.35rem;font-weight:900;margin-top:.25rem}.km-result-sub{opacity:.92;font-weight:650;margin-top:.18rem}
@keyframes kmPop{0%{transform:scale(.92);opacity:0}100%{transform:scale(1);opacity:1}}
@keyframes kmBounce{0%{transform:translateY(8px) scale(.75)}55%{transform:translateY(-4px) scale(1.12)}100%{transform:translateY(0) scale(1)}}
@keyframes kmBubble{0%{transform:translateX(-10px) scale(.96);opacity:0}100%{transform:none;opacity:1}}
@keyframes kmFloat{0%{transform:translateY(8px) rotate(0);opacity:0}35%{opacity:.9}100%{transform:translateY(-28px) rotate(45deg);opacity:0}}
@media(max-width:760px){.km-badge-grid{grid-template-columns:repeat(2,minmax(0,1fr));}}
</style>
        """,
        unsafe_allow_html=True,
    )


inject_style()


def inject_theme_override():
    theme = st.session_state.get("theme", "Arcade")
    if theme == "Cute":
        css = """
        <style>
        :root{--bg1:#fff0f7;--bg2:#fff8fc;--bg3:#fff4df;--blue:#ff72ab;--sky:#ffb6d2;--mint:#72d9b2;--violet:#a987ff;--orange:#ffb95d;--ink:#4d3552;--muted:#8d6d8e;--line:#f3dbe8;}
        .stApp{background:radial-gradient(circle at 15% 10%,rgba(255,172,207,.22),transparent 23%),radial-gradient(circle at 85% 18%,rgba(255,216,130,.20),transparent 20%),linear-gradient(180deg,#fff0f7 0%,#fff9fc 55%,#fff6e7 100%);}
        .km-hero{background:linear-gradient(135deg,#ff73ad 0%,#ff9cc5 38%,#a98aff 72%,#ffd36a 100%);}
        button[kind="primary"]{background:linear-gradient(135deg,#ff6da7,#a781ff)!important;}
        </style>
        """
    elif theme == "Night":
        css = """
        <style>
        :root{--bg1:#11182f;--bg2:#17213b;--bg3:#10172d;--card:#202b48;--ink:#edf5ff;--muted:#a9bbd8;--line:#324366;--blue:#55a7ff;--sky:#7bd8ff;--mint:#3ee1aa;--violet:#a67dff;--orange:#ffc14d;}
        html,body,[class*=css]{color:#edf5ff;}
        .stApp{background:radial-gradient(circle at 16% 12%,rgba(65,113,220,.25),transparent 24%),radial-gradient(circle at 86% 18%,rgba(128,81,218,.20),transparent 20%),linear-gradient(180deg,#11182f 0%,#17213b 58%,#10172d 100%);}
        [data-testid="stHeader"]{background:rgba(15,22,43,.76);}
        .km-card,.km-stat-card,.km-podium,.km-settings-box,[data-testid="stMetric"]{background:linear-gradient(180deg,#202b48,#1a253f);border-color:#324366;color:#edf5ff;}
        .km-soft{background:linear-gradient(180deg,#202b48,#19243d);}
        .km-good{background:linear-gradient(180deg,#193e38,#1b2f3d);border-color:#2d725e;}
        .km-bad{background:linear-gradient(180deg,#4a2938,#27283e);border-color:#714056;}
        .km-question,.km-profile-name,.km-panel-title{color:#f5f9ff;}
        .km-small,.km-qno,.km-japanese,.km-stat-label{color:#a9bbd8;}
        [data-testid="stRadio"] label{background:#202b48;border-color:#324366;color:#edf5ff;}
        [data-baseweb="select"]>div,.stTextInput input,.stNumberInput input{background:#202b48!important;color:#edf5ff!important;border-color:#324366!important;}
        </style>
        """
    else:
        css = """<style></style>"""
    st.markdown(css, unsafe_allow_html=True)


inject_theme_override()


# ---------- Local learning model ----------
def qstat(qid: str) -> dict:
    return st.session_state.progress["question_stats"].get(
        qid,
        {"attempts": 0, "correct": 0, "wrong": 0, "streak": 0, "last_seen": None, "last_correct": None, "total_seconds": 0.0},
    )


def mastery(stat: dict) -> float:
    n = int(stat.get("attempts", 0) or 0)
    if n <= 0:
        return 0.0
    acc = float(stat.get("correct", 0) or 0) / n
    exposure = 1.0 - math.exp(-n / 3.0)
    score = 100.0 * acc * exposure + min(10.0, 2.0 * int(stat.get("streak", 0) or 0))
    return max(0.0, min(100.0, score))


def parse_iso(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def due_now(stat: dict) -> bool:
    attempts = int(stat.get("attempts", 0) or 0)
    if attempts == 0:
        return True
    if int(stat.get("wrong", 0) or 0) > 0 and not stat.get("last_correct"):
        return True
    last = parse_iso(stat.get("last_seen"))
    if not last:
        return True
    streak = int(stat.get("streak", 0) or 0)
    interval_days = [0, 1, 3, 7, 14, 30, 60][min(streak, 6)]
    return datetime.now(timezone.utc) >= last + timedelta(days=interval_days)


def priority_score(q: dict) -> float:
    s = qstat(q["id"])
    n = int(s.get("attempts", 0) or 0)
    if n == 0:
        return 5.0 + random.random()
    wrong_rate = int(s.get("wrong", 0) or 0) / max(1, n)
    due_bonus = 2.0 if due_now(s) else 0.0
    return 3.0 * wrong_rate + 2.0 * (1.0 - mastery(s) / 100.0) + due_bonus + random.random() * 0.25


def record_answer(qid: str, was_correct: bool, seconds: float):
    progress = st.session_state.progress
    s = progress["question_stats"].setdefault(
        qid,
        {"attempts": 0, "correct": 0, "wrong": 0, "streak": 0, "last_seen": None, "last_correct": None, "total_seconds": 0.0},
    )
    s["attempts"] += 1
    s["total_seconds"] = float(s.get("total_seconds", 0.0)) + max(0.0, min(float(seconds), 600.0))
    s["last_seen"] = utc_now_iso()
    if was_correct:
        s["correct"] += 1
        s["streak"] = int(s.get("streak", 0)) + 1
        s["last_correct"] = utc_now_iso()
    else:
        s["wrong"] += 1
        s["streak"] = 0
    progress["updated_at"] = utc_now_iso()


def add_session(mode: str, question_ids: list[str], correct: int, seconds: float, bank_label: str = ""):
    st.session_state.progress["sessions"].append(
        {
            "timestamp": utc_now_iso(),
            "mode": mode,
            "bank": bank_label,
            "questions": len(question_ids),
            "correct": int(correct),
            "percent": round(100 * correct / max(1, len(question_ids)), 1),
            "seconds": round(max(0.0, seconds), 1),
            "question_ids": question_ids,
        }
    )
    st.session_state.progress["sessions"] = st.session_state.progress["sessions"][-250:]
    st.session_state.progress["updated_at"] = utc_now_iso()


# ---------- Bank helpers ----------
def bank_label(q: dict) -> str:
    return f"{q['bank']} · Set {int(q.get('set') or 0)}"


def display_question_id(q: dict) -> str:
    return q["id"]


def set_options_for_bank(bank: str) -> list[str]:
    if bank == "A1":
        return ["All", "14", "15", "16"]
    if bank == "B1":
        return ["All"] + [str(i) for i in range(1, 11)]
    return ["All"]


def filter_questions(bank: str = "All", set_filter: str = "All", category: str = "All") -> list[dict]:
    qs = QUESTIONS
    if bank != "All":
        qs = [q for q in qs if q["bank"] == bank]
    if set_filter != "All":
        try:
            set_no = int(set_filter)
            qs = [q for q in qs if int(q.get("set") or 0) == set_no]
        except Exception:
            pass
    if category != "All":
        qs = [q for q in qs if q["category"] == category]
    return list(qs)


def select_review_questions(pool: list[dict], mode: str, count: int) -> list[str]:
    if not pool:
        return []
    count = min(count, len(pool))
    if mode == "Random":
        chosen = random.sample(pool, count)
    elif mode == "Unseen":
        unseen = [q for q in pool if qstat(q["id"])["attempts"] == 0]
        seen = [q for q in pool if qstat(q["id"])["attempts"] > 0]
        random.shuffle(unseen)
        seen.sort(key=priority_score, reverse=True)
        chosen = (unseen + seen)[:count]
    elif mode == "Wrong answers":
        wrong = [q for q in pool if qstat(q["id"])["wrong"] > 0]
        wrong.sort(key=priority_score, reverse=True)
        rest = [q for q in pool if q not in wrong]
        random.shuffle(rest)
        chosen = (wrong + rest)[:count]
    elif mode == "Due / adaptive":
        due = [q for q in pool if due_now(qstat(q["id"]))]
        due.sort(key=priority_score, reverse=True)
        rest = [q for q in pool if q not in due]
        rest.sort(key=priority_score, reverse=True)
        chosen = (due + rest)[:count]
    else:
        chosen = sorted(pool, key=priority_score, reverse=True)[:count]
    return [q["id"] for q in chosen]


# ---------- Sound, haptics and mascot feedback ----------
@st.cache_data(show_spinner=False)
def audio_data_uri(name: str) -> str | None:
    path = SOUND_DIR / f"{name}.wav"
    if not path.exists():
        return None
    return "data:audio/wav;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def feedback_fx(kind: str):
    st.session_state.feedback_nonce += 1
    uri = audio_data_uri(kind) if st.session_state.sound_on else None
    vibrate_map = {"correct":"24", "wrong":"36,24,36", "combo":"20,20,35", "badge":"18,20,18,20,45", "pass":"25,20,25,20,60", "retry":"40"}
    pattern = vibrate_map.get(kind, "24")
    vibrate = f"navigator.vibrate && navigator.vibrate([{pattern}]);" if st.session_state.haptics_on else ""
    audio = f'<audio id="mainfx" autoplay preload="auto"><source src="{uri}" type="audio/wav"></audio>' if uri else ""
    bloop_uri = audio_data_uri("bloop") if st.session_state.sound_on and kind in {"correct", "wrong", "combo", "complete", "pass", "retry", "badge"} else None
    bloop = f'<audio id="bloopfx" preload="auto"><source src="{bloop_uri}" type="audio/wav"></audio>' if bloop_uri else ""
    delayed = "setTimeout(()=>{const b=document.getElementById('bloopfx'); if(b){b.volume=.42; b.play().catch(()=>{});}},260);" if bloop_uri else ""
    components.html(f"<div style='height:0'>{audio}{bloop}<script>{vibrate}{delayed}</script></div>", height=0, width=0)


def feedback_animation(kind: str, combo: int = 0):
    data = {
        "correct": ("✨", "Correct!", "Nice read."),
        "wrong": ("💡", "Almost!", "Lock in the rule and keep moving."),
        "combo": ("🔥", f"{combo}x Combo!", "You are on a roll."),
        "pass": ("🏆", "Mission Cleared!", "You passed the practice threshold."),
        "retry": ("🛠️", "Training Complete", "Review the misses and run it again."),
        "badge": ("🏅", "Achievement Unlocked!", "New badge earned."),
        "complete": ("⭐", "Stage Clear!", "Good study block."),
    }
    icon, title, sub = data.get(kind, data["complete"])
    cls = "good" if kind in {"correct","combo","pass","badge","complete"} else "bad"
    particles = "".join(f"<i style='--i:{i}'>{x}</i>" for i,x in enumerate(["✦","•","★","✧","•","✦","★"]))
    st.markdown(
        f"<div class='km-fx km-fx-{cls}'><div class='km-fx-particles'>{particles}</div><div class='km-fx-icon'>{icon}</div><div class='km-fx-title'>{html.escape(title)}</div><div class='km-fx-sub'>{html.escape(sub)}</div></div>",
        unsafe_allow_html=True,
    )


def mascot_feedback(kind: str, combo: int = 0):
    messages = {
        "correct": ["Nice! That rule is locked in.", "Clean answer. Keep driving!", "Great read — onto the next one!"],
        "wrong": ["Almost! This is exactly the kind of trap worth catching here.", "Good miss to find now. Read the rule once and try again later.", "Tricky one. I saved it as a weak spot for you."],
        "complete": ["Stage clear! Small repeats build strong recall.", "Good run. Your weak spots just got smaller."],
        "pass": ["You cleared the mission! That was a strong exam run.", "Practice threshold passed. Great control!"],
        "retry": ["Training run complete. Review the misses and come back stronger.", "You found exactly what to work on next."],
        "combo": [f"{combo} in a row! Keep the combo alive!", f"Combo x{combo}! Your recall is heating up!"],
        "badge": ["New badge unlocked! Nice progress.", "Achievement earned! Keep collecting them."],
    }
    text = random.choice(messages.get(kind, messages["complete"]))
    cols = st.columns([1, 5])
    if MASCOT_FILE.exists():
        cols[0].image(str(MASCOT_FILE), width=82)
    else:
        cols[0].markdown("### 🐶")
    cols[1].markdown(f"<div class='km-mascot-line km-mascot-pop'><div class='km-mascot-bubble'>💬 {html.escape(text)}</div></div>", unsafe_allow_html=True)


def achievement_catalog() -> list[dict]:
    stats = st.session_state.progress["question_stats"]
    attempts = sum(int(s.get("attempts", 0) or 0) for s in stats.values())
    unique_seen = sum(1 for s in stats.values() if int(s.get("attempts", 0) or 0) > 0)
    max_streak = max([int(s.get("streak", 0) or 0) for s in stats.values()] or [0])
    image_seen = sum(1 for q in QUESTIONS if q.get("images") and qstat(q["id"])["attempts"] > 0)
    a1_seen = any(qstat(q["id"])["attempts"] > 0 for q in QUESTIONS if q.get("bank") == "A1")
    b1_seen = any(qstat(q["id"])["attempts"] > 0 for q in QUESTIONS if q.get("bank") == "B1")
    exams = [s for s in st.session_state.progress.get("sessions", []) if s.get("mode") == "exam"]
    passed = any(float(s.get("percent") or 0) >= 90 for s in exams)
    perfect = any(int(s.get("questions") or 0) == 50 and int(s.get("correct") or 0) == 50 for s in exams)
    return [
        {"id":"first","icon":"🚗","name":"First Drive","desc":"Answer your first question","earned":attempts >= 1},
        {"id":"warm","icon":"⚡","name":"Engine Warm","desc":"Answer 10 questions","earned":attempts >= 10},
        {"id":"rookie","icon":"🛣️","name":"Road Rookie","desc":"See 50 unique questions","earned":unique_seen >= 50},
        {"id":"combo","icon":"🔥","name":"Hot Streak","desc":"Reach a 5-answer correct streak","earned":max_streak >= 5},
        {"id":"image","icon":"👀","name":"Sharp Eye","desc":"Practice 20 image questions","earned":image_seen >= 20},
        {"id":"explorer","icon":"🗺️","name":"Bank Explorer","desc":"Practice both A1 and B1","earned":a1_seen and b1_seen},
        {"id":"pass","icon":"🏆","name":"Mission Clear","desc":"Pass a practice exam","earned":passed},
        {"id":"perfect","icon":"👑","name":"Perfect Drive","desc":"Score 50/50 on an exam","earned":perfect},
        {"id":"veteran","icon":"🎖️","name":"Road Veteran","desc":"Answer 250 questions","earned":attempts >= 250},
    ]


def check_new_achievements():
    current = {a["id"] for a in achievement_catalog() if a["earned"]}
    seen = st.session_state.get("seen_achievement_ids", set())
    new_ids = list(current - set(seen))
    if new_ids:
        ach = next((a for a in achievement_catalog() if a["id"] == new_ids[0]), None)
        st.session_state.seen_achievement_ids = set(current)
        st.session_state.achievement_toast = ach
        st.session_state.pending_fx = "badge"


def prime_achievement_snapshot():
    if not st.session_state.get("achievements_ready", False):
        st.session_state.seen_achievement_ids = {a["id"] for a in achievement_catalog() if a["earned"]}
        st.session_state.achievements_ready = True


def render_achievement_toast():
    ach = st.session_state.get("achievement_toast")
    if ach:
        st.session_state.achievement_toast = None
        feedback_animation("badge")
        st.markdown(f"<div class='km-callout'><strong>{ach['icon']} {html.escape(ach['name'])}</strong><br>{html.escape(ach['desc'])}</div>", unsafe_allow_html=True)
        mascot_feedback("badge")


# ---------- Optional shared ranking backend ----------
@st.cache_resource(show_spinner=False)
def supabase_client():
    if create_client is None:
        return None
    try:
        url = st.secrets["SUPABASE_URL"]
        try:
            key = st.secrets["SUPABASE_SECRET_KEY"]
        except Exception:
            key = st.secrets["SUPABASE_SERVICE_ROLE_KEY"]
    except Exception:
        return None
    if not url or not key:
        return None
    try:
        return create_client(url, key)
    except Exception:
        return None


def online_enabled() -> bool:
    return supabase_client() is not None


def safe_player_name() -> str:
    raw = (st.session_state.player_name or "").strip()
    raw = re.sub(r"[^\w .\-]", "", raw, flags=re.UNICODE)[:24].strip()
    return raw or f"Driver-{st.session_state.guest_code}"


def sync_live_exam(exam: dict):
    db = supabase_client()
    if db is None or not exam or exam.get("submitted"):
        return
    try:
        answered = len(exam.get("answers", {}))
        correct = sum(
            1
            for qid, answer in exam.get("answers", {}).items()
            if qid in BY_ID and bool(answer) == bool(BY_ID[qid]["answer"])
        )
        payload = {
            "session_id": exam["session_id"],
            "display_name": safe_player_name(),
            "avatar": st.session_state.avatar,
            "bank": exam.get("bank", "All"),
            "set_label": str(exam.get("set", "All")),
            "total_questions": len(exam.get("ids", [])),
            "answered": answered,
            "correct": correct,
            "started_at": exam.get("started_iso"),
            "last_seen": utc_now_iso(),
            "status": "active",
        }
        db.table("live_exams").upsert(payload, on_conflict="session_id").execute()
        st.session_state.online_error = None
    except Exception as exc:
        st.session_state.online_error = str(exc)


def finish_live_exam(exam: dict, correct: int, elapsed: float):
    db = supabase_client()
    if db is None or exam.get("online_saved"):
        return
    try:
        total = len(exam["ids"])
        pct = round(100 * correct / max(1, total), 1)
        db.table("live_exams").upsert(
            {
                "session_id": exam["session_id"],
                "display_name": safe_player_name(),
                "avatar": st.session_state.avatar,
                "bank": exam.get("bank", "All"),
                "set_label": str(exam.get("set", "All")),
                "total_questions": total,
                "answered": total,
                "correct": correct,
                "started_at": exam.get("started_iso"),
                "last_seen": utc_now_iso(),
                "status": "finished",
            },
            on_conflict="session_id",
        ).execute()
        db.table("exam_results").insert(
            {
                "session_id": exam["session_id"],
                "display_name": safe_player_name(),
                "avatar": st.session_state.avatar,
                "bank": exam.get("bank", "All"),
                "set_label": str(exam.get("set", "All")),
                "score": correct,
                "total_questions": total,
                "percent": pct,
                "elapsed_seconds": round(elapsed, 1),
                "passed": pct >= META["exam_standard"]["pass_percent"],
                "completed_at": utc_now_iso(),
            }
        ).execute()
        exam["online_saved"] = True
        st.session_state.online_error = None
    except Exception as exc:
        st.session_state.online_error = str(exc)


def fetch_live_exams() -> list[dict]:
    db = supabase_client()
    if db is None:
        return []
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(timespec="seconds")
    try:
        res = (
            db.table("live_exams")
            .select("display_name,avatar,bank,set_label,total_questions,answered,correct,started_at,last_seen")
            .eq("status", "active")
            .gte("last_seen", cutoff)
            .order("correct", desc=True)
            .order("answered", desc=True)
            .execute()
        )
        return list(res.data or [])
    except Exception as exc:
        st.session_state.online_error = str(exc)
        return []


def fetch_exam_results(limit: int = 300) -> list[dict]:
    db = supabase_client()
    if db is None:
        return []
    try:
        res = (
            db.table("exam_results")
            .select("display_name,avatar,bank,set_label,score,total_questions,percent,elapsed_seconds,passed,completed_at")
            .order("completed_at", desc=True)
            .limit(limit)
            .execute()
        )
        return list(res.data or [])
    except Exception as exc:
        st.session_state.online_error = str(exc)
        return []


@st.fragment(run_every="15s")
def exam_heartbeat():
    exam = st.session_state.get("exam")
    if exam and not exam.get("submitted"):
        sync_live_exam(exam)
        if online_enabled():
            st.caption("🟢 Live room connected · ranking updates automatically")


# ---------- Reusable rendering ----------
def render_question(q: dict, position: int, total: int, reveal: bool = False, selected=None):
    safe_bank = html.escape(bank_label(q))
    safe_cat = html.escape(q["category"])
    safe_id = html.escape(display_question_id(q))
    safe_question = html.escape(q["question_en"]).replace("\n", "<br>")
    safe_ja = html.escape(q.get("question_ja", "")).replace("\n", "<br>")
    tags = f'<span class="km-pill">{safe_bank}</span><span class="km-pill">{safe_cat}</span>'
    st.markdown(
        f'<div class="km-card km-soft"><div class="km-qno">QUESTION {position} OF {total} · {safe_id}</div>'
        f'<div>{tags}</div><div class="km-question">{safe_question}</div>'
        + (f'<div class="km-japanese">{safe_ja}</div>' if st.session_state.show_japanese and q.get("question_ja") else "")
        + "</div>",
        unsafe_allow_html=True,
    )
    for img in q.get("images", []):
        path = ROOT / img
        if path.exists():
            st.image(str(path), use_container_width=True)
    if reveal:
        is_correct = selected is not None and bool(selected) == bool(q["answer"])
        css = "km-good" if is_correct else "km-bad"
        label = "Correct" if is_correct else "Not quite"
        answer_text = "TRUE" if q["answer"] else "FALSE"
        safe_explanation = html.escape(q["explanation"]).replace("\n", "<br>")
        st.markdown(
            f'<div class="km-card {css}"><strong>{label}</strong><br>Correct answer: <strong>{answer_text}</strong>'
            f'<div class="km-divider"></div>{safe_explanation}</div>',
            unsafe_allow_html=True,
        )
        combo = int((st.session_state.review or {}).get("combo", 0)) if st.session_state.get("review") else 0
        if is_correct and combo >= 3:
            feedback_animation("combo", combo)
            mascot_feedback("combo", combo)
        else:
            feedback_animation("correct" if is_correct else "wrong", combo)
            mascot_feedback("correct" if is_correct else "wrong", combo)
        render_sources(q)


def render_sources(q: dict):
    sources = q.get("sources") or []
    if not sources:
        return
    with st.expander("Official verification details"):
        for src in sources:
            title = src.get("title") or src.get("key") or "Reference"
            org = src.get("organization", "")
            section = src.get("section", "")
            url = src.get("url")
            text = " — ".join(x for x in [org, title, section] if x)
            if url:
                st.markdown(f"- [{text}]({url})")
            else:
                st.markdown(f"- {text}")


def progress_json() -> str:
    return json.dumps(st.session_state.progress, ensure_ascii=False, indent=2)




def study_level_info():
    stats = st.session_state.progress["question_stats"]
    attempts = sum(int(s.get("attempts", 0) or 0) for s in stats.values())
    level = 1 + attempts // 25
    xp = attempts % 25
    xp_goal = 25
    return level, xp, xp_goal


def study_day_streak() -> int:
    sessions = st.session_state.progress.get("sessions", [])
    if not sessions:
        return 0
    dates = set()
    for sess in sessions:
        ts = parse_iso(sess.get("timestamp"))
        if ts:
            dates.add(ts.astimezone(timezone.utc).date())
    if not dates:
        return 0
    day = datetime.now(timezone.utc).date()
    streak = 0
    while day in dates:
        streak += 1
        day -= timedelta(days=1)
    return streak


def best_exam_percent() -> float:
    best = 0.0
    for sess in st.session_state.progress.get("sessions", []):
        if sess.get("mode") == "exam":
            try:
                best = max(best, float(sess.get("percent") or 0.0))
            except Exception:
                pass
    return best


def render_mode_card(title: str, subtitle: str, icon: str, css_class: str):
    st.markdown(
        f"<div class='km-mode-card {css_class}'><div class='km-mode-icon'>{icon}</div><div class='km-mode-title'>{html.escape(title)}</div><div class='km-mode-sub'>{html.escape(subtitle)}</div></div>",
        unsafe_allow_html=True,
    )


def player_controls(compact: bool = False):
    if compact:
        c1, c2 = st.columns([3, 1])
        st.session_state.player_name = c1.text_input("Nickname", value=st.session_state.player_name, placeholder=f"Driver-{st.session_state.guest_code}", max_chars=24, key="player_compact")
        st.session_state.avatar = c2.selectbox("Avatar", AVATARS, index=AVATARS.index(st.session_state.avatar), key="avatar_compact")
        return
    st.markdown("### Your study profile")
    st.caption("Use a nickname for the public ranking. No account or email is required.")
    c1, c2 = st.columns([3, 1])
    st.session_state.player_name = c1.text_input("Nickname", value=st.session_state.player_name, placeholder=f"Driver-{st.session_state.guest_code}", max_chars=24, key="player_home")
    st.session_state.avatar = c2.selectbox("Avatar", AVATARS, index=AVATARS.index(st.session_state.avatar), key="avatar_home")
    st.markdown(f"<div class='km-card'><strong>{st.session_state.avatar} {html.escape(safe_player_name())}</strong><br><span class='km-small'>This is the name shown in live rankings.</span></div>", unsafe_allow_html=True)


def header():
    c1, c2 = st.columns([5, 1.15])
    c1.markdown(
        '<div class="km-hero"><div class="km-title">A1 B1 Karimen Reviewer</div>'
        '<div class="km-subtitle">Game-style study flow · 650 real practice questions · smart review · exam simulation · live rankings</div>'
        '<div class="km-badges"><span class="km-badge">🎮 Playful UI</span><span class="km-badge">🧠 Smart Review</span><span class="km-badge">🏆 Live Rankings</span><span class="km-badge">📱 Mobile First</span></div></div>',
        unsafe_allow_html=True,
    )
    if MASCOT_FILE.exists():
        c2.image(str(MASCOT_FILE), width=98)
    nav_options = ["Home", "Review", "Exam", "Rankings", "Progress", "Bank"]
    current = st.session_state.nav if st.session_state.nav in nav_options else "Home"
    nav = st.radio("Navigation", nav_options, index=nav_options.index(current), horizontal=True, label_visibility="collapsed")
    st.session_state.nav = nav
    with st.expander("🎛️ Game settings", expanded=False):
        st.markdown("<div class='km-settings-box'>", unsafe_allow_html=True)
        c1, c2 = st.columns([1.25, 1])
        st.session_state.theme = c1.selectbox("Theme", ["Arcade", "Cute", "Night"], index=["Arcade", "Cute", "Night"].index(st.session_state.get("theme", "Arcade")))
        st.session_state.show_japanese = c2.toggle("Show Japanese", value=st.session_state.show_japanese)
        c3, c4 = st.columns(2)
        st.session_state.sound_on = c3.toggle("Sound effects", value=st.session_state.sound_on)
        st.session_state.haptics_on = c4.toggle("Phone vibration", value=st.session_state.haptics_on)
        st.caption(f"Ranking name: {st.session_state.avatar} {safe_player_name()} · Theme: {st.session_state.theme}")
        st.markdown("</div>", unsafe_allow_html=True)
    return nav


# ---------- Pages ----------
def page_home():
    level, xp, xp_goal = study_level_info()
    streak = study_day_streak()
    best_exam = best_exam_percent()
    attempted = sum(1 for qid in st.session_state.progress["question_stats"] if qstat(qid)["attempts"] > 0)
    due = sum(1 for q in QUESTIONS if qstat(q["id"])["attempts"] > 0 and due_now(qstat(q["id"])))
    unseen = sum(1 for q in QUESTIONS if qstat(q["id"])["attempts"] == 0)
    weak = sum(1 for q in QUESTIONS if qstat(q["id"])["attempts"] > 0 and mastery(qstat(q["id"])) < 60)

    st.markdown(
        f"<div class='km-profile'><div class='km-profile-name'>{st.session_state.avatar} {html.escape(safe_player_name())}</div>"
        f"<div class='km-profile-sub'>Level {level} Road Rookie · Bright game mode active</div>"
        f"<div class='km-xp'><div class='km-xp-fill' style='width:{(xp/max(1,xp_goal))*100:.1f}%'></div></div>"
        f"<div class='km-small' style='color:rgba(255,255,255,.9);margin-top:.38rem'>XP {xp}/{xp_goal} to next level</div>"
        f"<div class='km-chip-row'><div class='km-chip'>🔥 {streak} day streak</div><div class='km-chip'>🏆 Best exam {best_exam:.0f}%</div><div class='km-chip'>📘 {attempted}/{len(QUESTIONS)} seen</div></div></div>",
        unsafe_allow_html=True,
    )

    with st.expander("👤 Edit nickname and avatar", expanded=False):
        player_controls(compact=True)

    st.markdown("<div class='km-panel-title'>Choose your next mission</div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        render_mode_card("Smart Review", "Adaptive practice that pushes due, weak, and unseen questions first.", "🧠", "km-mode-blue")
        if st.button("Start smart review", use_container_width=True, type="primary", key="home_smart_review"):
            ids = select_review_questions(QUESTIONS, "Due / adaptive", 20)
            st.session_state.review = {"ids": ids, "index": 0, "correct": 0, "answered": 0, "started": time.time(), "mode": "Due / adaptive", "bank": "All", "combo": 0, "max_combo": 0}
            st.session_state.review_feedback = None
            st.session_state.review_started_at = time.time()
            st.session_state.pending_fx = "start"
            st.session_state.nav = "Review"
            st.rerun()
    with c2:
        render_mode_card("Exam Mode", "A focused test run with timer, flags, and a real score finish.", "🏁", "km-mode-green")
        if st.button("Take 50-question exam", use_container_width=True, type="primary", key="home_exam_start"):
            start_exam("All", "All", 50, 30)
            st.session_state.pending_fx = "start"
            st.session_state.nav = "Exam"
            st.rerun()

    c3, c4 = st.columns(2)
    with c3:
        render_mode_card("Live Rankings", "See who is studying now and compare best completed 50-question runs.", "🏆", "km-mode-orange")
        if st.button("Open rankings", use_container_width=True, key="home_rankings_open"):
            st.session_state.nav = "Rankings"
            st.rerun()
    with c4:
        render_mode_card("Question Bank", "Browse the whole database by bank, set, category, and keyword.", "🔎", "km-mode-violet")
        if st.button("Browse question bank", use_container_width=True, key="home_bank_open"):
            st.session_state.nav = "Bank"
            st.rerun()

    st.markdown("<div class='km-panel-title'>Your dashboard</div>", unsafe_allow_html=True)
    st.markdown(
        f"<div class='km-stat-band'>"
        f"<div class='km-stat-card'><div class='km-stat-label'>Questions</div><div class='km-stat-value'>{META['question_count']}</div><div class='km-small'>A1 + B1 total</div></div>"
        f"<div class='km-stat-card'><div class='km-stat-label'>Due Today</div><div class='km-stat-value'>{due}</div><div class='km-small'>ready to review</div></div>"
        f"<div class='km-stat-card'><div class='km-stat-label'>Weak Spots</div><div class='km-stat-value'>{weak}</div><div class='km-small'>mastery under 60%</div></div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        f"<div class='km-card km-soft'><strong>A1</strong> · 150 questions · Sets 14, 15, 16 &nbsp; • &nbsp; <strong>B1</strong> · 500 questions · Sets 1–10"
        f"<div class='km-divider'></div><span class='km-small'>Image questions: {META['image_question_count']} · Unseen questions left: {unseen} · No demo/sample bank included.</span></div>",
        unsafe_allow_html=True,
    )

    earned = [a for a in achievement_catalog() if a["earned"]]
    st.markdown(f"<div class='km-card km-soft'><strong>🏅 Achievements</strong><br><span class='km-small'>{len(earned)}/{len(achievement_catalog())} badges unlocked · Open Progress to see the collection.</span></div>", unsafe_allow_html=True)

    if online_enabled():
        live = fetch_live_exams()
        st.markdown(f"<div class='km-callout'><span class='km-live-dot'></span><strong>{len(live)} examiner(s) active now</strong> · Open Rankings to watch the live room.</div>", unsafe_allow_html=True)
    else:
        st.info("Live rankings are ready in the app but need the free Supabase connection once. The reviewer still works normally without it.")

    with st.expander("💾 Progress backup and restore", expanded=False):
        st.caption("Your learning history lives in this browser session. Download a small backup when you want to keep or move it.")
        c1, c2 = st.columns(2)
        c1.download_button("Download progress", data=progress_json(), file_name="karimen_progress.json", mime="application/json", use_container_width=True)
        uploaded = c2.file_uploader("Import progress", type=["json"], label_visibility="collapsed")
        if uploaded is not None:
            raw_bytes = uploaded.getvalue()
            marker = hash(raw_bytes)
            if st.session_state.last_import_hash != marker:
                try:
                    st.session_state.progress = normalize_progress(json.loads(raw_bytes.decode("utf-8")))
                    st.session_state.last_import_hash = marker
                    st.success("Progress imported.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Could not import progress: {exc}")

    with st.expander("ℹ️ About the practice exam", expanded=False):
        st.write("The default simulation uses 50 true/false questions, 30 minutes, and a 90% practice pass threshold (45/50).")
        st.markdown(f"[Official format reference: Osaka Prefectural Police]({META['exam_standard']['url']})")
        st.caption("This is a study reviewer, not an official examination system.")


def page_review():
    review = st.session_state.review
    if not review or review.get("finished"):
        if review and review.get("finished"):
            render_review_summary(review)
            return

        st.markdown("### 🎯 Choose a review mission")
        st.markdown("<div class='km-card km-soft'><strong>Tap a mission and start.</strong><br><span class='km-small'>No setup needed for the quick modes. Custom filters are tucked under Advanced Mission.</span></div>", unsafe_allow_html=True)

        def launch_quick(mode_name: str, count_value: int = 20):
            ids = select_review_questions(QUESTIONS, mode_name, count_value)
            st.session_state.review = {"ids": ids, "index": 0, "correct": 0, "answered": 0, "started": time.time(), "mode": mode_name, "bank": "All", "combo": 0, "max_combo": 0}
            st.session_state.review_feedback = None
            st.session_state.review_started_at = time.time()
            st.session_state.pending_fx = "start"
            st.rerun()

        c1, c2 = st.columns(2)
        with c1:
            render_mode_card("Smart Mix", "The game chooses due, weak, and forgotten questions for you.", "🧠", "km-mode-blue")
            if st.button("Play Smart Mix", use_container_width=True, type="primary", key="review_quick_smart"):
                launch_quick("Due / adaptive", 20)
        with c2:
            render_mode_card("Weak Spot Hunt", "Attack questions you previously missed and reinforce them.", "🎯", "km-mode-pink")
            if st.button("Hunt Weak Spots", use_container_width=True, key="review_quick_wrong"):
                launch_quick("Wrong answers", 20)

        c3, c4 = st.columns(2)
        with c3:
            render_mode_card("New Roads", "Only fresh questions first — perfect for expanding coverage.", "🗺️", "km-mode-green")
            if st.button("Explore New Roads", use_container_width=True, key="review_quick_unseen"):
                launch_quick("Unseen", 20)
        with c4:
            render_mode_card("Mystery Run", "A random 20-question challenge from the full database.", "🎲", "km-mode-violet")
            if st.button("Start Mystery Run", use_container_width=True, key="review_quick_random"):
                launch_quick("Random", 20)

        with st.expander("🛠️ Advanced Mission — choose bank, set, category and length", expanded=False):
            c1, c2 = st.columns(2)
            bank = c1.selectbox("Bank", BANK_OPTIONS, key="review_bank")
            set_filter = c2.selectbox("Set", set_options_for_bank(bank), key="review_set")
            categories = ["All"] + sorted({q["category"] for q in filter_questions(bank, set_filter)})
            category = st.selectbox("Category", categories, key="review_category")
            c1, c2 = st.columns(2)
            mode = c1.selectbox("Strategy", ["Due / adaptive", "Wrong answers", "Unseen", "Weakest", "Random"], key="review_mode")
            count = c2.slider("Questions", min_value=5, max_value=100, value=20, step=5)
            pool = filter_questions(bank, set_filter, category)
            st.caption(f"{len(pool)} questions match these filters.")
            if st.button("Launch custom mission", type="primary", use_container_width=True, disabled=not pool):
                ids = select_review_questions(pool, mode, count)
                st.session_state.review = {"ids": ids, "index": 0, "correct": 0, "answered": 0, "started": time.time(), "mode": mode, "bank": bank, "set": set_filter, "category": category, "combo": 0, "max_combo": 0}
                st.session_state.review_feedback = None
                st.session_state.review_started_at = time.time()
                st.session_state.pending_fx = "start"
                st.rerun()
        return

    ids = review["ids"]
    idx = review["index"]
    q = BY_ID[ids[idx]]
    st.progress((idx + 1) / max(1, len(ids)), text=f"Level {idx + 1} / {len(ids)}")
    feedback = st.session_state.review_feedback
    render_question(q, idx + 1, len(ids), reveal=feedback is not None, selected=feedback)

    if feedback is None:
        c1, c2 = st.columns(2)
        if c1.button("✅ TRUE", use_container_width=True, type="primary"):
            answer_review(q, True)
            if bool(q["answer"]) is True and int(review.get("combo", 0)) in {3, 5, 10, 15, 20}:
                st.session_state.pending_fx = "combo"
            else:
                st.session_state.pending_fx = "correct" if bool(q["answer"]) is True else "wrong"
            st.rerun()
        if c2.button("❌ FALSE", use_container_width=True):
            answer_review(q, False)
            if bool(q["answer"]) is False and int(review.get("combo", 0)) in {3, 5, 10, 15, 20}:
                st.session_state.pending_fx = "combo"
            else:
                st.session_state.pending_fx = "correct" if bool(q["answer"]) is False else "wrong"
            st.rerun()
    else:
        if st.button("Next level →", use_container_width=True, type="primary"):
            if idx + 1 >= len(ids):
                review["finished"] = True
                add_session("review", ids, review["correct"], time.time() - review["started"], review.get("bank", "All"))
                st.session_state.pending_fx = "complete"
            else:
                review["index"] += 1
                st.session_state.review_started_at = time.time()
            st.session_state.review_feedback = None
            st.rerun()

    with st.expander("📊 Learning status for this question"):
        s = qstat(q["id"])
        c1, c2, c3 = st.columns(3)
        c1.metric("Attempts", s["attempts"])
        c2.metric("Accuracy", f"{(100*s['correct']/s['attempts']):.0f}%" if s["attempts"] else "—")
        c3.metric("Mastery", f"{mastery(s):.0f}%")


def answer_review(q: dict, choice: bool):
    review = st.session_state.review
    elapsed = time.time() - st.session_state.review_started_at
    ok = bool(choice) == bool(q["answer"])
    record_answer(q["id"], ok, elapsed)
    review["answered"] += 1
    review["correct"] += int(ok)
    if ok:
        review["combo"] = int(review.get("combo", 0)) + 1
        review["max_combo"] = max(int(review.get("max_combo", 0)), review["combo"])
    else:
        review["combo"] = 0
    st.session_state.review_feedback = choice
    check_new_achievements()


def render_review_summary(review):
    total = len(review["ids"])
    correct = review["correct"]
    pct = 100 * correct / max(1, total)
    st.markdown("### Review complete")
    feedback_animation("complete")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Score", f"{correct}/{total}")
    c2.metric("Accuracy", f"{pct:.0f}%")
    c3.metric("Best combo", f"{int(review.get('max_combo', 0))}x")
    c4.metric("Mode", review.get("mode", "Review"))
    mascot_feedback("complete")
    if st.button("New review", use_container_width=True, type="primary"):
        st.session_state.review = None
        st.session_state.review_feedback = None
        st.rerun()


def start_exam(bank: str, set_filter: str, count: int, minutes: int):
    pool = filter_questions(bank, set_filter)
    count = min(count, len(pool))
    ids = [q["id"] for q in random.sample(pool, count)]
    now = time.time()
    st.session_state.exam = {
        "ids": ids,
        "index": 0,
        "answers": {},
        "flagged": [],
        "started": now,
        "started_iso": utc_now_iso(),
        "deadline": now + minutes * 60,
        "minutes": minutes,
        "bank": bank,
        "set": set_filter,
        "submitted": False,
        "session_id": uuid.uuid4().hex,
        "online_saved": False,
        "celebrated": False,
    }
    sync_live_exam(st.session_state.exam)


def submit_exam():
    exam = st.session_state.exam
    if not exam or exam.get("submitted"):
        return
    correct = 0
    for qid in exam["ids"]:
        ans = exam["answers"].get(qid, None)
        q = BY_ID[qid]
        ok = ans is not None and bool(ans) == bool(q["answer"])
        correct += int(ok)
        record_answer(qid, ok, exam.get("minutes", 30) * 60 / max(1, len(exam["ids"])))
    elapsed = max(0.0, time.time() - exam["started"])
    exam["correct"] = correct
    exam["elapsed"] = elapsed
    exam["submitted"] = True
    add_session("exam", exam["ids"], correct, elapsed, exam.get("bank", "All"))
    finish_live_exam(exam, correct, elapsed)
    pct = 100 * correct / max(1, len(exam["ids"]))
    st.session_state.pending_fx = "pass" if pct >= META["exam_standard"]["pass_percent"] else "retry"
    check_new_achievements()


def timer_widget(deadline: float):
    # Browser-side display keeps counting smoothly without rerunning the full app.
    deadline_ms = int(deadline * 1000)
    components.html(
        f"""
<div id="timer" style="font-family:system-ui;font-weight:800;font-size:18px;color:#41546f;text-align:right;padding:2px 4px"></div>
<script>
const end={deadline_ms};
function tick(){{
  const s=Math.max(0,Math.floor((end-Date.now())/1000));
  const m=Math.floor(s/60), r=s%60;
  document.getElementById('timer').innerText='⏱ '+String(m).padStart(2,'0')+':'+String(r).padStart(2,'0');
}}
tick(); setInterval(tick,500);
</script>
        """,
        height=34,
    )


def page_exam():
    exam = st.session_state.exam
    if not exam:
        st.markdown("### 🏁 Exam Challenge")
        render_mode_card("Official-Style Run", "50 questions · 30 minutes · 90% practice target · leaderboard eligible", "🏆", "km-mode-orange")
        if st.button("Start 50Q Challenge", use_container_width=True, type="primary", key="exam_quick_start"):
            start_exam("All", "All", 50, 30)
            st.session_state.pending_fx = "start"
            st.rerun()

        st.markdown("<div class='km-callout'>🔥 Finish a 50-question run to appear on the shared ranking board. Your live progress is visible while you play.</div>", unsafe_allow_html=True)

        with st.expander("🛠️ Custom Challenge", expanded=False):
            c1, c2 = st.columns(2)
            bank = c1.selectbox("Bank", BANK_OPTIONS, key="exam_bank")
            set_filter = c2.selectbox("Set", set_options_for_bank(bank), key="exam_set")
            pool = filter_questions(bank, set_filter)
            c1, c2 = st.columns(2)
            max_count = min(100, len(pool))
            default_count = min(50, max_count)
            count = c1.number_input("Questions", min_value=5, max_value=max_count, value=default_count, step=5)
            minutes = c2.number_input("Minutes", min_value=5, max_value=120, value=30, step=5)
            if st.button("Launch custom challenge", use_container_width=True, disabled=not pool):
                start_exam(bank, set_filter, int(count), int(minutes))
                st.session_state.pending_fx = "start"
                st.rerun()
        return

    if exam.get("submitted"):
        render_exam_results(exam)
        return

    if time.time() >= exam["deadline"]:
        submit_exam()
        st.warning("Time expired. The exam was submitted automatically.")
        st.rerun()

    sync_live_exam(exam)
    exam_heartbeat()
    ids = exam["ids"]
    idx = exam["index"]
    q = BY_ID[ids[idx]]
    top1, top2 = st.columns([4, 1.35])
    top1.progress((idx + 1) / max(1, len(ids)), text=f"Stage {idx + 1} of {len(ids)}")
    with top2:
        timer_widget(exam["deadline"])

    render_question(q, idx + 1, len(ids), reveal=False)
    current = exam["answers"].get(q["id"])
    c1, c2 = st.columns(2)
    true_clicked = c1.button("✅ TRUE" + ("  ✓" if current is True else ""), use_container_width=True, type="primary", key=f"exam_true_{q['id']}")
    false_clicked = c2.button("❌ FALSE" + ("  ✓" if current is False else ""), use_container_width=True, key=f"exam_false_{q['id']}")
    if true_clicked:
        exam["answers"][q["id"]] = True
        sync_live_exam(exam)
        st.rerun()
    if false_clicked:
        exam["answers"][q["id"]] = False
        sync_live_exam(exam)
        st.rerun()

    flagged = q["id"] in exam["flagged"]
    flag = st.checkbox("🚩 Flag for later review", value=flagged, key=f"flag_{q['id']}")
    if flag and not flagged:
        exam["flagged"].append(q["id"])
    elif not flag and flagged:
        exam["flagged"].remove(q["id"])

    c1, c2 = st.columns(2)
    if c1.button("← Previous", use_container_width=True, disabled=idx == 0):
        exam["index"] -= 1
        st.rerun()
    if c2.button("Next →", use_container_width=True, disabled=idx >= len(ids) - 1):
        exam["index"] += 1
        st.rerun()

    jump = st.selectbox("Jump to question", list(range(1, len(ids) + 1)), index=idx, key=f"exam_jump_{idx}")
    if jump - 1 != exam["index"]:
        exam["index"] = jump - 1
        st.rerun()

    with st.expander("🧭 Exam status"):
        unanswered = [i + 1 for i, qid in enumerate(ids) if qid not in exam["answers"]]
        flagged_n = [i + 1 for i, qid in enumerate(ids) if qid in exam["flagged"]]
        st.write(f"Answered: {len(exam['answers'])}/{len(ids)}")
        st.write(f"Unanswered: {', '.join(map(str, unanswered)) if unanswered else 'None'}")
        st.write(f"Flagged: {', '.join(map(str, flagged_n)) if flagged_n else 'None'}")

    unanswered_count = len(ids) - len(exam["answers"])
    confirm_unanswered = True
    if unanswered_count:
        confirm_unanswered = st.checkbox(f"Submit with {unanswered_count} unanswered question(s)", value=False)
    if st.button("Submit exam", use_container_width=True, type="primary", disabled=bool(unanswered_count and not confirm_unanswered)):
        submit_exam()
        st.rerun()


def render_exam_results(exam):
    total = len(exam["ids"])
    correct = exam.get("correct", 0)
    pct = 100 * correct / max(1, total)
    pass_pct = META["exam_standard"]["pass_percent"]
    passed = pct >= pass_pct
    if online_enabled() and not exam.get("online_saved"):
        finish_live_exam(exam, correct, exam.get("elapsed", 0.0))
    result_title = "MISSION CLEARED!" if passed else "TRAINING COMPLETE"
    result_sub = "Excellent run — you cleared the practice target." if passed else "Review the misses, then come back for another run."
    st.markdown(f"<div class='km-result-hero'><div style='font-size:2rem'>{'🏆' if passed else '🛠️'}</div><div class='km-result-score'>{pct:.0f}%</div><div class='km-result-title'>{result_title}</div><div class='km-result-sub'>{result_sub}</div></div>", unsafe_allow_html=True)
    feedback_animation("pass" if passed else "retry")
    st.markdown("### 🏆 Exam result")
    c1, c2, c3 = st.columns(3)
    c1.metric("Score", f"{correct}/{total}")
    c2.metric("Accuracy", f"{pct:.1f}%")
    c3.metric("Result", "PASS" if passed else "REVIEW")
    mascot_feedback("pass" if passed else "retry")
    if passed and total == 50 and not exam.get("celebrated"):
        st.balloons()
        exam["celebrated"] = True

    if total == 50:
        st.success("Passed the 90% practice threshold.") if passed else st.error("Below the 90% practice threshold. Review the missed items below.")
    else:
        st.info("The same 90% practice threshold is shown, but only a 50-question run is included on the main shared ranking board.")

    if online_enabled() and total == 50:
        st.success("🏆 This result was submitted to the shared ranking board.")

    rows = []
    for pos, qid in enumerate(exam["ids"], 1):
        q = BY_ID[qid]
        ans = exam["answers"].get(qid, None)
        ok = ans is not None and bool(ans) == bool(q["answer"])
        if not ok:
            rows.append((pos, q, ans))
    st.markdown(f"### Missed / unanswered ({len(rows)})")
    if not rows:
        st.success("Perfect score.")
    for pos, q, ans in rows:
        with st.expander(f"Q{pos} · {q['id']} · {q['category']}"):
            st.write(q["question_en"])
            if st.session_state.show_japanese and q.get("question_ja"):
                st.caption(q["question_ja"])
            st.write(f"Your answer: {'TRUE' if ans is True else 'FALSE' if ans is False else 'Unanswered'}")
            st.write(f"Correct answer: {'TRUE' if q['answer'] else 'FALSE'}")
            st.write(q["explanation"])
            render_sources(q)

    c1, c2, c3 = st.columns(3)
    if c1.button("New exam", use_container_width=True, type="primary"):
        st.session_state.exam = None
        st.rerun()
    if c2.button("Review misses", use_container_width=True, disabled=not rows):
        ids = [q["id"] for _, q, _ in rows]
        st.session_state.review = {"ids": ids, "index": 0, "correct": 0, "answered": 0, "started": time.time(), "mode": "Exam mistakes", "bank": exam.get("bank", "All"), "combo": 0, "max_combo": 0}
        st.session_state.review_feedback = None
        st.session_state.review_started_at = time.time()
        st.session_state.nav = "Review"
        st.rerun()
    if c3.button("View ranking", use_container_width=True):
        st.session_state.nav = "Rankings"
        st.rerun()


@st.fragment(run_every="15s")
def live_rankings_fragment():
    live = fetch_live_exams()
    if not live:
        st.caption("No active examiners in the last 5 minutes.")
        return
    rows = []
    for i, r in enumerate(live, 1):
        total = int(r.get("total_questions") or 0)
        answered = int(r.get("answered") or 0)
        correct = int(r.get("correct") or 0)
        started = parse_iso(r.get("started_at"))
        elapsed = "—"
        if started:
            sec = max(0, int((datetime.now(timezone.utc) - started).total_seconds()))
            elapsed = f"{sec//60}:{sec%60:02d}"
        rows.append({
            "#": i,
            "Examiner": f"{r.get('avatar') or '🚙'} {r.get('display_name') or 'Driver'}",
            "Live score": f"{correct}/{total}",
            "Progress": f"{answered}/{total}",
            "Elapsed": elapsed,
            "Bank": r.get("bank") or "All",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.caption("Live score is the number currently correct. The table refreshes every 15 seconds.")


def build_best_leaderboard(results: list[dict]) -> pd.DataFrame:
    # Fair comparison: only completed 50-question runs.
    valid = [r for r in results if int(r.get("total_questions") or 0) == 50]
    best = {}
    for r in valid:
        name = str(r.get("display_name") or "Driver")
        avatar = r.get("avatar") or "🚙"
        key = (name, avatar)
        score = int(r.get("score") or 0)
        elapsed = float(r.get("elapsed_seconds") or 999999)
        prev = best.get(key)
        if prev is None or score > int(prev.get("score") or 0) or (score == int(prev.get("score") or 0) and elapsed < float(prev.get("elapsed_seconds") or 999999)):
            best[key] = r
    ordered = sorted(best.values(), key=lambda r: (-int(r.get("score") or 0), float(r.get("elapsed_seconds") or 999999), str(r.get("display_name") or "")))
    rows = []
    for i, r in enumerate(ordered[:30], 1):
        elapsed = int(float(r.get("elapsed_seconds") or 0))
        rows.append({
            "Rank": i,
            "Examiner": f"{r.get('avatar') or '🚙'} {r.get('display_name') or 'Driver'}",
            "Best": f"{int(r.get('score') or 0)}/50",
            "Accuracy": f"{float(r.get('percent') or 0):.1f}%",
            "Time": f"{elapsed//60}:{elapsed%60:02d}",
            "Result": "PASS" if r.get("passed") else "REVIEW",
        })
    return pd.DataFrame(rows)


def page_rankings():
    st.markdown("### 🏆 Live exam room")
    st.caption("Use a nickname only. Active examiners are considered online when their exam has checked in within the last 5 minutes.")
    if not online_enabled():
        st.warning("Shared rankings are not connected yet. The rest of the reviewer is fully usable.")
        st.markdown(
            "<div class='km-card'><strong>One-time setup</strong><br>1. Create a free Supabase project.<br>2. Run <code>supabase_setup.sql</code> from this package in Supabase SQL Editor.<br>3. Add <code>SUPABASE_URL</code> and <code>SUPABASE_SECRET_KEY</code> to your Streamlit app Secrets.<br>4. Reboot the app.</div>",
            unsafe_allow_html=True,
        )
        return

    live_rankings_fragment()

    st.markdown("### All-time best 50-question exams")
    results = fetch_exam_results(500)
    board = build_best_leaderboard(results)
    if board.empty:
        st.caption("No completed 50-question exams yet.")
    else:
        top3 = board.head(3).to_dict("records")
        if top3:
            st.markdown("<div class='km-top3'>", unsafe_allow_html=True)
            cols = st.columns(len(top3))
            medals = ["🥇", "🥈", "🥉"]
            for i, (col, row) in enumerate(zip(cols, top3)):
                with col:
                    st.markdown(
                        f"<div class='km-podium'><div class='km-podium-rank'>{medals[i]}</div><div class='km-podium-name'>{html.escape(str(row['Examiner']))}</div><div class='km-podium-score'>{html.escape(str(row['Best']))}</div><div class='km-small'>{html.escape(str(row['Time']))} · {html.escape(str(row['Accuracy']))}</div></div>",
                        unsafe_allow_html=True,
                    )
        st.dataframe(board, use_container_width=True, hide_index=True)
        my_name = safe_player_name()
        match = board[board["Examiner"].str.endswith(my_name, na=False)]
        if not match.empty:
            row = match.iloc[0]
            st.markdown(f"<div class='km-callout'>Your current best rank: <span class='km-rank'>#{int(row['Rank'])}</span> · {row['Best']} · {row['Time']}</div>", unsafe_allow_html=True)

    if results:
        st.markdown("### Recent finishes")
        recent_rows = []
        for r in results[:20]:
            elapsed = int(float(r.get("elapsed_seconds") or 0))
            recent_rows.append({
                "Examiner": f"{r.get('avatar') or '🚙'} {r.get('display_name') or 'Driver'}",
                "Score": f"{int(r.get('score') or 0)}/{int(r.get('total_questions') or 0)}",
                "Accuracy": f"{float(r.get('percent') or 0):.1f}%",
                "Time": f"{elapsed//60}:{elapsed%60:02d}",
                "Bank": r.get("bank") or "All",
            })
        st.dataframe(pd.DataFrame(recent_rows), use_container_width=True, hide_index=True)

    if st.session_state.online_error:
        with st.expander("Connection details"):
            st.code(st.session_state.online_error)


def page_progress():
    stats = st.session_state.progress["question_stats"]
    sessions = st.session_state.progress["sessions"]
    attempts = sum(s.get("attempts", 0) for s in stats.values())
    correct = sum(s.get("correct", 0) for s in stats.values())
    attempted_q = sum(1 for s in stats.values() if s.get("attempts", 0) > 0)
    coverage = 100 * attempted_q / len(QUESTIONS)
    accuracy = 100 * correct / max(1, attempts) if attempts else 0

    st.markdown("### 📈 Your progress")
    c1, c2, c3 = st.columns(3)
    c1.metric("Accuracy", f"{accuracy:.1f}%" if attempts else "—")
    c2.metric("Coverage", f"{coverage:.1f}%")
    c3.metric("Attempts", attempts)

    st.markdown("### 🏅 Achievement collection")
    achievements = achievement_catalog()
    cards = []
    for a in achievements:
        cls = "" if a["earned"] else " locked"
        status = "Unlocked" if a["earned"] else "Locked"
        cards.append(f"<div class='km-badge-card{cls}'><div class='km-badge-icon'>{a['icon']}</div><div class='km-badge-name'>{html.escape(a['name'])}</div><div class='km-badge-desc'>{html.escape(a['desc'])}<br><strong>{status}</strong></div></div>")
    st.markdown("<div class='km-badge-grid'>" + "".join(cards) + "</div>", unsafe_allow_html=True)

    grouped = defaultdict(list)
    for q in QUESTIONS:
        grouped[q["category"]].append(q)
    rows = []
    for cat, qs in grouped.items():
        cat_stats = [qstat(q["id"]) for q in qs]
        cat_attempts = sum(s["attempts"] for s in cat_stats)
        cat_correct = sum(s["correct"] for s in cat_stats)
        seen = sum(1 for s in cat_stats if s["attempts"] > 0)
        avg_mastery = sum(mastery(s) for s in cat_stats) / len(cat_stats)
        rows.append({
            "Category": cat,
            "Questions": len(qs),
            "Coverage %": round(100 * seen / len(qs), 1),
            "Accuracy %": round(100 * cat_correct / cat_attempts, 1) if cat_attempts else None,
            "Mastery %": round(avg_mastery, 1),
            "Attempts": cat_attempts,
        })
    df = pd.DataFrame(rows).sort_values(["Mastery %", "Category"])
    st.markdown("### Category performance")
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.bar_chart(df.set_index("Category")[["Mastery %"]], height=340)

    weak_rows = []
    for q in QUESTIONS:
        s = qstat(q["id"])
        if s["attempts"] <= 0:
            continue
        weak_rows.append({
            "ID": q["id"], "Bank": bank_label(q), "Category": q["category"],
            "Attempts": s["attempts"], "Wrong": s["wrong"],
            "Accuracy %": round(100*s["correct"]/s["attempts"], 1),
            "Mastery %": round(mastery(s), 1),
            "Avg sec": round(s["total_seconds"]/s["attempts"], 1),
            "Question": q["question_en"],
        })
    st.markdown("### Hardest questions")
    if weak_rows:
        weak_df = pd.DataFrame(weak_rows).sort_values(["Mastery %", "Wrong", "Attempts"], ascending=[True, False, False]).head(30)
        st.dataframe(weak_df, use_container_width=True, hide_index=True)
    else:
        st.caption("Answer some questions first.")

    if sessions:
        st.markdown("### Session history")
        sess_df = pd.DataFrame(sessions[-50:])
        show_cols = [c for c in ["timestamp", "mode", "bank", "questions", "correct", "percent", "seconds"] if c in sess_df.columns]
        st.dataframe(sess_df[show_cols].iloc[::-1], use_container_width=True, hide_index=True)
        exams = sess_df[sess_df["mode"] == "exam"] if "mode" in sess_df else pd.DataFrame()
        if not exams.empty:
            st.line_chart(exams[["percent"]].reset_index(drop=True), height=250)

    with st.expander("How Mastery is calculated"):
        st.write("Mastery is an app-local study score, not an official test metric. It combines accuracy, number of exposures, and the current correct-answer streak.")

    st.download_button("Download progress backup", progress_json(), "karimen_progress.json", "application/json", use_container_width=True)


def page_bank():
    st.markdown("### 🔎 Question bank")
    c1, c2 = st.columns(2)
    bank = c1.selectbox("Bank", BANK_OPTIONS, key="browse_bank")
    set_filter = c2.selectbox("Set", set_options_for_bank(bank), key="browse_set")
    pool0 = filter_questions(bank, set_filter)
    categories = ["All"] + sorted({q["category"] for q in pool0})
    category = st.selectbox("Category", categories, key="browse_cat")
    search = st.text_input("Search", placeholder="e.g. crosswalk, parking, signal, A1-S16-Q048")
    only_images = st.checkbox("Image questions only")
    pool = filter_questions(bank, set_filter, category)
    if search.strip():
        s = search.lower().strip()
        pool = [q for q in pool if s in q["id"].lower() or s in q["question_en"].lower() or s in q.get("question_ja", "").lower() or s in q["explanation"].lower()]
    if only_images:
        pool = [q for q in pool if q.get("images")]
    st.caption(f"{len(pool)} questions")
    if not pool:
        return
    labels = [f"{q['id']} · {bank_label(q)} · {q['question_en'][:68]}" for q in pool]
    selected_label = st.selectbox("Select question", labels)
    q = pool[labels.index(selected_label)]
    render_question(q, 1, 1, reveal=True, selected=q["answer"])
    s = qstat(q["id"])
    c1, c2, c3 = st.columns(3)
    c1.metric("Attempts", s["attempts"])
    c2.metric("Wrong", s["wrong"])
    c3.metric("Mastery", f"{mastery(s):.0f}%")



def play_pending_fx():
    kind = st.session_state.get("pending_fx")
    if kind:
        st.session_state.pending_fx = None
        feedback_fx(kind)


def footer():
    st.markdown("<div class='km-divider'></div><div class='km-small'>A1 B1 Karimen Reviewer · Build 3.2 Game+ · Study aid only · Shared ranking uses nicknames only</div>", unsafe_allow_html=True)


prime_achievement_snapshot()
nav = header()
play_pending_fx()
render_achievement_toast()
if nav == "Home":
    page_home()
elif nav == "Review":
    page_review()
elif nav == "Exam":
    page_exam()
elif nav == "Rankings":
    page_rankings()
elif nav == "Progress":
    page_progress()
elif nav == "Bank":
    page_bank()
footer()
