import base64
import hashlib
import json
import zlib
from datetime import datetime, timedelta

import streamlit as st

from alam_core import is_followed, parse_dt, toggle_follow

COOKIE_NAME = "alam_profile_v2"
# Version 3 adds `b` (bookmark/save snapshots) while keeping the cookie name stable.
# The decoder is intentionally additive so existing v2 browser profiles migrate
# silently instead of making users re-import/reset their local personalization.
COOKIE_VERSION = 3
MAX_READ = 48
MAX_FEEDBACK = 30
MAX_MUTED = 24
MAX_SAVED_SNAPSHOTS = 48

VOTE_WEIGHT = {
    "MORE": 6,
    "IMPORTANT": 10,
    "LESS": -6,
    "NOT_USEFUL": -10,
}


def _sid(story_id):
    return hashlib.sha1(str(story_id).encode("utf-8")).hexdigest()[:12]


def _default_profile():
    # `b` stores the article-version minute observed when a story was saved. It is
    # separate from the existing followed-story ID cookie because the latter remains
    # intentionally human-portable/backward-compatible across old ALAM versions.
    return {"v": COOKIE_VERSION, "r": {}, "m": [], "f": {}, "s": {}, "b": {}}


def _encode(profile):
    raw = json.dumps(profile, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    packed = zlib.compress(raw, 9)
    return base64.urlsafe_b64encode(packed).decode("ascii").rstrip("=")


def _decode(code):
    value = str(code or "").strip()
    if not value:
        return _default_profile()
    padded = value + "=" * (-len(value) % 4)
    raw = zlib.decompress(base64.urlsafe_b64decode(padded.encode("ascii")))
    decoded = json.loads(raw.decode("utf-8"))
    if not isinstance(decoded, dict):
        raise ValueError("Profile must be an object")
    profile = _default_profile()
    for key in ("r", "m", "f", "s", "b"):
        if key in decoded and isinstance(decoded[key], type(profile[key])):
            profile[key] = decoded[key]
    return profile


def _trim(profile):
    out = _default_profile()
    out["s"] = dict(profile.get("s") or {})
    reads = profile.get("r") or {}
    if isinstance(reads, dict):
        newest = sorted(reads.items(), key=lambda item: int(item[1] or 0), reverse=True)[:MAX_READ]
        out["r"] = dict(newest)
    muted = profile.get("m") or []
    out["m"] = [str(x) for x in muted[-MAX_MUTED:]]
    feedback = profile.get("f") or {}
    if isinstance(feedback, dict):
        out["f"] = dict(list(feedback.items())[-MAX_FEEDBACK:])
    bookmarks = profile.get("b") or {}
    if isinstance(bookmarks, dict):
        newest_bookmarks = sorted(
            bookmarks.items(), key=lambda item: int(item[1] or 0), reverse=True
        )[:MAX_SAVED_SNAPSHOTS]
        out["b"] = {str(key): int(value or 0) for key, value in newest_bookmarks}
    return out


def _apply_settings(profile):
    settings = profile.get("s") or {}
    interests = settings.get("interests")
    if isinstance(interests, dict):
        st.session_state["alam_interest_preferences"] = {str(k): bool(v) for k, v in interests.items()}
    for key, target in (
        ("alert_min", "alam_alert_min_importance"),
        ("alert_action", "alam_alert_only_actionable"),
        ("alert_change", "alam_alert_material_change"),
        ("dark", "alam_dark_mode"),
    ):
        if key in settings:
            st.session_state[target] = settings[key]


def init_local_profile(manager=None):
    st.session_state.setdefault("alam_local_profile", _default_profile())
    if st.session_state.get("alam_local_profile_loaded"):
        return
    loaded = None
    if manager:
        try:
            raw = manager.get(cookie=COOKIE_NAME)
            if raw:
                loaded = _decode(raw)
        except Exception:
            loaded = None
    if loaded:
        st.session_state["alam_local_profile"] = _trim(loaded)
        _apply_settings(st.session_state["alam_local_profile"])
    st.session_state["alam_local_profile_loaded"] = True


def _profile():
    return st.session_state.setdefault("alam_local_profile", _default_profile())


def _save(manager=None):
    profile = _trim(_profile())
    st.session_state["alam_local_profile"] = profile
    if manager:
        try:
            manager.set(
                COOKIE_NAME,
                _encode(profile),
                expires_at=datetime.now() + timedelta(days=365),
                key="set_alam_local_profile",
            )
        except Exception:
            pass


def persist_settings(manager=None):
    profile = _profile()
    profile["s"] = {
        "interests": dict(st.session_state.get("alam_interest_preferences") or {}),
        "alert_min": int(st.session_state.get("alam_alert_min_importance", 85)),
        "alert_action": bool(st.session_state.get("alam_alert_only_actionable", False)),
        "alert_change": bool(st.session_state.get("alam_alert_material_change", True)),
        "dark": bool(st.session_state.get("alam_dark_mode", False)),
    }
    _save(manager)


def _version_minute(record):
    return int(parse_dt(record.get("created_at")).timestamp() // 60)


def is_unread(record):
    read_version = int((_profile().get("r") or {}).get(_sid(record.get("id")), 0) or 0)
    return _version_minute(record) > read_version


def mark_read(record, manager=None):
    sid = _sid(record.get("id"))
    current = int((_profile().get("r") or {}).get(sid, 0) or 0)
    version = _version_minute(record)
    if current >= version:
        return
    reads = _profile().setdefault("r", {})
    reads.pop(sid, None)
    reads[sid] = version
    _save(manager)


def mark_all_read(records, manager=None):
    reads = _profile().setdefault("r", {})
    for record in records:
        sid = _sid(record.get("id"))
        reads.pop(sid, None)
        reads[sid] = _version_minute(record)
    _save(manager)


def is_muted(record_or_id):
    story_id = record_or_id.get("id") if isinstance(record_or_id, dict) else record_or_id
    return _sid(story_id) in set(_profile().get("m") or [])


def toggle_muted(record, manager=None):
    sid = _sid(record.get("id"))
    muted = list(_profile().get("m") or [])
    if sid in muted:
        muted = [x for x in muted if x != sid]
    else:
        muted.append(sid)
    _profile()["m"] = muted[-MAX_MUTED:]
    _save(manager)
    return sid in _profile()["m"]


def feedback_for(record):
    entry = (_profile().get("f") or {}).get(_sid(record.get("id")))
    return str(entry[0]) if isinstance(entry, list) and entry else None


def set_feedback(record, vote, topics=None, manager=None):
    vote = str(vote or "").upper()
    if vote not in VOTE_WEIGHT:
        return
    sid = _sid(record.get("id"))
    feedback = _profile().setdefault("f", {})
    feedback.pop(sid, None)
    feedback[sid] = [
        vote,
        str(record.get("_category") or ""),
        [str(x) for x in (topics or [])[:4]],
    ]
    _save(manager)


def adaptive_boost(record, topics=None):
    category = str(record.get("_category") or "")
    wanted = set(str(x) for x in (topics or []))
    score = 0.0
    for entry in (_profile().get("f") or {}).values():
        if not isinstance(entry, list) or not entry:
            continue
        vote = str(entry[0])
        weight = VOTE_WEIGHT.get(vote, 0)
        prior_category = str(entry[1]) if len(entry) > 1 else ""
        prior_topics = set(str(x) for x in (entry[2] if len(entry) > 2 and isinstance(entry[2], list) else []))
        overlap = len(wanted & prior_topics)
        if overlap:
            score += weight * min(1.0, 0.55 + 0.2 * overlap)
        elif category and category == prior_category:
            score += weight * 0.22
    return int(max(-18, min(18, round(score))))


def toggle_saved(record, manager=None):
    """Toggle the existing Followed/Saved state and snapshot the current version.

    The legacy followed-story cookie remains the source of truth for whether a story
    is saved, so this is backward-compatible with old browsers and existing sync
    codes. The local profile stores only the version observed at save time. When the
    same stable story ID gets a newer material record, Saved can therefore flag the
    change without requiring login or a backend write.
    """
    was_saved = is_followed(record.get("id"))
    toggle_follow(record.get("id"), manager)
    sid = _sid(record.get("id"))
    bookmarks = _profile().setdefault("b", {})
    if was_saved:
        bookmarks.pop(sid, None)
    else:
        bookmarks.pop(sid, None)
        bookmarks[sid] = _version_minute(record)
    _save(manager)
    return not was_saved


def saved_has_update(record):
    """True only when a locally-snapshotted saved story has a newer version."""
    if not is_followed(record.get("id")):
        return False
    saved_version = int((_profile().get("b") or {}).get(_sid(record.get("id")), 0) or 0)
    if saved_version <= 0:
        # Existing saves from pre-v3 profiles have no trustworthy save-time version.
        # Do not falsely label them updated; the next unsave/save action establishes
        # a baseline and future material versions will be detectable.
        return False
    return _version_minute(record) > saved_version


def saved_snapshot_count():
    return len(_profile().get("b") or {})


def render_story_controls(record, topics, manager=None):
    current = feedback_for(record)
    st.markdown("#### Tune ALAM")
    st.caption("This adjusts ranking in this browser only; it never changes the factual article.")
    cols = st.columns(4)
    options = [
        ("More", "MORE"),
        ("Important", "IMPORTANT"),
        ("Less", "LESS"),
        ("Not useful", "NOT_USEFUL"),
    ]
    for col, (label, vote) in zip(cols, options):
        shown = f"✓ {label}" if current == vote else label
        if col.button(shown, key=f"feedback_{vote}_{_sid(record.get('id'))}", use_container_width=True):
            set_feedback(record, vote, topics, manager)
            st.toast("Preference saved in this browser.")
            st.rerun()
    muted = is_muted(record)
    if st.button("Unmute story" if muted else "Mute future updates from this story", key=f"mute_{_sid(record.get('id'))}", use_container_width=True):
        toggle_muted(record, manager)
        st.rerun()


def export_code():
    return _encode(_trim(_profile()))


def import_code(code, manager=None):
    profile = _trim(_decode(code))
    st.session_state["alam_local_profile"] = profile
    _apply_settings(profile)
    _save(manager)
    return profile


def reset_profile(manager=None):
    st.session_state["alam_local_profile"] = _default_profile()
    _save(manager)


def profile_counts():
    profile = _profile()
    return {
        "read": len(profile.get("r") or {}),
        "muted": len(profile.get("m") or []),
        "feedback": len(profile.get("f") or {}),
        "saved_snapshots": len(profile.get("b") or {}),
    }


def render_profile_tools(manager=None):
    counts = profile_counts()
    st.markdown("#### Portable browser profile")
    st.caption(
        f"{counts['read']} read · {counts['muted']} muted · {counts['feedback']} feedback signals · "
        f"{counts['saved_snapshots']} saved-version snapshots. No account or Supabase write required."
    )
    st.code(export_code(), language=None)
    incoming = st.text_input("Import ALAM profile code", key="alam_profile_import")
    if st.button("Import profile", disabled=not incoming.strip(), use_container_width=True):
        try:
            import_code(incoming, manager)
            st.success("Profile imported.")
            st.rerun()
        except Exception:
            st.error("Invalid ALAM profile code.")
    with st.expander("Reset local profile"):
        st.warning("This clears local read, mute, feedback and saved-version history on this browser. The separate Saved list is not deleted here.")
        if st.button("Reset local profile", key="reset_local_profile", use_container_width=True):
            reset_profile(manager)
            st.rerun()
