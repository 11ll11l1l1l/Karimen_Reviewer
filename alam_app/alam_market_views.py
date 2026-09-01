import json

import streamlit as st

from alam_core import CATEGORY_META, esc, feed_score, is_followed, parse_dt

MARKET_TYPES = {"market_outlook", "market_recap", "market_risk", "market_regime"}


def is_market_record(record):
    return record.get("_category") == "reflection" and str(record.get("type", "")).lower() in MARKET_TYPES


def render_market(records, manager=None, comments=None, views=None):
    subset = [r for r in records if is_market_record(r)]
    meta = CATEGORY_META["reflection"]
    st.markdown(
        f'<div class="hero mobile-hero"><div class="hero-kicker" style="color:{meta["accent"]}">{meta["emoji"]} MARKET INTELLIGENCE</div>'
        '<div class="hero-title">Ano ang gumagalaw sa Japan market?</div>'
        '<div class="hero-copy">Explain the move, trace the global-to-Japan transmission, then separate daily noise from what may matter next session, next week, and 1–3 months.</div></div>',
        unsafe_allow_html=True,
    )
    if not subset:
        st.markdown('<div class="empty-box">Wala pang market-intelligence article. The first pre-market/close outlook will appear when Agent 3 publishes a qualifying update.</div>', unsafe_allow_html=True)
        return

    latest = max(subset, key=lambda r: parse_dt(r.get("created_at")))
    content = latest.get("content") or {}
    regime = content.get("market_regime") or "WATCH"
    bias = content.get("opening_bias")
    session = content.get("session") or "Latest outlook"
    st.markdown(
        '<div class="mobile-brief">'
        f'<div class="mobile-brief-card"><div class="mobile-brief-value">{esc(session)}</div><div class="mobile-brief-label">session</div></div>'
        f'<div class="mobile-brief-card"><div class="mobile-brief-value">{esc(regime)}</div><div class="mobile-brief-label">market regime</div></div>'
        f'<div class="mobile-brief-card"><div class="mobile-brief-value">{esc(bias or "—")}</div><div class="mobile-brief-label">opening bias</div></div>'
        '</div>',
        unsafe_allow_html=True,
    )

    search = st.text_input("Hanapin", placeholder="Search yen, BOJ, semiconductors, rates…", key="search_market_mobile", type="search", label_visibility="collapsed")
    filt = st.pills("Market filter", ["All", "Pre-market", "Close", "Risk", "Following"], default="All", required=True, key="filter_market_mobile", label_visibility="collapsed", width="stretch")
    if search:
        q = search.lower().strip()
        subset = [r for r in subset if q in json.dumps(r, ensure_ascii=False).lower()]
    if filt == "Pre-market":
        subset = [r for r in subset if "pre" in str((r.get("content") or {}).get("session", "")).lower() or (r.get("content") or {}).get("opening_bias")]
    elif filt == "Close":
        subset = [r for r in subset if "close" in str((r.get("content") or {}).get("session", "")).lower() or str(r.get("type", "")).lower() == "market_recap"]
    elif filt == "Risk":
        subset = [r for r in subset if str(r.get("type", "")).lower() == "market_risk" or "risk" in json.dumps(r.get("content") or {}, ensure_ascii=False).lower()]
    elif filt == "Following":
        subset = [r for r in subset if is_followed(r.get("id"))]

    if not subset:
        st.markdown('<div class="empty-box">Walang matching market outlook ngayon.</div>', unsafe_allow_html=True)
        return

    subset.sort(key=feed_score, reverse=True)
    cols = st.columns(2, wrap=True)
    for i, record in enumerate(subset):
        with cols[i % 2]:
            views.render_card(record, f"market_{i}", manager, comments)
