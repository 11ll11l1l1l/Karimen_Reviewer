"""Grounded article action follow-through for ALAM.ph.

Only structured action-plan steps already present in a validated ALAM article are
rendered. Completion is optional browser-local state; this module never invents
instructions, changes article facts, or requires an account/backend write.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import zlib
from datetime import datetime, timedelta

import streamlit as st


COOKIE_NAME = "alam_action_progress_v1"
MAX_STORIES = 32
MAX_STEPS = 8
MAX_COOKIE_JSON_BYTES = 16 * 1024
# Browser cookie limits vary, and the cookie name/expiry metadata also consume the
# per-cookie budget. Keep the encoded value comfortably below common ceilings so a
# full valid checklist history does not silently degrade to session-only state.
MAX_COOKIE_VALUE_BYTES = 3500


def _compact(value, limit=420):
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _story_key(story_id):
    return hashlib.sha1(str(story_id).encode("utf-8")).hexdigest()[:12]


def _step_key(story_id, step):
    identity = "|".join(
        (
            str(story_id or ""),
            _compact(step.get("step"), 180).lower(),
            _compact(step.get("action"), 260).lower(),
            _compact(step.get("done_when"), 220).lower(),
        )
    )
    return hashlib.sha1(identity.encode("utf-8")).hexdigest()[:16]


def action_plan(record):
    """Return a safe display plan from explicit structured article metadata only."""
    content = record.get("content") if isinstance(record, dict) and isinstance(record.get("content"), dict) else {}
    raw = content.get("action_plan")
    if not isinstance(raw, dict):
        return None
    raw_steps = raw.get("steps")
    if not isinstance(raw_steps, list):
        return None

    steps = []
    seen = set()
    for candidate in raw_steps:
        if not isinstance(candidate, dict):
            continue
        title = _compact(candidate.get("step"), 180)
        action = _compact(candidate.get("action"), 420)
        done_when = _compact(candidate.get("done_when"), 360)
        if not title or not action:
            continue
        key = _step_key(record.get("id"), candidate)
        if key in seen:
            continue
        seen.add(key)
        minutes = candidate.get("time_minutes")
        try:
            minutes = int(minutes) if minutes is not None else None
        except (TypeError, ValueError, OverflowError):
            minutes = None
        steps.append(
            {
                "key": key,
                "title": title,
                "action": action,
                "done_when": done_when,
                "minutes": minutes if minutes is not None and 0 <= minutes <= 1440 else None,
            }
        )
        if len(steps) >= MAX_STEPS:
            break
    if not steps:
        return None
    return {
        "goal": _compact(raw.get("goal"), 360),
        "deadline": _compact(raw.get("deadline") or content.get("deadline"), 420),
        "steps": steps,
    }


def _normalize_progress(decoded):
    """Normalize browser/session progress before any render path trusts its shape.

    Streamlit session state can survive code reloads and component/rerun transitions,
    so it is not safe to assume the cached value still matches this module's current
    dictionary-of-string-lists contract. Apply the same bounds used for cookie input
    instead of allowing stale/malformed cached values to crash article rendering.
    """
    if not isinstance(decoded, dict):
        return {}
    clean = {}
    for story, values in decoded.items():
        if not isinstance(values, list):
            continue
        valid = [str(item)[:32] for item in values if isinstance(item, str) and item]
        if valid:
            clean[str(story)[:20]] = list(dict.fromkeys(valid))[:MAX_STEPS]
    return dict(list(clean.items())[-MAX_STORIES:])


def _decode(raw):
    value = str(raw or "").strip()
    if not value:
        return {}
    try:
        padded = value + "=" * (-len(value) % 4)
        compressed = base64.urlsafe_b64decode(padded.encode("ascii"))
        # Browser cookies are user-controlled input. Bound decompression before JSON
        # parsing so a tiny high-ratio payload cannot make a routine page rerun spend
        # unbounded memory/CPU. Normal checklist state is far below this ceiling.
        inflater = zlib.decompressobj()
        payload = inflater.decompress(compressed, MAX_COOKIE_JSON_BYTES + 1)
        if len(payload) > MAX_COOKIE_JSON_BYTES or not inflater.eof or inflater.unconsumed_tail:
            return {}
        decoded = json.loads(payload.decode("utf-8"))
    except Exception:
        return {}
    return _normalize_progress(decoded)


def _encode(progress):
    raw = json.dumps(progress, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(zlib.compress(raw, 9)).decode("ascii").rstrip("=")


def _encode_for_cookie(progress):
    """Encode recent progress inside a conservative browser-cookie value budget.

    The normalized dictionary is ordered oldest-to-newest: each changed story is
    popped and re-added by ``set_step_completed``. If the valid state grows beyond
    the persistence envelope, evict only the oldest stories from the cookie copy.
    The full normalized state remains in Streamlit session state for this session.
    """
    persisted = _normalize_progress(progress)
    encoded = _encode(persisted)
    while persisted and len(encoded.encode("ascii")) > MAX_COOKIE_VALUE_BYTES:
        persisted.pop(next(iter(persisted)))
        encoded = _encode(persisted)
    return encoded


def _load_progress():
    if "alam_action_progress" in st.session_state:
        progress = _normalize_progress(st.session_state["alam_action_progress"])
        st.session_state["alam_action_progress"] = progress
        return progress
    raw = None
    try:
        raw = st.context.cookies.get(COOKIE_NAME)
    except Exception:
        raw = None
    progress = _decode(raw)
    st.session_state["alam_action_progress"] = progress
    return progress


def _save_progress(progress, manager=None):
    progress = _normalize_progress(progress)
    st.session_state["alam_action_progress"] = progress
    if manager:
        try:
            manager.set(
                COOKIE_NAME,
                _encode_for_cookie(progress),
                expires_at=datetime.now() + timedelta(days=365),
                key="set_alam_action_progress",
            )
        except Exception:
            pass


def completed_step_keys(record):
    return set(_load_progress().get(_story_key(record.get("id")), []))


def set_step_completed(record, step_key, completed, manager=None):
    """Persist one action toggle while preserving progress on unchanged story steps."""
    plan = action_plan(record)
    valid = {step["key"] for step in (plan or {}).get("steps", [])}
    if step_key not in valid:
        return False
    progress = _load_progress()
    story = _story_key(record.get("id"))
    current = [key for key in progress.get(story, []) if key in valid]
    before = set(current)
    if completed:
        current = list(dict.fromkeys(current + [step_key]))
    else:
        current = [key for key in current if key != step_key]
    if current:
        progress.pop(story, None)
        progress[story] = current[:MAX_STEPS]
    else:
        progress.pop(story, None)
    if set(current) != before:
        _save_progress(progress, manager)
        return True
    return False


def progress_counts(record):
    plan = action_plan(record)
    if not plan:
        return (0, 0)
    valid = {step["key"] for step in plan["steps"]}
    done = completed_step_keys(record) & valid
    return (len(done), len(valid))


def action_focus(record, completed=None):
    """Return the next verified step and remaining effort without inventing priority.

    Action-plan order is editorially supplied by the validated record, so the first
    unfinished item is the only defensible next step. Remaining time is shown only
    when every unfinished step has an explicit valid time estimate.
    """
    plan = action_plan(record)
    if not plan:
        return None
    completed = set(completed if completed is not None else completed_step_keys(record))
    unfinished = [step for step in plan["steps"] if step["key"] not in completed]
    if not unfinished:
        return {"complete": True, "next": None, "remaining": 0, "remaining_minutes": 0}
    estimates = [step.get("minutes") for step in unfinished]
    remaining_minutes = sum(estimates) if all(value is not None for value in estimates) else None
    return {
        "complete": False,
        "next": unfinished[0],
        "remaining": len(unfinished),
        "remaining_minutes": remaining_minutes,
    }


def render_action_checklist(record, manager=None):
    """Render optional mobile-friendly follow-through beneath article decision cards."""
    plan = action_plan(record)
    if not plan:
        return
    completed = completed_step_keys(record)
    total = len(plan["steps"])
    done = len(completed & {step["key"] for step in plan["steps"]})
    focus = action_focus(record, completed)

    st.markdown("#### Action checklist")
    st.caption(
        f"{done}/{total} complete · Saved on this browser. These are the article’s validated action-plan steps, not new AI advice."
    )
    if plan.get("goal"):
        st.markdown(f"**Goal:** {plan['goal']}")
    if plan.get("deadline"):
        st.markdown(f"**Timing:** {plan['deadline']}")

    if focus and not focus["complete"]:
        next_step = focus["next"]
        effort = ""
        if focus["remaining_minutes"] is not None:
            effort = f" · ~{focus['remaining_minutes']} min remaining"
        st.info(
            f"Next verified step: {next_step['title']} — {next_step['action']}"
            f" · {focus['remaining']} step{'s' if focus['remaining'] != 1 else ''} left{effort}"
        )

    for index, step in enumerate(plan["steps"], start=1):
        checked = step["key"] in completed
        label = f"{index}. {step['title']}"
        value = st.checkbox(
            label,
            value=checked,
            key=f"alam_action_{_story_key(record.get('id'))}_{step['key']}",
        )
        meta = []
        if step.get("minutes") is not None:
            meta.append(f"~{step['minutes']} min")
        if step.get("done_when"):
            meta.append(f"Done when: {step['done_when']}")
        st.caption(step["action"] + ((" · " + " · ".join(meta)) if meta else ""))
        if value != checked:
            set_step_completed(record, step["key"], value, manager)
            st.rerun()

    if done == total:
        st.success("Action plan complete on this browser.")
