"""Saved-story collections and material-update review for ALAM.ph.

Saved IDs remain browser-local first so ALAM works without an account. A compact
collection cookie adds organization without requiring login, while authenticated
readers can mirror the same collection choice into the existing RLS-protected
``saved_articles.collection`` column. Material-update review behavior is preserved.
"""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timedelta

import streamlit as st

import alam_auth
import alam_intelligence as intelligence
import alam_local_state as localstate
from alam_core import esc, feed_score, is_followed


SAVED_CSS = r"""
<style>
.saved-update-summary{border:1px solid rgba(89,104,242,.16);background:#EEF0FF;border-radius:16px;padding:11px 13px;margin:5px 0 12px;font-size:.80rem;line-height:1.45;color:#4854C8}
.saved-update-badge{display:inline-flex;border-radius:999px;background:#5968F2;color:#fff;font-size:.62rem;font-weight:950;letter-spacing:.04em;padding:4px 7px;margin:0 0 6px}
.saved-change-preview{border-left:3px solid #5968F2;background:#F8F9FF;border-radius:0 12px 12px 0;padding:9px 11px;margin:7px 0 9px;font-size:.76rem;line-height:1.45;color:#475467}
.saved-change-preview b{color:#17202A}
.saved-sync-note{font-size:.74rem;line-height:1.45;color:#667085;margin:5px 0 9px}
.saved-collection-summary{font-size:.75rem;line-height:1.45;color:#667085;margin:5px 0 9px}
@media(max-width:760px){.saved-change-preview{font-size:.78rem}.saved-update-summary{font-size:.82rem}}
</style>
"""

COLLECTION_COOKIE = "alam_saved_collections_v1"
COLLECTIONS = (
    ("Read Later", "read_later"),
    ("Important", "important"),
    ("Money", "money"),
    ("Japan", "japan"),
    ("Family", "family"),
    ("Ideas", "ideas"),
)
COLLECTION_LABELS = {slug: label for label, slug in COLLECTIONS}
DEFAULT_COLLECTION = "read_later"
MAX_COLLECTION_ASSIGNMENTS = 80


def _collection_key(story_id):
    """Use a short stable key so the anonymous collection cookie stays small."""
    return hashlib.sha1(str(story_id).encode("utf-8")).hexdigest()[:12]


def _normalize_collection(value):
    text = str(value or "").strip().lower().replace(" ", "_")
    aliases = {"saved": DEFAULT_COLLECTION, "readlater": DEFAULT_COLLECTION}
    text = aliases.get(text, text)
    return text if text in COLLECTION_LABELS else DEFAULT_COLLECTION


def _decode_collection_cookie(raw):
    if not raw:
        return {}
    try:
        payload = json.loads(str(raw))
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    result = {}
    for key, value in list(payload.items())[-MAX_COLLECTION_ASSIGNMENTS:]:
        compact_key = str(key).strip()[:12]
        if len(compact_key) == 12:
            result[compact_key] = _normalize_collection(value)
    return result


def _collection_map():
    if st.session_state.get("alam_saved_collections_loaded"):
        return st.session_state.setdefault("alam_saved_collections", {})
    try:
        raw = st.context.cookies.get(COLLECTION_COOKIE)
    except Exception:
        raw = None
    st.session_state["alam_saved_collections"] = _decode_collection_cookie(raw)
    st.session_state["alam_saved_collections_loaded"] = True
    return st.session_state["alam_saved_collections"]


def _persist_collection_map(manager=None):
    mapping = dict(list(_collection_map().items())[-MAX_COLLECTION_ASSIGNMENTS:])
    st.session_state["alam_saved_collections"] = mapping
    if manager:
        try:
            manager.set(
                COLLECTION_COOKIE,
                json.dumps(mapping, separators=(",", ":")),
                expires_at=datetime.now() + timedelta(days=365),
                key="set_alam_saved_collections",
            )
        except Exception:
            pass


def _local_collection(story_id):
    return _normalize_collection(_collection_map().get(_collection_key(story_id)))


def _set_local_collection(story_id, collection, manager=None):
    mapping = _collection_map()
    key = _collection_key(story_id)
    mapping.pop(key, None)
    mapping[key] = _normalize_collection(collection)
    _persist_collection_map(manager)
    return mapping[key]


def _cloud_collections(saved_ids):
    """Read only this authenticated user's collection labels through normal RLS."""
    if not alam_auth.is_signed_in():
        return {}, None
    user_id = str(alam_auth.account_summary().get("user_id") or "").strip()
    if not user_id or not saved_ids:
        return {}, None
    try:
        response = (
            alam_auth.get_auth_client()
            .table("saved_articles")
            .select("article_id,collection")
            .eq("user_id", user_id)
            .in_("article_id", list(saved_ids))
            .execute()
        )
        return {
            str(row.get("article_id")): _normalize_collection(row.get("collection"))
            for row in (response.data or [])
            if isinstance(row, dict) and row.get("article_id")
        }, None
    except Exception:
        return {}, "Account collections are temporarily unavailable."


def _set_cloud_collection(story_id, collection):
    """Upsert one collection assignment with the per-session authenticated client."""
    if not alam_auth.is_signed_in():
        return False, None
    user_id = str(alam_auth.account_summary().get("user_id") or "").strip()
    if not user_id:
        return False, None
    try:
        alam_auth.get_auth_client().table("saved_articles").upsert(
            {
                "user_id": user_id,
                "article_id": str(story_id),
                "collection": _normalize_collection(collection),
            },
            on_conflict="user_id,article_id",
        ).execute()
        return True, None
    except Exception:
        return False, "Saved locally; cloud collection sync will retry after account sync."


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
    """Persist legacy Saved IDs without inventing save-version or collection history."""
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


def _compact(value, limit=180):
    text = str(value or "").strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _change_preview(record, all_records):
    change = intelligence.change_snapshot(record, all_records)
    if not change:
        return None
    return _compact(change[0]), _compact(change[1])


def _effective_collections(saved):
    """Cloud is authoritative for signed-in rows; anonymous assignments remain fallback."""
    local = {str(record.get("id")): _local_collection(record.get("id")) for record in saved}
    cloud, error = _cloud_collections(local.keys())
    effective = dict(local)
    effective.update(cloud)
    return effective, error


def render_saved(records, manager, comments, views, all_records=None):
    all_records = all_records or records
    saved = [record for record in records if is_followed(record.get("id"))]
    collections, cloud_error = _effective_collections(saved)

    st.markdown(
        '<div class="hero mobile-hero"><div class="hero-kicker">🔖 SAVED</div>'
        '<div class="hero-title">Keep what matters.</div>'
        '<div class="hero-copy">Sort saved intelligence into small collections, then review material changes without losing the bookmark.</div></div>',
        unsafe_allow_html=True,
    )

    if not saved:
        st.info("No saved topics yet. Open a story and tap + Bantayan.")
    else:
        counts = {}
        for story_id in (str(record.get("id")) for record in saved):
            slug = collections.get(story_id, DEFAULT_COLLECTION)
            counts[slug] = counts.get(slug, 0) + 1
        summary = " · ".join(
            f"{COLLECTION_LABELS[slug]} {counts[slug]}"
            for _, slug in COLLECTIONS
            if counts.get(slug)
        )
        st.markdown(
            f'<div class="saved-collection-summary">{esc(summary or "Read Later")}</div>',
            unsafe_allow_html=True,
        )
        filter_labels = ["All", *[label for label, _ in COLLECTIONS]]
        selected_label = st.selectbox(
            "Saved collection",
            filter_labels,
            label_visibility="collapsed",
            key="saved_collection_filter_v1",
        )
        selected_slug = None if selected_label == "All" else dict(COLLECTIONS)[selected_label]
        visible = [
            record
            for record in saved
            if selected_slug is None
            or collections.get(str(record.get("id")), DEFAULT_COLLECTION) == selected_slug
        ]

        updated = [record for record in visible if localstate.saved_has_update(record)]
        if updated:
            noun = "story has" if len(updated) == 1 else "stories have"
            st.markdown(
                '<div class="saved-update-summary"><strong>'
                f'{len(updated)} saved {noun} a newer ALAM version.</strong> '
                'Updated stories are first. Review the change, then clear the update without removing the bookmark.</div>',
                unsafe_allow_html=True,
            )

        if cloud_error:
            st.caption("Account collection sync is temporarily unavailable; browser collections still work.")

        ordered = sorted(
            visible,
            key=lambda record: (localstate.saved_has_update(record), feed_score(record)),
            reverse=True,
        )
        if not ordered:
            st.info(f"No stories in {selected_label} yet.")
        cols = st.columns(2, wrap=True)
        for index, record in enumerate(ordered):
            story_id = str(record.get("id"))
            current_slug = collections.get(story_id, DEFAULT_COLLECTION)
            current_label = COLLECTION_LABELS[current_slug]
            with cols[index % 2]:
                has_update = localstate.saved_has_update(record)
                if has_update:
                    st.markdown('<div class="saved-update-badge">UPDATED SINCE SAVED</div>', unsafe_allow_html=True)
                    preview = _change_preview(record, all_records)
                    if preview:
                        st.markdown(
                            "<div class='saved-change-preview'>"
                            f"<b>Before:</b> {esc(preview[0])}<br>"
                            f"<b>Now:</b> {esc(preview[1])}</div>",
                            unsafe_allow_html=True,
                        )
                views.render_card(record, f"saved_v5_{index}", manager, comments)
                labels = [label for label, _ in COLLECTIONS]
                new_label = st.selectbox(
                    "Collection",
                    labels,
                    index=labels.index(current_label),
                    key=f"saved_collection_{_collection_key(story_id)}",
                )
                new_slug = dict(COLLECTIONS)[new_label]
                if new_slug != current_slug:
                    _set_local_collection(story_id, new_slug, manager)
                    _, sync_error = _set_cloud_collection(story_id, new_slug)
                    if sync_error:
                        st.toast(sync_error)
                    else:
                        st.toast(f"Moved to {new_label}.")
                    st.rerun()
                if has_update:
                    if st.button(
                        "✓ Mark this update reviewed",
                        key=f"saved_review_{record.get('id')}_{index}",
                        use_container_width=True,
                    ):
                        if localstate.acknowledge_saved_update(record, manager):
                            st.toast("Update reviewed. Future material changes will alert you again.")
                        st.rerun()

    st.markdown("#### Saved sync")
    st.markdown(
        '<div class="saved-sync-note">The compact Saved ID code moves bookmarks between devices. '
        'Collection labels stay in this browser automatically and also follow your account when signed in.</div>',
        unsafe_allow_html=True,
    )
    code = _encode_saved(st.session_state.get("followed_stories", []))
    st.code(code or "(nothing saved)", language=None)
    incoming = st.text_input("Import saved sync code", key="saved_sync_import_v5")
    if st.button("Import saved list", use_container_width=True, disabled=not incoming.strip(), key="saved_sync_button_v5"):
        try:
            ids = _decode_saved(incoming)
            _persist_followed_ids(ids, manager)
            st.success(f"Imported {len(ids)} saved topic IDs.")
            st.rerun()
        except Exception:
            st.error("Invalid saved sync code.")
