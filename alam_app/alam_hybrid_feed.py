"""Verified GitHub audit overlay for temporary Supabase synchronization lag.

Supabase remains ALAM's durable/queryable primary layer. Content agents commit their
verified JSON audit records to GitHub before the trusted mirror writes those records
to Supabase. If that mirror is delayed, newer validated audit records may temporarily
need to appear in the reader without changing the source-of-truth policy.

This module adds only audit versions absent from the database result. Exact mirrored
versions stay database-backed, and the overlay naturally disappears once Supabase
contains the same stable story/version key. It is a continuity mechanism, not a new
publication path.
"""

from __future__ import annotations

from datetime import timezone

from alam_core import parse_dt


def version_key(record):
    """Stable identity for one material story version across storage backends.

    GitHub audit records commonly preserve Japan's +09:00 offset while Postgres
    serializes the same instant as +00:00. Normalize both to UTC before comparing so
    an already-mirrored version is not falsely reported as pending sync work.
    """
    if not isinstance(record, dict) or not record.get("id"):
        return None
    created_at = parse_dt(record.get("created_at")).astimezone(timezone.utc)
    return (
        str(record.get("id")),
        created_at.isoformat(),
    )


def _publication_time(record):
    """Return the public-feed timestamp with a legacy-safe creation fallback."""
    return parse_dt(record.get("published_at") or record.get("created_at"))


def merge_missing_audit_versions(database_records, audit_records):
    """Return database records plus only audit versions not already mirrored.

    The returned overlay count describes versions, not unique stories. Exact database
    versions win over their audit copy so normalized Supabase source hydration and
    storage metadata remain authoritative whenever the mirror is healthy.

    Public ordering follows ``published_at`` just like the Supabase query. Falling
    back to ``created_at`` preserves legacy records that predate an explicit
    publication timestamp. This prevents temporary sync lag from reordering the feed.
    """
    db = [dict(record) for record in (database_records or []) if isinstance(record, dict)]
    audit = [dict(record) for record in (audit_records or []) if isinstance(record, dict)]
    database_keys = {key for key in (version_key(record) for record in db) if key}
    overlay = []
    seen = set(database_keys)
    for record in audit:
        key = version_key(record)
        if not key or key in seen:
            continue
        seen.add(key)
        record["_storage"] = "verified_audit_overlay"
        overlay.append(record)

    combined = db + overlay
    combined.sort(key=_publication_time, reverse=True)
    return combined, len(overlay)
