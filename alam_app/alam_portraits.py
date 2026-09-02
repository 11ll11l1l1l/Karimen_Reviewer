from functools import lru_cache
from pathlib import Path

import streamlit as st

from alam_core import age_label, esc
from alam_personas import comments_for_story, persona_for_comment

APP_DIR = Path(__file__).resolve().parent
PORTRAIT_DIR = APP_DIR / "assets" / "personas"

LENS_LABELS = {
    "discover": "Discover",
    "practical": "Practical",
    "reflection": "Market",
    "trend": "Trend",
}

PERSONA_LENS = {
    "kiko-kuryoso": "discover",
    "mara-teka": "discover",
    "mika-sulit": "practical",
    "ramon-ingat": "practical",
    "jiro-daloy": "reflection",
    "aya-presyo": "reflection",
    "nico-signal": "trend",
    "bea-base-rate": "trend",
}

PORTRAIT_CSS = r"""
<style>
.panel-face-photo{width:52px;height:52px;min-width:52px;border-radius:50%;object-fit:cover;display:block;border:2px solid rgba(255,255,255,.96);box-shadow:0 4px 13px rgba(23,32,42,.16);background:#edf0f4}
.panel-thread-item .panel-face-photo{width:44px;height:44px;min-width:44px}
.panel-no-photo{width:52px;height:52px;min-width:52px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:#eef1f5;font-size:1.25rem}
@media(max-width:760px){.panel-face-photo,.panel-no-photo{width:48px;height:48px;min-width:48px}.panel-thread-item .panel-face-photo{width:42px;height:42px;min-width:42px}}
</style>
"""


@lru_cache(maxsize=16)
def portrait_uri(persona_id):
    path = PORTRAIT_DIR / f"{persona_id}.b64"
    try:
        payload = path.read_text(encoding="ascii").strip()
    except OSError:
        return ""
    if not payload:
        return ""
    return "data:image/webp;base64," + payload


def _portrait(persona):
    uri = portrait_uri(str(persona.get("id") or ""))
    if uri:
        return f'<img class="panel-face-photo" src="{uri}" alt="Portrait of {esc(persona.get("name", "panel voice"))}">'
    return f'<span class="panel-no-photo">{esc(persona.get("emoji", "💬"))}</span>'


def _comment_lens(comment):
    raw = str(comment.get("agent") or comment.get("lens") or "").lower()
    if raw in LENS_LABELS:
        return raw
    return PERSONA_LENS.get(str(comment.get("persona_id") or ""), "")


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
        'Same evidence, four useful angles: what is new, what it means in practice, market impact, and the longer-term pattern.</div>',
        unsafe_allow_html=True,
    )

    cards = []
    for lens in ("discover", "practical", "reflection", "trend"):
        comment = latest.get(lens)
        if comment:
            persona = persona_for_comment(comment)
            cards.append(
                '<div class="panel-card"><div class="panel-head">'
                + _portrait(persona)
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
            '<div class="panel-thread-item">' + _portrait(persona) + '<div>'
            f'<div class="panel-persona-name">{esc(persona.get("name", "ALAM Voice"))}</div>'
            f'<div class="panel-role">{esc(persona.get("role", "Perspective"))} · {esc(age_label(comment.get("created_at")))}</div>'
            + reply_line + f'<div class="panel-body" style="margin-top:6px">{esc(comment.get("body", ""))}</div>'
            + '</div></div>',
            unsafe_allow_html=True,
        )


def install(views):
    views._render_panel = render_panel
    views._render_full_thread = render_full_thread
