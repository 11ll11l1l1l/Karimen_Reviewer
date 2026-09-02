"""Story-lifecycle integrity rules for ALAM's trusted public audit archive.

Lifecycle is editorial state, not a freshness timer. A six-hour database sync delay does
not make a fact stale, and an old but still-current regulation must not disappear merely
because its first record is old. For that reason this module never infers expiry from wall
clock age.

What it does protect is explicit editorial retirement. Once an audit story reaches
``FADING`` or ``RESOLVED``, a later version that returns it to an active state must explain
why it was reactivated. Without that boundary, an agent retry or stale prompt can
accidentally resurrect an already-settled story and make it look newly actionable.

The module has no Supabase/Streamlit dependency so the same deterministic rule can run in
trusted synchronization and CI tests.
"""

from __future__ import annotations

from datetime import datetime, timezone

ACTIVE_STATES = {"NEW", "DEVELOPING", "CONFIRMED"}
RETIRED_STATES = {"FADING", "RESOLVED"}
KNOWN_STATES = ACTIVE_STATES | RETIRED_STATES
LIFECYCLE_CONTRACT = "alam-lifecycle-reactivation-v1"


def _parse_time(value):
    """Return a comparable aware timestamp; malformed legacy values sort first."""
    if value is None or not str(value).strip():
        return datetime(1970, 1, 1, tzinfo=timezone.utc)
    text = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return datetime(1970, 1, 1, tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _reactivation_reason(record):
    """Return the deliberate reopening explanation from the v5 lifecycle namespace."""
    content = record.get("content") if isinstance(record, dict) else None
    if not isinstance(content, dict):
        return ""
    lifecycle = content.get("lifecycle")
    if not isinstance(lifecycle, dict):
        return ""
    return str(lifecycle.get("reactivation_reason") or "").strip()


def _rejection(article_id, category, path, record, previous_state):
    """Build the private/publication-gate shape already used by rejected_candidates."""
    return {
        "article_id": article_id,
        "agent_id": str(record.get("agent") or category or "unknown").strip().lower(),
        "category": str(category or "unknown"),
        "path": str(path),
        "title": str(record.get("title") or "").strip() or None,
        "created_at": record.get("created_at"),
        "reasons": ["retired_story_reactivation_reason_required"],
        "warnings": [],
        "metrics": {
            "contract": LIFECYCLE_CONTRACT,
            "previous_lifecycle": previous_state,
            "incoming_lifecycle": str(record.get("status") or "").upper(),
        },
        "candidate": record,
    }


def lifecycle_rejections(prepared_archive):
    """Return unsafe retired->active transitions from a prepared public archive.

    ``prepared_archive`` is the deterministic mapping produced by
    ``prepare_public_archive`` after evidence and chronology validation. Exact duplicate
    versions are already collapsed there, so each adjacent record here represents a real
    audit version rather than a file-layout duplicate.

    FADING/RESOLVED are not hard terminal states: facts can change. Reactivation is
    allowed when ``content.lifecycle.reactivation_reason`` is non-empty. We intentionally
    do not require a reason for ordinary active-state movement such as CONFIRMED ->
    DEVELOPING because genuinely new contradictory evidence can make a stable story fluid
    again; the existing change-summary/history contract remains the audit explanation.
    """
    rejections = []
    for article_id, versions in (prepared_archive or {}).items():
        ordered = sorted(
            list(versions or []),
            key=lambda item: (_parse_time(item[2].get("created_at")), str(item[1])),
        )
        previous_state = None
        for category, path, record in ordered:
            if not isinstance(record, dict):
                continue
            incoming_state = str(record.get("status") or "").strip().upper()
            if incoming_state not in KNOWN_STATES:
                # Shape validation owns unknown statuses. Ignoring them here avoids
                # producing a misleading transition diagnosis for a malformed record.
                previous_state = incoming_state or previous_state
                continue
            if (
                previous_state in RETIRED_STATES
                and incoming_state in ACTIVE_STATES
                and not _reactivation_reason(record)
            ):
                rejections.append(
                    _rejection(str(article_id), category, path, record, previous_state)
                )
            previous_state = incoming_state
    return rejections
