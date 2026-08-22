from __future__ import annotations

import json
import html
import math
import random
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

ROOT = Path(__file__).resolve().parent
DATA_FILE = ROOT / "data" / "questions.json"
PROGRESS_VERSION = 2

st.set_page_config(
    page_title="Karimen Reviewer",
    page_icon="🚗",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ---------- Styling ----------
st.markdown(
    """
<style>
:root { --card-radius: 18px; }
.block-container { max-width: 860px; padding-top: 1rem; padding-bottom: 4rem; }
[data-testid="stHeader"] { background: rgba(255,255,255,0); }
.km-hero { padding: 0.25rem 0 0.65rem 0; }
.km-title { font-size: clamp(1.65rem, 7vw, 2.55rem); font-weight: 800; line-height: 1.05; margin: 0; }
.km-subtitle { opacity: .72; margin-top: .4rem; }
.km-card { border: 1px solid rgba(128,128,128,.24); border-radius: var(--card-radius); padding: 1rem 1.05rem; margin: .55rem 0; }
.km-qno { font-size: .83rem; opacity: .68; font-weight: 650; letter-spacing: .02em; }
.km-question { font-size: clamp(1.16rem, 4.3vw, 1.48rem); line-height: 1.55; font-weight: 650; margin-top: .55rem; }
.km-japanese { font-size: 1rem; line-height: 1.55; opacity: .78; margin-top: .75rem; }
.km-good { border-left: 5px solid #2e9d63; }
.km-bad { border-left: 5px solid #cf4b4b; }
.km-neutral { border-left: 5px solid #6b7280; }
.km-pill { display:inline-block; border:1px solid rgba(128,128,128,.25); border-radius:999px; padding:.2rem .55rem; margin:.1rem .15rem .1rem 0; font-size:.8rem; opacity:.82; }
.km-small { font-size: .88rem; opacity:.72; }
.km-divider { height:1px; background:rgba(128,128,128,.18); margin:1rem 0; }
div.stButton > button { min-height: 3.15rem; border-radius: 13px; font-weight: 750; font-size: 1.02rem; }
[data-testid="stMetric"] { border:1px solid rgba(128,128,128,.20); border-radius:15px; padding:.65rem .7rem; }
[data-testid="stImage"] img { border-radius: 14px; }
@media (max-width: 640px) {
  .block-container { padding-left: .85rem; padding-right: .85rem; padding-top: .65rem; }
  .km-card { padding: .9rem; border-radius: 15px; }
  div.stButton > button { min-height: 3.35rem; }
}
</style>
""",
    unsafe_allow_html=True,
)


# ---------- Data ----------
@st.cache_data(show_spinner=False)
def load_data():
    doc = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    questions = doc["questions"]
    by_id = {q["id"]: q for q in questions}
    return doc["metadata"], questions, by_id


META, QUESTIONS, BY_ID = load_data()


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


def normalize_progress(raw: dict) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("Progress file is not a JSON object.")
    out = default_progress()
    stats = raw.get("question_stats", {})
    if isinstance(stats, dict):
        for qid, s in stats.items():
            if qid not in BY_ID or not isinstance(s, dict):
                continue
            attempts = max(0, int(s.get("attempts", 0) or 0))
            correct = max(0, min(attempts, int(s.get("correct", 0) or 0)))
            total_seconds = max(0.0, float(s.get("total_seconds", 0.0) or 0.0))
            out["question_stats"][qid] = {
                "attempts": attempts,
                "correct": correct,
                "wrong": attempts - correct,
                "streak": max(0, int(s.get("streak", 0) or 0)),
                "last_seen": s.get("last_seen"),
                "last_correct": s.get("last_correct"),
                "total_seconds": total_seconds,
            }
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
        "last_import_hash": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_state()


def qstat(qid: str) -> dict:
    return st.session_state.progress["question_stats"].get(
        qid,
        {"attempts": 0, "correct": 0, "wrong": 0, "streak": 0, "last_seen": None, "last_correct": None, "total_seconds": 0.0},
    )


def mastery(stat: dict) -> float:
    """A transparent app-local mastery estimate: accuracy × exposure confidence + streak bonus."""
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


BANK_OPTIONS = ["All", "A1", "B1"]
A1_INTERNAL_BANKS = {"KM14", "KM15", "KM16"}


def bank_group(q: dict) -> str:
    """User-facing bank name while preserving stable internal IDs/data."""
    if q["bank"] in A1_INTERNAL_BANKS:
        return "A1"
    if q["bank"] == "menkyoblog":
        return "B1"
    return q["bank"]


def bank_set(q: dict) -> str:
    if q["bank"] in A1_INTERNAL_BANKS:
        return q["bank"].replace("KM", "")
    if q["bank"] == "menkyoblog":
        return str(q.get("set", ""))
    return ""


def bank_label(q: dict) -> str:
    group = bank_group(q)
    subset = bank_set(q)
    return f"{group} · Set {subset}" if subset else group


def display_question_id(q: dict) -> str:
    """Friendly public ID; the original ID remains unchanged internally for progress/images."""
    number = int(q.get("number", 0) or 0)
    if q["bank"] in A1_INTERNAL_BANKS:
        return f"A1-{bank_set(q)}-Q{number:03d}"
    if q["bank"] == "menkyoblog":
        return f"B1-{int(q.get('set', 0) or 0):02d}-Q{number:02d}"
    return q["id"]


def set_options_for_bank(bank: str) -> list[str]:
    if bank == "A1":
        return ["All", "14", "15", "16"]
    if bank == "B1":
        return ["All"] + [str(i) for i in range(1, 11)]
    return ["All"]


def display_saved_bank(value: str) -> str:
    """Translate older saved session labels without invalidating existing progress backups."""
    if value in A1_INTERNAL_BANKS or value == "A1":
        return "A1"
    if value in {"menkyoblog", "B1"}:
        return "B1"
    return value


def filter_questions(bank: str = "All", set_filter: str = "All", category: str = "All") -> list[dict]:
    qs = QUESTIONS
    if bank == "A1":
        qs = [q for q in qs if q["bank"] in A1_INTERNAL_BANKS]
    elif bank == "B1":
        qs = [q for q in qs if q["bank"] == "menkyoblog"]
    elif bank != "All":
        # Backward compatibility for old saved state / direct internal bank names.
        qs = [q for q in qs if q["bank"] == bank]

    if set_filter != "All":
        if bank == "A1":
            qs = [q for q in qs if q["bank"] == f"KM{set_filter}"]
        elif bank == "B1":
            try:
                set_no = int(set_filter)
                qs = [q for q in qs if q.get("set") == set_no]
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
        ranked = sorted(pool, key=priority_score, reverse=True)
        chosen = ranked[:count]
    return [q["id"] for q in chosen]


def render_question(q: dict, position: int, total: int, reveal: bool = False, selected=None):
    safe_bank = html.escape(bank_label(q))
    safe_cat = html.escape(q["category"])
    safe_id = html.escape(display_question_id(q))
    safe_question = html.escape(q["question_en"]).replace("\n", "<br>")
    safe_ja = html.escape(q.get("question_ja", "")).replace("\n", "<br>")
    tags = f'<span class="km-pill">{safe_bank}</span><span class="km-pill">{safe_cat}</span>'
    st.markdown(
        f'<div class="km-card"><div class="km-qno">QUESTION {position} OF {total} · {safe_id}</div>'
        f'<div>{tags}</div><div class="km-question">{safe_question}</div>'
        + (f'<div class="km-japanese">{safe_ja}</div>' if st.session_state.show_japanese and q.get("question_ja") else "")
        + '</div>',
        unsafe_allow_html=True,
    )
    for img in q.get("images", []):
        path = ROOT / img
        if path.exists():
            st.image(str(path), use_container_width=True)
    if reveal:
        is_correct = selected is not None and bool(selected) == bool(q["answer"])
        css = "km-good" if is_correct else "km-bad"
        label = "Correct" if is_correct else "Incorrect"
        answer_text = "TRUE" if q["answer"] else "FALSE"
        safe_explanation = html.escape(q["explanation"]).replace("\n", "<br>")
        st.markdown(
            f'<div class="km-card {css}"><strong>{label}</strong><br>Correct answer: <strong>{answer_text}</strong><div class="km-divider"></div>{safe_explanation}</div>',
            unsafe_allow_html=True,
        )
        render_sources(q)


def render_sources(q: dict):
    sources = q.get("sources") or []
    page = q.get("source_page")
    if not sources and not page:
        return
    with st.expander("Source / verification details"):
        if q.get("verification_status") == "verified":
            st.caption("A1 item: answer cross-checked in the verified reviewer package.")
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
        if page:
            st.markdown(f"- [Original source question page]({page})")
            st.caption("B1 items preserve the source answer and the English explanation supplied in the extracted bank.")


def progress_json() -> str:
    return json.dumps(st.session_state.progress, ensure_ascii=False, indent=2)


def header():
    st.markdown(
        '<div class="km-hero"><div class="km-title">Karimen Reviewer</div>'
        '<div class="km-subtitle">650-question mobile reviewer · review, exam simulation, adaptive practice and analytics</div></div>',
        unsafe_allow_html=True,
    )
    nav_options = ["Home", "Review", "Exam", "Statistics", "Question Bank"]
    current = st.session_state.nav if st.session_state.nav in nav_options else "Home"
    nav = st.radio("Navigation", nav_options, index=nav_options.index(current), horizontal=True, label_visibility="collapsed")
    st.session_state.nav = nav
    st.session_state.show_japanese = st.toggle("Show original Japanese where available", value=st.session_state.show_japanese)
    return nav


# ---------- Pages ----------
def page_home():
    c1, c2, c3 = st.columns(3)
    c1.metric("Questions", META["question_count"])
    c2.metric("Image questions", META["image_question_count"])
    attempted = sum(1 for qid in st.session_state.progress["question_stats"] if qstat(qid)["attempts"] > 0)
    c3.metric("Attempted", attempted)

    st.markdown("### Included banks")
    st.markdown(
        "<div class='km-card'><strong>A1</strong> · 150 questions across 3 sets (14, 15, 16)<br>"
        "<strong>B1</strong> · 500 questions across 10 sets<br><span class='km-small'>No demo/sample bank is included.</span></div>",
        unsafe_allow_html=True,
    )

    st.markdown("### Recommended today")
    stats = st.session_state.progress["question_stats"]
    due = sum(1 for q in QUESTIONS if qstat(q["id"])["attempts"] > 0 and due_now(qstat(q["id"])))
    unseen = sum(1 for q in QUESTIONS if qstat(q["id"])["attempts"] == 0)
    weak = sum(1 for q in QUESTIONS if qstat(q["id"])["attempts"] > 0 and mastery(qstat(q["id"])) < 60)
    c1, c2, c3 = st.columns(3)
    c1.metric("Due", due)
    c2.metric("Weak", weak)
    c3.metric("Unseen", unseen)

    c1, c2 = st.columns(2)
    if c1.button("Start adaptive review", use_container_width=True, type="primary"):
        pool = QUESTIONS
        ids = select_review_questions(pool, "Due / adaptive", 20)
        st.session_state.review = {"ids": ids, "index": 0, "correct": 0, "answered": 0, "started": time.time(), "mode": "Due / adaptive", "bank": "All"}
        st.session_state.review_feedback = None
        st.session_state.review_started_at = time.time()
        st.session_state.nav = "Review"
        st.rerun()
    if c2.button("Take 50-question exam", use_container_width=True):
        start_exam("All", "All", 50, 30)
        st.session_state.nav = "Exam"
        st.rerun()

    st.markdown("### Progress backup")
    st.caption("Streamlit Community Cloud should not be treated as permanent per-user storage. Download this small progress file and re-import it when you change devices or after a deployment reset.")
    c1, c2 = st.columns(2)
    c1.download_button(
        "Download progress",
        data=progress_json(),
        file_name="karimen_progress.json",
        mime="application/json",
        use_container_width=True,
    )
    uploaded = c2.file_uploader("Import progress", type=["json"], label_visibility="collapsed")
    if uploaded is not None:
        raw_bytes = uploaded.getvalue()
        marker = hash(raw_bytes)
        if st.session_state.last_import_hash != marker:
            try:
                raw = json.loads(raw_bytes.decode("utf-8"))
                st.session_state.progress = normalize_progress(raw)
                st.session_state.last_import_hash = marker
                st.success("Progress imported.")
                st.rerun()
            except Exception as exc:
                st.error(f"Could not import progress: {exc}")

    with st.expander("About the exam simulation"):
        st.write("The default simulation uses 50 true/false questions, 30 minutes, and a 90% pass threshold (45/50).")
        st.markdown(f"[Official reference: Osaka Prefectural Police]({META['exam_standard']['url']})")
        st.caption("The app is a study reviewer, not an official examination system. Question wording comes from the included study banks.")


def page_review():
    review = st.session_state.review
    if not review or review.get("finished"):
        st.markdown("### Configure review")
        c1, c2 = st.columns(2)
        bank = c1.selectbox("Bank", BANK_OPTIONS, key="review_bank")
        set_opts = set_options_for_bank(bank)
        set_filter = c2.selectbox("Set", set_opts, key="review_set")
        categories = ["All"] + sorted({q["category"] for q in filter_questions(bank, set_filter)})
        category = st.selectbox("Category", categories, key="review_category")
        c1, c2 = st.columns(2)
        mode = c1.selectbox("Review strategy", ["Due / adaptive", "Wrong answers", "Unseen", "Weakest", "Random"], key="review_mode")
        count = c2.slider("Questions", min_value=5, max_value=100, value=20, step=5)
        pool = filter_questions(bank, set_filter, category)
        st.caption(f"{len(pool)} questions match these filters.")
        if st.button("Start review", type="primary", use_container_width=True, disabled=not pool):
            ids = select_review_questions(pool, mode, count)
            st.session_state.review = {"ids": ids, "index": 0, "correct": 0, "answered": 0, "started": time.time(), "mode": mode, "bank": bank, "set": set_filter, "category": category}
            st.session_state.review_feedback = None
            st.session_state.review_started_at = time.time()
            st.rerun()
        if review and review.get("finished"):
            render_review_summary(review)
        return

    ids = review["ids"]
    idx = review["index"]
    q = BY_ID[ids[idx]]
    st.progress(idx / max(1, len(ids)), text=f"{idx + 1} / {len(ids)}")
    feedback = st.session_state.review_feedback
    render_question(q, idx + 1, len(ids), reveal=feedback is not None, selected=feedback)

    if feedback is None:
        c1, c2 = st.columns(2)
        if c1.button("○  TRUE", use_container_width=True, type="primary"):
            answer_review(q, True)
            st.rerun()
        if c2.button("×  FALSE", use_container_width=True):
            answer_review(q, False)
            st.rerun()
    else:
        if st.button("Next question", use_container_width=True, type="primary"):
            if idx + 1 >= len(ids):
                review["finished"] = True
                add_session("review", ids, review["correct"], time.time() - review["started"], review.get("bank", "All"))
            else:
                review["index"] += 1
                st.session_state.review_started_at = time.time()
            st.session_state.review_feedback = None
            st.rerun()

    with st.expander("Current learning status"):
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
    st.session_state.review_feedback = choice


def render_review_summary(review):
    total = len(review["ids"])
    correct = review["correct"]
    pct = 100 * correct / max(1, total)
    st.markdown("### Review complete")
    c1, c2, c3 = st.columns(3)
    c1.metric("Score", f"{correct}/{total}")
    c2.metric("Accuracy", f"{pct:.0f}%")
    c3.metric("Mode", review.get("mode", "Review"))
    if st.button("New review", use_container_width=True, type="primary"):
        st.session_state.review = None
        st.session_state.review_feedback = None
        st.rerun()


def start_exam(bank: str, set_filter: str, count: int, minutes: int):
    pool = filter_questions(bank, set_filter)
    count = min(count, len(pool))
    ids = [q["id"] for q in random.sample(pool, count)]
    st.session_state.exam = {
        "ids": ids,
        "index": 0,
        "answers": {},
        "flagged": [],
        "started": time.time(),
        "deadline": time.time() + minutes * 60,
        "minutes": minutes,
        "bank": bank,
        "set": set_filter,
        "submitted": False,
    }


def submit_exam():
    exam = st.session_state.exam
    if not exam or exam.get("submitted"):
        return
    correct = 0
    elapsed = time.time() - exam["started"]
    per_q = elapsed / max(1, len(exam["ids"]))
    for qid in exam["ids"]:
        selected = exam["answers"].get(qid, None)
        ok = selected is not None and bool(selected) == bool(BY_ID[qid]["answer"])
        correct += int(ok)
        record_answer(qid, ok, per_q)
    exam["correct"] = correct
    exam["submitted"] = True
    exam["submitted_at"] = time.time()
    add_session("exam", exam["ids"], correct, elapsed, exam.get("bank", "All"))


def timer_widget(deadline: float):
    remaining = max(0, int(deadline - time.time()))
    html = f"""
    <div style='font-family:system-ui;text-align:center;font-weight:800;font-size:21px;padding:7px 4px'>
      Time remaining: <span id='timer'></span>
    </div>
    <script>
      let remaining={remaining};
      function draw() {{
        let m=Math.floor(remaining/60), s=remaining%60;
        document.getElementById('timer').textContent=String(m).padStart(2,'0')+':'+String(s).padStart(2,'0');
        if (remaining>0) remaining--;
      }}
      draw(); setInterval(draw,1000);
    </script>
    """
    components.html(html, height=48)


def page_exam():
    exam = st.session_state.exam
    if not exam:
        st.markdown("### Configure exam")
        c1, c2 = st.columns(2)
        bank = c1.selectbox("Question pool", BANK_OPTIONS, key="exam_bank")
        set_opts = set_options_for_bank(bank)
        set_filter = c2.selectbox("Set", set_opts, key="exam_set")
        c1, c2 = st.columns(2)
        count = c1.selectbox("Questions", [20, 30, 50, 100], index=2)
        minutes = c2.selectbox("Time limit", [15, 20, 30, 45, 60], index=2)
        pool = filter_questions(bank, set_filter)
        st.caption(f"Pool: {len(pool)} questions. Official-style default: 50 questions / 30 minutes / 90% pass.")
        if st.button("Start exam", type="primary", use_container_width=True, disabled=len(pool) < count):
            start_exam(bank, set_filter, count, minutes)
            st.rerun()
        return

    if exam.get("submitted"):
        render_exam_results(exam)
        return

    # Any interaction after time expiry submits the exam. The visible timer itself continues client-side.
    if time.time() >= exam["deadline"]:
        submit_exam()
        st.rerun()

    ids = exam["ids"]
    idx = exam["index"]
    q = BY_ID[ids[idx]]
    timer_widget(exam["deadline"])
    answered = len(exam["answers"])
    st.progress(answered / max(1, len(ids)), text=f"Answered {answered}/{len(ids)}")
    render_question(q, idx + 1, len(ids), reveal=False)

    current = exam["answers"].get(q["id"], None)
    if current is not None:
        st.info(f"Selected answer: {'TRUE' if current else 'FALSE'}")
    c1, c2 = st.columns(2)
    if c1.button("○  TRUE", use_container_width=True, type="primary" if current is True else "secondary"):
        exam["answers"][q["id"]] = True
        st.rerun()
    if c2.button("×  FALSE", use_container_width=True, type="primary" if current is False else "secondary"):
        exam["answers"][q["id"]] = False
        st.rerun()

    flagged = q["id"] in exam["flagged"]
    flag = st.checkbox("Flag for review", value=flagged, key=f"flag_{q['id']}")
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

    with st.expander("Exam status"):
        unanswered = [i + 1 for i, qid in enumerate(ids) if qid not in exam["answers"]]
        flagged_n = [i + 1 for i, qid in enumerate(ids) if qid in exam["flagged"]]
        st.write(f"Unanswered: {', '.join(map(str, unanswered)) if unanswered else 'None'}")
        st.write(f"Flagged: {', '.join(map(str, flagged_n)) if flagged_n else 'None'}")

    unanswered_count = len(ids) - len(exam["answers"])
    confirm_unanswered = True
    if unanswered_count:
        confirm_unanswered = st.checkbox(f"Submit with {unanswered_count} unanswered question(s)", value=False)
    if st.button("Submit exam", use_container_width=True, disabled=bool(unanswered_count and not confirm_unanswered)):
        submit_exam()
        st.rerun()


def render_exam_results(exam):
    total = len(exam["ids"])
    correct = exam.get("correct", 0)
    pct = 100 * correct / max(1, total)
    pass_pct = META["exam_standard"]["pass_percent"]
    passed = pct >= pass_pct
    st.markdown("### Exam result")
    c1, c2, c3 = st.columns(3)
    c1.metric("Score", f"{correct}/{total}")
    c2.metric("Accuracy", f"{pct:.1f}%")
    c3.metric("Result", "PASS" if passed else "REVIEW")
    if total == 50:
        st.success("Passed the 90% practice threshold.") if passed else st.error("Below the 90% practice threshold. Review the missed items below.")
    else:
        st.info("Pass/review uses the same 90% threshold; only a 50-question run mirrors the standard provisional-license written-test question count.")

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

    c1, c2 = st.columns(2)
    if c1.button("New exam", use_container_width=True, type="primary"):
        st.session_state.exam = None
        st.rerun()
    if c2.button("Review missed questions", use_container_width=True, disabled=not rows):
        ids = [q["id"] for _, q, _ in rows]
        st.session_state.review = {"ids": ids, "index": 0, "correct": 0, "answered": 0, "started": time.time(), "mode": "Exam mistakes", "bank": exam.get("bank", "All")}
        st.session_state.review_feedback = None
        st.session_state.review_started_at = time.time()
        st.session_state.nav = "Review"
        st.rerun()


def page_statistics():
    stats = st.session_state.progress["question_stats"]
    sessions = st.session_state.progress["sessions"]
    attempts = sum(s.get("attempts", 0) for s in stats.values())
    correct = sum(s.get("correct", 0) for s in stats.values())
    attempted_q = sum(1 for s in stats.values() if s.get("attempts", 0) > 0)
    coverage = 100 * attempted_q / len(QUESTIONS)
    accuracy = 100 * correct / max(1, attempts) if attempts else 0

    st.markdown("### Learning dashboard")
    c1, c2, c3 = st.columns(3)
    c1.metric("Accuracy", f"{accuracy:.1f}%" if attempts else "—")
    c2.metric("Coverage", f"{coverage:.1f}%")
    c3.metric("Attempts", attempts)

    rows = []
    grouped = defaultdict(list)
    for q in QUESTIONS:
        grouped[q["category"]].append(q)
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
    chart_df = df.set_index("Category")[["Mastery %"]]
    st.bar_chart(chart_df, height=360)

    weak_rows = []
    for q in QUESTIONS:
        s = qstat(q["id"])
        if s["attempts"] <= 0:
            continue
        weak_rows.append({
            "ID": display_question_id(q), "Bank": bank_label(q), "Category": q["category"],
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
        if "bank" in sess_df.columns:
            sess_df["bank"] = sess_df["bank"].map(display_saved_bank)
        show_cols = [c for c in ["timestamp", "mode", "bank", "questions", "correct", "percent", "seconds"] if c in sess_df.columns]
        st.dataframe(sess_df[show_cols].iloc[::-1], use_container_width=True, hide_index=True)
        exams = sess_df[sess_df["mode"] == "exam"] if "mode" in sess_df else pd.DataFrame()
        if not exams.empty:
            st.line_chart(exams[["percent"]].reset_index(drop=True), height=260)

    st.markdown("### Answer pattern")
    true_correct = false_correct = true_attempts = false_attempts = 0
    for q in QUESTIONS:
        s = qstat(q["id"])
        if q["answer"]:
            true_attempts += s["attempts"]; true_correct += s["correct"]
        else:
            false_attempts += s["attempts"]; false_correct += s["correct"]
    patt = pd.DataFrame([
        {"Correct answer": "TRUE", "Attempts": true_attempts, "Accuracy %": round(100*true_correct/true_attempts, 1) if true_attempts else None},
        {"Correct answer": "FALSE", "Attempts": false_attempts, "Accuracy %": round(100*false_correct/false_attempts, 1) if false_attempts else None},
    ])
    st.dataframe(patt, use_container_width=True, hide_index=True)

    with st.expander("How Mastery is calculated"):
        st.write("Mastery is an app-local study score, not an official test metric. It combines your accuracy, number of exposures, and current correct-answer streak. New questions therefore start near 0% even if answered correctly once, then rise with repeated correct recall.")

    st.download_button("Download progress backup", progress_json(), "karimen_progress.json", "application/json", use_container_width=True)


def page_bank():
    st.markdown("### Question bank")
    c1, c2 = st.columns(2)
    bank = c1.selectbox("Bank", BANK_OPTIONS, key="browse_bank")
    set_opts = set_options_for_bank(bank)
    set_filter = c2.selectbox("Set", set_opts, key="browse_set")
    pool0 = filter_questions(bank, set_filter)
    categories = ["All"] + sorted({q["category"] for q in pool0})
    category = st.selectbox("Category", categories, key="browse_cat")
    search = st.text_input("Search", placeholder="e.g. crosswalk, parking, signal, A1-16-Q048")
    only_images = st.checkbox("Image questions only")
    pool = filter_questions(bank, set_filter, category)
    if search.strip():
        s = search.lower().strip()
        pool = [q for q in pool if s in q["id"].lower() or s in display_question_id(q).lower() or s in q["question_en"].lower() or s in q.get("question_ja", "").lower() or s in q["explanation"].lower()]
    if only_images:
        pool = [q for q in pool if q.get("images")]
    st.caption(f"{len(pool)} questions")
    if not pool:
        return
    labels = [f"{display_question_id(q)} · {bank_label(q)} · {q['question_en'][:70]}" for q in pool]
    selected_label = st.selectbox("Select question", labels)
    q = pool[labels.index(selected_label)]
    render_question(q, 1, 1, reveal=True, selected=q["answer"])
    s = qstat(q["id"])
    c1, c2, c3 = st.columns(3)
    c1.metric("Attempts", s["attempts"])
    c2.metric("Wrong", s["wrong"])
    c3.metric("Mastery", f"{mastery(s):.0f}%")


def footer():
    st.markdown("<div class='km-divider'></div><div class='km-small'>Karimen Professional Reviewer · Streamlit build 2.0 · Study aid only</div>", unsafe_allow_html=True)


nav = header()
if nav == "Home":
    page_home()
elif nav == "Review":
    page_review()
elif nav == "Exam":
    page_exam()
elif nav == "Statistics":
    page_statistics()
elif nav == "Question Bank":
    page_bank()
footer()
