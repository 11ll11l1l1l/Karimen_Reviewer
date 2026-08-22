from __future__ import annotations

import base64
import html
import json
import os
import random
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from karimen_core import (
    add_session,
    category_stats,
    daily_question_ids,
    daily_streak,
    default_progress,
    mastery,
    normalize_progress,
    parse_iso,
    record_answer,
    record_confidence,
    is_bookmarked,
    toggle_bookmark,
    select_question_ids,
    stat_for,
    utc_now_iso,
)

try:
    from supabase import create_client
except Exception:
    create_client = None

try:
    import edge_tts
except Exception:
    edge_tts = None

ROOT = Path(__file__).resolve().parent
DATA_FILE = ROOT / "data" / "questions.json"
QUESTION_ASSET_ROOT = ROOT
SOUND_DIR = ROOT / "assets" / "sounds"
MASCOT_DIR = ROOT / "assets" / "mascots"
FALLBACK_MASCOT = ROOT / "assets" / "mascot.png"
JST = timezone(timedelta(hours=9))
BUILD = "4.4 Polished"

st.set_page_config(
    page_title="Karimen Reviewer",
    page_icon="🐱",
    layout="wide",
    initial_sidebar_state="collapsed",
)


@st.cache_data(show_spinner=False)
def load_data():
    doc = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    questions = doc["questions"]
    return doc["metadata"], questions, {q["id"]: q for q in questions}


META, QUESTIONS, BY_ID = load_data()
VALID_IDS = set(BY_ID)
BANK_OPTIONS = ["All", "A1", "B1"]
BANK_SCOPE_LABELS = {"All": "A1 + B1", "A1": "A1 only", "B1": "B1 only"}
AVATARS = ["🐱", "🚙", "🦊", "🐼", "🌸", "⭐", "🚦"]
CHARACTER_NAMES = {"🐱": "Police Cat", "🚙": "Road Car", "🦊": "Fox Driver", "🐼": "Panda Driver", "🌸": "Sakura", "⭐": "Road Star", "🚦": "Traffic Light"}
VOICE_MODES = [
    "Natural neural voice (online)",
    "Cute neural voice (online)",
    "Friendly neural voice (online)",
    "Device voice (offline)",
    "Cute bloops",
    "Off",
]
PASS_PERCENT = float(META.get("exam_standard", {}).get("pass_percent", 90))


def init_state():
    defaults = {
        "progress": default_progress(),
        "route": "Home",
        "nav_choice": "Home",
        "sync_nav": False,
        "active_game": None,
        "review": None,
        "review_feedback": None,
        "review_started_at": time.time(),
        "exam": None,
        "player_name": "",
        "avatar": "🐱",
        "guest_code": uuid.uuid4().hex[:4].upper(),
        "profile_ready": False,
        "bank_scope": "All",
        "opt_sound": True,
        "opt_voice": True,
        "voice_mode": "Natural neural voice (online)",
        "opt_haptics": True,
        "opt_japanese": False,
        "opt_theme": "Arcade",
        "pending_fx": None,
        "pending_voice": None,
        "mascot_state": "idle",
        "mascot_category": "General rules",
        "feedback_nonce": 0,
        "seen_achievement_ids": set(),
        "achievement_toast": None,
        "achievements_ready": False,
        "last_import_hash": None,
        "online_error": None,
        "ranking_diagnostic": None,
        "voice_backend_error": None,
        "voice_backend_status": "Not tested yet",
        "voice_rate": 0,
        "voice_pitch": 0,
        "voice_volume": 90,
        "fx_volume": 72,
        "resume_notice": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    # Migrate live sessions from v4.3 safely before any widgets are created.
    if st.session_state.get("voice_mode") == "Natural device voice":
        st.session_state.voice_mode = "Device voice (offline)"
    if int((st.session_state.get("progress") or {}).get("version", 0) or 0) < 7:
        st.session_state.progress = normalize_progress(st.session_state.progress, VALID_IDS)


init_state()


def inject_style():
    st.markdown(
        """
<style>
:root{--ink:#17345f;--muted:#6d83a4;--line:#cfe4f8;--card:#fff;--blue:#087ff5;--nav:#073a80;--green:#1bc47d;--red:#ff4d6d;--gold:#ffba22;--purple:#7654ff;--shadow:0 12px 30px rgba(31,77,145,.13)}
html,body,[class*="css"]{color:var(--ink)}
.stApp{background:radial-gradient(circle at 12% 6%,rgba(61,188,255,.20),transparent 24%),radial-gradient(circle at 88% 12%,rgba(255,167,78,.15),transparent 22%),linear-gradient(180deg,#eaf7ff 0%,#f7fbff 55%,#fff6e9 100%)}
.block-container{max-width:1180px;padding-top:.45rem;padding-bottom:5rem}
[data-testid="stHeader"]{background:rgba(239,248,255,.8);backdrop-filter:blur(10px)}
.km-top{position:relative;overflow:hidden;background:linear-gradient(135deg,#0873ee,#1da8ff 55%,#76d9ff);border:2px solid rgba(255,255,255,.55);border-radius:26px;padding:.9rem 1rem;color:#fff;box-shadow:0 16px 34px rgba(10,71,164,.22)}
.km-top:after{content:"";position:absolute;right:-35px;top:-58px;width:180px;height:180px;border-radius:50%;background:rgba(255,255,255,.13)}
.km-logo{font-size:clamp(1.65rem,5vw,2.55rem);font-weight:950;letter-spacing:-.04em;line-height:1;text-shadow:0 3px 0 rgba(0,44,114,.18)}
.km-tag{font-weight:760;margin-top:.3rem;opacity:.95}.km-hud{display:flex;gap:.45rem;flex-wrap:wrap;margin-top:.6rem}.km-hud span{background:rgba(4,51,126,.27);border:1px solid rgba(255,255,255,.3);border-radius:999px;padding:.28rem .62rem;font-size:.78rem;font-weight:850}
.km-card{background:rgba(255,255,255,.97);border:1px solid var(--line);border-radius:22px;padding:1rem;margin:.55rem 0;box-shadow:var(--shadow)}
.km-section{font-size:1.14rem;font-weight:950;margin:1rem 0 .5rem}.km-small{font-size:.85rem;color:var(--muted)}.km-divider{height:1px;background:#dceafb;margin:.8rem 0}
.km-profile{background:linear-gradient(135deg,#173d92,#167cff 57%,#65d2ff);border-radius:24px;padding:1rem;color:#fff;box-shadow:0 15px 32px rgba(28,72,168,.22)}
.km-profile-name{font-size:1.35rem;font-weight:950}.km-profile-sub{font-weight:720;opacity:.94}.km-xp{height:10px;background:rgba(255,255,255,.2);border-radius:999px;overflow:hidden;margin:.45rem 0}.km-xp i{display:block;height:100%;background:linear-gradient(90deg,#ffd23f,#fff9a4);border-radius:999px}
.km-chips{display:flex;gap:.5rem;flex-wrap:wrap}.km-chip{background:rgba(255,255,255,.16);border:1px solid rgba(255,255,255,.28);border-radius:15px;padding:.42rem .65rem;font-size:.78rem;font-weight:850}
.km-mode{position:relative;overflow:hidden;color:#fff;border-radius:22px;padding:1rem;min-height:145px;box-shadow:0 13px 28px rgba(40,76,135,.16)}.km-mode:after{content:"";position:absolute;right:-24px;bottom:-28px;width:100px;height:100px;background:rgba(255,255,255,.12);border-radius:50%}.km-mode h3{margin:0;font-size:1.2rem}.km-mode p{font-weight:650;line-height:1.45;margin:.35rem 0 0;opacity:.96}.km-blue{background:linear-gradient(135deg,#147df5,#5cbdff)}.km-green{background:linear-gradient(135deg,#0abf76,#58dc8d)}.km-orange{background:linear-gradient(135deg,#ff8d18,#ffc33d)}.km-purple{background:linear-gradient(135deg,#6a4dff,#a569ff)}.km-pink{background:linear-gradient(135deg,#ff507e,#ff8baa)}.km-cyan{background:linear-gradient(135deg,#04a9cf,#60ddf5)}
.km-world{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:.5rem;background:linear-gradient(180deg,#dff4ff,#f8fdff);border:1px solid #c7e4f8;border-radius:23px;padding:.75rem}.km-stage{background:#fff;border:1px solid #d8eafa;border-radius:17px;padding:.7rem .4rem;text-align:center;min-height:110px;box-shadow:0 5px 13px rgba(54,91,139,.08)}.km-stage.locked{filter:grayscale(.85);opacity:.55}.km-stage-icon{font-size:1.55rem}.km-stage-name{font-size:.78rem;font-weight:900;margin-top:.2rem}.km-stage-stars{color:#ffaf00;font-size:.8rem}.km-stage-req{font-size:.65rem;color:#7287a4}
.km-question{background:#fff;border:2px solid #cfe5fa;border-radius:25px;padding:1rem 1.05rem;box-shadow:0 14px 32px rgba(38,87,153,.12)}.km-qhead{display:flex;align-items:center;justify-content:space-between;gap:.55rem;flex-wrap:wrap}.km-cat{background:linear-gradient(135deg,#724dff,#a96cff);color:#fff;border-radius:999px;padding:.34rem .7rem;font-size:.8rem;font-weight:900}.km-diff{background:#fff2c4;border:1px solid #efd073;border-radius:999px;padding:.3rem .6rem;font-size:.78rem;font-weight:900;color:#8b6500}.km-qid{font-size:.76rem;color:var(--muted);font-weight:800;margin-top:.65rem}.km-qtext{font-size:clamp(1.12rem,3.8vw,1.5rem);font-weight:850;line-height:1.5;margin-top:.45rem}.km-ja{font-size:.95rem;line-height:1.55;color:#637795;border-top:1px dashed #d8e7f6;margin-top:.75rem;padding-top:.65rem}
.km-feedback-good{background:linear-gradient(180deg,#ebfff5,#fff);border:1px solid #aee4cb}.km-feedback-bad{background:linear-gradient(180deg,#fff0f3,#fff);border:1px solid #f0c4ce}.km-exp{line-height:1.55;margin-top:.4rem}
.km-gamehud{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.5rem;margin:.55rem 0}.km-gamehud>div{background:linear-gradient(180deg,#0b4e9e,#073875);border:1px solid rgba(255,255,255,.18);border-radius:16px;color:#fff;text-align:center;padding:.55rem}.km-gamehud b{display:block;font-size:1.05rem}.km-gamehud span{font-size:.7rem;font-weight:780;opacity:.88}
.km-mascot{background:linear-gradient(180deg,#eaf7ff,#fff);border:2px solid #b9ddfb;border-radius:23px;padding:.7rem;box-shadow:var(--shadow);text-align:center}.km-mascot-frame{width:100%;height:250px;display:flex;align-items:center;justify-content:center;overflow:hidden;padding:.55rem}.km-mascot-frame.compact{height:165px}.km-mascot-frame.header{height:105px;padding:.15rem}.km-mascot-frame img{display:block;width:auto;height:auto;max-width:185px;max-height:88%;object-fit:contain;object-position:center;border-radius:18px}.km-mascot-frame.compact img{max-width:128px}.km-mascot-frame.header img{max-width:78px;max-height:82px}.km-profile-setup{background:linear-gradient(135deg,#0b70e8,#4dbdff 56%,#9ce3ff);border:2px solid rgba(255,255,255,.65);border-radius:28px;padding:1.15rem;color:#fff;box-shadow:0 18px 42px rgba(22,83,168,.23);margin:.4rem 0 1rem}.km-profile-setup h1{margin:0;font-size:clamp(1.8rem,5vw,2.8rem)}.km-profile-setup p{font-weight:700;opacity:.96}.km-speech{background:#fff;border:2px solid #ffc84d;border-radius:18px;padding:.65rem .7rem;font-weight:850;line-height:1.4;margin-top:.4rem}.km-state{display:inline-block;background:#0a4087;color:#fff;border-radius:999px;padding:.24rem .55rem;font-size:.7rem;font-weight:900}.km-uniform{display:flex;align-items:center;gap:.55rem;margin-top:.55rem;background:#f6fbff;border:1px solid #d7e9f8;border-radius:15px;padding:.45rem;text-align:left}.km-uniform img{width:55px;height:55px;object-fit:contain;border-radius:13px;background:#eaf6ff}.km-uniform b{font-size:.78rem}.km-uniform span{display:block;font-size:.68rem;color:#7385a1}
.km-dotline{display:flex;gap:.28rem;flex-wrap:wrap;justify-content:center;background:#083d7e;border-radius:17px;padding:.5rem}.km-dot{width:29px;height:29px;display:inline-flex;align-items:center;justify-content:center;border-radius:50%;background:#225991;color:#fff;font-size:.7rem;font-weight:900}.km-dot.done{background:#1ac377}.km-dot.now{background:#1593ff;box-shadow:0 0 0 3px rgba(81,202,255,.42)}
.km-result{background:linear-gradient(135deg,#0875ee,#6d4eff 58%,#ffab35);color:#fff;border-radius:27px;text-align:center;padding:1.15rem;box-shadow:0 17px 35px rgba(53,71,171,.24)}.km-result-score{font-size:2.8rem;font-weight:950;line-height:1}.km-result-title{font-size:1.25rem;font-weight:950;margin-top:.25rem}
.km-weak{display:grid;grid-template-columns:minmax(130px,1.25fr) 2fr 58px;gap:.5rem;align-items:center;margin:.48rem 0}.km-bar{height:10px;background:#e8eef7;border-radius:999px;overflow:hidden}.km-bar i{display:block;height:100%;background:linear-gradient(90deg,#ff695b,#ffc32e,#24c884);border-radius:999px}.km-weak b{font-size:.82rem}.km-weak span{text-align:right;font-size:.78rem;font-weight:900}
.km-ach{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.55rem}.km-ach>div{background:#fff;border:1px solid #d9e9f7;border-radius:16px;padding:.7rem;box-shadow:0 5px 13px rgba(55,88,132,.07)}.km-ach .locked{opacity:.42;filter:grayscale(1)}
.km-toast{background:linear-gradient(135deg,#fff7c2,#ffe287);border:1px solid #efc948;border-radius:18px;padding:.75rem 1rem;font-weight:850;color:#614b00;box-shadow:var(--shadow)}
[data-testid="stImage"] img{border-radius:18px}.km-qimage{display:flex;justify-content:center;align-items:center;background:rgba(239,248,255,.75);border:1px solid #d7e9f8;border-radius:20px;padding:.55rem;margin:.6rem 0}.km-qimage img{display:block;max-width:100%;width:auto;height:auto;max-height:390px;object-fit:contain;border-radius:15px}.km-resume{background:linear-gradient(135deg,#fff7c7,#ffe38b);border:1px solid #e9c64b;border-radius:18px;padding:.72rem .85rem;margin:.5rem 0;color:#614d00;font-weight:780}.km-coach{background:linear-gradient(135deg,#eef8ff,#fff7d8);border:1px solid #cfe4f8;border-left:6px solid #ffb52b;border-radius:18px;padding:.72rem .85rem;margin:.6rem 0}.km-coach b{display:block;font-size:.95rem}.km-coach span{font-size:.82rem;color:#5e7596}.km-tools{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.45rem}.km-confidence{background:#f7fbff;border:1px solid #d7e9f8;border-radius:16px;padding:.65rem;margin-top:.6rem}.km-voice-ok{color:#087a4a;font-weight:800}.km-voice-warn{color:#9b6200;font-weight:800}div.stButton>button{min-height:3.15rem;border-radius:15px;font-weight:850;border:1px solid #d7e5f4;box-shadow:0 5px 13px rgba(49,84,132,.07)}button[kind="primary"]{background:linear-gradient(135deg,#087ff5,#55baff)!important;border:0!important;color:#fff!important}.stProgress>div>div>div{border-radius:999px}[data-baseweb="select"]>div,.stTextInput input,.stNumberInput input{border-radius:15px!important}
@media(max-width:850px){.km-world{grid-template-columns:repeat(3,minmax(0,1fr))}.km-gamehud{grid-template-columns:repeat(2,minmax(0,1fr))}.km-ach{grid-template-columns:repeat(2,minmax(0,1fr))}.km-mascot-frame{height:210px}.km-mascot-frame img{max-width:185px}.km-qimage img{max-height:330px}}
@media(max-width:580px){.block-container{padding-left:.6rem;padding-right:.6rem;padding-top:.25rem}.km-top{border-radius:20px;padding:.75rem}.km-logo{font-size:1.7rem}.km-hud{gap:.3rem}.km-hud span{font-size:.68rem;padding:.22rem .45rem}.km-world{grid-template-columns:repeat(2,minmax(0,1fr))}.km-question{padding:.78rem;border-radius:19px}.km-qtext{font-size:1.12rem}.km-ach{grid-template-columns:1fr}.km-tools{grid-template-columns:1fr}.km-mascot-frame{height:165px;padding:.2rem}.km-mascot-frame img{max-width:140px;max-height:150px}.km-mascot-frame.compact{height:135px}.km-mascot-frame.compact img{max-width:120px}.km-qimage{padding:.3rem}.km-qimage img{max-height:260px}div.stButton>button{min-height:3.35rem;font-size:.93rem}}
</style>
""",
        unsafe_allow_html=True,
    )


def inject_theme():
    theme = st.session_state.opt_theme
    if theme == "Cute":
        st.markdown("<style>.stApp{background:linear-gradient(180deg,#fff0f8,#edf9ff 55%,#fff7dd)}.km-top{background:linear-gradient(135deg,#ff70ad,#9b72ff 55%,#53c9ff)}</style>", unsafe_allow_html=True)
    elif theme == "Night":
        st.markdown("<style>.stApp{background:linear-gradient(180deg,#0f1d3a,#172a4d 65%,#24334d)}.km-card,.km-question,.km-mascot{background:#f8fbff}.km-top{background:linear-gradient(135deg,#17265c,#394bc0 55%,#16a7d9)}</style>", unsafe_allow_html=True)


inject_style()
inject_theme()


# ---------- Progress / data helpers ----------
def qstat(qid: str) -> dict:
    return stat_for(st.session_state.progress, qid)


def active_bookmarks() -> list[str]:
    active = {q["id"] for q in active_questions()}
    return [qid for qid in st.session_state.progress.get("bookmarks", []) if qid in active]


def bookmark_count() -> int:
    return len(active_bookmarks())


def bank_label(q: dict) -> str:
    return f"{q['bank']} · Set {int(q.get('set') or 0)}"


def set_options_for_bank(bank: str) -> list[str]:
    if bank == "A1":
        return ["All", "14", "15", "16"]
    if bank == "B1":
        return ["All"] + [str(i) for i in range(1, 11)]
    return ["All"]


def active_bank_scope() -> str:
    scope = str(st.session_state.get("bank_scope", "All"))
    return scope if scope in BANK_OPTIONS else "All"


def available_bank_options() -> list[str]:
    scope = active_bank_scope()
    return BANK_OPTIONS if scope == "All" else [scope]


def effective_bank(bank: str = "All") -> str:
    scope = active_bank_scope()
    if scope != "All":
        return scope
    return bank if bank in BANK_OPTIONS else "All"


def active_questions() -> list[dict]:
    scope = active_bank_scope()
    return list(QUESTIONS) if scope == "All" else [q for q in QUESTIONS if q["bank"] == scope]


def filter_questions(bank: str = "All", set_filter: str = "All", category: str = "All") -> list[dict]:
    scope = active_bank_scope()
    if scope != "All" and bank not in {"All", scope}:
        return []
    resolved = effective_bank(bank)
    qs = QUESTIONS if resolved == "All" else [q for q in QUESTIONS if q["bank"] == resolved]
    if set_filter != "All":
        try:
            set_no = int(set_filter)
            qs = [q for q in qs if int(q.get("set") or 0) == set_no]
        except (TypeError, ValueError):
            return []
    if category != "All":
        qs = [q for q in qs if q["category"] == category]
    return list(qs)


def safe_player_name() -> str:
    raw = (st.session_state.player_name or "").strip()
    raw = re.sub(r"[^\w .\-]", "", raw, flags=re.UNICODE)[:24].strip()
    return raw or f"Driver-{st.session_state.guest_code}"


def progress_json() -> str:
    return json.dumps(st.session_state.progress, ensure_ascii=False, indent=2)


def unique_seen_count() -> int:
    return sum(1 for q in active_questions() if int(qstat(q["id"]).get("attempts", 0) or 0) > 0)


def category_rows() -> list[dict]:
    return category_stats(active_questions(), st.session_state.progress)


def weak_categories(limit: int = 4) -> list[dict]:
    rows = [r for r in category_rows() if r["attempts"] > 0]
    rows.sort(key=lambda r: (r["mastery"], r["accuracy"], -r["attempts"]))
    return rows[:limit]


def today_jst():
    return datetime.now(JST).date()


def session_matches_scope(session: dict) -> bool:
    scope = active_bank_scope()
    if scope == "All":
        return True
    return str(session.get("bank") or "") == scope


def daily_completed_today() -> bool:
    today = today_jst()
    for s in st.session_state.progress.get("sessions", []):
        if s.get("mode") != "daily" or not session_matches_scope(s):
            continue
        ts = parse_iso(s.get("timestamp"))
        if ts and ts.astimezone(JST).date() == today:
            return True
    return False


def daily_challenge_streak() -> int:
    scoped_sessions = [s for s in st.session_state.progress.get("sessions", []) if session_matches_scope(s)]
    return daily_streak(scoped_sessions, today_jst(), JST)


def best_exam_percent() -> float:
    vals = [float(s.get("percent") or 0) for s in st.session_state.progress.get("sessions", []) if s.get("mode") == "exam" and session_matches_scope(s)]
    return max(vals or [0.0])


def achievement_catalog() -> list[dict]:
    stats = st.session_state.progress.get("question_stats", {})
    attempts = sum(int(s.get("attempts", 0) or 0) for s in stats.values())
    unique_seen = unique_seen_count()
    image_seen = sum(1 for q in active_questions() if q.get("images") and int(qstat(q["id"]).get("attempts", 0) or 0) > 0)
    sessions = st.session_state.progress.get("sessions", [])
    exams = [s for s in sessions if s.get("mode") == "exam"]
    max_combo = max([int(s.get("max_combo", 0) or 0) for s in sessions] + [int((st.session_state.review or {}).get("max_combo", 0) or 0), 0])
    survival_best = max([int(s.get("questions", 0) or 0) for s in sessions if s.get("mode") == "survival"] or [0])
    return [
        {"id": "first", "icon": "🚗", "name": "First Drive", "desc": "Answer your first question", "earned": attempts >= 1},
        {"id": "warm", "icon": "⚡", "name": "Engine Warm", "desc": "Answer 10 questions", "earned": attempts >= 10},
        {"id": "rookie", "icon": "🗺️", "name": "Road Rookie", "desc": "See 50 unique questions", "earned": unique_seen >= 50},
        {"id": "combo", "icon": "🔥", "name": "Hot Streak", "desc": "Get 5 correct in a row", "earned": max_combo >= 5},
        {"id": "image", "icon": "👀", "name": "Sharp Eye", "desc": "Practice 20 image questions", "earned": image_seen >= 20},
        {"id": "daily3", "icon": "📅", "name": "Daily Driver", "desc": "Complete a 3-day daily streak", "earned": daily_challenge_streak() >= 3},
        {"id": "survivor", "icon": "❤️", "name": "Survivor", "desc": "Reach 15 questions in Survival", "earned": survival_best >= 15},
        {"id": "pass", "icon": "🏆", "name": "Mock Pass", "desc": "Pass a 50-question mock exam", "earned": any(float(s.get("percent") or 0) >= PASS_PERCENT for s in exams)},
        {"id": "perfect", "icon": "💯", "name": "Perfect Drive", "desc": "Score 50/50 on a mock exam", "earned": any(int(s.get("questions") or 0) == 50 and int(s.get("correct") or 0) == 50 for s in exams)},
        {"id": "boss", "icon": "👑", "name": "Boss Breaker", "desc": "Clear a Boss Exam with 90%+", "earned": any(s.get("mode") == "boss" and float(s.get("percent") or 0) >= 90 for s in sessions)},
        {"id": "collector", "icon": "⭐", "name": "Rule Collector", "desc": "Bookmark 10 rules to revisit", "earned": bookmark_count() >= 10},
    ]


def total_xp() -> int:
    stats = st.session_state.progress.get("question_stats", {})
    correct = sum(int(s.get("correct", 0) or 0) for s in stats.values())
    wrong = sum(int(s.get("wrong", 0) or 0) for s in stats.values())
    sessions = st.session_state.progress.get("sessions", [])
    bonus = 0
    bonus += 30 * sum(1 for s in sessions if s.get("mode") == "daily")
    bonus += 60 * sum(1 for s in sessions if s.get("mode") == "exam" and float(s.get("percent") or 0) >= PASS_PERCENT)
    bonus += 100 * sum(1 for s in sessions if s.get("mode") == "boss" and float(s.get("percent") or 0) >= 90)
    bonus += 20 * sum(1 for a in achievement_catalog() if a["earned"])
    return correct * 10 + wrong * 2 + bonus


def level_info():
    total = total_xp()
    goal = 250
    return 1 + total // goal, total % goal, goal


def driver_title(level: int) -> str:
    title = "Learner Driver"
    for req, name in [(3, "Road Rookie"), (6, "City Driver"), (10, "Road Expert"), (15, "Karimen Ace"), (22, "Road Master")]:
        if level >= req:
            title = name
    return title


def pass_readiness() -> float:
    sessions = st.session_state.progress.get("sessions", [])
    exams = [float(s.get("percent") or 0) for s in sessions if s.get("mode") == "exam" and session_matches_scope(s)][-3:]
    exam_signal = sum(exams) / len(exams) if exams else 0.0
    practiced = [r["mastery"] for r in category_rows() if r["attempts"] > 0]
    mastery_signal = sum(practiced) / len(practiced) if practiced else 0.0
    coverage = 100 * unique_seen_count() / max(1, len(active_questions()))
    if exams:
        return max(0.0, min(100.0, .58 * exam_signal + .27 * mastery_signal + .15 * coverage))
    return max(0.0, min(100.0, .65 * mastery_signal + .35 * coverage))


def coach_recommendation() -> tuple[str, str, str]:
    """Return a small personalized next-step recommendation without changing any mode."""
    if not daily_completed_today():
        return "📅 Daily Challenge", "Complete today's 10-question mission first to build your streak.", "daily"
    scoped = [qstat(q["id"]) for q in active_questions()]
    sure_wrong = sum(int(x.get("confidence_sure_wrong", 0) or 0) for x in scoped)
    if sure_wrong:
        return "🧩 Fix confident misconceptions", f"You have {sure_wrong} confident miss(es). Mistake Hunt should come before more random practice.", "mistakes"
    if bookmark_count() >= 5:
        return "⭐ Revisit Saved Rules", f"You have {bookmark_count()} bookmarked rules waiting for retrieval practice.", "bookmarks"
    weak = weak_categories(1)
    if weak and float(weak[0].get("mastery", 0) or 0) < 70:
        return "🧠 Smart Review", f"Your weakest current topic is {weak[0]['category']} at {float(weak[0].get('mastery',0)):.0f}% mastery.", "review"
    if unique_seen_count() < max(25, int(0.5 * len(active_questions()))):
        return "🗺️ Expand coverage", "Smart Review will prioritize unseen and due rules so your bank coverage keeps growing.", "review"
    if best_exam_percent() < PASS_PERCENT:
        return "🏁 Mock Exam", "You have enough coverage to check readiness with a 50-question exam.", "exam"
    return "👑 Boss Exam", "Your recent progress is strong. Challenge the hardest 20 questions next.", "boss"


def prime_achievements():
    if not st.session_state.achievements_ready:
        st.session_state.seen_achievement_ids = {a["id"] for a in achievement_catalog() if a["earned"]}
        st.session_state.achievements_ready = True


def check_new_achievements():
    current = {a["id"] for a in achievement_catalog() if a["earned"]}
    new = current - set(st.session_state.seen_achievement_ids)
    if new:
        st.session_state.seen_achievement_ids = current
        st.session_state.achievement_toast = next((a for a in achievement_catalog() if a["id"] in new), None)
        st.session_state.pending_fx = "badge"


# ---------- Audio / voice ----------
VOICE_TEXT = {
    "ready": ["Ready? Let's drive!", "Ready when you are. Let's do this!"],
    "focus": ["Read every word carefully.", "Take your time. Watch the exact wording."],
    "correct": ["Correct! Nice work!", "Yes! That's right!", "Great job!"],
    "streak": ["Great streak! Keep going!", "You're on a roll!", "Amazing streak!"],
    "wrong": ["Almost. Check the exact rule.", "Not quite. Read the rule once more."],
    "pleading": ["Please get the next one right. You can do it!", "Come on, one careful answer. I know you can do it!"],
    "comeback": ["Yes! Great comeback!", "That's it! You're back!"],
    "victory": ["Mission cleared! You did it!", "Great work! Mission complete!"],
}

NEURAL_VOICE_IDS = {
    "Natural neural voice (online)": "en-US-AriaNeural",
    "Cute neural voice (online)": "en-US-AnaNeural",
    "Friendly neural voice (online)": "en-US-JennyNeural",
}

NEURAL_VOICE_PROFILES = {
    "Natural neural voice (online)": ("+0%", "+0Hz"),
    "Cute neural voice (online)": ("+2%", "+2Hz"),
    "Friendly neural voice (online)": ("+0%", "+0Hz"),
}

def voice_phrase(voice_key: str) -> str:
    phrases = VOICE_TEXT.get(str(voice_key), [])
    if isinstance(phrases, str):
        return phrases
    if not phrases:
        return ""
    # A little variation makes the mascot less repetitive without changing the learning content.
    return random.choice(list(phrases))


@st.cache_data(show_spinner=False)
def audio_uri(path_str: str) -> str | None:
    path = Path(path_str)
    if not path.exists():
        return None
    mime = "audio/wav" if path.suffix.lower() == ".wav" else "audio/mpeg"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


@st.cache_data(show_spinner=False)
def image_uri(path_str: str) -> str | None:
    path = Path(path_str)
    if not path.exists():
        return None
    suffix = path.suffix.lower().lstrip(".") or "png"
    mime = "image/jpeg" if suffix in {"jpg", "jpeg"} else f"image/{suffix}"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


@st.cache_data(show_spinner=False, ttl=86400)
def neural_tts_bytes(text: str, voice_id: str, rate: str = "+0%", pitch: str = "+0Hz") -> tuple[bytes | None, str | None]:
    """Generate high-quality mascot speech on the Streamlit server.

    Online neural speech is deliberately *not* auto-replaced by browser TTS when
    it fails. Some Android device voices sound robotic; silently falling back was
    the reason a user could select a neural voice and still hear poor speech.
    """
    if edge_tts is None:
        return None, "edge-tts is not installed. Neural speech is unavailable on this deployment."
    try:
        communicator = edge_tts.Communicate(
            text,
            voice=voice_id,
            rate=rate,
            volume="+0%",
            pitch=pitch,
            connect_timeout=5,
            receive_timeout=12,
        )
        chunks: list[bytes] = []
        for item in communicator.stream_sync():
            if item.get("type") == "audio" and item.get("data"):
                chunks.append(item["data"])
        data = b"".join(chunks)
        if not data:
            return None, "Neural speech returned no audio. No robotic fallback was used."
        return data, None
    except Exception as exc:
        return None, f"Neural speech unavailable ({exc}). No robotic fallback was used."


def queue_media(fx: str | None = None, voice: str | None = None):
    if fx:
        st.session_state.pending_fx = fx
    if voice:
        st.session_state.pending_voice = voice


def _tts_script(text: str, autoplay: bool = True, delay_ms: int = 180, volume: float = 0.9) -> str:
    safe_text = json.dumps(str(text), ensure_ascii=False)
    return f"""
<script>
(function(){{
  const text={safe_text};
  const volume={max(0.0, min(1.0, float(volume))):.2f};
  function chooseVoice(){{
    const voices=window.speechSynthesis ? speechSynthesis.getVoices() : [];
    if(!voices.length) return null;
    const score=(v)=>{{
      const n=(v.name||'').toLowerCase(), l=(v.lang||'').toLowerCase();
      let s=0;
      if(l.startsWith('en-us')) s+=10; else if(l.startsWith('en')) s+=6;
      if(/natural|neural|premium|enhanced|google/.test(n)) s+=18;
      if(/aria|jenny|samantha|serena|ava|sonia|emma|ana/.test(n)) s+=12;
      if(/female/.test(n)) s+=3;
      if(/espeak|festival/.test(n)) s-=25;
      return s;
    }};
    return voices.slice().sort((a,b)=>score(b)-score(a))[0];
  }}
  function speak(){{
    if(!window.speechSynthesis || !text) return;
    speechSynthesis.cancel();
    const u=new SpeechSynthesisUtterance(text);
    const v=chooseVoice(); if(v){{u.voice=v;u.lang=v.lang||'en-US';}} else {{u.lang='en-US';}}
    u.rate=0.98; u.pitch=1.02; u.volume=volume;
    speechSynthesis.speak(u);
  }}
  window.kmSpeak=speak;
  {f'setTimeout(speak, {int(delay_ms)});' if autoplay else ''}
}})();
</script>"""


def _bytes_audio_uri(data: bytes, mime: str = "audio/mpeg") -> str:
    return f"data:{mime};base64," + base64.b64encode(data).decode("ascii")


def play_pending_media():
    """Play feedback audio without overlapping the effect and spoken line."""
    fx = st.session_state.pending_fx
    voice_key = st.session_state.pending_voice
    st.session_state.pending_fx = None
    st.session_state.pending_voice = None

    fx_uri = audio_uri(str(SOUND_DIR / f"{fx}.wav")) if fx and st.session_state.opt_sound else None
    voice_mode = st.session_state.get("voice_mode", "Natural neural voice (online)") if st.session_state.get("opt_voice", True) else "Off"
    phrase = voice_phrase(str(voice_key)) if voice_key else ""
    neural_uri = None
    device_script = ""

    if phrase and voice_mode in NEURAL_VOICE_IDS:
        base_rate, base_pitch = NEURAL_VOICE_PROFILES.get(voice_mode, ("+0%", "+0Hz"))
        # User tuning is intentionally modest; large pitch changes make neural voices synthetic.
        rate_delta = int(st.session_state.get("voice_rate", 0) or 0)
        pitch_delta = int(st.session_state.get("voice_pitch", 0) or 0)
        base_rate_n = int(base_rate.replace("%", "")) + rate_delta
        base_pitch_n = int(base_pitch.replace("Hz", "")) + pitch_delta
        data, err = neural_tts_bytes(phrase, NEURAL_VOICE_IDS[voice_mode], f"{base_rate_n:+d}%", f"{base_pitch_n:+d}Hz")
        st.session_state.voice_backend_error = err
        if data:
            neural_uri = _bytes_audio_uri(data)
            st.session_state.voice_backend_status = f"Neural voice active · {NEURAL_VOICE_IDS[voice_mode]}"
        else:
            # Do not silently fall back to potentially robotic browser speech.
            st.session_state.voice_backend_status = "Neural voice unavailable · speech skipped (no robotic fallback)"
    elif phrase and voice_mode == "Device voice (offline)":
        st.session_state.voice_backend_error = None
        st.session_state.voice_backend_status = "Device voice selected · quality depends on this phone/browser"
        device_script = _tts_script(phrase, autoplay=True, delay_ms=520 if fx_uri else 140, volume=float(st.session_state.get("voice_volume", 90))/100.0)
    elif phrase and voice_mode == "Cute bloops":
        st.session_state.voice_backend_error = None
        st.session_state.voice_backend_status = "Cute bloops selected"
        bloop = audio_uri(str(SOUND_DIR / "bloop.wav"))
        if bloop and not fx_uri:
            fx_uri = bloop
    elif voice_mode == "Off":
        st.session_state.voice_backend_status = "Voice off"

    parts = ["<div style='height:0;overflow:hidden'>"]
    fx_volume = max(0.0, min(1.0, float(st.session_state.get('fx_volume', 72))/100.0))
    voice_volume = max(0.0, min(1.0, float(st.session_state.get('voice_volume', 90))/100.0))
    if fx_uri:
        parts.append(f'<audio id="kmfx" autoplay><source src="{fx_uri}" type="audio/wav"></audio><script>document.getElementById("kmfx").volume={fx_volume:.2f};</script>')
    if neural_uri:
        parts.append(f'<audio id="kmvoice" preload="auto"><source src="{neural_uri}" type="audio/mpeg"></audio><script>document.getElementById("kmvoice").volume={voice_volume:.2f};</script>')
        # Sequence voice after the short effect instead of layering both together.
        if fx_uri:
            parts.append("""
<script>
(function(){
  const fx=document.getElementById('kmfx'), voice=document.getElementById('kmvoice');
  let started=false;
  const speak=()=>{if(started||!voice)return;started=true;setTimeout(()=>voice.play().catch(()=>{}),90)};
  if(fx){fx.addEventListener('ended',speak,{once:true});setTimeout(()=>{if(fx.paused)speak()},500);} else {speak();}
})();
</script>""")
        else:
            parts.append("<script>setTimeout(()=>document.getElementById('kmvoice')?.play().catch(()=>{}),120);</script>")
    if device_script:
        parts.append(device_script)
    if st.session_state.opt_haptics and fx:
        patterns = {"correct": "25", "wrong": "35,20,35", "combo": "20,20,40", "badge": "20,20,20,20,50", "pass": "20,20,20,20,60", "complete": "20,20,40"}
        parts.append(f"<script>navigator.vibrate && navigator.vibrate([{patterns.get(fx, '20')}]);</script>")
    parts.append("</div>")
    if len(parts) > 2:
        components.html("".join(parts), height=0, width=0)


def voice_button(voice_key: str):
    if not st.session_state.get("opt_voice", True):
        return
    mode = st.session_state.get("voice_mode", "Natural neural voice (online)")
    if mode == "Off":
        return
    phrase = voice_phrase(str(voice_key))
    if not phrase:
        return
    button_style = "border:0;border-radius:999px;background:#0a4c99;color:white;padding:8px 14px;font-weight:800;cursor:pointer"
    if mode in NEURAL_VOICE_IDS:
        base_rate, base_pitch = NEURAL_VOICE_PROFILES.get(mode, ("+0%", "+0Hz"))
        rate_n = int(base_rate.replace("%", "")) + int(st.session_state.get("voice_rate", 0) or 0)
        pitch_n = int(base_pitch.replace("Hz", "")) + int(st.session_state.get("voice_pitch", 0) or 0)
        data, err = neural_tts_bytes(phrase, NEURAL_VOICE_IDS[mode], f"{rate_n:+d}%", f"{pitch_n:+d}Hz")
        st.session_state.voice_backend_error = err
        if data:
            st.session_state.voice_backend_status = f"Neural voice active · {NEURAL_VOICE_IDS[mode]}"
            uri = _bytes_audio_uri(data)
            components.html(
                f"<div style='text-align:center;margin-top:4px'><button onclick=\"document.getElementById('v').play()\" style='{button_style}'>🔊 Test neural mascot</button><audio id='v'><source src='{uri}' type='audio/mpeg'></audio></div>",
                height=48,
            )
        else:
            st.session_state.voice_backend_status = "Neural voice unavailable · no robotic fallback used"
            st.caption("Neural voice could not be generated. The app will stay silent rather than secretly switching to a robotic device voice.")
    elif mode == "Device voice (offline)":
        st.session_state.voice_backend_error = None
        st.session_state.voice_backend_status = "Device voice selected · quality depends on this phone/browser"
        components.html(
            "<div style='text-align:center;margin-top:4px'><button onclick=\"window.kmSpeak&&window.kmSpeak()\" style='" + button_style + "'>🔊 Test device voice</button>" + _tts_script(phrase, autoplay=False, volume=float(st.session_state.get('voice_volume', 90))/100.0) + "</div>",
            height=48,
        )
    elif mode == "Cute bloops":
        st.session_state.voice_backend_error = None
        st.session_state.voice_backend_status = "Cute bloops selected"
        bloop = audio_uri(str(SOUND_DIR / "bloop.wav"))
        if bloop:
            components.html(f"<div style='text-align:center;margin-top:4px'><button onclick=\"document.getElementById('v').play()\" style='{button_style}'>🐾 Test mascot bloop</button><audio id='v'><source src='{bloop}' type='audio/wav'></audio></div>", height=48)


def render_mascot_image(asset: Path, compact: bool = False, header: bool = False):
    uri = image_uri(str(asset))
    if not uri:
        return
    cls = "km-mascot-frame" + (" compact" if compact else "") + (" header" if header else "")
    st.markdown(f"<div class='{cls}'><img src='{uri}' alt='Karimen cat mascot'></div>", unsafe_allow_html=True)


# ---------- Mascot ----------
def outfit_key(category: str) -> str:
    c = (category or "").lower()
    if "exam" in c or "simulation" in c:
        return "exam"
    if "signal" in c or "sign" in c:
        return "signals"
    if "parking" in c or "stopping" in c:
        return "parking"
    if "pedestrian" in c or "crossing" in c:
        return "pedestrian"
    if "railroad" in c:
        return "railroad"
    if any(x in c for x in ["speed", "overtaking", "hill", "curve", "lane", "road position"]):
        return "speed"
    if any(x in c for x in ["hazard", "operation", "starting", "fitness", "emergenc"]):
        return "night"
    if any(x in c for x in ["legal", "licens"]):
        return "legal"
    return "signals"


def category_asset(category: str) -> Path:
    path = MASCOT_DIR / f"category_{outfit_key(category)}.png"
    return path if path.exists() else FALLBACK_MASCOT


def reaction_asset(state: str) -> Path:
    mapping = {
        "idle": "reaction_idle.png",
        "correct": "reaction_correct.png",
        "streak": "reaction_streak.png",
        "wrong": "reaction_wrong.png",
        "double_wrong": "reaction_double_wrong.png",
        "pleading": "reaction_pleading.png",
        "comeback": "reaction_comeback.png",
        "victory": "reaction_victory.png",
    }
    path = MASCOT_DIR / mapping.get(state, "reaction_idle.png")
    return path if path.exists() else category_asset(st.session_state.mascot_category)


def mascot_message(state: str, category: str, combo: int = 0, wrong_chain: int = 0) -> str:
    focus = {
        "Traffic signals": "Watch the signal wording carefully.",
        "Signs & road markings": "Read the shape, color, and road marking together.",
        "Pedestrians & crossings": "Pedestrian protection comes first.",
        "Parking & stopping": "Check the place, distance, and exception words.",
        "Intersections & turns": "Picture who has priority before answering.",
        "Speed & braking": "Separate safe technique from the legal limit.",
        "Railroad crossings": "Think stop, look, and confirm the crossing is safe.",
    }.get(category, "Picture the road situation and read every word.")
    if state == "correct":
        return random.choice(["Correct! Nice one.", "Yes! You read that rule well.", "Great answer. Keep moving!"])
    if state == "streak":
        return f"{combo} in a row! You're on fire!"
    if state == "wrong":
        return "Almost. Slow down and lock in the exact rule."
    if state == "pleading":
        return "Please get the next one right! Read every word for me."
    if state == "double_wrong":
        return "Please... one careful answer. We can break this losing streak."
    if state == "comeback":
        return "That's it! Great comeback! Keep going!"
    if state == "victory":
        return "Mission cleared! You did it!"
    return focus


def state_voice(state: str) -> str:
    return {
        "idle": "focus",
        "correct": "correct",
        "streak": "streak",
        "wrong": "wrong",
        "pleading": "pleading",
        "double_wrong": "pleading",
        "comeback": "comeback",
        "victory": "victory",
    }.get(state, "ready")


def set_mascot_state(state: str, category: str, combo: int = 0, wrong_chain: int = 0, speak: bool = True):
    st.session_state.mascot_state = state
    st.session_state.mascot_category = category
    if speak:
        st.session_state.pending_voice = state_voice(state)
    return mascot_message(state, category, combo, wrong_chain)


def render_mascot_panel(category: str, state: str | None = None, message: str | None = None, compact: bool = False):
    state = state or st.session_state.mascot_state
    message = message or mascot_message(state, category)
    main_asset = category_asset(category) if state == "idle" else reaction_asset(state)
    uniform_asset = category_asset(category)
    labels = {"idle": "Ready", "correct": "Correct", "streak": "On Fire", "wrong": "Almost", "pleading": "Please!", "double_wrong": "Losing Streak", "comeback": "Comeback", "victory": "Victory"}
    st.markdown("<div class='km-mascot'>", unsafe_allow_html=True)
    render_mascot_image(main_asset, compact=compact)
    st.markdown(f"<span class='km-state'>🐾 {html.escape(labels.get(state, 'Ready'))}</span><div class='km-speech'>{html.escape(message)}</div>", unsafe_allow_html=True)
    if state != "idle":
        img_uri = "data:image/png;base64," + base64.b64encode(uniform_asset.read_bytes()).decode("ascii") if uniform_asset.exists() else ""
        st.markdown(f"<div class='km-uniform'><img src='{img_uri}'><div><b>Category uniform</b><span>{html.escape(outfit_key(category).title())} outfit · same gray-and-white cat</span></div></div>", unsafe_allow_html=True)
    if not compact and st.session_state.get("opt_voice", True) and st.session_state.get("voice_mode") != "Off":
        speak_key = f"mascot_speak_{st.session_state.get('route','Home')}_{state}_{outfit_key(category)}"
        if st.button("🔊 Hear mascot", use_container_width=True, key=speak_key):
            queue_media(voice=state_voice(state))
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


# ---------- Shared Supabase rankings ----------
def _secret(name: str) -> str:
    try:
        value = st.secrets[name]
        if value:
            return str(value).strip()
    except Exception:
        pass
    return str(os.getenv(name, "") or "").strip()


def _supabase_key() -> tuple[str, str]:
    for name in ("SUPABASE_SECRET_KEY", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_KEY"):
        value = _secret(name)
        if value:
            return value, name
    return "", ""


def supabase_key_role() -> str:
    key, source = _supabase_key()
    if not key:
        return "missing"
    if key.startswith("sb_secret_"):
        return "secret"
    if key.startswith("sb_publishable_"):
        return "publishable"
    # Legacy Supabase JWT keys include the role in their payload.
    if key.count(".") == 2:
        try:
            payload = key.split(".")[1]
            payload += "=" * (-len(payload) % 4)
            data = json.loads(base64.urlsafe_b64decode(payload.encode("ascii")).decode("utf-8"))
            role = str(data.get("role") or "").strip().lower()
            if role:
                return role
        except Exception:
            pass
    return f"unknown:{source or 'key'}"


@st.cache_resource(show_spinner=False)
def supabase_client():
    if create_client is None:
        return None
    url = _secret("SUPABASE_URL")
    key, _ = _supabase_key()
    if not url or not key:
        return None
    try:
        return create_client(url, key)
    except Exception:
        return None


def online_enabled() -> bool:
    return supabase_client() is not None


def _ranking_probe_payload(session_id: str) -> dict:
    return {
        "session_id": session_id,
        "display_name": "__karimen_healthcheck__",
        "avatar": "🐾",
        "bank": "All",
        "set_label": "healthcheck",
        "total_questions": 1,
        "answered": 0,
        "correct": 0,
        "started_at": utc_now_iso(),
        "last_seen": utc_now_iso(),
        "status": "diagnostic",
    }


def ranking_connection_state(force: bool = False) -> tuple[bool, str]:
    """Verify both read *and write* access, not merely client creation.

    RLS with an anon/publishable key can make SELECT return an empty result without
    raising, which previously produced a false green "connected" state. This probe
    performs a temporary upsert and delete so the ranking status reflects reality.
    """
    cached = st.session_state.get("ranking_diagnostic")
    if cached and not force and time.time() - float(cached.get("checked_at", 0)) < 300:
        return bool(cached.get("ok")), str(cached.get("message") or "")

    def finish(ok: bool, message: str) -> tuple[bool, str]:
        st.session_state.ranking_diagnostic = {"ok": ok, "message": message, "checked_at": time.time(), "role": supabase_key_role()}
        return ok, message

    if create_client is None:
        return finish(False, "The supabase Python package is not installed.")
    if not _secret("SUPABASE_URL"):
        return finish(False, "SUPABASE_URL is missing from Streamlit Secrets.")
    key, source = _supabase_key()
    if not key:
        return finish(False, "SUPABASE_SECRET_KEY or SUPABASE_SERVICE_ROLE_KEY is missing from Streamlit Secrets.")

    role = supabase_key_role()
    if role in {"anon", "publishable"}:
        return finish(
            False,
            f"{source} is an anon/publishable key. The ranking tables use RLS, so use the Supabase secret/service-role key in Streamlit Secrets instead.",
        )

    db = supabase_client()
    if db is None:
        return finish(False, "The Supabase client could not be created. Check the URL and key.")

    probe_id = f"health-{st.session_state.guest_code}-{uuid.uuid4().hex[:8]}"
    try:
        db.table("exam_results").select("session_id").limit(1).execute()
        db.table("live_exams").select("session_id").limit(1).execute()
        db.table("live_exams").upsert(_ranking_probe_payload(probe_id), on_conflict="session_id").execute()
        try:
            db.table("live_exams").delete().eq("session_id", probe_id).execute()
        except Exception:
            # A diagnostic row is harmless because status='diagnostic' is never shown.
            pass
        st.session_state.online_error = None
        return finish(True, f"Connected with {source} ({role}) and verified ranking write access.")
    except Exception as exc:
        st.session_state.online_error = str(exc)
        return finish(False, f"Supabase client exists, but ranking read/write verification failed: {exc}")


def sync_live_exam(exam: dict, status: str = "active") -> bool:
    db = supabase_client()
    if db is None or not exam:
        st.session_state.online_error = "Supabase client is unavailable."
        return False
    try:
        answered = len(exam.get("answers", {}))
        correct = sum(
            1 for qid, ans in exam.get("answers", {}).items()
            if qid in BY_ID and bool(ans) == bool(BY_ID[qid]["answer"])
        )
        payload = {
            "session_id": exam["session_id"],
            "display_name": safe_player_name(),
            "avatar": st.session_state.avatar,
            "bank": exam.get("bank", effective_bank("All")),
            "set_label": str(exam.get("set", "All")),
            "total_questions": len(exam.get("ids", [])),
            "answered": answered,
            "correct": correct,
            "started_at": exam.get("started_iso") or utc_now_iso(),
            "last_seen": utc_now_iso(),
            "status": status,
        }
        db.table("live_exams").upsert(payload, on_conflict="session_id").execute()
        st.session_state.online_error = None
        return True
    except Exception as exc:
        st.session_state.online_error = str(exc)
        return False


def save_online_result(exam: dict) -> bool:
    db = supabase_client()
    if db is None or exam.get("online_saved"):
        return bool(exam and exam.get("online_saved"))
    try:
        total = len(exam["ids"])
        correct = int(exam.get("correct", 0))
        pct = round(100 * correct / max(1, total), 1)
        sync_live_exam(exam, "finished")
        db.table("exam_results").upsert({
            "session_id": exam["session_id"],
            "display_name": safe_player_name(),
            "avatar": st.session_state.avatar,
            "bank": exam.get("bank", effective_bank("All")),
            "set_label": str(exam.get("set", "All")),
            "score": correct,
            "total_questions": total,
            "percent": pct,
            "elapsed_seconds": round(float(exam.get("elapsed", 0.0)), 1),
            "passed": pct >= PASS_PERCENT,
            "completed_at": utc_now_iso(),
        }, on_conflict="session_id").execute()
        exam["online_saved"] = True
        st.session_state.online_error = None
        return True
    except Exception as exc:
        st.session_state.online_error = str(exc)
        return False


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
        st.session_state.online_error = None
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
            .select("display_name,avatar,bank,set_label,score,total_questions,percent,elapsed_seconds,passed,completed_at,session_id")
            .order("completed_at", desc=True)
            .limit(limit)
            .execute()
        )
        st.session_state.online_error = None
        return list(res.data or [])
    except Exception as exc:
        st.session_state.online_error = str(exc)
        return []


@st.fragment(run_every="15s")
def exam_heartbeat():
    exam = st.session_state.get("exam")
    if exam and not exam.get("submitted"):
        sync_live_exam(exam, "active")


@st.fragment(run_every="15s")
def live_rankings_fragment(bank_filter: str = "All"):
    live = fetch_live_exams()
    if bank_filter != "All":
        live = [r for r in live if str(r.get("bank") or "All") == bank_filter]
    if not live:
        st.caption("No active examiners in the last 5 minutes.")
        if st.session_state.get("online_error"):
            st.caption(f"Ranking refresh error: {st.session_state.online_error}")
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
        rows.append({"#": i, "Examiner": f"{r.get('avatar') or '🚙'} {r.get('display_name') or 'Driver'}", "Live score": f"{correct}/{total}", "Progress": f"{answered}/{total}", "Elapsed": elapsed, "Bank": r.get("bank") or "All"})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.caption("Live room refreshes every 15 seconds.")


def build_best_leaderboard(results: list[dict]) -> pd.DataFrame:
    valid = [r for r in results if int(r.get("total_questions") or 0) == 50]
    best: dict[tuple[str, str, str], dict] = {}
    for r in valid:
        key = (str(r.get("display_name") or "Driver"), str(r.get("avatar") or "🚙"), str(r.get("bank") or "All"))
        score = int(r.get("score") or 0)
        elapsed = float(r.get("elapsed_seconds") or 999999)
        prev = best.get(key)
        if prev is None or score > int(prev.get("score") or 0) or (score == int(prev.get("score") or 0) and elapsed < float(prev.get("elapsed_seconds") or 999999)):
            best[key] = r
    ordered = sorted(best.values(), key=lambda r: (-int(r.get("score") or 0), float(r.get("elapsed_seconds") or 999999), str(r.get("display_name") or "")))
    rows = []
    for i, r in enumerate(ordered[:100], 1):
        elapsed = int(float(r.get("elapsed_seconds") or 0))
        rows.append({"Rank": i, "Examiner": f"{r.get('avatar') or '🚙'} {r.get('display_name') or 'Driver'}", "Best": f"{int(r.get('score') or 0)}/50", "Accuracy": f"{float(r.get('percent') or 0):.1f}%", "Time": f"{elapsed//60}:{elapsed%60:02d}", "Bank": r.get("bank") or "All", "Result": "PASS" if r.get("passed") else "REVIEW"})
    return pd.DataFrame(rows)


# ---------- Routing ----------
def go(route: str, clear_game: bool = False):
    st.session_state.route = route
    st.session_state.sync_nav = True
    if clear_game:
        st.session_state.active_game = None


def header():
    level, _, _ = level_info()
    c1, c2 = st.columns([5.5, 1.1])
    with c1:
        scope = BANK_SCOPE_LABELS.get(active_bank_scope(), "A1 + B1")
        total = len(active_questions())
        st.markdown(f"<div class='km-top'><div class='km-logo'>🐾 KARIMEN REVIEWER</div><div class='km-tag'>Practice • Learn • Master • Pass</div><div class='km-hud'><span>{html.escape(st.session_state.avatar)} {html.escape(safe_player_name())}</span><span>📚 {html.escape(scope)}</span><span>⭐ Level {level}</span><span>🪙 {total_xp():,} XP</span><span>🔥 Daily {daily_challenge_streak()}</span><span>📘 {unique_seen_count()}/{total}</span></div></div>", unsafe_allow_html=True)
    with c2:
        state = st.session_state.mascot_state
        asset = category_asset(st.session_state.mascot_category) if state == "idle" else reaction_asset(state)
        render_mascot_image(asset, header=True)

    nav_options = ["Home", "Play", "Mistakes", "Progress", "Rankings", "Bank"]
    if st.session_state.sync_nav or st.session_state.nav_choice not in nav_options:
        st.session_state.nav_choice = st.session_state.route if st.session_state.route in nav_options else "Home"
        st.session_state.sync_nav = False
    choice = st.radio("Navigation", nav_options, horizontal=True, key="nav_choice", label_visibility="collapsed")
    if choice != st.session_state.route:
        # Preserve an active review/exam while browsing another page. Returning
        # to Play resumes it instead of silently orphaning the run.
        st.session_state.route = choice

    with st.expander("⚙️ Settings", expanded=False):
        st.markdown(f"**Player:** {st.session_state.avatar} {html.escape(safe_player_name())}  \n**Question scope:** {BANK_SCOPE_LABELS.get(active_bank_scope(), 'A1 + B1')}")
        c1, c2, c3 = st.columns(3)
        c1.checkbox("Sound effects", key="opt_sound")
        c2.checkbox("Mascot voice", key="opt_voice")
        c3.checkbox("Phone vibration", key="opt_haptics")
        c1, c2 = st.columns(2)
        c1.checkbox("Show Japanese text", key="opt_japanese")
        c2.selectbox("Theme", ["Arcade", "Cute", "Night"], key="opt_theme")
        selected_voice = st.selectbox(
            "Mascot voice style", VOICE_MODES, key="voice_mode", disabled=not st.session_state.opt_voice,
            help="Online neural voices are preferred. If neural generation fails, v4.4 does not secretly switch to a robotic device voice; choose Device voice explicitly if you want offline speech.",
        )
        if st.session_state.opt_voice and selected_voice in NEURAL_VOICE_IDS:
            v1, v2 = st.columns(2)
            v1.slider("Voice speed", min_value=-5, max_value=5, step=1, key="voice_rate", help="Small adjustments only; 0 is most natural.")
            v2.slider("Voice pitch", min_value=-3, max_value=3, step=1, key="voice_pitch", help="Small adjustments only; 0 is most natural.")
        if st.session_state.opt_voice:
            v1, v2 = st.columns(2)
            v1.slider("Mascot voice volume", min_value=20, max_value=100, step=5, key="voice_volume")
            v2.slider("Effect volume", min_value=0, max_value=100, step=5, key="fx_volume", disabled=not st.session_state.opt_sound)
            if st.button("🔊 Test selected voice", use_container_width=True, key="settings_test_voice"):
                queue_media(voice="ready")
                st.rerun()
            status = st.session_state.get("voice_backend_status") or "Not tested yet"
            css = "km-voice-warn" if "unavailable" in status.lower() or "device" in status.lower() else "km-voice-ok"
            st.markdown(f"<div class='{css}'>Voice: {html.escape(status)}</div>", unsafe_allow_html=True)
            if st.session_state.get("voice_backend_error"):
                st.caption(st.session_state.voice_backend_error)
            st.caption("If automatic speech is silent on mobile, tap Hear mascot or Test selected voice once. Browsers can block audio autoplay until the page has received a user interaction.")
        pending = resumable_game()
        if pending:
            st.caption("Finish or discard the active run before changing player or bank scope. This prevents accidental loss of an unfinished exam/review.")
        if st.button("Change player / character / A1-B1 scope", use_container_width=True, key="change_profile", disabled=bool(pending)):
            st.session_state.profile_ready = False
            st.session_state.active_game = None
            st.rerun()


def render_toast():
    ach = st.session_state.achievement_toast
    if ach:
        st.session_state.achievement_toast = None
        st.markdown(f"<div class='km-toast'>{ach['icon']} Achievement unlocked: <strong>{html.escape(ach['name'])}</strong> · {html.escape(ach['desc'])}</div>", unsafe_allow_html=True)


# ---------- UI helpers ----------
def render_mode_card(title: str, subtitle: str, icon: str, cls: str):
    st.markdown(f"<div class='km-mode {cls}'><div style='font-size:1.7rem'>{icon}</div><h3>{html.escape(title)}</h3><p>{html.escape(subtitle)}</p></div>", unsafe_allow_html=True)


def render_sources(q: dict):
    sources = q.get("sources") or []
    if not sources:
        return
    with st.expander("Official / verification sources", expanded=False):
        for src in sources:
            org = src.get("organization") or "Source"
            title = src.get("title") or "Reference"
            section = src.get("section") or ""
            url = src.get("url") or ""
            if url:
                st.markdown(f"- [{org} — {title}]({url})" + (f" · {section}" if section else ""))
            else:
                st.write(f"- {org} — {title}" + (f" · {section}" if section else ""))


def render_contained_image(path: Path, alt: str = "Question illustration"):
    uri = image_uri(str(path))
    if not uri:
        st.warning(f"Missing image: {path.name}")
        return
    st.markdown(
        f"<div class='km-qimage'><img src='{uri}' alt='{html.escape(alt)}' loading='lazy'></div>",
        unsafe_allow_html=True,
    )


def render_question(q: dict, position: int, total: int, reveal: bool = False, selected=None):
    st.session_state.mascot_category = q["category"]
    diff = max(1, min(3, int(q.get("difficulty") or 1)))
    stars = "★" * diff + "☆" * (3 - diff)
    qtext = html.escape(q["question_en"]).replace("\n", "<br>")
    ja = html.escape(q.get("question_ja", "")).replace("\n", "<br>")
    st.markdown(f"<div class='km-question'><div class='km-qhead'><span class='km-cat'>🚦 {html.escape(q['category'])}</span><span class='km-diff'>{stars}</span><span><b>Q{position}/{total}</b></span></div><div class='km-qid'>{html.escape(q['id'])} · {html.escape(bank_label(q))}</div><div class='km-qtext'>{qtext}</div>{f'<div class=\"km-ja\">{ja}</div>' if st.session_state.opt_japanese and ja else ''}</div>", unsafe_allow_html=True)
    for img in q.get("images", []):
        path = QUESTION_ASSET_ROOT / img
        if path.exists():
            render_contained_image(path, f"Illustration for {q['id']}")
        else:
            st.warning(f"Missing question image: {img}")
    if reveal:
        ok = selected is not None and bool(selected) == bool(q["answer"])
        correct_text = "TRUE" if q["answer"] else "FALSE"
        cls = "km-feedback-good" if ok else "km-feedback-bad"
        st.markdown(f"<div class='km-card {cls}'><strong>{'✅ Correct' if ok else '❌ Incorrect'}</strong> · Correct answer: <strong>{correct_text}</strong><div class='km-exp'>{html.escape(q['explanation'])}</div></div>", unsafe_allow_html=True)
        render_sources(q)


def game_hud(review: dict):
    combo = int(review.get("combo", 0))
    correct = int(review.get("correct", 0))
    answered = int(review.get("answered", 0))
    lives = review.get("lives")
    accuracy = round(100 * correct / max(1, answered)) if answered else 0
    life_text = "❤️" * max(0, int(lives)) if lives is not None else "∞"
    st.markdown(f"<div class='km-gamehud'><div><b>🔥 {combo}</b><span>STREAK</span></div><div><b>⭐ {correct * 10}</b><span>RUN XP</span></div><div><b>{accuracy}%</b><span>ACCURACY</span></div><div><b>{life_text}</b><span>{'LIVES' if lives is not None else 'PRACTICE'}</span></div></div>", unsafe_allow_html=True)


def question_dots(review: dict):
    total = len(review.get("ids", []))
    idx = int(review.get("index", 0))
    if total > 20:
        return
    dots = []
    for i in range(total):
        cls = "done" if i < idx else "now" if i == idx else ""
        dots.append(f"<span class='km-dot {cls}'>{i + 1}</span>")
    st.markdown("<div class='km-dotline'>" + "".join(dots) + "</div>", unsafe_allow_html=True)


def world_html() -> str:
    seen = unique_seen_count()
    total = max(1, len(active_questions()))
    milestones = [0.0, 0.08, 0.20, 0.35, 0.55, 0.75]
    names = [("🏫", "Driving School"), ("🏙️", "City Roads"), ("🚦", "Intersections"), ("🛣️", "Highway"), ("🌙", "Night Driving"), ("🏁", "Final Exam")]
    stages = [(icon, name, min(total, int(round(total * frac)))) for (icon, name), frac in zip(names, milestones)]
    parts = []
    for i, (icon, name, req) in enumerate(stages):
        unlocked = seen >= req
        next_req = stages[i + 1][2] if i + 1 < len(stages) else total
        frac = max(0, min(1, (seen - req) / max(1, next_req - req))) if unlocked else 0
        nstars = max(1, min(3, 1 + int(frac * 3))) if unlocked else 0
        stars = "★" * nstars + "☆" * (3 - nstars) if unlocked else "🔒"
        req_text = "Unlocked" if unlocked else f"See {req} questions"
        parts.append(f"<div class='km-stage {'locked' if not unlocked else ''}'><div class='km-stage-icon'>{icon}</div><div class='km-stage-name'>{name}</div><div class='km-stage-stars'>{stars}</div><div class='km-stage-req'>{req_text}</div></div>")
    return "".join(parts)


# ---------- Review game ----------
def start_review(ids: list[str], label: str, kind: str = "review", bank: str = "All", lives: int | None = None, target: int = 0) -> bool:
    ids = [qid for qid in ids if qid in BY_ID]
    if not ids:
        return False
    st.session_state.review = {
        "ids": ids, "index": 0, "correct": 0, "answered": 0, "started": time.time(), "label": label,
        "kind": kind, "bank": effective_bank(bank), "combo": 0, "max_combo": 0, "wrong_chain": 0, "lives": lives,
        "target": target, "finished": False, "session_saved": False,
        "missed_ids": [], "skipped": 0, "retry_counts": {},
    }
    st.session_state.review_feedback = None
    st.session_state.review_started_at = time.time()
    st.session_state.active_game = "review"
    st.session_state.mascot_state = "idle"
    queue_media("start", "ready")
    go("Play")
    return True


def launch_smart():
    return start_review(select_question_ids(active_questions(), st.session_state.progress, "Due / adaptive", 20), "Smart Review", bank=effective_bank("All"))


def launch_daily():
    replay = daily_completed_today()
    kind = "daily_replay" if replay else "daily"
    label = "Daily Challenge Replay" if replay else "Today's Daily Challenge"
    ids = daily_question_ids(active_questions(), today_jst(), 10)
    return start_review(ids, label, kind=kind, bank=effective_bank("All"), target=90)


def launch_survival():
    ids = select_question_ids(active_questions(), st.session_state.progress, "Due / adaptive", 50)
    return start_review(ids, "Survival Mode", kind="survival", bank=effective_bank("All"), lives=3)


def launch_boss():
    ids = select_question_ids(active_questions(), st.session_state.progress, "Weakest", 20)
    return start_review(ids, "Boss Exam", kind="boss", bank=effective_bank("All"), target=90)


def launch_mistakes():
    ids = select_question_ids(active_questions(), st.session_state.progress, "Wrong answers", 20)
    return start_review(ids, "Mistake Hunt", kind="review", bank=effective_bank("All"))


def launch_bookmarks():
    ids = active_bookmarks()
    if not ids:
        return False
    # Most recently bookmarked rules appear first.
    return start_review(list(reversed(ids))[:30], "Saved Rules", kind="review", bank=effective_bank("All"))


def launch_image_drill():
    pool = [q for q in active_questions() if q.get("images")]
    ids = select_question_ids(pool, st.session_state.progress, "Due / adaptive", 20)
    return start_review(ids, "Image Drill", kind="review", bank=effective_bank("All"))


def launch_guessed():
    ids = select_question_ids(active_questions(), st.session_state.progress, "Guessed", 20)
    return start_review(ids, "Guess Check", kind="review", bank=effective_bank("All"))


def skip_review_current() -> bool:
    review = st.session_state.get("review")
    if not review or st.session_state.get("review_feedback") is not None:
        return False
    ids = review.get("ids", [])
    idx = int(review.get("index", 0))
    if idx >= len(ids) - 1:
        return False
    qid = ids.pop(idx)
    ids.append(qid)
    review["skipped"] = int(review.get("skipped", 0)) + 1
    st.session_state.review_started_at = time.time()
    st.session_state.mascot_state = "idle"
    return True


def finish_review(review: dict):
    if review.get("session_saved"):
        return
    answered = int(review.get("answered", 0))
    if answered <= 0:
        review["session_saved"] = True
        return
    used = review["ids"][:answered]
    kind = review.get("kind", "review")
    session_mode = {"daily": "daily", "daily_replay": "daily_replay", "survival": "survival", "boss": "boss"}.get(kind, "review")
    row = add_session(
        st.session_state.progress, session_mode, used, int(review.get("correct", 0)), time.time() - float(review.get("started", time.time())), review.get("bank", "All"),
        max_combo=int(review.get("max_combo", 0)), lives_left=review.get("lives"),
    )
    review["session_saved"] = True
    pct = float(row.get("percent") or 0)
    success = kind not in {"boss"} or pct >= 90
    set_mascot_state("victory" if success else "pleading", st.session_state.mascot_category, speak=True)
    queue_media("complete" if success else "retry", "victory" if success else "pleading")
    check_new_achievements()


def answer_review(q: dict, choice: bool):
    review = st.session_state.review
    if not review or st.session_state.review_feedback is not None:
        return
    elapsed = time.time() - st.session_state.review_started_at
    ok = bool(choice) == bool(q["answer"])
    record_answer(st.session_state.progress, q["id"], ok, elapsed)
    review["answered"] = int(review.get("answered", 0)) + 1
    review["correct"] = int(review.get("correct", 0)) + int(ok)
    prev_wrong = int(review.get("wrong_chain", 0))
    if ok:
        review["combo"] = int(review.get("combo", 0)) + 1
        review["max_combo"] = max(int(review.get("max_combo", 0)), int(review["combo"]))
        review["wrong_chain"] = 0
        if prev_wrong >= 2:
            state = "comeback"
        elif int(review["combo"]) >= 3:
            state = "streak"
        else:
            state = "correct"
        fx = "combo" if int(review["combo"]) in {3, 5, 10, 15, 20} else "correct"
    else:
        review["combo"] = 0
        review["wrong_chain"] = prev_wrong + 1
        if q["id"] not in review.setdefault("missed_ids", []):
            review["missed_ids"].append(q["id"])
        if review.get("lives") is not None:
            review["lives"] = max(0, int(review["lives"]) - 1)
        state = "double_wrong" if int(review["wrong_chain"]) >= 3 else "pleading" if int(review["wrong_chain"]) >= 2 else "wrong"
        fx = "wrong"
    retry_queued = False
    # In ordinary learning modes, one missed rule is inserted a few questions
    # later for immediate retrieval practice. Daily/Survival/Boss keep their
    # fixed challenge structure unchanged.
    if (not ok) and review.get("kind", "review") == "review":
        retry_counts = review.setdefault("retry_counts", {})
        used = int(retry_counts.get(q["id"], 0) or 0)
        if used < 1:
            insert_at = min(len(review["ids"]), int(review.get("index", 0)) + 4)
            review["ids"].insert(insert_at, q["id"])
            retry_counts[q["id"]] = used + 1
            retry_queued = True
    message = set_mascot_state(state, q["category"], int(review.get("combo", 0)), int(review.get("wrong_chain", 0)), speak=False)
    queue_media(fx, state_voice(state))
    st.session_state.review_feedback = {"selected": bool(choice), "ok": ok, "state": state, "message": message, "confidence": None, "retry_queued": retry_queued}
    if review.get("kind") == "survival" and int(review.get("lives", 1)) <= 0:
        review["finished"] = True
        finish_review(review)
    check_new_achievements()


def render_review_summary(review: dict):
    answered = max(1, int(review.get("answered", 0)))
    correct = int(review.get("correct", 0))
    pct = 100 * correct / answered
    kind = review.get("kind", "review")
    if kind == "survival":
        title = "SURVIVAL RUN OVER"
        subtitle = f"You reached {answered} questions."
    elif kind in {"daily", "daily_replay"}:
        title = "DAILY CHALLENGE CLEAR"
        subtitle = f"{correct}/{answered} correct · current daily streak {daily_challenge_streak()} day(s)."
    elif kind == "boss":
        title = "BOSS DEFEATED!" if pct >= 90 else "BOSS ESCAPED"
        subtitle = "90% target cleared." if pct >= 90 else "Train the weak spots and challenge it again."
    else:
        title = "STAGE CLEAR"
        subtitle = "Your adaptive queue has been updated."
    st.markdown(f"<div class='km-result'><div style='font-size:2rem'>{'🏆' if pct >= 90 else '⭐'}</div><div class='km-result-score'>{pct:.0f}%</div><div class='km-result-title'>{title}</div><div>{html.escape(subtitle)}</div></div>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Correct", f"{correct}/{answered}")
    c2.metric("Best streak", f"{int(review.get('max_combo', 0))}x")
    c3.metric("Run XP", correct * 10 + (answered - correct) * 2)
    c4.metric("Mode", kind.replace("_", " ").title())
    state = "victory" if (kind != "boss" or pct >= 90) else "pleading"
    render_mascot_panel(st.session_state.mascot_category, state, mascot_message(state, st.session_state.mascot_category))
    c1, c2, c3 = st.columns(3)
    if c1.button("🎮 Choose another mode", use_container_width=True, type="primary", key="review_summary_modes"):
        st.session_state.review = None
        st.session_state.review_feedback = None
        st.session_state.active_game = None
        go("Play")
        st.rerun()
    missed = [qid for qid in review.get("missed_ids", []) if qid in BY_ID]
    if c2.button("🔁 Retry this run's misses", use_container_width=True, disabled=not missed, key="review_summary_retry_run"):
        if start_review(missed, "Retry This Run", kind="review", bank=review.get("bank", "All")):
            st.rerun()
    if c3.button("🎯 Train all mistakes", use_container_width=True, key="review_summary_mistakes"):
        if launch_mistakes():
            st.rerun()
        else:
            st.info("No saved mistakes yet.")


def page_review():
    review = st.session_state.review
    if not review:
        st.session_state.active_game = None
        page_play()
        return
    if review.get("finished"):
        finish_review(review)
        render_review_summary(review)
        return
    ids = review.get("ids", [])
    idx = int(review.get("index", 0))
    if idx >= len(ids):
        review["finished"] = True
        finish_review(review)
        render_review_summary(review)
        return
    q = BY_ID[ids[idx]]
    game_hud(review)
    question_dots(review)
    feedback = st.session_state.review_feedback
    main, side = st.columns([3.4, 1.25], gap="medium")
    with main:
        st.progress((idx + 1) / max(1, len(ids)), text=f"{review.get('label', 'Review')} · Question {idx + 1}/{len(ids)}")
        bookmarked = is_bookmarked(st.session_state.progress, q["id"])
        t1, t2, t3 = st.columns(3)
        if t1.button("★ Saved" if bookmarked else "☆ Save rule", use_container_width=True, key=f"review_bookmark_{q['id']}_{idx}"):
            toggle_bookmark(st.session_state.progress, q["id"])
            check_new_achievements()
            st.rerun()
        if t2.button("↪ Skip for later", use_container_width=True, disabled=feedback is not None or idx >= len(ids) - 1, key=f"review_skip_{q['id']}_{idx}"):
            if skip_review_current():
                st.rerun()
        t3.caption(f"Skipped this run: {int(review.get('skipped', 0))}")

        render_question(q, idx + 1, len(ids), reveal=feedback is not None, selected=feedback.get("selected") if feedback else None)
        if feedback is None:
            c1, c2 = st.columns(2)
            if c1.button("⭕ TRUE", use_container_width=True, type="primary", key=f"review_true_{q['id']}_{idx}"):
                answer_review(q, True)
                st.rerun()
            if c2.button("❌ FALSE", use_container_width=True, key=f"review_false_{q['id']}_{idx}"):
                answer_review(q, False)
                st.rerun()
        else:
            if feedback.get("confidence") is None:
                st.markdown("<div class='km-confidence'><strong>How sure were you?</strong><br><span class='km-small'>This does not change your score. It helps find lucky guesses and confident misconceptions.</span></div>", unsafe_allow_html=True)
                c1, c2 = st.columns(2)
                sure_label = "🧠 I knew it" if feedback.get("ok") else "😬 I was sure"
                if c1.button(sure_label, use_container_width=True, key=f"confidence_sure_{q['id']}_{idx}"):
                    record_confidence(st.session_state.progress, q["id"], False, bool(feedback.get("ok")))
                    st.session_state.review_feedback["confidence"] = "sure"
                    st.rerun()
                if c2.button("🎲 I guessed", use_container_width=True, key=f"confidence_guess_{q['id']}_{idx}"):
                    record_confidence(st.session_state.progress, q["id"], True, bool(feedback.get("ok")))
                    st.session_state.review_feedback["confidence"] = "guess"
                    st.rerun()
            else:
                label = "Marked as guessed" if feedback.get("confidence") == "guess" else "Confidence recorded"
                st.caption(f"✓ {label}")
            if feedback.get("retry_queued"):
                st.info("🔁 This missed rule has been queued once more later in this run so you can retrieve it again from memory.")
            if st.button("Next question ➜", use_container_width=True, type="primary", key=f"review_next_{q['id']}_{idx}"):
                if idx + 1 >= len(ids):
                    review["finished"] = True
                    finish_review(review)
                else:
                    review["index"] = idx + 1
                    st.session_state.review_started_at = time.time()
                    st.session_state.mascot_state = "idle"
                st.session_state.review_feedback = None
                st.rerun()
        with st.expander("Learning status for this question", expanded=False):
            s = qstat(q["id"])
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Attempts", int(s.get("attempts", 0)))
            c2.metric("Accuracy", f"{100 * int(s.get('correct', 0)) / max(1, int(s.get('attempts', 0))):.0f}%" if int(s.get("attempts", 0)) else "—")
            c3.metric("Mastery", f"{mastery(s):.0f}%")
            c4.metric("Guessed", int(s.get("confidence_guessed", 0) or 0))
            if int(s.get("confidence_sure_wrong", 0) or 0) > 0:
                st.warning(f"You were confident but wrong {int(s.get('confidence_sure_wrong', 0))} time(s) on this rule. Prioritize it for review.")
    with side:
        state = feedback.get("state") if feedback else "idle"
        message = feedback.get("message") if feedback else mascot_message("idle", q["category"])
        render_mascot_panel(q["category"], state, message)
    if st.button("← Leave this run", use_container_width=True, key="leave_review_run"):
        st.session_state.review = None
        st.session_state.review_feedback = None
        st.session_state.active_game = None
        go("Play")
        st.rerun()


# ---------- Exam ----------
def start_exam(bank: str = "All", set_filter: str = "All", count: int = 50, minutes: int = 30) -> bool:
    pool = filter_questions(bank, set_filter)
    if not pool:
        return False
    count = max(1, min(int(count), len(pool)))
    ids = [q["id"] for q in random.sample(pool, count)]
    now = time.time()
    st.session_state.exam = {
        "ids": ids, "index": 0, "answers": {}, "flagged": [], "started": now, "started_iso": utc_now_iso(),
        "deadline": now + int(minutes) * 60, "minutes": int(minutes), "bank": effective_bank(bank), "set": set_filter,
        "submitted": False, "session_id": uuid.uuid4().hex, "online_saved": False, "celebrated": False,
    }
    st.session_state.active_game = "exam"
    queue_media("start", "ready")
    sync_live_exam(st.session_state.exam)
    go("Play")
    return True


def submit_exam():
    exam = st.session_state.exam
    if not exam or exam.get("submitted"):
        return
    correct = 0
    per_q_seconds = float(exam.get("minutes", 30)) * 60 / max(1, len(exam["ids"]))
    for qid in exam["ids"]:
        ans = exam["answers"].get(qid)
        ok = ans is not None and bool(ans) == bool(BY_ID[qid]["answer"])
        correct += int(ok)
        record_answer(st.session_state.progress, qid, ok, per_q_seconds)
    elapsed = max(0.0, time.time() - float(exam["started"]))
    exam["correct"] = correct
    exam["elapsed"] = elapsed
    exam["submitted"] = True
    row = add_session(st.session_state.progress, "exam", exam["ids"], correct, elapsed, exam.get("bank", "All"))
    save_online_result(exam)
    passed = float(row.get("percent") or 0) >= PASS_PERCENT
    set_mascot_state("victory" if passed else "pleading", "Simulation / Exam", speak=False)
    queue_media("pass" if passed else "retry", "victory" if passed else "pleading")
    check_new_achievements()


def timer_widget(deadline: float):
    deadline_ms = int(deadline * 1000)
    components.html(f"""
<div id="timer" style="font-family:system-ui;font-weight:900;font-size:18px;color:#274a78;text-align:right;padding:3px"></div>
<script>const end={deadline_ms};function tick(){{const s=Math.max(0,Math.floor((end-Date.now())/1000));const m=Math.floor(s/60),r=s%60;document.getElementById('timer').innerText='⏱ '+String(m).padStart(2,'0')+':'+String(r).padStart(2,'0');}}tick();setInterval(tick,500);</script>
""", height=35)


def render_exam_results(exam: dict):
    if online_enabled() and not exam.get("online_saved"):
        save_online_result(exam)
    total = len(exam["ids"])
    correct = int(exam.get("correct", 0))
    pct = 100 * correct / max(1, total)
    passed = pct >= PASS_PERCENT
    st.markdown(f"<div class='km-result'><div style='font-size:2rem'>{'🏆' if passed else '🛠️'}</div><div class='km-result-score'>{pct:.0f}%</div><div class='km-result-title'>{'MISSION CLEARED!' if passed else 'TRAINING COMPLETE'}</div><div>{'Practice threshold passed.' if passed else 'Review the misses and run it again.'}</div></div>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Score", f"{correct}/{total}")
    c2.metric("Accuracy", f"{pct:.1f}%")
    c3.metric("Target", f"{PASS_PERCENT:.0f}%")
    c4.metric("Time", f"{int(exam.get('elapsed', 0)) // 60}:{int(exam.get('elapsed', 0)) % 60:02d}")
    render_mascot_panel("Simulation / Exam", "victory" if passed else "pleading")
    if passed and total == 50 and not exam.get("celebrated"):
        st.balloons()
        exam["celebrated"] = True
    misses = []
    for pos, qid in enumerate(exam["ids"], 1):
        q = BY_ID[qid]
        ans = exam["answers"].get(qid)
        if ans is None or bool(ans) != bool(q["answer"]):
            misses.append((pos, q, ans))
    st.markdown(f"<div class='km-section'>Missed / unanswered ({len(misses)})</div>", unsafe_allow_html=True)
    if not misses:
        st.success("Perfect score.")
    for pos, q, ans in misses:
        with st.expander(f"Q{pos} · {q['id']} · {q['category']}"):
            st.write(q["question_en"])
            if st.session_state.opt_japanese and q.get("question_ja"):
                st.caption(q["question_ja"])
            st.write(f"Your answer: {'TRUE' if ans is True else 'FALSE' if ans is False else 'Unanswered'}")
            st.write(f"Correct answer: {'TRUE' if q['answer'] else 'FALSE'}")
            st.write(q["explanation"])
            render_sources(q)
    c1, c2, c3 = st.columns(3)
    if c1.button("New exam", use_container_width=True, type="primary", key="exam_new_result"):
        st.session_state.exam = None
        st.session_state.active_game = None
        go("Play")
        st.rerun()
    if c2.button("Review misses", use_container_width=True, disabled=not misses, key="exam_review_misses"):
        if start_review([q["id"] for _, q, _ in misses], "Exam Mistakes"):
            st.rerun()
    if c3.button("View rankings", use_container_width=True, key="exam_rankings"):
        st.session_state.active_game = None
        go("Rankings")
        st.rerun()


def page_exam():
    exam = st.session_state.exam
    if not exam:
        st.session_state.active_game = None
        page_play()
        return
    if exam.get("submitted"):
        render_exam_results(exam)
        return
    if time.time() >= float(exam["deadline"]):
        submit_exam()
        st.warning("Time expired. The exam was submitted automatically.")
        st.rerun()
    exam_heartbeat()
    ids = exam["ids"]
    idx = int(exam["index"])
    q = BY_ID[ids[idx]]
    c1, c2 = st.columns([4, 1.25])
    c1.progress((idx + 1) / max(1, len(ids)), text=f"Exam · Question {idx + 1}/{len(ids)} · Answered {len(exam['answers'])}/{len(ids)}")
    with c2:
        timer_widget(float(exam["deadline"]))
    render_question(q, idx + 1, len(ids), reveal=False)
    current = exam["answers"].get(q["id"])
    c1, c2 = st.columns(2)
    if c1.button("⭕ TRUE" + (" ✓" if current is True else ""), use_container_width=True, type="primary", key=f"exam_true_{q['id']}"):
        exam["answers"][q["id"]] = True
        sync_live_exam(exam)
        st.rerun()
    if c2.button("❌ FALSE" + (" ✓" if current is False else ""), use_container_width=True, key=f"exam_false_{q['id']}"):
        exam["answers"][q["id"]] = False
        sync_live_exam(exam)
        st.rerun()
    flagged = q["id"] in exam["flagged"]
    flag = st.checkbox("🚩 Flag for later review", value=flagged, key=f"flag_{exam['session_id']}_{q['id']}")
    if flag and not flagged:
        exam["flagged"].append(q["id"])
    elif not flag and flagged:
        exam["flagged"].remove(q["id"])
    c1, c2 = st.columns(2)
    if c1.button("← Previous", use_container_width=True, disabled=idx == 0, key=f"exam_prev_{idx}"):
        exam["index"] = idx - 1
        st.rerun()
    if c2.button("Next →", use_container_width=True, disabled=idx >= len(ids) - 1, key=f"exam_next_{idx}"):
        exam["index"] = idx + 1
        st.rerun()
    jump = st.selectbox("Jump to question", list(range(1, len(ids) + 1)), index=idx, key=f"exam_jump_{exam['session_id']}_{idx}")
    if int(jump) - 1 != idx:
        exam["index"] = int(jump) - 1
        st.rerun()
    with st.expander("Exam status"):
        unanswered = [i + 1 for i, qid in enumerate(ids) if qid not in exam["answers"]]
        flagged_n = [i + 1 for i, qid in enumerate(ids) if qid in exam["flagged"]]
        st.write(f"Unanswered: {', '.join(map(str, unanswered)) if unanswered else 'None'}")
        st.write(f"Flagged: {', '.join(map(str, flagged_n)) if flagged_n else 'None'}")
    unanswered_count = len(ids) - len(exam["answers"])
    allow_submit = True
    if unanswered_count:
        allow_submit = st.checkbox(f"Submit with {unanswered_count} unanswered question(s)", value=False, key=f"submit_confirm_{exam['session_id']}")
    if st.button("Submit exam", use_container_width=True, type="primary", disabled=bool(unanswered_count and not allow_submit), key=f"submit_exam_{exam['session_id']}"):
        submit_exam()
        st.rerun()
    if st.button("← Leave exam without submitting", use_container_width=True, key=f"leave_exam_{exam['session_id']}"):
        sync_live_exam(exam, "abandoned")
        st.session_state.exam = None
        st.session_state.active_game = None
        go("Play")
        st.rerun()


# ---------- Pages ----------
def resumable_game() -> tuple[str, str] | None:
    review = st.session_state.get("review")
    exam = st.session_state.get("exam")
    if review and not review.get("finished"):
        return "review", str(review.get("label") or "Review run")
    if exam and not exam.get("submitted"):
        return "exam", f"Exam · {len(exam.get('answers', {}))}/{len(exam.get('ids', []))} answered"
    return None


def resume_game(kind: str):
    st.session_state.active_game = kind
    go("Play")


def page_home():
    level, xp, goal = level_info()
    seen = unique_seen_count()
    st.markdown(f"<div class='km-profile'><div class='km-profile-name'>{html.escape(st.session_state.avatar)} {html.escape(safe_player_name())}</div><div class='km-profile-sub'>Level {level} · {driver_title(level)}</div><div class='km-xp'><i style='width:{100 * xp / goal:.1f}%'></i></div><div style='font-size:.8rem;font-weight:750'>{xp}/{goal} XP to next level · Total XP {total_xp():,}</div><div class='km-chips'><div class='km-chip'>🔥 Daily {daily_challenge_streak()}</div><div class='km-chip'>🏆 Best exam {best_exam_percent():.0f}%</div><div class='km-chip'>📘 {seen}/{len(active_questions())} seen</div><div class='km-chip'>⭐ {bookmark_count()} saved</div></div></div>", unsafe_allow_html=True)
    pending = resumable_game()
    if pending:
        kind, label = pending
        st.markdown(f"<div class='km-resume'>⏯️ Active run saved: {html.escape(label)}. Browsing other pages will not erase it.</div>", unsafe_allow_html=True)
        if st.button("Continue active run", use_container_width=True, type="primary", key="home_resume_active"):
            resume_game(kind)
            st.rerun()
        st.caption("Finish or discard the active run before starting another game. Progress and Rankings remain safe to browse from the navigation bar.")
        return
    rec_title, rec_text, rec_mode = coach_recommendation()
    st.markdown(f"<div class='km-coach'><b>🐾 Mochi recommends: {html.escape(rec_title)}</b><span>{html.escape(rec_text)}</span></div>", unsafe_allow_html=True)
    if st.button(f"Start {rec_title}", use_container_width=True, key="home_coach_recommendation"):
        launchers = {"daily": launch_daily, "mistakes": launch_mistakes, "bookmarks": launch_bookmarks, "review": launch_smart, "exam": start_exam, "boss": launch_boss}
        fn = launchers.get(rec_mode)
        if fn and fn():
            st.rerun()
        else:
            st.info("That recommendation is not available yet; Smart Review is always a safe fallback.")
    st.markdown("<div class='km-section'>Today's mission</div>", unsafe_allow_html=True)
    c1, c2 = st.columns([2.3, 1])
    with c1:
        done = daily_completed_today()
        st.markdown(f"<div class='km-mode km-purple'><div style='font-size:1.7rem'>📅</div><h3>Daily Challenge</h3><p>10 fixed questions for today, including image questions. {'Already completed — replay is available without another daily bonus.' if done else '+30 XP completion bonus and daily streak credit.'}</p></div>", unsafe_allow_html=True)
        if st.button("Replay today's challenge" if done else "Start today's challenge", use_container_width=True, type="primary", key="home_daily"):
            if launch_daily():
                st.rerun()
    with c2:
        render_mascot_panel("General rules", "correct" if done else "idle", "Great work today!" if done else "Ten questions today. Let's do this!", compact=True)
    st.markdown("<div class='km-section'>Your journey</div>", unsafe_allow_html=True)
    st.markdown("<div class='km-world'>" + world_html() + "</div>", unsafe_allow_html=True)
    st.markdown("<div class='km-section'>Quick play</div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        render_mode_card("Smart Review", "Adaptive queue prioritizes due, weak, and unseen rules.", "🧠", "km-blue")
        if st.button("Start Smart Review", use_container_width=True, type="primary", key="home_smart"):
            if launch_smart():
                st.rerun()
    with c2:
        render_mode_card("Exam Mode", "50 questions, 30 minutes, 90% practice target.", "🏁", "km-green")
        if st.button("Start 50Q Exam", use_container_width=True, key="home_exam"):
            if start_exam():
                st.rerun()
    with c3:
        render_mode_card("Survival", "Three lives. How far can you go before all hearts are gone?", "⚡", "km-orange")
        if st.button("Start Survival", use_container_width=True, key="home_survival"):
            if launch_survival():
                st.rerun()
    weak = weak_categories(4)
    st.markdown("<div class='km-section'>Weak topics</div>", unsafe_allow_html=True)
    if weak:
        rows = []
        for r in weak:
            score = max(0, min(100, r["mastery"]))
            rows.append(f"<div class='km-weak'><b>{html.escape(r['category'])}</b><div class='km-bar'><i style='width:{score:.1f}%'></i></div><span>{score:.0f}%</span></div>")
        st.markdown("<div class='km-card'>" + "".join(rows) + "</div>", unsafe_allow_html=True)
        if st.button("🎯 Review saved mistakes", use_container_width=True, key="home_weak"):
            if launch_mistakes():
                st.rerun()
            else:
                st.info("No saved mistakes yet. Smart Review will build your weak-topic data.")
    else:
        st.info("Weak-topic data appears after you answer some questions.")
    backup_panel()


def page_play():
    if st.session_state.active_game == "review" and st.session_state.review:
        page_review()
        return
    if st.session_state.active_game == "exam" and st.session_state.exam:
        page_exam()
        return
    pending = resumable_game()
    if pending:
        kind, label = pending
        st.markdown(f"<div class='km-resume'>⏯️ You still have an unfinished {html.escape(label)}.</div>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        if c1.button("Resume run", use_container_width=True, type="primary", key="play_resume_pending"):
            resume_game(kind)
            st.rerun()
        if c2.button("Discard run", use_container_width=True, key="play_discard_pending"):
            if kind == "exam" and st.session_state.exam:
                sync_live_exam(st.session_state.exam, "abandoned")
                st.session_state.exam = None
            elif kind == "review":
                st.session_state.review = None
                st.session_state.review_feedback = None
            st.session_state.active_game = None
            st.rerun()
        return
    st.session_state.active_game = None
    st.markdown("<div class='km-section'>Choose game mode</div>", unsafe_allow_html=True)
    level, _, _ = level_info()
    boss_unlocked = level >= 5 or unique_seen_count() >= 100
    modes = [
        ("📘", "Review Mode", "Learn with explanations and adaptive repetition.", "review", "km-blue"),
        ("📝", "Exam Mode", "Full 50-question simulation with timer and flags.", "exam", "km-green"),
        ("📅", "Daily Challenge", "Ten fixed questions per day. Build a streak.", "daily", "km-purple"),
        ("⚡", "Survival Mode", "Three lives. Every wrong answer costs a heart.", "survival", "km-orange"),
        ("👑", "Boss Exam", "Twenty of your hardest questions. Target 90%.", "boss", "km-pink"),
        ("🎯", "Mistake Hunt", "Train only questions you have actually missed.", "mistakes", "km-cyan"),
        ("⭐", "Saved Rules", "Practice questions you bookmarked for later.", "bookmarks", "km-purple"),
        ("🖼️", "Image Drill", "Adaptive practice using only questions with road images.", "images", "km-blue"),
        ("🎲", "Guess Check", "Revisit rules you marked as guesses, even when you got them right.", "guessed", "km-orange"),
    ]
    cols = st.columns(2)
    for i, (icon, title, sub, key, cls) in enumerate(modes):
        with cols[i % 2]:
            render_mode_card(title, sub, icon, cls)
            disabled = key == "boss" and not boss_unlocked
            label = "🔒 Unlock at Level 5 / 100 seen" if disabled else f"Play {title}"
            if st.button(label, use_container_width=True, disabled=disabled, key=f"play_{key}", type="primary" if key in {"review", "daily"} else "secondary"):
                ok = False
                if key == "review":
                    ok = launch_smart()
                elif key == "exam":
                    ok = start_exam()
                elif key == "daily":
                    ok = launch_daily()
                elif key == "survival":
                    ok = launch_survival()
                elif key == "boss":
                    ok = launch_boss()
                elif key == "mistakes":
                    ok = launch_mistakes()
                elif key == "bookmarks":
                    ok = launch_bookmarks()
                elif key == "images":
                    ok = launch_image_drill()
                elif key == "guessed":
                    ok = launch_guessed()
                if ok:
                    st.rerun()
                else:
                    st.warning("That mode has no eligible questions yet.")
    with st.expander("🛠️ Custom review mission", expanded=False):
        c1, c2 = st.columns(2)
        bank = c1.selectbox("Bank", available_bank_options(), key="custom_bank")
        set_filter = c2.selectbox("Set", set_options_for_bank(bank), key="custom_set")
        pool0 = filter_questions(bank, set_filter)
        categories = ["All"] + sorted({q["category"] for q in pool0})
        category = st.selectbox("Category", categories, key="custom_category")
        c1, c2 = st.columns(2)
        strategy = c1.selectbox("Strategy", ["Due / adaptive", "Wrong answers", "Guessed", "Unseen", "Weakest", "Random"], key="custom_strategy")
        count = c2.slider("Questions", 5, 100, 20, 5, key="custom_count")
        pool = filter_questions(bank, set_filter, category)
        st.caption(f"{len(pool)} questions match these filters.")
        if st.button("Launch custom mission", use_container_width=True, type="primary", disabled=not pool, key="custom_launch"):
            ids = select_question_ids(pool, st.session_state.progress, strategy, count)
            if start_review(ids, f"{strategy} · {category}", bank=bank):
                st.rerun()
            else:
                st.warning("No questions currently match that strategy. Try another strategy.")
    with st.expander("🛠️ Custom exam", expanded=False):
        c1, c2 = st.columns(2)
        bank = c1.selectbox("Exam bank", available_bank_options(), key="exam_custom_bank")
        set_filter = c2.selectbox("Exam set", set_options_for_bank(bank), key="exam_custom_set")
        pool = filter_questions(bank, set_filter)
        c1, c2 = st.columns(2)
        max_count = max(1, min(100, len(pool)))
        min_count = 5 if max_count >= 5 else 1
        default_count = min(50, max_count)
        count = c1.number_input("Questions", min_value=min_count, max_value=max_count, value=max(min_count, default_count), step=5 if max_count >= 5 else 1, key="exam_custom_count")
        minutes = c2.number_input("Minutes", min_value=5, max_value=120, value=30, step=5, key="exam_custom_minutes")
        if st.button("Launch custom exam", use_container_width=True, disabled=not pool, key="exam_custom_launch"):
            if start_exam(bank, set_filter, int(count), int(minutes)):
                st.rerun()


def page_mistakes():
    wrong = [(q, qstat(q["id"])) for q in active_questions() if int(qstat(q["id"]).get("wrong", 0) or 0) > 0]
    wrong.sort(key=lambda x: (mastery(x[1]), -int(x[1].get("wrong", 0))))
    st.markdown("<div class='km-section'>📕 My Mistake Book</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='km-card'><strong>{len(wrong)} questions</strong> have been missed at least once.<br><span class='km-small'>Only real mistakes appear here; the app no longer substitutes random questions when the list is empty.</span></div>", unsafe_allow_html=True)
    if not wrong:
        render_mascot_panel("General rules", "correct", "No saved mistakes yet. Start a review or exam first.")
        return
    cats = ["All"] + sorted({q["category"] for q, _ in wrong})
    cat = st.selectbox("Filter category", cats, key="mistake_filter")
    shown = [x for x in wrong if cat == "All" or x[0]["category"] == cat]
    if st.button("🎯 Train top mistakes", use_container_width=True, type="primary", key="mistake_train"):
        if start_review([q["id"] for q, _ in shown[:20]], "Mistake Book Training"):
            st.rerun()
    for q, s in shown[:50]:
        acc = 100 * int(s.get("correct", 0)) / max(1, int(s.get("attempts", 0)))
        with st.expander(f"{q['id']} · {q['category']} · {int(s.get('wrong', 0))} miss(es) · {acc:.0f}%"):
            st.write(q["question_en"])
            for img in q.get("images", []):
                path = ROOT / img
                if path.exists():
                    render_contained_image(path, f"Illustration for {q['id']}")
            st.success(f"Correct answer: {'TRUE' if q['answer'] else 'FALSE'}")
            st.write(q["explanation"])
            render_sources(q)


def page_progress():
    level, xp, goal = level_info()
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Level", level)
    c2.metric("Total XP", f"{total_xp():,}")
    c3.metric("Questions seen", f"{unique_seen_count()}/{len(active_questions())}")
    c4.metric("Saved rules", bookmark_count())
    c5.metric("Pass readiness", f"{pass_readiness():.0f}%")
    st.caption("Pass readiness is an in-app study estimate based on recent mock exams, category mastery, and bank coverage. It is not an official probability.")
    scoped_stats = [qstat(q["id"]) for q in active_questions()]
    guessed = sum(int(x.get("confidence_guessed", 0) or 0) for x in scoped_stats)
    lucky = sum(int(x.get("confidence_guess_correct", 0) or 0) for x in scoped_stats)
    sure_wrong = sum(int(x.get("confidence_sure_wrong", 0) or 0) for x in scoped_stats)
    if guessed or sure_wrong:
        a, b, c = st.columns(3)
        a.metric("Answers marked guessed", guessed)
        b.metric("Correct guesses", lucky)
        c.metric("Confident misses", sure_wrong)
        if sure_wrong:
            st.warning("Confident misses are especially important: you believed the wrong rule. Use Guessed/Weakest review and your Mistake Book to correct these first.")
    st.markdown("<div class='km-section'>World progress</div>", unsafe_allow_html=True)
    st.markdown("<div class='km-world'>" + world_html() + "</div>", unsafe_allow_html=True)
    rows = category_rows()
    df = pd.DataFrame(rows).sort_values(["mastery", "attempts"], ascending=[True, False])
    st.markdown("<div class='km-section'>Category performance</div>", unsafe_allow_html=True)
    if not df.empty:
        show = df[["category", "seen", "count", "attempts", "accuracy", "mastery"]].copy()
        show["accuracy"] = show["accuracy"].round(1)
        show["mastery"] = show["mastery"].round(1)
        st.dataframe(show, use_container_width=True, hide_index=True)
        chart = show.set_index("category")[["mastery"]].sort_values("mastery", ascending=False)
        st.bar_chart(chart, height=280, width="stretch")
    sessions = [x for x in st.session_state.progress.get("sessions", []) if session_matches_scope(x)]
    if sessions:
        trend = pd.DataFrame(sessions[-30:]).copy()
        if "percent" in trend.columns:
            trend["Run"] = range(max(1, len(sessions) - len(trend) + 1), len(sessions) + 1)
            trend["Accuracy %"] = pd.to_numeric(trend["percent"], errors="coerce")
            trend = trend.dropna(subset=["Accuracy %"]).set_index("Run")[["Accuracy %"]]
            if not trend.empty:
                st.markdown("<div class='km-section'>Recent accuracy trend</div>", unsafe_allow_html=True)
                st.line_chart(trend, height=260, width="stretch")
    st.markdown("<div class='km-section'>Achievements</div>", unsafe_allow_html=True)
    cards = []
    for a in achievement_catalog():
        cards.append(f"<div class='{'locked' if not a['earned'] else ''}'><div style='font-size:1.5rem'>{a['icon']}</div><strong>{html.escape(a['name'])}</strong><div class='km-small'>{html.escape(a['desc'])}</div></div>")
    st.markdown("<div class='km-ach'>" + "".join(cards) + "</div>", unsafe_allow_html=True)
    sessions = [x for x in st.session_state.progress.get("sessions", []) if session_matches_scope(x)]
    if sessions:
        st.markdown("<div class='km-section'>Recent sessions</div>", unsafe_allow_html=True)
        recent = pd.DataFrame(sessions[-20:][::-1])
        cols = [c for c in ["timestamp", "mode", "questions", "correct", "percent", "seconds", "max_combo"] if c in recent.columns]
        st.dataframe(recent[cols], use_container_width=True, hide_index=True)
    backup_panel()


def local_rankings_df() -> pd.DataFrame:
    rows = [s for s in st.session_state.progress.get("sessions", []) if s.get("mode") == "exam" and int(s.get("questions", 0)) == 50 and session_matches_scope(s)]
    data = []
    for s in rows:
        data.append({"Driver": f"{st.session_state.avatar} {safe_player_name()}", "Score": f"{int(s.get('correct', 0))}/50", "Percent": float(s.get("percent", 0)), "Seconds": float(s.get("seconds", 0)), "Completed": s.get("timestamp", "")})
    if not data:
        return pd.DataFrame(columns=["Driver", "Score", "Percent", "Seconds", "Completed"])
    return pd.DataFrame(data).sort_values(["Percent", "Seconds"], ascending=[False, True])


def page_rankings():
    st.markdown("<div class='km-section'>🏆 Live Rankings</div>", unsafe_allow_html=True)
    connected, message = ranking_connection_state()
    role = supabase_key_role()
    c1, c2 = st.columns([3, 1])
    with c1:
        if connected:
            st.success("🟢 Supabase ranking connected and write-tested")
            st.caption(message)
        else:
            st.error("Shared ranking is not ready.")
            st.caption(message)
    with c2:
        if st.button("🔄 Re-test connection", use_container_width=True, key="ranking_retest"):
            try:
                supabase_client.clear()
            except Exception:
                pass
            st.session_state.ranking_diagnostic = None
            st.session_state.online_error = None
            ranking_connection_state(force=True)
            st.rerun()

    if not connected:
        st.markdown(
            "<div class='km-card'><strong>Required Streamlit Secrets</strong><br>"
            "<code>SUPABASE_URL</code><br><code>SUPABASE_SECRET_KEY</code> or <code>SUPABASE_SERVICE_ROLE_KEY</code><br><br>"
            "Do not use the anon/publishable key with the included RLS setup. Run <code>supabase_setup.sql</code> in the same Supabase project, then restart the Streamlit app.</div>",
            unsafe_allow_html=True,
        )
        st.caption(f"Detected key role: {role}")
        if st.session_state.online_error:
            with st.expander("Connection error details"):
                st.code(st.session_state.online_error)
        local = local_rankings_df()
        if not local.empty:
            st.markdown("#### This device's 50-question results")
            st.dataframe(local, use_container_width=True, hide_index=True)
        return

    rank_options = available_bank_options()
    bank_filter = st.selectbox("Ranking bank", rank_options, key="ranking_bank_filter", help="Rankings are most comparable within the same question bank.")
    st.caption("Active exams are shown for five minutes after their last heartbeat. Live data refreshes every 15 seconds.")
    live_rankings_fragment(bank_filter)

    st.markdown("#### All-time best 50-question exams")
    results = fetch_exam_results(500)
    if bank_filter != "All":
        results = [r for r in results if str(r.get("bank") or "All") == bank_filter]
    board = build_best_leaderboard(results)
    if board.empty:
        st.info("No completed 50-question exams have been submitted yet.")
    else:
        top3 = board.head(3).to_dict("records")
        if top3:
            cols = st.columns(len(top3))
            medals = ["🥇", "🥈", "🥉"]
            for i, (col, row) in enumerate(zip(cols, top3)):
                with col:
                    st.markdown(f"<div class='km-card' style='text-align:center'><div style='font-size:2rem'>{medals[i]}</div><strong>{html.escape(str(row['Examiner']))}</strong><div style='font-size:1.45rem;font-weight:950'>{html.escape(str(row['Best']))}</div><span class='km-small'>{html.escape(str(row['Time']))} · {html.escape(str(row['Accuracy']))} · {html.escape(str(row['Bank']))}</span></div>", unsafe_allow_html=True)
        st.dataframe(board, use_container_width=True, hide_index=True)
        my_exact = f"{st.session_state.avatar} {safe_player_name()}"
        mine = board[board["Examiner"] == my_exact]
        if not mine.empty:
            row = mine.iloc[0]
            st.info(f"Your current best rank: #{int(row['Rank'])} · {row['Best']} · {row['Time']} · {row['Bank']}")

    if results:
        st.markdown("#### Recent finishes")
        recent = []
        for r in results[:20]:
            elapsed = int(float(r.get("elapsed_seconds") or 0))
            recent.append({"Examiner": f"{r.get('avatar') or '🚙'} {r.get('display_name') or 'Driver'}", "Score": f"{int(r.get('score') or 0)}/{int(r.get('total_questions') or 0)}", "Accuracy": f"{float(r.get('percent') or 0):.1f}%", "Time": f"{elapsed//60}:{elapsed%60:02d}", "Bank": r.get("bank") or "All"})
        st.dataframe(pd.DataFrame(recent), use_container_width=True, hide_index=True)

    if st.session_state.online_error:
        with st.expander("Connection details"):
            st.code(st.session_state.online_error)

def page_bank():
    st.markdown("<div class='km-section'>📚 Question Bank</div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    bank = c1.selectbox("Bank", available_bank_options(), key="bank_page_bank")
    set_filter = c2.selectbox("Set", set_options_for_bank(bank), key="bank_page_set")
    pool0 = filter_questions(bank, set_filter)
    cats = ["All"] + sorted({q["category"] for q in pool0})
    category = st.selectbox("Category", cats, key="bank_page_category")
    pool = filter_questions(bank, set_filter, category)
    saved_only = st.checkbox("Show bookmarked rules only", value=False, key="bank_saved_only")
    if saved_only:
        saved = set(active_bookmarks())
        pool = [q for q in pool if q["id"] in saved]
    st.caption(f"{len(pool)} questions")
    if not pool:
        st.info("No questions match this filter yet.")
        return
    labels = [f"{q['id']} · {q['category']} · {q['question_en'][:80]}" for q in pool]
    label = st.selectbox("Select question", labels, key="bank_page_question")
    q = pool[labels.index(label)]
    saved = is_bookmarked(st.session_state.progress, q["id"])
    if st.button("★ Remove bookmark" if saved else "☆ Bookmark this rule", use_container_width=True, key=f"bank_bookmark_{q['id']}"):
        toggle_bookmark(st.session_state.progress, q["id"])
        check_new_achievements()
        st.rerun()
    render_question(q, 1, 1, reveal=True, selected=q["answer"])
    s = qstat(q["id"])
    c1, c2, c3 = st.columns(3)
    c1.metric("Attempts", int(s.get("attempts", 0)))
    c2.metric("Wrong", int(s.get("wrong", 0)))
    c3.metric("Mastery", f"{mastery(s):.0f}%")


def backup_panel():
    with st.expander("💾 Progress backup / restore", expanded=False):
        st.download_button("Download progress", data=progress_json(), file_name="karimen_progress_v44.json", mime="application/json", use_container_width=True, key="download_progress")
        uploaded = st.file_uploader("Import progress JSON", type=["json"], key="progress_upload")
        if uploaded is not None:
            raw = uploaded.getvalue()
            marker = hash(raw)
            if st.session_state.last_import_hash != marker:
                try:
                    st.session_state.progress = normalize_progress(json.loads(raw.decode("utf-8")), VALID_IDS)
                    st.session_state.last_import_hash = marker
                    prime_achievements()
                    st.success("Progress imported successfully.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Could not import progress: {exc}")


# ---------- First-screen player setup ----------
def page_profile_setup():
    st.markdown("<div class='km-profile-setup'><h1>🐾 KARIMEN REVIEWER</h1><p>Choose your driver profile before entering the game.</p></div>", unsafe_allow_html=True)
    left, right = st.columns([1, 1.5])
    with left:
        render_mascot_image(reaction_asset("idle"))
        st.markdown("<div class='km-card'><strong>Blue traffic-officer cat</strong><br><span class='km-small'>The same gray-and-white mascot changes pose and outfit as you study.</span></div>", unsafe_allow_html=True)
    with right:
        with st.form("profile_setup", clear_on_submit=False):
            name = st.text_input("Your ranking name", value=st.session_state.player_name, placeholder=f"Driver-{st.session_state.guest_code}", max_chars=24, help="This nickname is shown on the shared Supabase ranking board.")
            avatar = st.selectbox("Your player character", AVATARS, index=AVATARS.index(st.session_state.avatar) if st.session_state.avatar in AVATARS else 0, format_func=lambda x: f"{x}  {CHARACTER_NAMES.get(x, 'Driver')}")
            scope = st.radio("Question bank", ["All", "A1", "B1"], index=["All", "A1", "B1"].index(active_bank_scope()), format_func=lambda x: BANK_SCOPE_LABELS[x], horizontal=True, help="This becomes the global scope for review, exams, daily challenge, survival, mistakes, and progress statistics.")
            c1, c2 = st.columns(2)
            voice_mode = c1.selectbox("Mascot voice", VOICE_MODES, index=VOICE_MODES.index(st.session_state.get("voice_mode", "Natural neural voice (online)")) if st.session_state.get("voice_mode", "Natural neural voice (online)") in VOICE_MODES else 0)
            theme = c2.selectbox("Theme", ["Arcade", "Cute", "Night"], index=["Arcade", "Cute", "Night"].index(st.session_state.opt_theme))
            submitted = st.form_submit_button("Start driving →", use_container_width=True, type="primary")
        st.caption("Voice recommendation: Natural neural voice. It requires internet, but v4.4 will stay silent if neural TTS fails instead of secretly switching to a robotic device voice.")
        if submitted:
            cleaned = re.sub(r"[^\w .\-]", "", (name or "").strip(), flags=re.UNICODE)[:24].strip()
            if len(cleaned) < 2:
                st.error("Enter a nickname with at least 2 characters so rankings can identify your result.")
            else:
                st.session_state.player_name = cleaned
                st.session_state.avatar = avatar
                st.session_state.bank_scope = scope
                for stale_key in ["custom_bank", "custom_set", "exam_custom_bank", "exam_custom_set", "bank_page_bank", "bank_page_set", "bank_page_category", "bank_page_question", "bank_saved_only", "mistake_filter", "custom_category", "custom_strategy", "ranking_bank_filter"]:
                    st.session_state.pop(stale_key, None)
                st.session_state.voice_mode = voice_mode
                st.session_state.opt_voice = voice_mode != "Off"
                st.session_state.opt_theme = theme
                st.session_state.profile_ready = True
                st.session_state.route = "Home"
                st.session_state.nav_choice = "Home"
                st.session_state.sync_nav = False
                st.rerun()


# ---------- Main ----------
if not st.session_state.profile_ready:
    page_profile_setup()
    st.stop()

prime_achievements()
header()
play_pending_media()
render_toast()

route = st.session_state.route
if route == "Home":
    page_home()
elif route == "Play":
    page_play()
elif route == "Mistakes":
    page_mistakes()
elif route == "Progress":
    page_progress()
elif route == "Rankings":
    page_rankings()
elif route == "Bank":
    page_bank()
else:
    st.session_state.route = "Home"
    st.rerun()

st.markdown(f"<div class='km-divider'></div><div class='km-small'>Karimen Reviewer · Build {BUILD} · {len(active_questions())} active questions ({BANK_SCOPE_LABELS.get(active_bank_scope(), 'A1 + B1')}) · Study aid only</div>", unsafe_allow_html=True)
