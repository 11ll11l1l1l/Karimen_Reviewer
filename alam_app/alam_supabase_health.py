"""Public-safe Supabase readiness diagnostics for ALAM.ph.

This module intentionally separates *operational truth* from UI rendering. A working
Supabase TCP/API connection does not prove that the ALAM schema exists, that trusted
GitHub -> Supabase synchronization has ever completed, or that the public app is
actually reading the database instead of its local migration fallback.

The database function consumed here exposes only sanitized aggregate/run fields. It
must never expose ``agent_runs.metadata`` wholesale, raw error strings, service-role
credentials, private repository identifiers, or any Global Engineering Job Radar
state.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from alam_supabase import _safe_error, get_supabase_public

PUBLIC_SYNC_HEALTH_RPC = "alam_public_sync_health"
DEFAULT_STALE_AFTER_HOURS = 6.0


@dataclass(frozen=True)
class SupabaseReadiness:
    """Normalized deployment/readiness state consumed by Settings and diagnostics.

    ``level`` is deliberately small and stable so product code can render it without
    re-implementing backend rules. ``ready`` means the database has a successful or
    acceptably recent trusted sync *and* the current content source is Supabase. It
    does not claim that every optional table contains rows.
    """

    code: str
    level: str
    ready: bool
    message: str
    detail: str | None = None
    last_sync_finished_at: str | None = None
    sync_age_hours: float | None = None
    published_articles: int | None = None


def _parse_dt(value: Any) -> datetime | None:
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


def _age_hours(value: Any, now: datetime | None = None) -> float | None:
    dt = _parse_dt(value)
    if dt is None:
        return None
    anchor = now or datetime.now(timezone.utc)
    if anchor.tzinfo is None:
        anchor = anchor.replace(tzinfo=timezone.utc)
    seconds = (anchor.astimezone(timezone.utc) - dt).total_seconds()
    # Future timestamps can happen briefly with clock skew. Treat them as age zero
    # rather than reporting a nonsensical negative freshness value.
    return max(0.0, seconds / 3600.0)


def normalize_public_sync_health(payload: Any) -> dict[str, Any]:
    """Normalize the RPC's single-row/list/dict shapes without inventing values."""
    if isinstance(payload, list):
        payload = payload[0] if payload else {}
    if not isinstance(payload, dict):
        return {}

    result = dict(payload)
    for key in ("stories_found", "stories_published", "stories_rejected", "error_count", "published_articles"):
        value = result.get(key)
        if value is None:
            continue
        try:
            result[key] = int(value)
        except (TypeError, ValueError):
            result[key] = None
    return result


def classify_supabase_readiness(
    *,
    connected: bool,
    content_source: str | None,
    sync_health: dict[str, Any] | None,
    sync_health_error: str | None = None,
    stale_after_hours: float = DEFAULT_STALE_AFTER_HOURS,
    now: datetime | None = None,
) -> SupabaseReadiness:
    """Convert low-level signals into one explicit operational state.

    The ordering is intentional: connection/schema problems outrank feed-source
    state, and a failed/partial trusted sync must remain visible even when an older
    set of Supabase rows is still readable. Local fallback is reported separately so
    a healthy connection cannot accidentally be presented as a completed cutover.
    """
    if not connected:
        return SupabaseReadiness(
            code="disconnected",
            level="error",
            ready=False,
            message="Supabase is not reachable with the public app credential.",
        )

    if sync_health_error:
        return SupabaseReadiness(
            code="sync_health_unavailable",
            level="warning",
            ready=False,
            message="Supabase is connected, but trusted-sync health is not available yet.",
            detail=sync_health_error,
        )

    health = normalize_public_sync_health(sync_health or {})
    if not health:
        return SupabaseReadiness(
            code="sync_health_empty",
            level="warning",
            ready=False,
            message="Supabase is connected, but ALAM cannot confirm synchronization state.",
        )

    status = str(health.get("last_sync_status") or "").strip().lower()
    finished_at = health.get("last_sync_finished_at")
    age = _age_hours(finished_at, now=now)
    articles = health.get("published_articles")

    common = {
        "last_sync_finished_at": str(finished_at) if finished_at else None,
        "sync_age_hours": age,
        "published_articles": articles,
    }

    if not status:
        return SupabaseReadiness(
            code="never_synchronized",
            level="warning",
            ready=False,
            message="ALAM's public schema is reachable, but no trusted Supabase sync has completed yet.",
            **common,
        )

    if status == "running":
        return SupabaseReadiness(
            code="sync_running",
            level="info",
            ready=False,
            message="A trusted ALAM Supabase synchronization is currently running.",
            **common,
        )

    if status == "failed":
        return SupabaseReadiness(
            code="sync_failed",
            level="error",
            ready=False,
            message="The latest trusted ALAM Supabase synchronization failed.",
            detail="Use the matching trusted workflow logs for the private error details.",
            **common,
        )

    if status == "partial":
        return SupabaseReadiness(
            code="sync_partial",
            level="warning",
            ready=False,
            message="The latest trusted ALAM Supabase synchronization completed only partially.",
            detail="The mirror may be readable, but reconciliation or another retry is required before declaring it healthy.",
            **common,
        )

    if status != "success":
        return SupabaseReadiness(
            code="sync_unknown_status",
            level="warning",
            ready=False,
            message="ALAM received an unknown trusted-sync status and will not assume the mirror is healthy.",
            detail=status,
            **common,
        )

    if age is not None and age > float(stale_after_hours):
        return SupabaseReadiness(
            code="sync_stale",
            level="warning",
            ready=False,
            message="The last trusted Supabase sync succeeded, but its freshness window has expired.",
            detail=f"Last successful sync was about {age:.1f} hours ago.",
            **common,
        )

    if content_source != "supabase":
        return SupabaseReadiness(
            code="local_fallback",
            level="warning",
            ready=False,
            message="Trusted sync is healthy, but the reader is still using local fallback data.",
            detail="Investigate empty/failed published-article reads before declaring cutover complete.",
            **common,
        )

    if articles == 0:
        return SupabaseReadiness(
            code="synchronized_empty",
            level="info",
            ready=True,
            message="Supabase synchronization is healthy and the public database currently has no published articles.",
            **common,
        )

    return SupabaseReadiness(
        code="ready",
        level="success",
        ready=True,
        message="Supabase is synchronized and the live ALAM feed is reading from it.",
        **common,
    )


def load_public_sync_health() -> tuple[dict[str, Any], str | None]:
    """Read the sanitized trusted-sync snapshot through the public RPC.

    RLS intentionally blocks direct anonymous reads of ``agent_runs``. The RPC is a
    narrow SECURITY DEFINER boundary defined by migration 005 and returns only fields
    approved for public deployment diagnostics. If that migration has not yet been
    applied, callers receive a safe error and can clearly report "diagnostics pending"
    instead of weakening the ``agent_runs`` policy.
    """
    try:
        response = get_supabase_public().rpc(PUBLIC_SYNC_HEALTH_RPC).execute()
        return normalize_public_sync_health(response.data), None
    except Exception as exc:  # Supabase/PostgREST client errors vary by version.
        return {}, _safe_error(exc)
