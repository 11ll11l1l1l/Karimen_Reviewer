"""Convergent integrity repair for ALAM's GitHub -> Supabase mirror.

The normal ingestion path is intentionally incremental for speed. Incremental writes
have one important failure mode: a process can update ``articles`` and then fail
before its version/source/topic writes finish. On the next run that same audit record
looks unchanged, so a purely incremental retry can preserve an incomplete mirror.

This module makes the trusted mirror *convergent*. GitHub JSON remains the audit
source of truth, while Supabase is repaired to the deterministic state implied by
that archive. It is called only from the service-role synchronization job and is
never imported by the public Streamlit application.
"""

from __future__ import annotations

import json
from collections import defaultdict

from alam_supabase_ingest import (
    LIFECYCLE,
    _article_inputs,
    _article_row,
    _parse_dt,
    _source_rows,
    _sync_prediction,
    _sync_topics,
)


def _canonical_record(record):
    """Return a stable representation used to identify duplicate archive versions.

    Agent output can be copied between files during recovery or batching. Treating
    identical JSON as another story version would make version numbering depend on
    file layout rather than on a material record change, so exact duplicates are
    collapsed before deterministic numbering.
    """
    return json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _dedupe_archive_records(items):
    """Sort archive records chronologically and remove exact duplicate payloads."""
    ordered = sorted(
        items,
        key=lambda item: (
            _parse_dt(item[2].get("created_at")),
            str(item[1]),
        ),
    )
    seen = set()
    unique = []
    for category, path, record in ordered:
        fingerprint = _canonical_record(record)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        unique.append((category, path, record))
    return unique


def _version_row(article_id, version_no, record):
    content = record.get("content") if isinstance(record.get("content"), dict) else {}
    change_summary = content.get("change_summary") if isinstance(content.get("change_summary"), dict) else None
    lifecycle = str(record.get("status") or "NEW").upper()
    if lifecycle not in LIFECYCLE:
        lifecycle = "NEW"
    return {
        "article_id": article_id,
        "version_no": version_no,
        "lifecycle_status": lifecycle,
        "change_summary": json.dumps(change_summary, ensure_ascii=False) if change_summary else None,
        "record": record,
        "created_at": record.get("created_at"),
    }


def _reconcile_versions(client, article_id, records):
    """Make numbered Supabase history match the immutable GitHub audit sequence.

    ``article_versions`` is a derived query layer, not the primary audit trail. It is
    therefore safe to repair a mismatched numbered slot and remove only trailing
    duplicate slots that cannot be justified by the current GitHub archive. The
    canonical JSON archive remains untouched and is the rollback source.
    """
    response = (
        client.table("article_versions")
        .select("version_no,record")
        .eq("article_id", article_id)
        .order("version_no")
        .execute()
    )
    existing = {
        int(row["version_no"]): _canonical_record(row.get("record") or {})
        for row in (response.data or [])
        if row.get("version_no") is not None
    }

    written = 0
    for index, (_, _, record) in enumerate(records, start=1):
        expected = _canonical_record(record)
        if existing.get(index) == expected:
            continue
        client.table("article_versions").upsert(
            _version_row(article_id, index, record),
            on_conflict="article_id,version_no",
        ).execute()
        written += 1

    # Older retry logic could create a trailing duplicate after a partial failure.
    # Remove only version numbers beyond the deterministic archive length; never
    # delete the GitHub record itself and never touch unrelated article IDs.
    extra = [version_no for version_no in existing if version_no > len(records)]
    if extra:
        client.table("article_versions").delete().eq("article_id", article_id).gt(
            "version_no", len(records)
        ).execute()
    return written, len(extra)


def _reconcile_sources(client, article_id, record):
    """Converge normalized current sources without a delete-before-insert window.

    Upserting desired rows first matters operationally: if Supabase fails midway, the
    previous good evidence set is still present. Stale rows are deleted only after the
    desired source set has been accepted by the database.
    """
    desired = _source_rows(record)
    desired_urls = {row["url"] for row in desired}
    if desired:
        client.table("article_sources").upsert(
            desired,
            on_conflict="article_id,url",
        ).execute()

    response = (
        client.table("article_sources")
        .select("id,url")
        .eq("article_id", article_id)
        .execute()
    )
    stale_ids = [
        row.get("id")
        for row in (response.data or [])
        if row.get("id") and row.get("url") not in desired_urls
    ]
    for source_id in stale_ids:
        client.table("article_sources").delete().eq("id", source_id).execute()
    return len(desired), len(stale_ids)


def reconcile_public_archive(client):
    """Repair all public ALAM records represented by the GitHub audit archive.

    The function deliberately scopes itself to ``_article_inputs()``, whose directory
    allow-list contains only Discover, Practical, Market/reflection and Trend. The
    private Global Engineering Job Radar therefore cannot be pulled into the public
    database by this reconciliation pass.
    """
    grouped = defaultdict(list)
    for category, path, record in _article_inputs():
        if not isinstance(record, dict) or not record.get("id") or not record.get("title"):
            continue
        grouped[str(record["id"])].append((category, path, record))

    stats = defaultdict(int)
    for article_id, raw_records in grouped.items():
        records = _dedupe_archive_records(raw_records)
        if not records:
            continue

        category, _, latest = records[-1]

        # The latest GitHub record is authoritative for the query-facing current row.
        # This unconditional upsert repairs a previous partial run even when its
        # timestamp equals the already-written ``articles.created_at`` value.
        client.table("articles").upsert(
            _article_row(latest, category),
            on_conflict="id",
        ).execute()
        stats["reconcile_articles"] += 1

        version_writes, version_deletes = _reconcile_versions(client, article_id, records)
        stats["reconcile_versions_written"] += version_writes
        stats["reconcile_versions_deleted"] += version_deletes

        source_upserts, source_deletes = _reconcile_sources(client, article_id, latest)
        stats["reconcile_sources_upserted"] += source_upserts
        stats["reconcile_sources_deleted"] += source_deletes

        # Topics currently use a small delete/rebuild helper. Running it here is still
        # valuable because the next reconciliation retries it after any partial job.
        # Prediction writes are already upserts and therefore naturally convergent.
        stats["reconcile_topics"] += int(_sync_topics(client, latest) or 0)
        stats["reconcile_predictions"] += int(bool(_sync_prediction(client, latest, category)))

    return dict(sorted(stats.items()))
