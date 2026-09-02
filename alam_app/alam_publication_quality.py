"""Fail-closed publication quality checks for trusted ALAM synchronization.

This module deliberately contains no Streamlit or Supabase client dependency so the
same rules can run in repository validation, trusted archive preflight, and tests.
The gate enforces only hard v5 contract invariants that would make public evidence
misleading or unusable. Research targets such as a second independent source remain
warnings because a unique primary announcement can legitimately be publishable with
one source when uncertainty is stated.

Rejected candidates may be persisted through the existing private
``rejected_candidates`` table. That table has RLS enabled and intentionally has no
anonymous/public read policy; the public app never imports this module or receives
raw rejected-candidate payloads.
"""

from __future__ import annotations

from datetime import datetime
from urllib.parse import urlparse

V5_CUTOFF = datetime.fromisoformat("2026-09-02T14:30:00+09:00")
PRIMARY_SOURCE_TYPES = {"official", "primary", "filing"}
QUALITY_CONTRACT = "alam-publication-quality-v1"


class PublicationQualityError(ValueError):
    """Raised when one or more modern public audit records cannot be published safely.

    ``rejections`` keeps structured private/operator detail for persistence while the
    exception message contains only stable IDs and reason codes. This avoids turning
    article text or third-party request details into generic sync-health diagnostics.
    """

    def __init__(self, rejections):
        self.rejections = tuple(rejections or [])
        summary = "; ".join(
            f"{item.get('article_id') or '<missing-id>'}: {','.join(item.get('reasons') or [])}"
            for item in self.rejections
        )
        super().__init__(
            "ALAM publication quality preflight rejected "
            f"{len(self.rejections)} candidate(s)" + (f": {summary}" if summary else "")
        )


def _record_time(record):
    """Return an aware record timestamp when it is parseable, otherwise ``None``."""
    if not isinstance(record, dict):
        return None
    raw = record.get("created_at")
    if raw is None or not str(raw).strip():
        return None
    try:
        value = datetime.fromisoformat(str(raw).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return value if value.tzinfo is not None else None


def requires_v5_quality(record):
    """Apply hard evidence requirements only to records written under the v5 contract.

    Older audit rows predate the current evidence schema and are kept rebuildable for
    backwards compatibility. New records cannot use that historical compatibility
    path to bypass evidence requirements because their explicit timestamp is at or
    after the v5 cutoff.
    """
    value = _record_time(record)
    return bool(value and value >= V5_CUTOFF)


def valid_source_url(value):
    """Return whether a source URL is a usable absolute HTTP(S) reference."""
    try:
        parsed = urlparse(str(value or "").strip())
    except Exception:
        return False
    return parsed.scheme.lower() in {"http", "https"} and bool(parsed.netloc)


def _source_metrics(sources):
    usable = []
    exact_urls = []
    primary_count = 0
    publishers = set()
    for source in sources if isinstance(sources, list) else []:
        if not isinstance(source, dict) or not valid_source_url(source.get("url")):
            continue
        url = str(source.get("url")).strip()
        usable.append(source)
        exact_urls.append(url)
        source_type = str(source.get("source_type") or "other").strip().lower()
        if source_type in PRIMARY_SOURCE_TYPES:
            primary_count += 1
        publisher = str(source.get("publisher") or "").strip().lower()
        if publisher:
            publishers.add(publisher)
    return {
        "source_count": len(usable),
        "distinct_source_urls": len(set(exact_urls)),
        "primary_source_count": primary_count,
        "publisher_count": len(publishers),
    }


def assess_article(record):
    """Return deterministic blocking reasons, warnings, and evidence metrics.

    Blocking rules intentionally match minimum truthfulness/data-integrity contracts:
    a modern article needs at least one usable source; every supplied source must have
    a valid URL; claims must be a list; FACT claims need valid 1-based source refs; and
    any source ref that is supplied must resolve to an existing source. A one-source
    article or an article without a primary source is flagged for operator attention
    but not rejected automatically because the research protocol explicitly allows
    unique primary announcements and calibrated uncertainty.
    """
    modern = requires_v5_quality(record)
    reasons = []
    warnings = []

    if not isinstance(record, dict):
        return {
            "publishable": not modern,
            "reasons": ["record_not_object"] if modern else [],
            "warnings": [],
            "metrics": _source_metrics([]),
        }

    if modern and not str(record.get("id") or "").strip():
        reasons.append("missing_stable_id")
    if modern and not str(record.get("title") or "").strip():
        reasons.append("missing_title")

    sources = record.get("sources")
    if not isinstance(sources, list):
        if modern:
            reasons.append("sources_not_list")
        source_list = []
    else:
        source_list = sources

    metrics = _source_metrics(source_list)
    if modern:
        if not source_list:
            reasons.append("no_sources")
        for index, source in enumerate(source_list, start=1):
            if not isinstance(source, dict):
                reasons.append(f"source_{index}_not_object")
            elif not valid_source_url(source.get("url")):
                reasons.append(f"source_{index}_invalid_url")
        if metrics["source_count"] == 0:
            reasons.append("no_usable_sources")

    claims = record.get("claims")
    if not isinstance(claims, list):
        if modern:
            reasons.append("claims_not_list")
        claim_list = []
    else:
        claim_list = claims

    fact_count = 0
    sourced_fact_count = 0
    for claim_index, claim in enumerate(claim_list, start=1):
        if not isinstance(claim, dict):
            if modern:
                reasons.append(f"claim_{claim_index}_not_object")
            continue
        kind = str(claim.get("kind") or "").strip().upper()
        refs = claim.get("source_refs")
        if refs is None:
            refs = []
        if not isinstance(refs, list):
            if modern:
                reasons.append(f"claim_{claim_index}_source_refs_not_list")
            refs = []

        valid_refs = []
        for ref in refs:
            if isinstance(ref, int) and not isinstance(ref, bool) and 1 <= ref <= len(source_list):
                valid_refs.append(ref)
            elif modern:
                reasons.append(f"claim_{claim_index}_source_ref_out_of_range")

        if kind == "FACT":
            fact_count += 1
            if valid_refs:
                sourced_fact_count += 1
            elif modern:
                reasons.append(f"fact_{claim_index}_missing_source_ref")

    metrics.update({
        "fact_count": fact_count,
        "sourced_fact_count": sourced_fact_count,
    })

    if modern and metrics["source_count"] == 1:
        warnings.append("single_source_only")
    if modern and metrics["source_count"] > 0 and metrics["primary_source_count"] == 0:
        warnings.append("no_primary_or_official_source")
    if modern and metrics["distinct_source_urls"] < metrics["source_count"]:
        warnings.append("duplicate_source_url")

    # Preserve order for human diagnostics while de-duplicating repeated failures,
    # e.g. an empty source list yields both the shape-level and usability-level codes.
    reasons = list(dict.fromkeys(reasons))
    warnings = list(dict.fromkeys(warnings))
    return {
        "publishable": not reasons,
        "reasons": reasons,
        "warnings": warnings,
        "metrics": metrics,
    }


def validate_archive_items(items):
    """Fail the complete public archive preflight when any v5 record is unsafe.

    The caller must invoke this before database mutation. Each rejection retains its
    source path and candidate record only for trusted logs/private persistence. The
    four public article directories are supplied by the ingestion allow-list, so this
    helper cannot discover or ingest the private Global Engineering Job Radar.
    """
    rejections = []
    for category, path, record in items:
        assessment = assess_article(record)
        if assessment["publishable"]:
            continue
        record_dict = record if isinstance(record, dict) else {}
        rejections.append({
            "article_id": str(record_dict.get("id") or "").strip() or None,
            "agent_id": str(record_dict.get("agent") or category or "unknown").strip().lower(),
            "category": str(category or "unknown"),
            "path": str(path),
            "title": str(record_dict.get("title") or "").strip() or None,
            "created_at": record_dict.get("created_at"),
            "reasons": assessment["reasons"],
            "warnings": assessment["warnings"],
            "metrics": assessment["metrics"],
            "candidate": record_dict,
        })
    if rejections:
        raise PublicationQualityError(rejections)
    return True


def _candidate_key(rejection):
    article_id = str(rejection.get("article_id") or "missing-id")
    created_at = str(rejection.get("created_at") or "missing-time")
    return f"article:{article_id}:{created_at}"[:500]


def persist_rejection(client, rejection):
    """Upsert one rejection diagnostically into the existing private table.

    ``rejected_candidates`` has no public read policy. We still keep ``reason`` to
    stable codes and place detailed checks under ``quality_checks`` so future admin
    tooling can aggregate causes without parsing prose. Since the historical schema
    has no unique constraint on ``candidate_key``, this helper resolves an existing
    row first to avoid creating one duplicate every failed retry.
    """
    agent_id = str(rejection.get("agent_id") or "unknown")
    candidate_key = _candidate_key(rejection)
    row = {
        "agent_id": agent_id,
        "candidate_key": candidate_key,
        "title": rejection.get("title"),
        "reason": "publication_quality_gate:" + ",".join(rejection.get("reasons") or []),
        "quality_checks": {
            "contract": QUALITY_CONTRACT,
            "blocking_reasons": list(rejection.get("reasons") or []),
            "warnings": list(rejection.get("warnings") or []),
            "metrics": dict(rejection.get("metrics") or {}),
            "source_path": rejection.get("path"),
        },
        "candidate": rejection.get("candidate") if isinstance(rejection.get("candidate"), dict) else {},
    }
    existing = (
        client.table("rejected_candidates")
        .select("id")
        .eq("agent_id", agent_id)
        .eq("candidate_key", candidate_key)
        .limit(1)
        .execute()
        .data
        or []
    )
    if existing and existing[0].get("id"):
        client.table("rejected_candidates").update(row).eq("id", existing[0]["id"]).execute()
    else:
        client.table("rejected_candidates").insert(row).execute()
    return candidate_key


def persist_quality_rejections(client, error):
    """Persist all structured rejections from ``PublicationQualityError``."""
    count = 0
    for rejection in getattr(error, "rejections", ()):
        persist_rejection(client, rejection)
        count += 1
    return count
