"""Verified GitHub audit overlay for temporary Supabase synchronization lag.

Supabase remains ALAM's durable/queryable primary layer. Content agents, however,
commit their verified JSON audit records to GitHub before the trusted mirror writes
those records to Supabase. If that mirror is delayed or its credentials are missing,
a non-empty database must not cause newer validated audit records to disappear from
the reader.

This module adds only audit versions absent from the database result. Exact mirrored
versions stay database-backed, and the overlay naturally disappears once Supabase
contains the same stable story/version key. It is a continuity mechanism, not a new
source-of-truth policy.
"""

from __future__ import annotations

from alam_core import parse_dt


def version_key(record):
    """Stable identity for one material story version across storage backends."""
    if not isinstance(record, dict) or not record.get("id"):
        return None
    return (
        str(record.get("id")),
        parse_dt(record.get("created_at")).isoformat(),
    )


def merge_missing_audit_versions(database_records, audit_records):
    """Return database records plus only audit versions not already mirrored.

    The returned overlay count describes versions, not unique stories. Callers use it
    only for runtime diagnostics. Exact database versions win over their audit copy so
    normalized Supabase source hydration and storage metadata remain authoritative
    whenever the mirror is healthy.
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
    combined.sort(key=lambda record: parse_dt(record.get("created_at")), reverse=True)
    return combined, len(overlay)
