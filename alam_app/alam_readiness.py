"""Production cutover diagnostics for ALAM.ph.

A successful Supabase connection only proves that the public client can reach the
project. It does *not* prove that GitHub audit data has been mirrored, that the mirror
is current, or that the Streamlit feed is actually reading database rows. This module
keeps those states separate and visible so operators and development agents do not
mistake connectivity for deployment readiness.

The diagnostics intentionally use only the public Supabase client and published data
allowed by RLS. No service-role information, private run logs, or secrets are exposed
to the Streamlit application.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import streamlit as st

from alam_core import DATA_DIR
from alam_supabase import get_supabase_public

ARTICLE_FOLDERS = ("discover", "practical", "reflection", "trend")

RUNTIME_STATUS_CSS = r"""
<style>
.alam-runtime-status{display:flex;align-items:flex-start;gap:9px;border-radius:13px;padding:9px 11px;margin:-3px 0 10px;font-size:.72rem;line-height:1.4}
.alam-runtime-status.live{background:rgba(8,125,91,.08);border:1px solid rgba(8,125,91,.13);color:#087454}
.alam-runtime-status.fallback{background:#FFF7E8;border:1px solid #F5D995;color:#815900}
.alam-runtime-dot{width:7px;height:7px;border-radius:50%;margin-top:.29rem;flex:none;background:currentColor}
@media(max-width:760px){.alam-runtime-status{font-size:.68rem;padding:8px 9px;margin-bottom:8px}}
</style>
"""


def _safe_iso(value):
    """Return an aware UTC datetime for freshness comparisons, or ``None``."""
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@st.cache_data(ttl=60, show_spinner=False)
def _audit_article_ids():
    """Read unique article IDs from ALAM's committed GitHub/local audit archive.

    The audit layer may contain several historical versions of one story. Using a set
    avoids treating history as missing database content while still catching stories
    that never reached Supabase at all.
    """
    ids = set()
    for folder_name in ARTICLE_FOLDERS:
        folder = DATA_DIR / folder_name
        if not folder.exists():
            continue
        for path in folder.rglob("*.json"):
            if path.name.startswith("_"):
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                # Data validation owns malformed-file reporting. Readiness should stay
                # available even when one audit file is damaged so Settings can help
                # diagnose the production state instead of crashing with the feed.
                continue
            records = payload if isinstance(payload, list) else [payload]
            for record in records:
                if isinstance(record, dict) and record.get("id") and record.get("title"):
                    ids.add(str(record["id"]))
    return tuple(sorted(ids))


@st.cache_data(ttl=60, show_spinner=False)
def cutover_report():
    """Return public mirror coverage and freshness without requiring trusted access."""
    audit_ids = set(_audit_article_ids())
    report = {
        "audit_articles": len(audit_ids),
        "db_articles": 0,
        "matched_articles": 0,
        "coverage_pct": 0.0,
        "missing_ids": [],
        "extra_ids": [],
        "sources": 0,
        "comments": 0,
        "versions": 0,
        "latest_db_update": None,
    }

    try:
        client = get_supabase_public()
        articles_response = (
            client.table("articles")
            .select("id,updated_at,published_at", count="exact")
            .eq("status", "published")
            .order("updated_at", desc=True)
            .limit(1000)
            .execute()
        )
        article_rows = list(articles_response.data or [])
        db_ids = {str(row.get("id")) for row in article_rows if row.get("id")}
        report["db_articles"] = int(getattr(articles_response, "count", None) or len(db_ids))
        report["matched_articles"] = len(audit_ids & db_ids)
        report["coverage_pct"] = (
            100.0 if not audit_ids and not db_ids
            else (100.0 * len(audit_ids & db_ids) / len(audit_ids)) if audit_ids
            else 0.0
        )
        report["missing_ids"] = sorted(audit_ids - db_ids)[:12]
        report["extra_ids"] = sorted(db_ids - audit_ids)[:12]
        if article_rows:
            report["latest_db_update"] = article_rows[0].get("updated_at") or article_rows[0].get("published_at")

        # Counts are intentionally separate from article readiness. A story can exist
        # in the database but still be operationally incomplete if its sources,
        # history, or cross-agent perspectives failed to mirror.
        for label, table in (
            ("sources", "article_sources"),
            ("comments", "agent_comments"),
            ("versions", "article_versions"),
        ):
            response = client.table(table).select("*", count="exact").limit(1).execute()
            report[label] = int(getattr(response, "count", None) or 0)
        return report, None
    except Exception as exc:
        # Public-facing diagnostics must not echo whole client/request objects because
        # third-party errors can contain noisy request metadata. The main Supabase
        # module already sanitizes credential-like values; here we keep the message
        # deliberately short and operational.
        return report, str(exc)[:220]


def _freshness_text(value):
    dt = _safe_iso(value)
    if not dt:
        return "unknown"
    age = datetime.now(timezone.utc) - dt
    seconds = max(0, int(age.total_seconds()))
    if seconds < 120:
        return "just now"
    if seconds < 3600:
        return f"{seconds // 60} min ago"
    if seconds < 86400:
        return f"{seconds // 3600} h ago"
    return f"{seconds // 86400} d ago"


def render_runtime_status():
    """Show the current feed source without making an extra database request.

    ``load_article_records`` sets ``alam_content_source`` before the brand/header is
    rendered. Using that already-known state makes the runtime indicator effectively
    free and prevents a misleading green "live" impression while ALAM is deliberately
    serving its GitHub audit fallback during a database-sync outage or migration.
    """
    source = st.session_state.get("alam_content_source")
    if source == "supabase":
        st.markdown(
            '<div class="alam-runtime-status live"><span class="alam-runtime-dot"></span>'
            '<div><strong>Supabase live.</strong> Current story feed is being served from the durable database layer.</div></div>',
            unsafe_allow_html=True,
        )
    elif source == "local_fallback":
        st.markdown(
            '<div class="alam-runtime-status fallback"><span class="alam-runtime-dot"></span>'
            '<div><strong>Safe fallback mode.</strong> ALAM is serving the verified GitHub audit archive because the Supabase mirror is not populated/current yet. Content remains usable, but cross-device database features may be incomplete.</div></div>',
            unsafe_allow_html=True,
        )


def render_cutover_readiness():
    """Render an operator-focused readiness panel inside ALAM Settings."""
    st.markdown("#### Production readiness")
    report, error = cutover_report()
    content_source = st.session_state.get("alam_content_source", "unknown")

    if error:
        st.error("Supabase schema/data readiness check failed.")
        st.caption(error)
        return

    audit_count = report["audit_articles"]
    db_count = report["db_articles"]
    coverage = report["coverage_pct"]
    live = content_source == "supabase" and db_count > 0

    if live and (audit_count == 0 or coverage >= 99.9):
        st.success("LIVE · ALAM is reading Supabase and the published audit mirror is complete.")
    elif live:
        st.warning("LIVE WITH GAP · ALAM is reading Supabase, but some GitHub audit stories are not mirrored yet.")
    elif db_count > 0:
        st.warning("DATABASE POPULATED · Supabase has published stories, but this session has not confirmed the feed cutover yet.")
    else:
        st.error("NOT CUT OVER · Supabase has no published ALAM stories; the app is still relying on migration fallback data.")
        st.caption(
            "If the SQL schema is already installed, the next required step is the trusted GitHub Actions mirror. "
            "That workflow needs repository Actions secrets SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY."
        )

    cols = st.columns(4)
    cols[0].metric("Audit stories", audit_count)
    cols[1].metric("Supabase stories", db_count)
    cols[2].metric("Mirror coverage", f"{coverage:.0f}%")
    cols[3].metric("DB freshness", _freshness_text(report.get("latest_db_update")))

    detail_cols = st.columns(3)
    detail_cols[0].metric("Sources", report["sources"])
    detail_cols[1].metric("Agent comments", report["comments"])
    detail_cols[2].metric("Story versions", report["versions"])

    if report["missing_ids"]:
        with st.expander(f"Missing from Supabase ({len(report['missing_ids'])} shown)"):
            st.code("\n".join(report["missing_ids"]), language=None)
    if report["extra_ids"]:
        with st.expander(f"Supabase-only IDs ({len(report['extra_ids'])} shown)"):
            st.code("\n".join(report["extra_ids"]), language=None)

    st.caption(
        "Connectivity, mirror coverage and feed cutover are checked separately. "
        "This prevents a healthy database connection from hiding a failed or stale ingestion pipeline."
    )
