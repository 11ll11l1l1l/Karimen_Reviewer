"""Saved-story experience for ALAM.ph.

Saved IDs historically live in a small browser cookie so ALAM works without an
account. ``alam_local_state`` now also stores the material story version seen when a
new save is created. This view combines both pieces: the old ID cookie decides what
is saved, while the version snapshot can highlight later story updates.

This is intentionally backend-agnostic. The same stable story IDs/version timestamps
work whether the current feed comes from Supabase or the verified GitHub fallback.
"""

from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta

import streamlit as st

import alam_local_state as localstate
from alam_core import feed_score, is_followed


SAVED_CSS = r"""
<style>
.saved-update-summary{border:1px solid rgba(89,104,242,.16);background:#EEF0FF;border-radius:16px;padding:11px 13px;margin:5px 0 12px;font-size:.80rem;line-height:1.45;color:#4854C8}
.saved-update-badge{display:inline-flex;border-radius:999px;background:#5968F2;color:#fff;font-size:.62rem;font-weight:950;letter-spacing:.04em;padding:4px 7px;margin:0 0 6px}
.saved-sync-note{font-size:.74rem;line-height:1.45;color:#667085;margin:5px 0 9px}
</style>
"""


def _encode_saved(ids):
    raw = json.dumps(sorted({str(value) for value in ids}), separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_saved(code):
    code = str(code or "").strip()
    if not code:
        return []
    padded = code + "=" * (-len(code) % 4)
    raw = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
    value = json.loads(raw)
    if not isinstance(value, list):
        raise ValueError("Saved sync code must decode to a list")
    return [str(item) for item in value]


def _persist_followed_ids(ids, manager=None):
    """Persist the legacy Saved ID cookie without touching version snapshots.

    Imported IDs may have been saved on another device whose exact save-version
    timestamps are unknown. ALAM therefore does not invent bookmark baselines for an
    imported list; update badges begin once a story is explicitly re-saved locally.
    """
    st.session_state["followed_stories"] = list(ids)
    if manager:
        try:
            manager.set(
                "alam_followed",
                json.dumps(list(ids)),
                expires_at=datetime.now() + timedelta(days=365),
                key="import_followed_saved_view",
            )
        except Exception:
            pass


def render_saved(records, manager, comments, views):
    saved = [record for record in records if is_followed(record.get("id"))]
    updated = [record for record in saved if localstate.saved_has_update(record)]

    st.markdown(
        '<div class="hero mobile-hero"><div class="hero-kicker">🔖 SAVED</div>'
        '<div class="hero-title">Keep what matters.</div>'
        '<div class="hero-copy">Your saved stories stay useful when the story itself changes—not just as frozen bookmarks.</div></div>',
        unsafe_allow_html=True,
    )

    if updated:
        noun = "story has" if len(updated) == 1 else "stories have"
        st.markdown(
            '<div class="saved-update-summary"><strong>'
            f'{len(updated)} saved {noun} a newer ALAM version.</strong> '
            'Updated stories are shown first so material changes do not disappear inside the bookmark list.</div>',
            unsafe_allow_html=True,
        )

    if saved:
        ordered = sorted(
            saved,
            key=lambda record: (localstate.saved_has_update(record), feed_score(record)),
            reverse=True,
        )
        cols = st.columns(2, wrap=True)
        for index, record in enumerate(ordered):
            with cols[index % 2]:
                if localstate.saved_has_update(record):
                    st.markdown('<div class="saved-update-badge">UPDATED SINCE SAVED</div>', unsafe_allow_html=True)
                views.render_card(record, f"saved_v3_{index}", manager, comments)
    else:
        st.info("No saved topics yet. Open a story and tap + Bantayan.")

    st.markdown("#### Saved sync")
    st.markdown(
        '<div class="saved-sync-note">The compact Saved ID code moves your bookmark list between devices. '
        'Your richer portable ALAM profile in Settings carries read/mute/feedback state and local saved-version snapshots.</div>',
        unsafe_allow_html=True,
    )
    code = _encode_saved(st.session_state.get("followed_stories", []))
    st.code(code or "(nothing saved)", language=None)
    incoming = st.text_input("Import saved sync code", key="saved_sync_import_v3")
    if st.button("Import saved list", use_container_width=True, disabled=not incoming.strip(), key="saved_sync_button_v3"):
        try:
            ids = _decode_saved(incoming)
            _persist_followed_ids(ids, manager)
            st.success(f"Imported {len(ids)} saved topic IDs.")
            st.rerun()
        except Exception:
            st.error("Invalid saved sync code.")
