import base64
import hashlib
import html
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import streamlit as st

from alam_core import (
    CATEGORY_META,
    age_label,
    category_meta,
    esc,
    feed_score,
    is_followed,
    parse_dt,
    source_quality,
    summarize_so_what,
    toggle_follow,
    type_label,
)

APP_DIR = Path(__file__).resolve().parent
LOGO_PATH = APP_DIR / "assets" / "alam_logo.svg"

BRAND_CSS = r"""
<style>
.brand-lockup{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:2px 0 10px}.brand-lockup img{display:block;width:min(330px,72vw);height:auto}.brand-updated{display:inline-flex;align-items:center;gap:7px;white-space:nowrap;border-radius:999px;padding:7px 10px;background:rgba(8,125,91,.10);color:#087454;font-size:.72rem;font-weight:900}.brand-dot{width:8px;height:8px;border-radius:50%;background:#0B9A74;box-shadow:0 0 0 5px rgba(11,154,116,.11)}
.article-visual{position:relative;width:100%;aspect-ratio:16/9;border-radius:16px;overflow:hidden;background:#E9EEF5;margin:9px 0 12px;border:1px solid rgba(23,32,42,.06)}.article-visual img{display:block;width:100%;height:100%;object-fit:cover}.article-visual.hero{border-radius:21px;margin:0}.image-credit{position:absolute;right:8px;bottom:7px;max-width:75%;background:rgba(17,43,74,.72);color:white;border-radius:999px;padding:4px 7px;font-size:.58rem;line-height:1.2;backdrop-filter:blur(8px)}
.top-story-wrap{display:grid;grid-template-columns:minmax(0,1.05fr) minmax(0,.95fr);gap:16px;align-items:stretch;margin:4px 0 12px}.top-story-copy{display:flex;flex-direction:column;justify-content:center;border:1px solid rgba(23,32,42,.07);border-radius:22px;padding:24px;background:rgba(255,255,255,.92);box-shadow:0 10px 30px rgba(23,32,42,.05)}.top-story-copy .hero-kicker{margin-bottom:8px}.top-story-title{font-size:clamp(1.6rem,4vw,2.7rem);line-height:1.02;letter-spacing:-.045em;font-weight:950}.top-story-summary{font-size:.96rem;line-height:1.55;color:#536173;margin-top:10px}
.st-key-main_nav div[data-testid="stPills"]>div,.st-key-main_nav [role="listbox"]{flex-wrap:nowrap!important;overflow-x:auto!important;scrollbar-width:none}.st-key-main_nav div[data-testid="stPills"]>div::-webkit-scrollbar{display:none}.st-key-main_nav button{flex:0 0 auto!important;white-space:nowrap!important}
@media(max-width:760px){.brand-lockup{align-items:flex-start}.brand-lockup img{width:min(275px,73vw)}.brand-updated{font-size:.65rem;padding:6px 8px}.top-story-wrap{grid-template-columns:1fr;gap:8px}.top-story-copy{padding:18px 16px;border-radius:18px}.top-story-title{font-size:1.62rem}.article-visual.hero{border-radius:18px}.story-card .article-visual{margin:8px 0 10px;border-radius:14px}}
</style>
"""


def _logo_data_uri():
    try:
        payload = LOGO_PATH.read_bytes()
    except OSError:
        return ""
    return "data:image/svg+xml;base64," + base64.b64encode(payload).decode("ascii")


def render_brand(records):
    latest = max((parse_dt(r.get("created_at")) for r in records), default=None)
    updated = age_label(latest) if latest else "waiting"
    logo = _logo_data_uri()
    if logo:
        brand = f'<img src="{logo}" alt="ALAM — See · Understand · Act">'
    else:
        brand = '<div style="font-size:1.8rem;font-weight:950">ALAM <small>See · Understand · Act</small></div>'
    st.markdown(
        f'<div class="brand-lockup">{brand}<div class="brand-updated"><span class="brand-dot"></span>{esc(updated)}</div></div>',
        unsafe_allow_html=True,
    )


def _external_image(record):
    candidates = [
        record.get("image_url"),
        record.get("hero_image"),
        record.get("thumbnail_url"),
    ]
    content = record.get("content") or {}
    image_obj = record.get("image") or content.get("image") or {}
    if isinstance(image_obj, dict):
        candidates.extend([image_obj.get("url"), image_obj.get("image_url")])
    candidates.extend([content.get("image_url"), content.get("hero_image")])
    for candidate in candidates:
        if candidate and urlparse(str(candidate)).scheme in {"http", "https"}:
            return str(candidate)
    return ""


def _image_credit(record):
    content = record.get("content") or {}
    image_obj = record.get("image") or content.get("image") or {}
    values = [record.get("image_credit"), content.get("image_credit")]
    if isinstance(image_obj, dict):
        values.extend([image_obj.get("credit"), image_obj.get("caption")])
    return next((str(v) for v in values if v), "")


def _svg_data_uri(record):
    meta = category_meta(record)
    category = str(record.get("_category") or "discover")
    accent = meta.get("accent", "#5968F2")
    soft = meta.get("soft", "#EEF0FF")
    digest = hashlib.sha256(str(record.get("id", record.get("title", "alam"))).encode("utf-8")).digest()
    x1 = 760 + digest[0] % 210
    y1 = 105 + digest[1] % 150
    r1 = 150 + digest[2] % 120
    x2 = 230 + digest[3] % 250
    y2 = 380 + digest[4] % 130
    tags = [str(x) for x in (record.get("tags") or []) if x][:2]
    line1 = html.escape((tags[0] if tags else meta.get("label", "ALAM")).upper()[:28])
    line2 = html.escape((tags[1] if len(tags) > 1 else meta.get("question", "Worth knowing"))[:40])

    art = {
        "discover": '<circle cx="930" cy="325" r="126" fill="none" stroke="white" stroke-width="7" opacity=".42"/><circle cx="930" cy="325" r="74" fill="none" stroke="white" stroke-width="5" opacity=".62"/><line x1="930" y1="325" x2="1080" y2="210" stroke="white" stroke-width="7" stroke-linecap="round" opacity=".7"/><circle cx="1080" cy="210" r="14" fill="#FFD35A"/>',
        "practical": '<rect x="790" y="190" width="285" height="310" rx="34" fill="white" opacity=".18"/><path d="M835 272 l25 25 48-58 M835 360 l25 25 48-58 M835 448 l25 25 48-58" fill="none" stroke="white" stroke-width="14" stroke-linecap="round" stroke-linejoin="round"/><line x1="930" y1="268" x2="1030" y2="268" stroke="white" stroke-width="11" stroke-linecap="round" opacity=".72"/><line x1="930" y1="356" x2="1030" y2="356" stroke="white" stroke-width="11" stroke-linecap="round" opacity=".72"/><line x1="930" y1="444" x2="1030" y2="444" stroke="white" stroke-width="11" stroke-linecap="round" opacity=".72"/>',
        "reflection": '<circle cx="930" cy="295" r="115" fill="#FFD7A0" opacity=".8"/><path d="M690 465 Q930 295 1170 465" fill="none" stroke="white" stroke-width="13" opacity=".7"/><path d="M735 498 Q930 350 1125 498" fill="none" stroke="white" stroke-width="8" opacity=".42"/>',
        "trend": '<path d="M760 465 C835 425 830 345 900 350 C970 355 968 270 1030 280 C1090 290 1095 195 1160 175" fill="none" stroke="white" stroke-width="16" stroke-linecap="round"/><circle cx="760" cy="465" r="14" fill="#FFD35A"/><circle cx="900" cy="350" r="14" fill="#FFD35A"/><circle cx="1030" cy="280" r="14" fill="#FFD35A"/><circle cx="1160" cy="175" r="14" fill="#FFD35A"/>',
    }.get(category, "")

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 675">
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{soft}"/><stop offset=".42" stop-color="{accent}"/><stop offset="1" stop-color="#112B4A"/></linearGradient><filter id="b"><feGaussianBlur stdDeviation="38"/></filter></defs>
<rect width="1200" height="675" fill="url(#g)"/><circle cx="{x1}" cy="{y1}" r="{r1}" fill="white" opacity=".11" filter="url(#b)"/><circle cx="{x2}" cy="{y2}" r="190" fill="#FFD35A" opacity=".10" filter="url(#b)"/>
<path d="M76 542 L220 254 L364 542 L304 542 L220 374 L136 542 Z" fill="white" opacity=".17"/><path d="M146 514 L220 422 L260 470 L286 445 L336 514 Z" fill="white" opacity=".34"/>
{art}
<text x="72" y="88" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="27" font-weight="800" letter-spacing="4" fill="white" opacity=".78">ALAM EDITORIAL</text>
<text x="72" y="162" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="61" font-weight="900" letter-spacing="-2" fill="white">{line1}</text>
<text x="76" y="210" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="27" font-weight="650" fill="white" opacity=".86">{line2}</text>
<text x="74" y="618" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="24" font-weight="700" fill="white" opacity=".72">See · Understand · Act</text>
</svg>'''
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")


def article_image_html(record, hero=False, show_credit=False):
    source = _external_image(record) or _svg_data_uri(record)
    credit = _image_credit(record) if show_credit and _external_image(record) else ""
    alt = record.get("image_alt") or f"Editorial visual for {record.get('title', 'ALAM article')}"
    credit_html = f'<div class="image-credit">{esc(credit)}</div>' if credit else ""
    hero_class = " hero" if hero else ""
    return f'<div class="article-visual{hero_class}"><img src="{esc(source)}" alt="{esc(alt)}" loading="lazy">{credit_html}</div>'


def install_visual_system(views):
    def card_html(record, comments=None):
        meta = category_meta(record)
        total, strong = source_quality(record)
        so_what = summarize_so_what(record)
        ref = st.session_state.get("visit_reference")
        chips = []
        if ref and parse_dt(record.get("created_at")).astimezone(timezone.utc) > ref.astimezone(timezone.utc):
            chips.append('<span class="status-chip">NEW</span>')
        try:
            new_comments = views._new_comment_count(comments, record.get("id"))
        except Exception:
            new_comments = 0
        if new_comments:
            chips.append(f'<span class="status-chip comment">{new_comments} new comments</span>')
        status = '<div class="story-status">' + ''.join(chips) + '</div>' if chips else ''
        return (
            '<div class="story-card">'
            f'<div class="story-accent" style="background:{meta["accent"]}"></div>'
            f'<div class="story-topline"><div class="story-label" style="margin:0;background:{meta["soft"]};color:{meta["accent"]}">{esc(type_label(record))}</div><div class="story-age">{esc(age_label(record.get("created_at")))}</div></div>'
            + status
            + article_image_html(record)
            + f'<div class="story-title">{esc(record.get("title", "Untitled"))}</div>'
            + f'<div class="story-summary">{esc(views._compact(record.get("summary")))}</div>'
            + (f'<div class="so-what"><strong>Why care:</strong> {esc(views._compact(so_what, 210))}</div>' if so_what else '')
            + f'<div class="story-meta" style="margin-top:10px"><span>{int(record.get("confidence", 0) or 0)}% confidence</span><span>{total} sources</span>'
            + (f'<span>{strong} primary/official</span>' if strong else '')
            + '</div></div>'
        )

    def render_today(all_records, records, comments=None, manager=None):
        if not records:
            st.info("Wala pang intelligence records.")
            return
        views._render_urgent(records)
        top = max(records, key=feed_score)
        st.markdown(
            '<div class="top-story-wrap">'
            + article_image_html(top, hero=True)
            + '<div class="top-story-copy"><div class="hero-kicker">🔥 TOP STORY</div>'
            + f'<div class="top-story-title">{esc(top.get("title", ""))}</div>'
            + f'<div class="top-story-summary">{esc(views._compact(top.get("summary"), 420))}</div></div></div>',
            unsafe_allow_html=True,
        )
        if st.button("Basahin ang top story →", key="hero_story", use_container_width=True):
            views._open_story(top)
        views._render_since(records, comments)
        mode = st.segmented_control("Briefing depth", ["⚡ 5 min", "📚 More", "🎲 Surprise"], default="⚡ 5 min", key="today_mode_mobile", label_visibility="collapsed", width="stretch")
        if mode == "⚡ 5 min":
            picks = []
            for category in CATEGORY_META:
                subset = [r for r in records if r.get("_category") == category]
                if subset:
                    picks.append(max(subset, key=feed_score))
        elif mode == "📚 More":
            picks = sorted(records, key=feed_score, reverse=True)[:8]
        else:
            pool = sorted(records, key=feed_score, reverse=True)[:min(15, len(records))]
            picks = [random.Random(datetime.now().strftime("%Y-%m-%d-%H")).choice(pool)] if pool else []
        st.markdown('<div class="section-eyebrow">Briefing</div><div class="section-title">Worth your attention ngayon</div>', unsafe_allow_html=True)
        cols = st.columns(2, wrap=True)
        for i, record in enumerate(picks):
            with cols[i % 2]:
                views.render_card(record, f"today_{i}", manager, comments)
        growing = [r for r in records if r.get("_category") == "trend" and str((r.get("content") or {}).get("direction", "")).upper() == "ACCELERATING" and 45 <= int((r.get("content") or {}).get("current_strength", r.get("importance", 0)) or 0) < 85]
        if growing:
            with st.expander("Quietly becoming important"):
                for i, record in enumerate(growing[:3]):
                    views.render_card(record, f"quiet_{i}", manager, comments)
        with st.expander("Signal map · how active are the four lenses?"):
            for key in CATEGORY_META:
                meta = CATEGORY_META[key]
                score = views._pulse_score(records, key)
                state = "Active" if score >= 70 else "Moving" if score >= 50 else "Quiet"
                st.markdown(f'<div class="pulse-card"><div class="pulse-row"><strong>{meta["emoji"]} {esc(meta["label"])}</strong><span>{score} · {state}</span></div><div class="pulse-bar-bg"><div class="pulse-bar" style="width:{score}%;background:{meta["accent"]}"></div></div></div>', unsafe_allow_html=True)

    def render_detail(all_records, record, comments, manager=None):
        if st.button("← Balik", key="back_detail"):
            st.session_state.pop("selected_story", None)
            st.rerun()
        meta = category_meta(record)
        total, strong = source_quality(record)
        tags = " · ".join(str(x) for x in record.get("tags", [])[:5])
        st.markdown(
            f'<div class="detail-shell"><div class="story-topline"><div class="story-label" style="margin:0;background:{meta["soft"]};color:{meta["accent"]}">{esc(type_label(record))}</div><div class="story-age">{esc(age_label(record.get("created_at")))}</div></div>'
            f'<div class="detail-title">{esc(record.get("title", ""))}</div><div class="detail-summary">{esc(record.get("summary", ""))}</div><div class="story-meta" style="margin-top:14px"><span>{int(record.get("confidence", 0) or 0)}% confidence</span><span>{total} sources</span><span>{strong} primary/official</span><span>{esc(tags)}</span></div></div>',
            unsafe_allow_html=True,
        )
        st.markdown(article_image_html(record, hero=True, show_credit=True), unsafe_allow_html=True)
        label = "✓ Binabantayan" if is_followed(record["id"]) else "+ Bantayan"
        if st.button(label, key=f"detail_follow_mobile_{record['id']}", use_container_width=True):
            toggle_follow(record["id"], manager)
            st.rerun()
        mode = st.segmented_control("View", ["⚡ 30 sec", "🗣 Panel", "🧾 Evidence", "🧠 Deep"], default="⚡ 30 sec", key=f"detail_mode_{record['id']}", label_visibility="collapsed", width="stretch")
        if mode == "🗣 Panel":
            views._render_panel(record, comments)
        elif mode == "🧾 Evidence":
            views._render_pr_vs_reality(record)
            views._render_claims(record)
            views._render_timeline(all_records, record)
            views._render_sources(record)
        elif mode == "🧠 Deep":
            views._render_deep(record, all_records, comments)
        else:
            views._render_30sec(record)

    views.render_brand = render_brand
    views._card_html = card_html
    views.render_today = render_today
    views.render_detail = render_detail
