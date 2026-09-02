import base64
import json
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

from alam_core import DATA_DIR, category_meta, esc, feed_score, is_followed, parse_dt, toggle_follow, type_label

WISDOM_DIR = DATA_DIR / "wisdom"

EXTRA_CSS = r"""
<style>
.wisdom-strip{margin:-2px 0 12px;padding:9px 12px 10px;border:1px solid rgba(23,32,42,.08);border-radius:15px;background:rgba(255,255,255,.66)}
.wisdom-verse{font-size:.73rem;line-height:1.35;color:#667085}
.wisdom-verse strong{color:#344054}
.wisdom-question{font-size:.82rem;line-height:1.38;font-weight:760;color:#273142;margin-top:6px}
.saved-sync{font-size:.76rem;color:#667085;line-height:1.45}
.search-result-meta{font-size:.70rem;color:#98A2B3;margin:-3px 0 7px}
@media(max-width:760px){
  .block-container{padding-bottom:7.2rem!important}
  .st-key-main_nav{position:fixed!important;top:auto!important;bottom:.55rem!important;left:50%!important;transform:translateX(-50%)!important;width:calc(100% - 1rem)!important;max-width:720px!important;z-index:1001!important;margin:0!important;padding:.38rem!important;border:1px solid rgba(23,32,42,.10)!important;border-radius:19px!important;background:rgba(245,244,240,.96)!important;box-shadow:0 14px 40px rgba(23,32,42,.18)!important;backdrop-filter:blur(18px)!important;-webkit-backdrop-filter:blur(18px)!important}
  .wisdom-strip{padding:8px 10px;margin-bottom:9px}.wisdom-verse{font-size:.68rem}.wisdom-question{font-size:.77rem}
}
</style>
"""

DARK_CSS = r"""
<style>
.stApp{background:#101319!important;color:#EDF1F7!important}
.alam-brand,.section-title,.story-title,.detail-title,.category-name{color:#F5F7FA!important}
.story-card,.detail-shell,.category-tile,.metric-mini,.pulse-card,.claim-box,.source-card,.pr-cell,.reading-box,.mind-change,.panel-card,.mobile-brief-card,.wisdom-strip{background:rgba(27,32,42,.96)!important;border-color:rgba(255,255,255,.10)!important;color:#EDF1F7!important}
.story-summary,.detail-summary,.detail-body,.panel-body,.category-q,.small-muted,.source-meta,.story-meta,.story-age,.wisdom-verse,.saved-sync{color:#AEB8C7!important}
.so-what,.mobile-bottomline{background:#202633!important;color:#DDE5EF!important}
.st-key-main_nav{background:rgba(16,19,25,.96)!important;border-color:rgba(255,255,255,.12)!important}
</style>
"""


def install_extras_css():
    st.markdown(EXTRA_CSS, unsafe_allow_html=True)
    if st.session_state.get("alam_dark_mode"):
        st.markdown(DARK_CSS, unsafe_allow_html=True)


@st.cache_data(ttl=60)
def load_latest_wisdom():
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
    today = datetime.now(timezone.utc).date().isoformat()
    eligible = [r for r in rows if str(r.get("date")) <= today]
    return eligible[-1] if eligible else rows[-1]


def render_wisdom_strip():
    item = load_latest_wisdom()
    if not item:
        return
    verses = item.get("verses") or []
    verse_html = []
    for verse in verses[:2]:
        if not isinstance(verse, dict) or not verse.get("reference") or not verse.get("text"):
            continue
        translation = f" ({esc(verse.get('translation'))})" if verse.get("translation") else ""
        verse_html.append(
            f'<div class="wisdom-verse"><strong>{esc(verse["reference"])}{translation}</strong> — “{esc(verse["text"])}”</div>'
        )
    question = esc(item.get("question", ""))
    based_on = esc(item.get("based_on", "yesterday"))
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
    categories = st.multiselect(
        "Lens",
        ["Discover", "Action", "Market", "Trends"],
        default=[],
        placeholder="All lenses",
    )
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
                    manager.set("alam_followed", json.dumps(ids), expires_at=datetime.now() + __import__("datetime").timedelta(days=365), key="import_followed")
                except Exception:
                    pass
            st.success(f"Imported {len(ids)} saved topic IDs.")
            st.rerun()
        except Exception:
            st.error("Invalid saved sync code.")


def render_settings():
    st.markdown('<div class="hero mobile-hero"><div class="hero-kicker">⚙ SETTINGS</div><div class="hero-title">Display</div></div>', unsafe_allow_html=True)
    enabled = st.toggle("Dark mode", value=bool(st.session_state.get("alam_dark_mode")), key="dark_toggle")
    if enabled != bool(st.session_state.get("alam_dark_mode")):
        st.session_state["alam_dark_mode"] = enabled
        st.rerun()
    st.caption("Dark mode is stored for this current app session.")


def render_share_tools(record):
    with st.expander("Share / copy summary"):
        parts = [record.get("title", ""), record.get("summary", "")]
        why = record.get("why_it_matters")
        if why:
            parts.append("Why it matters: " + str(why))
        parts.append("ALAM")
        st.code("\n\n".join(x for x in parts if x), language=None)
        st.caption("Use the copy button in the box above, then share it in any app.")
