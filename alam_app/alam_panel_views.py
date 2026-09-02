"""Detailed cross-agent discussion UI for ALAM.ph.

The panel is not a social comment section. Each persona represents a specialist lens,
so the UI should preserve reasoning, uncertainty, evidence references and reply
context instead of compressing every contribution into a decorative one-liner.

This module is installed over ``alam_mobile_views._render_panel`` from the Streamlit
entry point. Keeping it separate avoids further enlarging the already-dense mobile
view module and makes future panel improvements easier to test/review independently.
"""

from __future__ import annotations

from collections import defaultdict

import streamlit as st

from alam_core import CATEGORY_META, age_label, esc
from alam_personas import PERSONAS, comments_for_story, persona_for_comment


PANEL_CSS = r"""
<style>
.alam-panel-summary{background:#17202A;color:#fff;border-radius:18px;padding:14px 16px;margin:8px 0 12px;font-size:.84rem;line-height:1.5}
.alam-panel-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin:10px 0 14px}
.alam-panel-lens{border:1px solid rgba(23,32,42,.09);background:rgba(255,255,255,.96);border-radius:18px;padding:14px;min-width:0}
.alam-panel-lens-top{display:flex;align-items:flex-start;justify-content:space-between;gap:8px}
.alam-panel-agent{font-size:.69rem;font-weight:950;color:#667085;text-transform:uppercase;letter-spacing:.05em}
.alam-panel-count{font-size:.64rem;font-weight:850;color:#98A2B3;white-space:nowrap}
.alam-panel-persona{font-size:.94rem;font-weight:900;margin-top:4px}
.alam-panel-role{font-size:.69rem;color:#667085;margin-top:1px}
.alam-panel-body{font-size:.86rem;line-height:1.58;color:#344054;margin-top:8px;white-space:pre-wrap}
.alam-panel-preview{font-size:.83rem;line-height:1.52;color:#344054;margin-top:8px}
.alam-panel-waiting{font-size:.82rem;line-height:1.45;color:#98A2B3;margin-top:8px}
.alam-stance{display:inline-flex;align-items:center;border-radius:999px;padding:3px 7px;font-size:.60rem;font-weight:950;letter-spacing:.045em;margin-top:6px}
.alam-stance.support{background:#ECFDF3;color:#027A48}.alam-stance.challenge{background:#FFF1F0;color:#B42318}.alam-stance.mixed{background:#FFF7E8;color:#B54708}.alam-stance.neutral{background:#F2F4F7;color:#667085}
.alam-thread-card{border:1px solid rgba(23,32,42,.09);background:rgba(255,255,255,.94);border-radius:17px;padding:14px 15px;margin:9px 0}
.alam-thread-head{display:flex;align-items:flex-start;justify-content:space-between;gap:10px}.alam-thread-persona{font-size:.92rem;font-weight:900}.alam-thread-role{font-size:.70rem;color:#667085;margin-top:1px}
.alam-thread-reply{font-size:.72rem;line-height:1.4;color:#667085;background:#F7F8FA;border-radius:10px;padding:7px 9px;margin-top:8px}
.alam-thread-meta{display:flex;flex-wrap:wrap;gap:6px 10px;color:#98A2B3;font-size:.68rem;margin-top:9px}
.alam-evidence-chip{display:inline-flex;padding:3px 7px;border-radius:999px;background:#F2F4F7;color:#475467;font-size:.62rem;font-weight:800}
@media(max-width:760px){.alam-panel-grid{grid-template-columns:1fr}.alam-panel-lens{padding:13px}.alam-thread-card{padding:13px}.alam-panel-body{font-size:.85rem}.alam-thread-head{gap:6px}}
</style>
"""


def _agent_category(comment):
    """Normalize legacy agent labels to one of ALAM's four public lenses."""
    raw = str(comment.get("agent") or "").lower()
    if "practical" in raw:
        return "practical"
    if "reflection" in raw or "reflect" in raw or "market" in raw:
        return "reflection"
    if "trend" in raw:
        return "trend"
    return "discover"


def _stance(comment):
    value = str(comment.get("stance") or "").strip().upper()
    return value if value in {"SUPPORT", "CHALLENGE", "MIXED"} else ""


def _stance_html(comment):
    stance = _stance(comment)
    css = stance.lower() if stance else "neutral"
    label = stance if stance else "ADDITIONAL VIEW"
    return f'<span class="alam-stance {css}">{esc(label)}</span>'


def _compact(text, limit=360):
    """Compact only the four-lens overview; the full thread always keeps full text."""
    text = str(text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _evidence_summary(comment):
    """Describe evidence attached to a comment without inventing source strength.

    Older comment records may have only ``body``. Newer records can reference article
    sources and/or carry their own claim/source metadata. The renderer is deliberately
    tolerant so richer future records improve automatically without breaking history.
    """
    refs = comment.get("article_source_refs") or []
    claims = comment.get("claims") or []
    sources = comment.get("sources") or []
    parts = []
    if isinstance(refs, list) and refs:
        parts.append(f"{len(refs)} article source ref{'s' if len(refs) != 1 else ''}")
    if isinstance(claims, list) and claims:
        classified = sum(1 for claim in claims if isinstance(claim, dict) and claim.get("classification"))
        parts.append(f"{len(claims)} claim{'s' if len(claims) != 1 else ''}" + (f" · {classified} classified" if classified else ""))
    if isinstance(sources, list) and sources:
        parts.append(f"{len(sources)} added source{'s' if len(sources) != 1 else ''}")
    return parts


def _render_thread(record, comments):
    thread = comments_for_story(comments, record["id"])
    if not thread:
        st.info("Tahimik pa ang panel. Agents comment only when they can add a distinct useful view.")
        return

    by_id = {str(comment.get("id")): comment for comment in thread if comment.get("id")}
    for comment in thread:
        persona = persona_for_comment(comment)
        reply = by_id.get(str(comment.get("reply_to") or ""))
        reply_html = ""
        if reply:
            reply_persona = persona_for_comment(reply)
            reply_excerpt = _compact(reply.get("body", ""), 150)
            reply_html = (
                '<div class="alam-thread-reply">'
                f'↳ Replying to <strong>{esc(reply_persona["emoji"] + " " + reply_persona["name"])}</strong>'
                + (f'<br>{esc(reply_excerpt)}' if reply_excerpt else "")
                + "</div>"
            )

        evidence = _evidence_summary(comment)
        evidence_html = "".join(f'<span class="alam-evidence-chip">{esc(item)}</span>' for item in evidence)
        meta_bits = [age_label(comment.get("created_at")), CATEGORY_META[_agent_category(comment)]["label"]]

        st.markdown(
            '<div class="alam-thread-card">'
            '<div class="alam-thread-head">'
            '<div>'
            f'<div class="alam-thread-persona">{esc(persona["emoji"] + " " + persona["name"])}</div>'
            f'<div class="alam-thread-role">{esc(persona.get("role", "Editorial Persona"))}</div>'
            '</div>'
            f'{_stance_html(comment)}'
            '</div>'
            f'{reply_html}'
            f'<div class="alam-panel-body">{esc(comment.get("body", ""))}</div>'
            + (f'<div class="alam-thread-meta">{evidence_html}</div>' if evidence_html else "")
            + '<div class="alam-thread-meta">'
            + " · ".join(esc(str(value)) for value in meta_bits if value)
            + '</div>'
            '</div>',
            unsafe_allow_html=True,
        )


def render_panel(record, comments):
    """Render lens overview plus complete detailed discussion for one story.

    The overview intentionally shows the latest contribution from each lens so the
    reader can compare four specialist positions quickly. It never replaces the full
    thread: owner personas, previous material-version comments and replies remain in
    the expandable discussion below.
    """
    thread = comments_for_story(comments, record["id"])
    by_category = defaultdict(list)
    for comment in thread:
        by_category[_agent_category(comment)].append(comment)

    st.markdown("#### 🗣 ALAM Panel")
    active = sum(1 for category in ("discover", "practical", "reflection", "trend") if by_category.get(category))
    challenge_count = sum(1 for comment in thread if _stance(comment) == "CHALLENGE")
    mixed_count = sum(1 for comment in thread if _stance(comment) == "MIXED")
    stance_note = ""
    if challenge_count or mixed_count:
        stance_note = f" · {challenge_count} challenge · {mixed_count} mixed"
    st.markdown(
        '<div class="alam-panel-summary">'
        f'<strong>{active}/4 lenses checked in.</strong>{esc(stance_note)} '
        'Each voice has a different job: novelty/evidence, practical consequence, market transmission, and pattern/base-rate calibration.'
        '</div>',
        unsafe_allow_html=True,
    )

    cards = []
    for category in ("discover", "practical", "reflection", "trend"):
        meta = CATEGORY_META[category]
        category_comments = by_category.get(category, [])
        if category_comments:
            comment = category_comments[-1]
            persona = persona_for_comment(comment)
            cards.append(
                '<div class="alam-panel-lens">'
                '<div class="alam-panel-lens-top">'
                f'<div class="alam-panel-agent">{meta["emoji"]} {esc(meta["label"])}</div>'
                f'<div class="alam-panel-count">{len(category_comments)} view{"s" if len(category_comments) != 1 else ""}</div>'
                '</div>'
                f'<div class="alam-panel-persona">{esc(persona["emoji"] + " " + persona["name"])}</div>'
                f'<div class="alam-panel-role">{esc(persona.get("role", "Editorial Persona"))}</div>'
                f'{_stance_html(comment)}'
                f'<div class="alam-panel-preview">{esc(_compact(comment.get("body", "")))}</div>'
                '</div>'
            )
        else:
            cards.append(
                '<div class="alam-panel-lens">'
                f'<div class="alam-panel-agent">{meta["emoji"]} {esc(meta["label"])}</div>'
                '<div class="alam-panel-waiting">No useful panel comment yet. Empty is better than filler.</div>'
                '</div>'
            )
    st.markdown('<div class="alam-panel-grid">' + "".join(cards) + '</div>', unsafe_allow_html=True)

    with st.expander(f"Read full reasoning · {len(thread)} comment{'s' if len(thread) != 1 else ''}"):
        _render_thread(record, comments)
        st.markdown("**Panel roles**")
        for category in ("discover", "practical", "reflection", "trend"):
            names = " · ".join(
                f"{persona['emoji']} {persona['name']} — {persona['role']}"
                for persona in PERSONAS.get(category, [])
            )
            st.caption(f"{CATEGORY_META[category]['label']}: {names}")


def install(mobile_views_module):
    """Install the richer panel while preserving all existing mobile view call sites."""
    mobile_views_module._render_panel = render_panel
