import base64
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import streamlit as st

from alam_core import DATA_DIR, feed_score, is_followed, normalize_category, parse_dt
from alam_supabase import (
    check_supabase_connection,
    database_public_health,
    load_article_history,
    load_latest_wisdom_from_db,
    load_published_articles,
)

WISDOM_DIR = DATA_DIR / "wisdom"
ARTICLE_DIRS = [DATA_DIR / name for name in ("discover", "practical", "reflection", "trend")]
JST = ZoneInfo("Asia/Tokyo")

EXTRA_CSS = r"""
<style>
.wisdom-strip{margin:-2px 0 12px;padding:9px 12px 10px;border:1px solid rgba(23,32,42,.08);border-radius:15px;background:rgba(255,255,255,.66)}
.wisdom-verse{font-size:.73rem;line-height:1.35;color:#667085}
.wisdom-verse strong{color:#344054}
.wisdom-question{font-size:.82rem;line-height:1.38;font-weight:760;color:#273142;margin-top:6px}
.saved-sync{font-size:.76rem;color:#667085;line-height:1.45}
.db-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:7px;margin-top:8px}.db-chip{padding:9px;border:1px solid rgba(23,32,42,.08);border-radius:13px;background:rgba(255,255,255,.7);text-align:center}.db-value{font-weight:900;font-size:1rem}.db-label{font-size:.65rem;color:#98A2B3;text-transform:uppercase;letter-spacing:.04em}
@media(max-width:760px){
  .block-container{padding-bottom:10rem!important}
  .st-key-main_nav{position:fixed!important;top:auto!important;bottom:calc(3.65rem + env(safe-area-inset-bottom, 0px))!important;left:50%!important;transform:translateX(-50%)!important;width:calc(100% - 1.6rem)!important;max-width:680px!important;z-index:1001!important;margin:0!important;padding:.34rem!important;border:1px solid rgba(23,32,42,.10)!important;border-radius:18px!important;background:rgba(245,244,240,.97)!important;box-shadow:0 12px 34px rgba(23,32,42,.16)!important;backdrop-filter:blur(18px)!important;-webkit-backdrop-filter:blur(18px)!important}
  .st-key-main_nav button{min-height:39px!important;padding-left:.34rem!important;padding-right:.34rem!important}
  .wisdom-strip{padding:8px 10px;margin-bottom:9px}.wisdom-verse{font-size:.68rem}.wisdom-question{font-size:.77rem}.db-grid{grid-template-columns:repeat(3,minmax(0,1fr))}
}
</style>
"""

DARK_CSS = r"""
<style>
.stApp{background:#101319!important;color:#EDF1F7!important}
.alam-brand,.section-title,.story-title,.detail-title,.category-name{color:#F5F7FA!important}
.story-card,.detail-shell,.category-tile,.metric-mini,.pulse-card,.claim-box,.source-card,.pr-cell,.reading-box,.mind-change,.panel-card,.mobile-brief-card,.wisdom-strip,.db-chip{background:rgba(27,32,42,.96)!important;border-color:rgba(255,255,255,.10)!important;color:#EDF1F7!important}
.story-summary,.detail-summary,.detail-body,.panel-body,.category-q,.small-muted,.source-meta,.story-meta,.story-age,.wisdom-verse,.saved-sync{color:#AEB8C7!important}
.so-what,.mobile-bottomline{background:#202633!important;color:#DDE5EF!important}
.st-key-main_nav{background:rgba(16,19,25,.96)!important;border-color:rgba(255,255,255,.12)!important}
</style>
"""


def install_extras_css():
    st.markdown(EXTRA_CSS, unsafe_allow_html=True)
    if st.session_state.get("alam_dark_mode"):
        st.markdown(DARK_CSS, unsafe_allow_html=True)


def _load_local_article_records():
    """Temporary GitHub/local fallback during the Supabase content migration."""
    records = []
    for folder in ARTICLE_DIRS:
        if not folder.exists():
            continue
        for path in sorted(folder.rglob("*.json")):
            if path.name.startswith("_"):
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                batch = payload if isinstance(payload, list) else [payload]
                for idx, item in enumerate(batch):
                    if not isinstance(item, dict) or not item.get("id") or not item.get("title"):
                        continue
                    copy = dict(item)
                    copy["_path"] = str(path.relative_to(DATA_DIR.parent))
                    copy["_category"] = normalize_category(copy)
                    copy["_record_key"] = f"{copy['_path']}::{idx}"
                    copy["_storage"] = "local"
                    records.append(copy)
            except Exception:
                continue
    return sorted(records, key=lambda r: parse_dt(r.get("created_at")), reverse=True)


@st.cache_data(ttl=45)
def load_article_records():
    """Prefer Supabase; keep local JSON only as a safe migration fallback.

    Supabase current rows and read-only version rows are combined so ALAM's existing
    story timeline continues to work. `latest_by_story` still picks only the newest
    version for the public feed.
    """
    supabase_records, supabase_error = load_published_articles()
    if supabase_records:
        st.session_state["alam_content_source"] = "supabase"
        st.session_state.pop("alam_supabase_content_error", None)

        history, history_error = load_article_history([r.get("id") for r in supabase_records])
        if history_error:
            st.session_state["alam_supabase_history_error"] = history_error
            history = []
        else:
            st.session_state.pop("alam_supabase_history_error", None)

        # Ingestion stores the current record in article_versions too. Remove the
        # exact duplicate so counts/timelines remain clean while retaining all older versions.
        current_keys = {
            (str(r.get("id")), parse_dt(r.get("created_at")).isoformat())
            for r in supabase_records
        }
        older = [
            r for r in history
            if (str(r.get("id")), parse_dt(r.get("created_at")).isoformat()) not in current_keys
        ]
        combined = older + supabase_records
        return sorted(combined, key=lambda r: parse_dt(r.get("created_at")), reverse=True)

    if supabase_error:
        st.session_state["alam_supabase_content_error"] = supabase_error
    else:
        st.session_state.pop("alam_supabase_content_error", None)
    st.session_state["alam_content_source"] = "local_fallback"
    return _load_local_article_records()


def _load_local_wisdom():
    if not WISDOM_DIR.exists():
        return None
    rows = []
    for path in WISDOM_DIR.glob("*.json"):
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(row, dict) and row.get("date") and row.get("question"):
                rows.append(row)
        except Exception:
            continue
    if not rows:
        return None
    rows.sort(key=lambda r: str(r.get("date")))
    today = datetime.now(JST).date().isoformat()
    eligible = [r for r in rows if str(r.get("date")) <= today]
    return eligible[-1] if eligible else rows[-1]


@st.cache_data(ttl=60)
def load_latest_wisdom():
    if st.session_state.get("alam_content_source") == "supabase":
        item, error = load_latest_wisdom_from_db()
        if item:
            return item
        if error:
            st.session_state["alam_supabase_wisdom_error"] = error
    return _load_local_wisdom()


def render_wisdom_strip():
    item = load_latest_wisdom()
    if not item:
        return
    verse_html = []
    for verse in (item.get("verses") or [])[:2]:
        if not isinstance(verse, dict) or not verse.get("reference") or not verse.get("text"):
            continue
        translation = f" ({verse.get('translation')})" if verse.get("translation") else ""
        verse_html.append(
            f'<div class="wisdom-verse"><strong>{verse["reference"]}{translation}</strong> — “{verse["text"]}”</div>'
        )
    question = str(item.get("question", ""))
    based_on = str(item.get("based_on", "yesterday"))
    st.markdown(
        '<div class="wisdom-strip">'
        + ''.join(verse_html)
        + f'<div class="wisdom-question">Yesterday · {based_on} — {question}</div></div>',
        unsafe_allow_html=True,
    )


def _haystack(record):
    pieces = [
        record.get("title", ""), record.get("summary", ""), record.get("why_it_matters", ""),
        " ".join(str(x) for x in record.get("tags", []) or []),
        " ".join(str(x) for x in record.get("geography", []) or []),
        json.dumps(record.get("content") or {}, ensure_ascii=False),
    ]
    return " ".join(str(x) for x in pieces).lower()


def render_search(records, comments, manager, views):
    st.markdown('<div class="hero mobile-hero"><div class="hero-kicker">🔎 SEARCH</div><div class="hero-title">Hanapin ang signal, hindi lang ang headline.</div><div class="hero-copy">Search titles, summaries, tags, places and article details.</div></div>', unsafe_allow_html=True)
    query = st.text_input("Search ALAM", placeholder="e.g. visa, gasoline, semiconductors, JGB, scam...")
    categories = st.multiselect("Lens", ["Discover", "Action", "Market", "Trends"], default=[], placeholder="All lenses")
    key_map = {"Discover": "discover", "Action": "practical", "Market": "reflection", "Trends": "trend"}
    wanted = {key_map[x] for x in categories}
    matches = records
    if wanted:
        matches = [r for r in matches if r.get("_category") in wanted]
    if query.strip():
        terms = [x.lower() for x in query.split() if x.strip()]
        matches = [r for r in matches if all(t in _haystack(r) for t in terms)]
    matches = sorted(matches, key=feed_score, reverse=True)
    st.caption(f"{len(matches)} matching current topics")
    if not matches:
        st.info("No matching current topic.")
        return
    cols = st.columns(2, wrap=True)
    for i, record in enumerate(matches[:40]):
        with cols[i % 2]:
            views.render_card(record, f"search_{i}", manager, comments)


def _encode_saved(ids):
    raw = json.dumps(sorted({str(x) for x in ids}), separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_saved(code):
    code = str(code or "").strip()
    if not code:
        return []
    padded = code + "=" * (-len(code) % 4)
    raw = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
    value = json.loads(raw)
    return [str(x) for x in value] if isinstance(value, list) else []


def render_saved(records, manager, comments, views):
    saved = [r for r in records if is_followed(r.get("id"))]
    st.markdown('<div class="hero mobile-hero"><div class="hero-kicker">🔖 SAVED</div><div class="hero-title">Keep what matters.</div><div class="hero-copy">Saved topics persist in this browser. Use a sync code to move the list to another device.</div></div>', unsafe_allow_html=True)
    if saved:
        cols = st.columns(2, wrap=True)
        for i, record in enumerate(sorted(saved, key=feed_score, reverse=True)):
            with cols[i % 2]:
                views.render_card(record, f"saved_{i}", manager, comments)
    else:
        st.info("No saved topics yet. Open a story and tap + Bantayan.")
    st.markdown("#### Saved sync")
    code = _encode_saved(st.session_state.get("followed_stories", []))
    st.code(code or "(nothing saved)", language=None)
    incoming = st.text_input("Import saved sync code", key="saved_sync_import")
    if st.button("Import saved list", use_container_width=True, disabled=not incoming.strip()):
        try:
            ids = _decode_saved(incoming)
            st.session_state["followed_stories"] = ids
            if manager:
                try:
                    manager.set("alam_followed", json.dumps(ids), expires_at=datetime.now() + timedelta(days=365), key="import_followed")
                except Exception:
                    pass
            st.success(f"Imported {len(ids)} saved topic IDs.")
            st.rerun()
        except Exception:
            st.error("Invalid saved sync code.")


def _render_db_health():
    health, error = database_public_health()
    if error:
        st.caption("Core connection works, but the full ALAM schema is not ready yet.")
        st.caption(error)
        return
    cells = []
    for label in ("articles", "sources", "comments", "predictions", "wisdom"):
        value = health.get(label)
        shown = "—" if value is None else str(value)
        cells.append(f'<div class="db-chip"><div class="db-value">{shown}</div><div class="db-label">{label}</div></div>')
    st.markdown('<div class="db-grid">' + ''.join(cells) + '</div>', unsafe_allow_html=True)


def render_settings():
    st.markdown('<div class="hero mobile-hero"><div class="hero-kicker">⚙ SETTINGS</div><div class="hero-title">Display</div></div>', unsafe_allow_html=True)
    enabled = st.toggle("Dark mode", value=bool(st.session_state.get("alam_dark_mode")), key="dark_toggle")
    if enabled != bool(st.session_state.get("alam_dark_mode")):
        st.session_state["alam_dark_mode"] = enabled
        st.rerun()
    st.caption("Dark mode is stored for this current app session.")

    st.divider()
    st.markdown("#### Database")
    connected, detail = check_supabase_connection()
    if connected:
        st.success("Supabase connected")
        source = st.session_state.get("alam_content_source")
        if source == "supabase":
            st.caption("Live article feed: Supabase · GitHub remains the agent audit trail.")
        elif source == "local_fallback":
            st.caption("Database connection is healthy, but the feed is temporarily using local migration fallback data.")
        else:
            st.caption("ALAM can read the Supabase database using the configured publishable key.")
        _render_db_health()
        content_error = st.session_state.get("alam_supabase_content_error")
        if content_error:
            st.warning("Supabase article storage is not ready yet. Local fallback remains active.")
            st.caption(content_error)
        history_error = st.session_state.get("alam_supabase_history_error")
        if history_error and source == "supabase":
            st.caption("Current feed is live, but story-history migration still needs the history policy migration.")
    else:
        st.error("Supabase connection failed")
        st.caption(detail)

    if st.button("Test Supabase again", key="test_supabase_connection", use_container_width=True):
        check_supabase_connection.clear()
        database_public_health.clear()
        load_published_articles.clear()
        load_article_history.clear()
        load_latest_wisdom_from_db.clear()
        load_article_records.clear()
        load_latest_wisdom.clear()
        st.rerun()


def render_share_tools(record):
    with st.expander("Share / copy summary"):
        parts = [record.get("title", ""), record.get("summary", "")]
        why = record.get("why_it_matters")
        if why:
            parts.append("Why it matters: " + str(why))
        parts.append("ALAM")
        st.code("\n\n".join(x for x in parts if x), language=None)
        st.caption("Use the copy button in the box above, then share it in any app.")
