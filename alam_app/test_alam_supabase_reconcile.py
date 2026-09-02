"""Small deterministic tests for ALAM Supabase reconciliation helpers.

These tests avoid network/database access. They protect the archive ordering, exact
payload deduplication, and fail-closed chronology rules that make retry repair safe.
"""

from pathlib import Path

import alam_supabase_reconcile as reconcile
from alam_supabase_reconcile import (
    ArchiveConflictError,
    _canonical_record,
    _dedupe_archive_records,
    _validate_archive_chronology,
)


def main():
    older = {
        "id": "story-1",
        "title": "Older",
        "created_at": "2026-09-01T00:00:00+00:00",
        "content": {"b": 2, "a": 1},
    }
    older_same_payload_different_key_order = {
        "title": "Older",
        "id": "story-1",
        "content": {"a": 1, "b": 2},
        "created_at": "2026-09-01T00:00:00+00:00",
    }
    newer = {
        "id": "story-1",
        "title": "Newer",
        "created_at": "2026-09-02T00:00:00+00:00",
        "content": {"a": 3},
    }

    assert _canonical_record(older) == _canonical_record(older_same_payload_different_key_order)

    rows = [
        ("discover", Path("z.json"), newer),
        ("discover", Path("b.json"), older_same_payload_different_key_order),
        ("discover", Path("a.json"), older),
    ]
    deduped = _dedupe_archive_records(rows)
    assert len(deduped) == 2, deduped
    assert deduped[0][2]["title"] == "Older"
    assert deduped[1][2]["title"] == "Newer"
    _validate_archive_chronology("story-1", deduped)

    # Exact duplicate records at the same timestamp are harmless: deduplication
    # removes them before chronology validation, so archive recovery copies do not
    # create false material versions.
    duplicate_rows = [
        ("discover", Path("a.json"), older),
        ("discover", Path("b.json"), older_same_payload_different_key_order),
    ]
    duplicate_deduped = _dedupe_archive_records(duplicate_rows)
    assert len(duplicate_deduped) == 1
    _validate_archive_chronology("story-1", duplicate_deduped)

    # Different payloads with one explicit timestamp are ambiguous. Old behavior
    # sorted these by file path, which was deterministic but could silently select a
    # production current version without any chronological evidence. Sync must now
    # fail closed instead.
    same_time_a = dict(older, title="A")
    same_time_b = dict(older, title="B")
    tie_rows = [
        ("discover", Path("b.json"), same_time_b),
        ("discover", Path("a.json"), same_time_a),
    ]
    tied = _dedupe_archive_records(tie_rows)
    assert [row[2]["title"] for row in tied] == ["A", "B"]
    try:
        _validate_archive_chronology("story-1", tied)
    except ArchiveConflictError as exc:
        message = str(exc)
        assert "story-1" in message
        assert "a.json" in message and "b.json" in message
        assert "same explicit created_at" in message
    else:
        raise AssertionError("same-timestamp different-payload conflict was not rejected")

    # Exercise the same public-archive preflight used by the trusted sync wrapper.
    # Monkeypatching only the local archive iterator keeps this deterministic and
    # proves the job-facing entry point fails before a database client is involved.
    original_inputs = reconcile._article_inputs
    try:
        reconcile._article_inputs = lambda: iter(tie_rows)
        try:
            reconcile.prepare_public_archive()
        except ArchiveConflictError:
            pass
        else:
            raise AssertionError("public archive preflight accepted an ambiguous chronology")
    finally:
        reconcile._article_inputs = original_inputs

    # Historical archive shapes without created_at remain compatible. The epoch used
    # internally for sorting must not be mistaken for a real timestamp asserted by the
    # record, otherwise legacy records would suddenly block production synchronization.
    legacy_a = {"id": "legacy-1", "title": "Legacy A"}
    legacy_b = {"id": "legacy-1", "title": "Legacy B"}
    legacy_rows = _dedupe_archive_records([
        ("discover", Path("b.json"), legacy_b),
        ("discover", Path("a.json"), legacy_a),
    ])
    assert [row[2]["title"] for row in legacy_rows] == ["Legacy A", "Legacy B"]
    _validate_archive_chronology("legacy-1", legacy_rows)

    print("ALAM Supabase reconciliation helper tests passed")


if __name__ == "__main__":
    main()
