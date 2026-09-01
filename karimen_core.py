from __future__ import annotations

import hashlib
import math
import random
import re
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Iterable

PROGRESS_VERSION = 8


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
        "confidence_known": 0,
        "confidence_guessed": 0,
        "confidence_guess_correct": 0,
        "confidence_sure_wrong": 0,
    }


def default_progress() -> dict:
    return {
        "version": PROGRESS_VERSION,
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
        "question_stats": {},
        "sessions": [],
        "bookmarks": [],
    }


def legacy_id_to_current(qid: str, valid_ids: set[str]) -> str | None:
    """Migrate every earlier Karimen/A1/B1 identifier into the v5 bank layout."""
    if qid in valid_ids:
        return qid
    text = str(qid).strip()

    # v3/v4 public IDs.
    m = re.fullmatch(r"A1-S(14|15|16)-Q(\d{1,3})", text, re.I)
    if m:
        candidate = f"KARIMEN-S{int(m.group(1)):02d}-Q{int(m.group(2)):03d}"
        return candidate if candidate in valid_ids else None
    m = re.fullmatch(r"B1-S(\d{1,2})-Q(\d{1,3})", text, re.I)
    if m and 1 <= int(m.group(1)) <= 10:
        candidate = f"KARIMEN-S{int(m.group(1)):02d}-Q{int(m.group(2)):03d}"
        return candidate if candidate in valid_ids else None

    # Older package IDs that only embedded the set/question number.
    m = re.search(r"(?:^|[^0-9])(14|15|16)-?Q(\d{1,3})$", text, re.I)
    if m:
        candidate = f"KARIMEN-S{int(m.group(1)):02d}-Q{int(m.group(2)):03d}"
        if candidate in valid_ids:
            return candidate
    m = re.search(r"s(\d{1,2})[_-]q(\d{1,3})$", text, re.I)
    if m and 1 <= int(m.group(1)) <= 10:
        candidate = f"KARIMEN-S{int(m.group(1)):02d}-Q{int(m.group(2)):03d}"
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
            s["confidence_known"] = max(0, int(value.get("confidence_known", 0) or 0))
            s["confidence_guessed"] = max(0, int(value.get("confidence_guessed", 0) or 0))
            s["confidence_guess_correct"] = max(0, int(value.get("confidence_guess_correct", 0) or 0))
            s["confidence_sure_wrong"] = max(0, int(value.get("confidence_sure_wrong", 0) or 0))
            out["question_stats"][qid] = s

    sessions = raw.get("sessions", [])
    if isinstance(sessions, list):
        migrated = []
        for row in sessions[-250:]:
            if not isinstance(row, dict):
                continue
            row = dict(row)
            if str(row.get("bank") or "") in {"A1", "B1"}:
                row["bank"] = "Karimen"
            if isinstance(row.get("question_ids"), list):
                new_ids = []
                for old in row["question_ids"]:
                    new = legacy_id_to_current(str(old), valid_ids)
                    if new:
                        new_ids.append(new)
                row["question_ids"] = new_ids
            migrated.append(row)
        out["sessions"] = migrated

    bookmarks = raw.get("bookmarks", [])
    if isinstance(bookmarks, list):
        migrated = []
        for old in bookmarks:
            qid = legacy_id_to_current(str(old), valid_ids)
            if qid and qid not in migrated:
                migrated.append(qid)
        out["bookmarks"] = migrated
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



def record_confidence(progress: dict, qid: str, guessed: bool, was_correct: bool | None = None) -> dict:
    """Record self-reported confidence after an attempt without changing score."""
    s = stat_for(progress, qid)
    key = "confidence_guessed" if guessed else "confidence_known"
    s[key] = int(s.get(key, 0) or 0) + 1
    if guessed and was_correct is True:
        s["confidence_guess_correct"] = int(s.get("confidence_guess_correct", 0) or 0) + 1
    if (not guessed) and was_correct is False:
        s["confidence_sure_wrong"] = int(s.get("confidence_sure_wrong", 0) or 0) + 1
    progress["updated_at"] = utc_now_iso()
    return s


def is_bookmarked(progress: dict, qid: str) -> bool:
    return qid in set(progress.get("bookmarks", []) or [])


def toggle_bookmark(progress: dict, qid: str) -> bool:
    items = list(dict.fromkeys(str(x) for x in (progress.get("bookmarks", []) or [])))
    if qid in items:
        items.remove(qid)
        active = False
    else:
        items.append(qid)
        active = True
    progress["bookmarks"] = items
    progress["updated_at"] = utc_now_iso()
    return active

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


def content_key(q: dict) -> str:
    """Stable equivalence key used to prevent identical source questions from crowding a run."""
    return str(q.get("content_key") or q.get("id") or "")


def _content_groups(questions: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for q in questions:
        grouped[content_key(q)].append(q)
    return grouped


def _group_attempts(group: list[dict], progress: dict) -> int:
    stats = progress.get("question_stats", {})
    return sum(int(stats.get(q["id"], {}).get("attempts", 0) or 0) for q in group)


def _group_last_seen(group: list[dict], progress: dict) -> float:
    """Latest encounter timestamp for equivalent content; 0 means never seen."""
    stats = progress.get("question_stats", {})
    vals = []
    for q in group:
        dt = parse_iso(stats.get(q["id"], {}).get("last_seen"))
        if dt:
            vals.append(dt.timestamp())
    return max(vals) if vals else 0.0


def coverage_first_ids(questions: list[dict], progress: dict, count: int, seed: int | None = None, adaptive_after_coverage: bool = True) -> list[str]:
    """Select unseen *content* first, then least-exposed/oldest content.

    Exact duplicate source records remain in the data set, but only one representative
    is selected until every distinct content group has been encountered. This prevents
    apparent repetition without deleting source records.
    """
    if not questions or count <= 0:
        return []
    count = min(int(count), len(questions))
    rng = random.Random(seed)
    groups = _content_groups(questions)
    rows = category_stats(questions, progress)
    cat_accuracy = {r["category"]: r["accuracy"] for r in rows if r["attempts"] > 0}

    reps = []
    leftovers = []
    for key, group in groups.items():
        # Prefer the actual source record with the fewest direct attempts as group representative.
        ranked = sorted(group, key=lambda q: (int(progress.get("question_stats", {}).get(q["id"], {}).get("attempts", 0) or 0), rng.random()))
        rep = ranked[0]
        attempts = _group_attempts(group, progress)
        last_seen = _group_last_seen(group, progress)
        adaptive = _priority(rep, progress, cat_accuracy, rng)
        reps.append((rep, attempts, last_seen, adaptive))
        leftovers.extend(ranked[1:])

    unseen = [x for x in reps if x[1] == 0]
    seen = [x for x in reps if x[1] > 0]
    rng.shuffle(unseen)
    # After coverage, the least-exposed and least-recently-seen rule comes first;
    # adaptive weakness breaks ties rather than overriding coverage.
    seen.sort(key=lambda x: (x[1], x[2], -x[3], rng.random()))
    chosen = [x[0] for x in (unseen + seen)[:count]]

    if len(chosen) < count:
        chosen_ids = {q["id"] for q in chosen}
        leftovers = [q for q in leftovers if q["id"] not in chosen_ids]
        leftovers.sort(key=lambda q: (
            int(progress.get("question_stats", {}).get(q["id"], {}).get("attempts", 0) or 0),
            _group_last_seen(groups[content_key(q)], progress),
            rng.random(),
        ))
        chosen.extend(leftovers[: count - len(chosen)])
    return [q["id"] for q in chosen[:count]]


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
    # Confidence is a learning signal: a lucky correct guess and, especially,
    # a confident misconception should come back sooner in Smart Review.
    guessed = int(s.get("confidence_guessed", 0) or 0)
    known = int(s.get("confidence_known", 0) or 0)
    guess_ratio = guessed / max(1, guessed + known)
    confidence_bonus = 1.15 * guess_ratio + min(2.0, 0.75 * int(s.get("confidence_sure_wrong", 0) or 0))
    return base + cat_bonus + confidence_bonus + rng.random() * 0.2


def select_question_ids(questions: list[dict], progress: dict, mode: str, count: int, seed: int | None = None) -> list[str]:
    if not questions or count <= 0:
        return []
    count = min(int(count), len(questions))
    rng = random.Random(seed)
    rows = category_stats(questions, progress)
    cat_accuracy = {r["category"]: r["accuracy"] for r in rows if r["attempts"] > 0}
    score = lambda q: _priority(q, progress, cat_accuracy, rng)

    # Coverage-first is the default learning/exam behavior in v5. It imposes a
    # hard unseen tier, so a previously-missed/due item can never crowd out a
    # never-encountered rule unless the user deliberately chooses a targeted drill.
    if mode in {"Coverage first", "Due / adaptive", "Smart"}:
        return coverage_first_ids(questions, progress, count, seed=seed)
    if mode == "Random":  # explicit pure-random mode only
        chosen = rng.sample(questions, count)
    elif mode == "Unseen":
        unseen = [q for q in questions if int(progress.get("question_stats", {}).get(q["id"], {}).get("attempts", 0) or 0) == 0]
        rng.shuffle(unseen)
        if len(unseen) >= count:
            chosen = unseen[:count]
        else:
            extra_ids = coverage_first_ids(questions, progress, count, seed=seed)
            selected = {q["id"] for q in unseen}
            chosen = unseen + [next(x for x in questions if x["id"] == qid) for qid in extra_ids if qid not in selected][:count-len(unseen)]
    elif mode == "Wrong answers":
        wrong = [q for q in questions if int(progress.get("question_stats", {}).get(q["id"], {}).get("wrong", 0) or 0) > 0]
        wrong.sort(key=score, reverse=True)
        if not wrong:
            return []
        chosen = wrong[:count]
    elif mode == "Guessed":
        guessed = [q for q in questions if int(progress.get("question_stats", {}).get(q["id"], {}).get("confidence_guessed", 0) or 0) > 0]
        guessed.sort(key=score, reverse=True)
        if not guessed:
            return []
        chosen = guessed[:count]
    else:  # deliberately targeted Weakest drill
        chosen = sorted(questions, key=score, reverse=True)[:count]
    return [q["id"] for q in chosen]

def daily_question_ids(questions: list[dict], challenge_date: date, count: int = 10, progress: dict | None = None, player_token: str = "") -> list[str]:
    if not questions or count <= 0:
        return []
    token = f"jdl-v50-{challenge_date.isoformat()}-{len(questions)}-{player_token}"
    seed = int(hashlib.sha256(token.encode()).hexdigest()[:16], 16)
    if progress is not None:
        # Daily questions are still stable for a given state/date, but unseen content is preferred.
        return coverage_first_ids(questions, progress, min(count, len(questions)), seed=seed)
    rng = random.Random(seed)
    chosen = rng.sample(questions, min(count, len(questions)))
    return [q["id"] for q in chosen]

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
