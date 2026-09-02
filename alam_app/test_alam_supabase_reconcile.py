"""Small deterministic tests for ALAM Supabase reconciliation helpers.

These tests avoid network/database access. They protect the archive ordering and exact
payload deduplication rules that make retry repair deterministic.
"""

from pathlib import Path

from alam_supabase_reconcile import _canonical_record, _dedupe_archive_records


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

    same_time_a = dict(older, title="A")
    same_time_b = dict(older, title="B")
    tie_rows = [
        ("discover", Path("b.json"), same_time_b),
        ("discover", Path("a.json"), same_time_a),
    ]
    tied = _dedupe_archive_records(tie_rows)
    assert [row[2]["title"] for row in tied] == ["A", "B"]

    print("ALAM Supabase reconciliation helper tests passed")


if __name__ == "__main__":
    main()
