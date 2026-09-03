"""Evidence-constrained related-story experience for opened ALAM stories.

Related stories are derived only from ALAM's existing connection tags/tags through
``alam_intelligence.connected_stories``. The view never invents a causal relationship:
it tells the reader exactly which shared signals caused the recommendation and lets
them open the validated ALAM record directly.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

import streamlit as st

import alam_intelligence as intelligence
from alam_core import age_label, category_meta, esc, type_label


RELATED_CSS = r"""
<style>
.related-shell{margin:18px 0 8px}.related-head{font-size:1.05rem;font-weight:950;color:#17202A}.related-sub{font-size:.78rem;line-height:1.45;color:#667085;margin:3px 0 10px}
.related-card{border:1px solid rgba(23,32,42,.09);background:rgba(255,255,255,.94);border-radius:17px;padding:13px 14px;margin:7px 0 5px}.related-top{display:flex;justify-content:space-between;gap:8px;align-items:center}.related-kind{font-size:.65rem;font-weight:950;letter-spacing:.055em;text-transform:uppercase}.related-age{font-size:.68rem;color:#98A2B3}.related-title{font-size:.94rem;font-weight:900;line-height:1.3;color:#17202A;margin-top:7px}.related-why{font-size:.77rem;line-height:1.42;color:#667085;margin-top:6px}.related-signal{display:inline-block;background:#F2F4F7;border-radius:999px;padding:3px 7px;margin:3px 4px 0 0;font-size:.66rem;color:#475467}.related-stretch{font-size:.67rem;font-weight:900;color:#5968F2;margin-top:6px}
@media(max-width:760px){.related-card{padding:12px 13px;border-radius:15px}.related-title{font-size:.91rem}}
</style>
"""


def _category(row: tuple[Any, ...]) -> str:
    other = row[2] if len(row) > 2 and isinstance(row[2], dict) else {}
    return str(other.get("_category") or "").strip().lower()


def related_story_selection(
    record: dict[str, Any], records: list[dict[str, Any]], limit: int = 3
) -> tuple[list[tuple[Any, ...]], int | None]:
    """Return related rows plus the index of an intentional diversity insertion.

    The explicit insertion index matters to presentation correctness. A shelf may be
    naturally diverse because the normal ranking already spans categories; in that
    case the UI must not claim that ALAM replaced a slot to create diversity.
    """
    if limit <= 0:
        return [], None
    pool = intelligence.connected_stories(record, records, limit=max(limit, 12))
    selected = list(pool[:limit])
    if len(selected) < 2 or len(selected) < limit:
        return selected, None

    categories = [_category(row) for row in selected if _category(row)]
    counts = Counter(categories)
    if len(counts) != 1:
        return selected, None

    dominant = categories[0]
    stretch = next((row for row in pool[limit:] if _category(row) and _category(row) != dominant), None)
    if stretch is None:
        return selected, None

    selected[-1] = stretch
    return selected, len(selected) - 1


def related_story_candidates(record: dict[str, Any], records: list[dict[str, Any]], limit: int = 3):
    """Return evidence-backed connections while avoiding a one-category echo shelf.

    Ranking still comes entirely from ``connected_stories``. We only reserve the
    final slot for the strongest already-connected story from another category when
    the normal top-N is concentrated in one category. This cannot introduce an
    unrelated story because every candidate has already passed the shared-signal
    relationship test.
    """
    selected, _stretch_index = related_story_selection(record, records, limit=limit)
    return selected


def render_related_stories(record: dict[str, Any], records: list[dict[str, Any]]) -> None:
    related, stretch_index = related_story_selection(record, records, limit=3)
    if not related:
        return

    st.markdown(RELATED_CSS, unsafe_allow_html=True)
    diversity_note = " ALAM keeps one evidence-connected story from a different category when the strongest links would otherwise all come from one lane." if stretch_index is not None else ""
    st.markdown(
        "<div class='related-shell'><div class='related-head'>Connected intelligence</div>"
        "<div class='related-sub'>Other validated ALAM stories sharing explicit tags/signals. "
        f"Shared signals are context, not proof that one event caused another.{esc(diversity_note)}</div></div>",
        unsafe_allow_html=True,
    )

    for index, (_overlap_count, _score, other, overlap) in enumerate(related):
        meta = category_meta(other)
        signals = "".join(
            f"<span class='related-signal'>{esc(str(signal))}</span>" for signal in overlap[:4]
        )
        stretch_label = "<div class='related-stretch'>Different lens · still connected by evidence</div>" if index == stretch_index else ""
        st.markdown(
            "<div class='related-card'>"
            "<div class='related-top'>"
            f"<span class='related-kind' style='color:{meta['accent']}'>{esc(type_label(other))}</span>"
            f"<span class='related-age'>{esc(age_label(other.get('created_at')))}</span></div>"
            f"<div class='related-title'>{esc(other.get('title', 'Untitled'))}</div>"
            f"<div class='related-why'>Connected by {len(overlap)} shared signal{'s' if len(overlap) != 1 else ''}: {signals}</div>"
            f"{stretch_label}</div>",
            unsafe_allow_html=True,
        )
        if st.button(
            "Open connected story →",
            key=f"related_story_{record.get('id')}_{index}_{other.get('id')}",
            use_container_width=True,
        ):
            st.session_state["selected_story"] = str(other["id"])
            st.rerun()
