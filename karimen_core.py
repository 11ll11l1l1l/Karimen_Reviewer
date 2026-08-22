from __future__ import annotations

import hashlib
import math
import random
import re
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Iterable

PROGRESS_VERSION = 6


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_stat() -> dict:
    return {
        "attempts": 0,
        "correct": 0,
        "wrong": 0,
        "streak": 0,
        "last_seen": None,
        "last_correct": None,
        "total_seconds": 0.0,
    }


def default_progress() -> dict:
    return {
        "version": PROGRESS_VERSION,
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
        "question_stats": {},
        "sessions": [],
    }


def legacy_id_to_current(qid: str, valid_ids: set[str]) -> str | None:
    if qid in valid_ids:
        return qid
    text = str(qid)
    m = re.search(r"(?:^|[^0-9])(14|15|16)-?Q(\d{1,3})$", text, re.I)
    if m:
        candidate = f"A1-S{int(m.group(1)):02d}-Q{int(m.group(2)):03d}"
        if candidate in valid_ids:
            return candidate
    m = re.search(r"s(\d{1,2})[_-]q(\d{1,3})$", text, re.I)
    if m and 1 <= int(m.group(1)) <= 10:
        candidate = f"B1-S{int(m.group(1)):02d}-Q{int(m.group(2)):03d}"
        if candidate in valid_ids:
            return candidate
    return None


def normalize_progress(raw: dict, valid_ids: set[str]) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("Progress file is not a JSON object.")
    out = default_progress()
    stats = raw.get("question_stats", {})
    if isinstance(stats, dict):
        for old_qid, value in stats.items():
            qid = legacy_id_to_current(str(old_qid), valid_ids)
            if not qid or not isinstance(value, dict):
                continue
            attempts = max(0, int(value.get("attempts", 0) or 0))
            correct = max(0, min(attempts, int(value.get("correct", 0) or 0)))
            s = new_stat()
            s["attempts"] = attempts
            s["correct"] = correct
            s["wrong"] = attempts - correct
            s["streak"] = max(0, int(value.get("streak", 0) or 0))
            s["last_seen"] = value.get("last_seen")
            s["last_correct"] = value.get("last_correct")
            s["total_seconds"] = max(0.0, float(value.get("total_seconds", 0.0) or 0.0))
            out["question_stats"][qid] = s
    sessions = raw.get("sessions", [])
    if isinstance(sessions, list):
        out["sessions"] = [x for x in sessions[-250:] if isinstance(x, dict)]
    out["created_at"] = raw.get("created_at") or out["created_at"]
    out["updated_at"] = utc_now_iso()
    return out


def stat_for(progress: dict, qid: str) -> dict:
    return progress.setdefault("question_stats", {}).setdefault(qid, new_stat())


def mastery(stat: dict) -> float:
    attempts = int(stat.get("attempts", 0) or 0)
    if attempts <= 0:
        return 0.0
    accuracy = float(stat.get("correct", 0) or 0) / attempts
    streak = min(5, int(stat.get("streak", 0) or 0)) / 5.0
    exposure = min(1.0, math.log1p(attempts) / math.log(6))
    return max(0.0, min(100.0, 100 * (0.66 * accuracy + 0.20 * streak + 0.14 * exposure)))


def parse_iso(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def due_now(stat: dict, now: datetime | None = None) -> bool:
    attempts = int(stat.get("attempts", 0) or 0)
    if attempts == 0:
        return True
    if int(stat.get("wrong", 0) or 0) > 0 and not stat.get("last_correct"):
        return True
    last = parse_iso(stat.get("last_seen"))
    if not last:
        return True
    now = now or datetime.now(timezone.utc)
    streak = int(stat.get("streak", 0) or 0)
    interval_days = [0, 1, 3, 7, 14, 30, 60][min(streak, 6)]
    return now >= last + timedelta(days=interval_days)


def record_answer(progress: dict, qid: str, was_correct: bool, seconds: float, now_iso: str | None = None) -> dict:
    s = stat_for(progress, qid)
    s["attempts"] = int(s.get("attempts", 0) or 0) + 1
    s["total_seconds"] = float(s.get("total_seconds", 0.0) or 0.0) + max(0.0, min(float(seconds), 600.0))
    stamp = now_iso or utc_now_iso()
    s["last_seen"] = stamp
    if was_correct:
        s["correct"] = int(s.get("correct", 0) or 0) + 1
        s["streak"] = int(s.get("streak", 0) or 0) + 1
        s["last_correct"] = stamp
    else:
        s["wrong"] = int(s.get("wrong", 0) or 0) + 1
        s["streak"] = 0
    # Always normalize wrong count in case an imported file was inconsistent.
    s["wrong"] = max(0, int(s["attempts"]) - int(s.get("correct", 0) or 0))
    progress["updated_at"] = stamp
    return s


def add_session(progress: dict, mode: str, question_ids: list[str], correct: int, seconds: float, bank: str = "", **extra) -> dict:
    row = {
        "timestamp": utc_now_iso(),
        "mode": mode,
        "bank": bank,
        "questions": len(question_ids),
        "correct": int(correct),
        "percent": round(100 * int(correct) / max(1, len(question_ids)), 1),
        "seconds": round(max(0.0, float(seconds)), 1),
        "question_ids": list(question_ids),
    }
    row.update(extra)
    progress.setdefault("sessions", []).append(row)
    progress["sessions"] = progress["sessions"][-250:]
    progress["updated_at"] = utc_now_iso()
    return row


def category_stats(questions: list[dict], progress: dict) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for q in questions:
        grouped[q["category"]].append(q)
    rows = []
    for category, qs in grouped.items():
        stats = [progress.get("question_stats", {}).get(q["id"], new_stat()) for q in qs]
        attempts = sum(int(s.get("attempts", 0) or 0) for s in stats)
        correct = sum(int(s.get("correct", 0) or 0) for s in stats)
        seen = sum(1 for s in stats if int(s.get("attempts", 0) or 0) > 0)
        rows.append({
            "category": category,
            "attempts": attempts,
            "correct": correct,
            "seen": seen,
            "accuracy": 100 * correct / attempts if attempts else 0.0,
            "mastery": sum(mastery(s) for s in stats) / max(1, len(stats)),
            "count": len(qs),
        })
    return rows


def _priority(q: dict, progress: dict, cat_accuracy: dict[str, float], rng: random.Random) -> float:
    s = progress.get("question_stats", {}).get(q["id"], new_stat())
    attempts = int(s.get("attempts", 0) or 0)
    if attempts == 0:
        base = 5.0
    else:
        wrong_rate = int(s.get("wrong", 0) or 0) / max(1, attempts)
        base = 3.0 * wrong_rate + 2.0 * (1.0 - mastery(s) / 100.0) + (2.0 if due_now(s) else 0.0)
    cat_acc = cat_accuracy.get(q["category"])
    cat_bonus = 0.0 if cat_acc is None else 1.5 * (1.0 - cat_acc / 100.0)
    return base + cat_bonus + rng.random() * 0.2


def select_question_ids(questions: list[dict], progress: dict, mode: str, count: int, seed: int | None = None) -> list[str]:
    if not questions or count <= 0:
        return []
    count = min(int(count), len(questions))
    rng = random.Random(seed)
    rows = category_stats(questions, progress)
    cat_accuracy = {r["category"]: r["accuracy"] for r in rows if r["attempts"] > 0}
    score = lambda q: _priority(q, progress, cat_accuracy, rng)

    if mode == "Random":
        chosen = rng.sample(questions, count)
    elif mode == "Unseen":
        unseen = [q for q in questions if int(progress.get("question_stats", {}).get(q["id"], {}).get("attempts", 0) or 0) == 0]
        seen = [q for q in questions if q not in unseen]
        rng.shuffle(unseen)
        seen.sort(key=score, reverse=True)
        chosen = (unseen + seen)[:count]
    elif mode == "Wrong answers":
        wrong = [q for q in questions if int(progress.get("question_stats", {}).get(q["id"], {}).get("wrong", 0) or 0) > 0]
        wrong.sort(key=score, reverse=True)
        if not wrong:
            return []
        chosen = wrong[:count]
    elif mode == "Due / adaptive":
        due = [q for q in questions if due_now(progress.get("question_stats", {}).get(q["id"], new_stat()))]
        due.sort(key=score, reverse=True)
        due_ids = {q["id"] for q in due}
        rest = [q for q in questions if q["id"] not in due_ids]
        rest.sort(key=score, reverse=True)
        chosen = (due + rest)[:count]
    else:  # Weakest
        chosen = sorted(questions, key=score, reverse=True)[:count]
    return [q["id"] for q in chosen]


def daily_question_ids(questions: list[dict], challenge_date: date, count: int = 10) -> list[str]:
    if not questions or count <= 0:
        return []
    token = f"karimen-v41-{challenge_date.isoformat()}-{len(questions)}"
    seed = int(hashlib.sha256(token.encode()).hexdigest()[:16], 16)
    rng = random.Random(seed)
    image_q = [q for q in questions if q.get("images")]
    plain_q = [q for q in questions if not q.get("images")]
    chosen: list[dict] = []
    if image_q:
        chosen += rng.sample(image_q, min(3, len(image_q), count))
    used = {q["id"] for q in chosen}
    remaining = [q for q in plain_q if q["id"] not in used]
    need = min(count - len(chosen), len(remaining))
    chosen += rng.sample(remaining, need)
    if len(chosen) < count:
        extra = [q for q in questions if q["id"] not in {x["id"] for x in chosen}]
        chosen += rng.sample(extra, min(count - len(chosen), len(extra)))
    rng.shuffle(chosen)
    return [q["id"] for q in chosen[:count]]


def daily_streak(sessions: Iterable[dict], today: date, tz=timezone.utc) -> int:
    dates = set()
    for s in sessions:
        if s.get("mode") != "daily":
            continue
        ts = parse_iso(s.get("timestamp"))
        if ts:
            dates.add(ts.astimezone(tz).date())
    day = today
    if day not in dates:
        day -= timedelta(days=1)
    n = 0
    while day in dates:
        n += 1
        day -= timedelta(days=1)
    return n
