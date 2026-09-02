"""Reader-facing evidence intelligence for ALAM.ph.

ALAM already stores structured sources and claim references, but a plain source list
forces readers to do the trust analysis themselves. This module converts only the
metadata already present in the stable v5 record into a compact evidence summary and
source cards that answer three questions without inventing certainty:

1. How much of the article's classified claims are actually tied to sources?
2. How many sources are primary/official rather than secondary commentary?
3. Do the citations come from more than one publisher/domain group?

The distinct-group metric is deliberately labelled as a diversity heuristic, not
"independent confirmation". Two outlets can repeat the same upstream report, and a
single institution can publish across several hostnames. The UI therefore exposes
what ALAM can verify from record metadata while preserving appropriate uncertainty.
"""

from __future__ import annotations

from urllib.parse import urlparse

import streamlit as st

from alam_core import CLAIM_META, esc, get_claims


EVIDENCE_CSS = r"""
<style>
.evidence-health-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin:8px 0 12px}
.evidence-health-card{border:1px solid rgba(23,32,42,.09);background:rgba(255,255,255,.95);border-radius:15px;padding:11px 12px;min-height:88px}
.evidence-health-value{font-size:1.05rem;font-weight:900;line-height:1.15;color:#17202A}
.evidence-health-label{font-size:.66rem;font-weight:900;letter-spacing:.055em;text-transform:uppercase;color:#667085;margin-top:5px}
.evidence-health-note{font-size:.70rem;line-height:1.38;color:#667085;margin-top:3px}
.evidence-caution{border:1px solid #F5D995;background:#FFF9ED;border-radius:13px;padding:9px 11px;margin:7px 0 12px;font-size:.77rem;line-height:1.42;color:#6B4D16}
.evidence-source{border:1px solid rgba(23,32,42,.09);background:#fff;border-radius:15px;padding:12px 13px;margin:8px 0}
.evidence-source-top{display:flex;align-items:flex-start;justify-content:space-between;gap:10px}
.evidence-source-index{font-size:.69rem;font-weight:950;color:#667085;letter-spacing:.045em;text-transform:uppercase}
.evidence-source-title{font-size:.88rem;font-weight:850;color:#17202A;line-height:1.35;margin-top:3px}
.evidence-source-meta{font-size:.72rem;line-height:1.42;color:#667085;margin-top:5px}
.evidence-badges{display:flex;flex-wrap:wrap;gap:5px;justify-content:flex-end}
.evidence-badge{display:inline-block;border-radius:999px;padding:3px 7px;font-size:.61rem;font-weight:900;letter-spacing:.04em;text-transform:uppercase;background:#F0F2F5;color:#475467;white-space:nowrap}
.evidence-badge.primary{background:#E7F7F1;color:#087D5B}.evidence-badge.claims{background:#EEF0FF;color:#4854C8}.evidence-badge.group{background:#EAF2FB;color:#2F6FB0}
.evidence-claim-map{border-top:1px solid rgba(23,32,42,.07);margin-top:9px;padding-top:8px;font-size:.74rem;line-height:1.45;color:#475467}
@media(max-width:760px){.evidence-health-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.evidence-health-card{min-height:82px}.evidence-source-top{display:block}.evidence-badges{justify-content:flex-start;margin-top:7px}}
</style>
"""

PRIMARY_TYPES = {"official", "primary", "filing"}


def _source_identity(source):
    """Return a conservative publisher/domain identity for diversity grouping.

    Publisher is preferred because one organization can use multiple domains. When
    publisher metadata is absent, hostname is a useful fallback. This is a diversity
    heuristic only; callers must not describe it as proof of independent reporting.
    """
    publisher = str(source.get("publisher") or "").strip().lower()
    if publisher:
        return "publisher:" + " ".join(publisher.split())
    try:
        host = (urlparse(str(source.get("url") or "")).hostname or "").lower()
    except ValueError:
        host = ""
    if host.startswith("www."):
        host = host[4:]
    return "domain:" + host if host else "unknown"


def _normalize_refs(value):
    if value is None:
        return []
    if isinstance(value, (str, int, float)):
        value = [value]
    if not isinstance(value, list):
        return []
    refs = []
    for raw in value:
        try:
            ref = int(raw)
        except (TypeError, ValueError):
            continue
        if ref > 0 and ref not in refs:
            refs.append(ref)
    return refs


def evidence_summary(record):
    """Return deterministic evidence metrics derived from one ALAM v5 record."""
    sources = [s for s in (record.get("sources") or []) if isinstance(s, dict)]
    claims = [c for c in get_claims(record) if isinstance(c, dict)]
    primary = sum(
        1
        for source in sources
        if str(source.get("source_type") or "").strip().lower() in PRIMARY_TYPES
        or source.get("is_primary") is True
    )
    identities = {_source_identity(source) for source in sources}
    identities.discard("unknown")

    covered_claims = 0
    referenced_source_indexes = set()
    for claim in claims:
        refs = _normalize_refs(claim.get("source_refs") or claim.get("sources"))
        valid = [ref for ref in refs if 1 <= ref <= len(sources)]
        if valid:
            covered_claims += 1
            referenced_source_indexes.update(valid)

    total_claims = len(claims)
    claim_coverage = round((covered_claims / total_claims) * 100) if total_claims else None
    return {
        "source_count": len(sources),
        "primary_count": primary,
        "distinct_groups": len(identities),
        "claim_count": total_claims,
        "covered_claims": covered_claims,
        "claim_coverage": claim_coverage,
        "referenced_sources": len(referenced_source_indexes),
    }


def source_claim_map(record):
    """Map 1-based source numbers to the classified claims that cite each source."""
    mapping = {}
    sources = [s for s in (record.get("sources") or []) if isinstance(s, dict)]
    for claim_index, claim in enumerate(get_claims(record), start=1):
        if not isinstance(claim, dict):
            continue
        for ref in _normalize_refs(claim.get("source_refs") or claim.get("sources")):
            if 1 <= ref <= len(sources):
                mapping.setdefault(ref, []).append((claim_index, claim))
    return mapping


def _render_summary(record):
    metrics = evidence_summary(record)
    coverage = metrics["claim_coverage"]
    coverage_text = f"{coverage}%" if coverage is not None else "—"
    coverage_note = (
        f"{metrics['covered_claims']} of {metrics['claim_count']} classified claims cite attached sources"
        if metrics["claim_count"]
        else "No structured classified claims available"
    )
    st.markdown(
        "<div class='evidence-health-grid'>"
        f"<div class='evidence-health-card'><div class='evidence-health-value'>{metrics['source_count']}</div><div class='evidence-health-label'>Attached sources</div><div class='evidence-health-note'>Usable citations in this story</div></div>"
        f"<div class='evidence-health-card'><div class='evidence-health-value'>{metrics['primary_count']}</div><div class='evidence-health-label'>Primary / official</div><div class='evidence-health-note'>Direct institutional or filing-type sources</div></div>"
        f"<div class='evidence-health-card'><div class='evidence-health-value'>{metrics['distinct_groups']}</div><div class='evidence-health-label'>Distinct source groups</div><div class='evidence-health-note'>Publisher/domain diversity heuristic</div></div>"
        f"<div class='evidence-health-card'><div class='evidence-health-value'>{coverage_text}</div><div class='evidence-health-label'>Claim coverage</div><div class='evidence-health-note'>{esc(coverage_note)}</div></div>"
        "</div>",
        unsafe_allow_html=True,
    )
    if metrics["source_count"] > 1 and metrics["distinct_groups"] <= 1:
        st.markdown(
            "<div class='evidence-caution'><strong>Source diversity is limited.</strong> "
            "Multiple links appear to come from one publisher/domain group. That can still be authoritative, "
            "but it is not the same as corroboration from separate source groups.</div>",
            unsafe_allow_html=True,
        )
    elif metrics["distinct_groups"] > 1:
        st.caption(
            "Distinct source groups indicate publisher/domain diversity only. ALAM does not treat that metric alone as proof of independent confirmation."
        )


def _render_source_cards(record):
    sources = [s for s in (record.get("sources") or []) if isinstance(s, dict)]
    if not sources:
        st.error("Walang source na naka-attach. Treat factual claims as unverified.")
        return
    claim_map = source_claim_map(record)
    identities = {}
    next_group = 1
    for source in sources:
        identity = _source_identity(source)
        if identity not in identities:
            identities[identity] = next_group
            next_group += 1

    st.markdown("#### Source-by-source support")
    for idx, source in enumerate(sources, start=1):
        publisher = source.get("publisher") or "Source"
        title = source.get("title") or publisher
        source_type = str(source.get("source_type") or "other").strip().lower()
        primary = source_type in PRIMARY_TYPES or source.get("is_primary") is True
        published = source.get("published_at") or "date not supplied"
        reliability = source.get("reliability")
        url = str(source.get("url") or "")
        valid_link = urlparse(url).scheme in {"http", "https"}
        group = identities.get(_source_identity(source))
        linked_claims = claim_map.get(idx, [])

        badges = []
        if primary:
            badges.append("<span class='evidence-badge primary'>Primary / official</span>")
        else:
            badges.append(f"<span class='evidence-badge'>{esc(source_type or 'other')}</span>")
        if group:
            badges.append(f"<span class='evidence-badge group'>Group {group}</span>")
        if linked_claims:
            badges.append(f"<span class='evidence-badge claims'>Supports {len(linked_claims)} claim{'s' if len(linked_claims) != 1 else ''}</span>")

        meta_parts = [f"Published/updated: {esc(published)}"]
        if reliability not in (None, ""):
            meta_parts.append(f"Reliability: {esc(reliability)}")
        if valid_link:
            meta_parts.append(f"<a href='{esc(url)}' target='_blank'>Open source ↗</a>")

        claim_html = ""
        if linked_claims:
            rows = []
            for claim_index, claim in linked_claims:
                kind = str(claim.get("kind") or "OPINION").upper()
                label = CLAIM_META.get(kind, (kind, "", "", ""))[0]
                text = str(claim.get("text") or "").strip()
                rows.append(f"<strong>Claim {claim_index} · {esc(label)}</strong> — {esc(text)}")
            claim_html = "<div class='evidence-claim-map'>" + "<br>".join(rows) + "</div>"
        else:
            claim_html = "<div class='evidence-claim-map'>No structured claim currently points to this source. It may support background/context, or the record may need stronger claim mapping.</div>"

        st.markdown(
            "<div class='evidence-source'>"
            "<div class='evidence-source-top'><div>"
            f"<div class='evidence-source-index'>Source {idx}</div>"
            f"<div class='evidence-source-title'>{esc(publisher)} — {esc(title)}</div>"
            "</div><div class='evidence-badges'>" + "".join(badges) + "</div></div>"
            f"<div class='evidence-source-meta'>{' · '.join(meta_parts)}</div>"
            f"{claim_html}</div>",
            unsafe_allow_html=True,
        )


def render_evidence(record, all_records, render_pr_vs_reality, render_claims, render_timeline):
    """Render evidence in decision order while reusing the mature claim/timeline views."""
    st.markdown("#### Evidence health")
    _render_summary(record)
    render_pr_vs_reality(record)
    render_claims(record)
    render_timeline(all_records, record)
    _render_source_cards(record)
