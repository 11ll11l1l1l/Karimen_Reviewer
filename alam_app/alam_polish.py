import base64
from pathlib import Path
from urllib.parse import urlparse

import streamlit as st

from alam_core import age_label, esc
from alam_personas import comments_for_story, persona_for_comment
import alam_visual_system as visual

APP_DIR = Path(__file__).resolve().parent
ASSET_DIR = APP_DIR / "assets"


def _asset_data_uri(path):
    try:
        payload = Path(path).read_bytes()
    except OSError:
        return ""
    suffix = Path(path).suffix.lower()
    mime = "image/svg+xml" if suffix == ".svg" else "image/png" if suffix == ".png" else "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(payload).decode("ascii")


PANEL_SPRITE = _asset_data_uri(ASSET_DIR / "panel" / "panel_faces.svg")
FALLBACK_IMAGES = {
    "discover": _asset_data_uri(ASSET_DIR / "editorial" / "discover.svg"),
    "practical": _asset_data_uri(ASSET_DIR / "editorial" / "practical.svg"),
    "reflection": _asset_data_uri(ASSET_DIR / "editorial" / "market.svg"),
    "trend": _asset_data_uri(ASSET_DIR / "editorial" / "trend.svg"),
}

FACE_POS = {
    "kiko-kuryoso": "0% 0%",
    "mara-teka": "33.333% 0%",
    "mika-sulit": "66.667% 0%",
    "ramon-ingat": "100% 0%",
    "jiro-daloy": "0% 100%",
    "aya-presyo": "33.333% 100%",
    "nico-signal": "66.667% 100%",
    "bea-base-rate": "100% 100%",
}

LENS_LABELS = {
    "discover": "Discover",
    "practical": "Practical",
    "reflection": "Market",
    "trend": "Trend",
}

POLISH_CSS = f"""
<style>
.panel-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:11px;margin:10px 0 14px}}
.panel-card{{border:1px solid rgba(23,32,42,.09);background:rgba(255,255,255,.94);border-radius:19px;padding:14px;box-shadow:0 6px 20px rgba(23,32,42,.035)}}
.panel-head{{display:flex;align-items:center;gap:10px;margin-bottom:8px}}
.panel-face{{width:50px;height:50px;min-width:50px;border-radius:50%;background-image:url('{PANEL_SPRITE}');background-size:400% 200%;background-repeat:no-repeat;border:2px solid rgba(255,255,255,.9);box-shadow:0 3px 10px rgba(23,32,42,.12)}}
.panel-persona-name{{font-size:.92rem;font-weight:950;line-height:1.05}}
.panel-role{{font-size:.69rem;color:#98A2B3;margin-top:3px}}
.panel-lens{{font-size:.66rem;font-weight:900;letter-spacing:.06em;text-transform:uppercase;color:#667085;margin-bottom:2px}}
.panel-body{{font-size:.87rem;line-height:1.55;color:#344054}}
.panel-summary{{background:#17202A;color:#fff;border-radius:18px;padding:13px 15px;margin:8px 0 12px;font-size:.84rem;line-height:1.48}}
.panel-thread-item{{display:grid;grid-template-columns:44px 1fr;gap:10px;border:1px solid rgba(23,32,42,.08);background:rgba(255,255,255,.88);border-radius:16px;padding:11px;margin:7px 0}}
.panel-thread-item .panel-face{{width:42px;height:42px;min-width:42px}}
.alam-disclaimer{{margin:26px 0 8px;border-top:1px solid rgba(23,32,42,.10);padding:17px 3px 4px;color:#7b8491;font-size:.70rem;line-height:1.55}}
.alam-disclaimer strong{{color:#59616d}}
.article-visual{{background:#e9eef5}}
.article-visual img{{background:#e9eef5}}
@media(max-width:760px){{.panel-grid{{grid-template-columns:1fr}}.panel-card{{padding:13px}}.panel-face{{width:46px;height:46px;min-width:46px}}}}
</style>
"""


def _fallback(record):
    return FALLBACK_IMAGES.get(str(record.get("_category") or "discover"), FALLBACK_IMAGES["discover"])


def _external_image(record):
    candidates = [record.get("image_url"), record.get("hero_image"), record.get("thumbnail_url")]
    content = record.get("content") or {}
    image_obj = record.get("image") or content.get("image") or {}
    if isinstance(image_obj, dict):
        candidates.extend([image_obj.get("url"), image_obj.get("image_url")])
    candidates.extend([content.get("image_url"), content.get("hero_image")])
    for value in candidates:
        if value and urlparse(str(value)).scheme in {"http", "https"}:
            return str(value)
    return ""


def _image_credit(record):
    content = record.get("content") or {}
    image_obj = record.get("image") or content.get("image") or {}
    values = [record.get("image_credit"), content.get("image_credit")]
    if isinstance(image_obj, dict):
        values.extend([image_obj.get("credit"), image_obj.get("caption")])
    return next((str(v) for v in values if v), "")


def article_image_html(record, hero=False, show_credit=False):
    fallback = _fallback(record)
    external = _external_image(record)
    source = external or fallback
    credit = _image_credit(record) if external and show_credit else ""
    alt = record.get("image_alt") or f"Visual for {record.get('title', 'ALAM story')}"
    hero_class = " hero" if hero else ""
    credit_html = f'<div class="image-credit">{esc(credit)}</div>' if credit else ""
    return (
        f'<div class="article-visual{hero_class}">'
        f'<img src="{esc(source)}" alt="{esc(alt)}" loading="lazy" '
        f'onerror="this.onerror=null;this.src=\'{fallback}\';">{credit_html}</div>'
    )


def _comment_lens(comment):
    raw = str(comment.get("agent") or comment.get("lens") or "").lower()
    if raw in LENS_LABELS:
        return raw
    pid = str(comment.get("persona_id") or "")
    if pid in {"kiko-kuryoso", "mara-teka"}:
        return "discover"
    if pid in {"mika-sulit", "ramon-ingat"}:
        return "practical"
    if pid in {"jiro-daloy", "aya-presyo"}:
        return "reflection"
    if pid in {"nico-signal", "bea-base-rate"}:
        return "trend"
    return ""


def _face(persona_id):
    pos = FACE_POS.get(str(persona_id), "0% 0%")
    return f'<span class="panel-face" style="background-position:{pos}"></span>'


def render_panel(record, comments):
    thread = comments_for_story(comments or [], record.get("id"))
    latest = {}
    for comment in thread:
        lens = _comment_lens(comment)
        if lens:
            latest[lens] = comment

    st.markdown("#### 🗣 ALAM Panel")
    st.markdown(
        f'<div class="panel-summary"><strong>{len(latest)}/4 perspectives available.</strong> '
        'Same evidence, different lenses: discovery, practical impact, markets, and longer-term pattern.</div>',
        unsafe_allow_html=True,
    )

    cards = []
    for lens in ("discover", "practical", "reflection", "trend"):
        comment = latest.get(lens)
        if comment:
            persona = persona_for_comment(comment)
            cards.append(
                '<div class="panel-card"><div class="panel-head">'
                + _face(persona.get("id"))
                + '<div><div class="panel-lens">' + esc(LENS_LABELS[lens]) + '</div>'
                + '<div class="panel-persona-name">' + esc(persona.get("name", "ALAM Voice")) + '</div>'
                + '<div class="panel-role">' + esc(persona.get("role", "Perspective")) + '</div></div></div>'
                + '<div class="panel-body">' + esc(comment.get("body", "")) + '</div></div>'
            )
        else:
            cards.append(
                '<div class="panel-card"><div class="panel-lens">' + esc(LENS_LABELS[lens]) + '</div>'
                '<div class="panel-body" style="color:#98A2B3">No additional perspective yet.</div></div>'
            )
    st.markdown('<div class="panel-grid">' + ''.join(cards) + '</div>', unsafe_allow_html=True)
    if thread:
        with st.expander(f"Open full discussion · {len(thread)} notes"):
            render_full_thread(record, comments)


def render_full_thread(record, comments):
    thread = comments_for_story(comments or [], record.get("id"))
    by_id = {str(c.get("id")): c for c in thread}
    for comment in thread:
        persona = persona_for_comment(comment)
        reply = by_id.get(str(comment.get("reply_to") or ""))
        reply_line = ""
        if reply:
            target = persona_for_comment(reply)
            reply_line = f'<div class="small-muted">↳ replying to {esc(target.get("name", "another view"))}</div>'
        st.markdown(
            '<div class="panel-thread-item">' + _face(persona.get("id")) + '<div>'
            f'<div class="panel-persona-name">{esc(persona.get("name", "ALAM Voice"))}</div>'
            f'<div class="panel-role">{esc(persona.get("role", "Perspective"))} · {esc(age_label(comment.get("created_at")))}</div>'
            + reply_line + f'<div class="panel-body" style="margin-top:6px">{esc(comment.get("body", ""))}</div>'
            + '</div></div>',
            unsafe_allow_html=True,
        )


def render_footer(all_records, records, comments):
    live = [r for r in records if not r.get("demo")]
    st.markdown(
        f'<div class="alam-disclaimer"><strong>About ALAM:</strong> {len(records)} current topics · '
        f'{len(all_records)} historical records · {len(live)} live records · {len(comments or [])} perspective notes.<br><br>'
        '<strong>Disclaimer:</strong> ALAM combines automated research, source checking and interpretation. '
        'It can be wrong, incomplete, or become outdated as events change. Verify important facts and decisions '
        'with the cited primary sources. Market commentary is general information, not personalized investment advice.</div>',
        unsafe_allow_html=True,
    )


def render_research_audit(records, all_records, comments, reader):
    st.markdown(
        "<div class='hero mobile-hero'><div class='hero-kicker'>🧪 ALAM AUDIT</div>"
        "<div class='hero-title'>Can ALAM earn your trust?</div>"
        "<div class='hero-copy'>Evidence discipline and update history measured from the archive. "
        "No invented overall trust score.</div></div>",
        unsafe_allow_html=True,
    )
    rows = reader._audit_metrics(all_records, comments)
    cols = st.columns(2, wrap=True)
    for i, row in enumerate(rows):
        with cols[i % 2]:
            st.markdown(
                f"<div class='reader-audit-card'><div class='reader-audit-title'>{esc(row['lens'])}</div>"
                f"<div class='reader-audit-grid'><div><b>{row['stories']}</b><span>stories / 30d</span></div>"
                f"<div><b>{row['strong_source_pct']}%</b><span>primary-quality sources</span></div>"
                f"<div><b>{row['fact_sourced_pct']}%</b><span>FACT claims sourced</span></div>"
                f"<div><b>{row['material_updates']}</b><span>material updates</span></div></div></div>",
                unsafe_allow_html=True,
            )
    st.caption("Forecast wins, misses and corrections remain visible in the prediction and story history views.")


def install(views, reader=None):
    visual.article_image_html = article_image_html
    views._render_panel = render_panel
    views._render_full_thread = render_full_thread
    views.render_footer = render_footer
    if reader is not None:
        reader.render_agent_audit = lambda records, all_records, comments: render_research_audit(records, all_records, comments, reader)
