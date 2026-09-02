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

from alam_publication_quality import validate_archive_items
from alam_supabase_ingest import (
    LIFECYCLE,
    _article_inputs,
    _article_row,
    _parse_dt,
    _source_rows,
    _sync_prediction,
    _sync_topics,
)


class ArchiveConflictError(ValueError):
    """Raised when the GitHub audit trail cannot define one safe story chronology.

    A stable article ID may legitimately have many versions, but two *different*
    payloads carrying the exact same explicit ``created_at`` timestamp are ambiguous:
    neither version can be proven to be later. Silently resolving that ambiguity by
    file-name ordering would make a repository-layout accident decide the production
    current article. Trusted synchronization therefore fails closed before content
    writes and requires the audit record itself to be corrected.
    """


def _canonical_record(record):
    """Return a stable representation used to identify duplicate archive versions.

    Agent output can be copied between files during recovery or batching. Treating
    identical JSON as another story version would make version numbering depend on
    file layout rather than on a material record change, so exact duplicates are
    collapsed before deterministic numbering.
    """
    return json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _dedupe_archive_records(items):
    """Sort archive records chronologically and remove exact duplicate payloads.

    Path ordering remains a deterministic tie-breaker for legacy records whose old
    shapes do not contain ``created_at``. Explicit equal timestamps with different
    payloads are rejected separately by ``_validate_archive_chronology`` because a
    path name is not legitimate evidence that one material story version is newer.
    """
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


def _explicit_timestamp(record):
    """Return a normalized explicit version timestamp, or ``None`` for legacy rows.

    Missing timestamps are intentionally not treated as ``1970-01-01`` conflicts.
    ``_parse_dt`` uses that epoch as a sorting fallback for historical compatibility,
    but converting the fallback into a conflict signal would suddenly invalidate old
    audit data that predates the current v5 chronology contract.
    """
    value = record.get("created_at") if isinstance(record, dict) else None
    if value is None or not str(value).strip():
        return None
    return _parse_dt(value).isoformat()


def _validate_archive_chronology(article_id, records):
    """Reject explicit equal-time, different-payload story versions.

    Exact duplicate payloads are harmless and have already been collapsed. What
    remains here is a true chronology conflict: multiple materially different records
    claim the same exact version time. We intentionally report only article ID,
    normalized timestamp, and archive paths; article contents stay in the private
    repository/log context and are not copied into public diagnostics.
    """
    by_timestamp = defaultdict(list)
    for category, path, record in records:
        timestamp = _explicit_timestamp(record)
        if timestamp is not None:
            by_timestamp[timestamp].append((category, path, record))

    conflicts = []
    for timestamp, items in sorted(by_timestamp.items()):
        fingerprints = {_canonical_record(item[2]) for item in items}
        if len(fingerprints) > 1:
            conflicts.append((timestamp, [str(item[1]) for item in items]))

    if conflicts:
        detail = "; ".join(
            f"{timestamp} -> {', '.join(paths)}"
            for timestamp, paths in conflicts
        )
        raise ArchiveConflictError(
            f"Ambiguous ALAM archive chronology for article {article_id}: {detail}. "
            "Different payloads must not share the same explicit created_at timestamp."
        )


def prepare_public_archive():
    """Load, quality-check, deduplicate, and validate public archive records.

    This is deliberately pure with respect to Supabase. The trusted sync job calls it
    before incremental ingestion, so both evidence-contract failures and ambiguous
    chronology stop before any public content mutation. Reconciliation calls the same
    function to guarantee both write paths enforce exactly one archive contract.

    Returns a mapping of stable article ID to deterministic version tuples.
    """
    # Materialize exactly once. `_article_inputs()` currently returns a list, but
    # keeping this boundary iterator-safe prevents the quality pass from consuming a
    # generator and leaving chronology/reconciliation with an empty archive. It also
    # guarantees every preflight stage examines the same immutable in-process snapshot.
    items = list(_article_inputs())

    # Evidence quality is checked against the complete allow-listed public archive
    # before invalid shapes are filtered for chronology grouping. Otherwise a v5 row
    # missing its stable ID/title could be silently skipped here and the trusted job
    # could incorrectly report a healthy mirror despite rejecting repository input.
    validate_archive_items(items)

    grouped = defaultdict(list)
    for category, path, record in items:
        if not isinstance(record, dict) or not record.get("id") or not record.get("title"):
            continue
        grouped[str(record["id"])].append((category, path, record))

    prepared = {}
    for article_id, raw_records in grouped.items():
        records = _dedupe_archive_records(raw_records)
        if not records:
            continue
        _validate_archive_chronology(article_id, records)
        prepared[article_id] = records
    return prepared


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


def reconcile_public_archive(client, prepared_archive=None):
    """Repair all public ALAM records represented by the GitHub audit archive.

    The function deliberately scopes itself to ``prepare_public_archive()``, whose
    underlying ``_article_inputs()`` directory allow-list contains only Discover,
    Practical, Market/reflection and Trend. The private Global Engineering Job Radar
    therefore cannot be pulled into the public database by this reconciliation pass.

    ``prepared_archive`` lets the trusted sync job reuse the already validated
    preflight snapshot, avoiding a second archive scan and guaranteeing that the
    records written are the same records that passed quality and conflict detection.
    """
    grouped = prepared_archive if prepared_archive is not None else prepare_public_archive()

    stats = defaultdict(int)
    for article_id, records in grouped.items():
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

        # Topic/prediction helpers are convergent and are re-run here so a later
        # reconciliation can repair any earlier partial trusted-sync failure.
        stats["reconcile_topics"] += int(_sync_topics(client, latest) or 0)
        stats["reconcile_predictions"] += int(bool(_sync_prediction(client, latest, category)))

    return dict(sorted(stats.items()))
