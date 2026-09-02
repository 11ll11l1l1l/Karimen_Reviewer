"""Trusted GitHub/audit-layer -> Supabase ingestion for ALAM.ph.

This module is never imported by the public Streamlit app. It requires a server-side
Supabase service-role/secret key and is intended for GitHub Actions or an admin CLI.
It preserves the existing JSON files as the immutable audit trail while making
Supabase the app's durable query/read layer.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

try:
    from supabase import create_client
except ModuleNotFoundError as exc:  # pragma: no cover - CLI configuration failure
    raise SystemExit("Install the Supabase Python package before running ingestion.") from exc

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
ARTICLE_DIRS = {
    "discover": DATA_DIR / "discover",
    "practical": DATA_DIR / "practical",
    "reflection": DATA_DIR / "reflection",
    "trend": DATA_DIR / "trend",
}
COMMENTS_DIR = DATA_DIR / "comments"
WISDOM_DIR = DATA_DIR / "wisdom"
LIFECYCLE = {"NEW", "DEVELOPING", "CONFIRMED", "FADING", "RESOLVED"}
PRIMARY_SOURCE_TYPES = {"official", "primary", "filing"}


def _client():
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = (
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        or os.environ.get("SUPABASE_SECRET_KEY", "").strip()
    )
    if not url or not key:
        raise RuntimeError(
            "Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_SECRET_KEY)."
        )
    return create_client(url, key)


def _parse_dt(value):
    if not value:
        return datetime(1970, 1, 1, tzinfo=timezone.utc)
    text = str(value).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        try:
            dt = datetime.fromisoformat(text + "T00:00:00+00:00")
        except ValueError:
            return datetime(1970, 1, 1, tzinfo=timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _load_json(path: Path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, list) else [payload]


def _slugify(value):
    text = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")
    return text[:100]


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _probability(value):
    number = _number(value)
    if number is None:
        return None
    if 0 <= number <= 1:
        number *= 100
    return max(0, min(100, number))


def _article_row(record, category):
    content = record.get("content") if isinstance(record.get("content"), dict) else {}
    impact = content.get("impact") if isinstance(content.get("impact"), dict) else {}
    lifecycle = str(record.get("status") or "NEW").upper()
    if lifecycle not in LIFECYCLE:
        lifecycle = "NEW"
    created = record.get("created_at") or datetime.now(timezone.utc).isoformat()
    return {
        "id": str(record["id"]),
        "story_key": str(record.get("story_key") or record["id"]),
        "category": category,
        "title": str(record.get("title") or "").strip(),
        "summary": str(record.get("summary") or "").strip() or None,
        "status": "published",
        "lifecycle_status": lifecycle,
        "published_at": record.get("published_at") or created,
        "created_at": created,
        "updated_at": created,
        "image_url": record.get("image_url"),
        "image_type": record.get("image_type"),
        "importance_score": _number(record.get("importance")),
        "confidence_score": _number(record.get("confidence")),
        "novelty_score": _number(content.get("novelty")),
        "urgency": impact.get("urgency") or record.get("urgency"),
        "record": record,
    }


def _source_rows(record):
    claims = record.get("claims") if isinstance(record.get("claims"), list) else []
    rows = []
    for index, source in enumerate(record.get("sources") or [], start=1):
        if not isinstance(source, dict) or not source.get("url"):
            continue
        supported = []
        for claim_index, claim in enumerate(claims, start=1):
            refs = claim.get("source_refs") if isinstance(claim, dict) else []
            if index in (refs or []):
                supported.append(claim_index)
        source_type = str(source.get("source_type") or "other").lower()
        rows.append({
            "article_id": str(record["id"]),
            "url": str(source["url"]),
            "publisher": source.get("publisher"),
            "title": source.get("title"),
            "published_at": source.get("published_at"),
            "source_type": source_type,
            "is_primary": source_type in PRIMARY_SOURCE_TYPES,
            "reliability": source.get("reliability"),
            "supports_claims": supported,
        })
    return rows


def _sync_sources(client, record, dry_run=False):
    """Converge normalized evidence rows without deleting the last known-good set first.

    Source rows are part of ALAM's trust surface, not decorative metadata. The previous
    incremental path deleted every source before inserting the replacement set. A
    transient PostgREST failure could therefore leave a newly published article with
    zero evidence until archive reconciliation happened to repair it later.

    Desired sources are now upserted first using the schema's ``(article_id, url)``
    uniqueness boundary. Stale rows are removed only after every desired source write
    succeeds. A failed upsert may leave an additive partial new set, but it cannot
    intentionally erase the previous good evidence set; a retry naturally converges.
    """
    sources = _source_rows(record)
    if dry_run:
        return len(sources)

    article_id = str(record["id"])
    desired_urls = {row["url"] for row in sources}

    # Write one row at a time so a deterministic failure can never be mistaken for a
    # successful batch. Cleanup begins only after all desired evidence rows are known
    # to have been accepted by Supabase.
    for source in sources:
        client.table("article_sources").upsert(
            source,
            on_conflict="article_id,url",
        ).execute()

    existing_rows = (
        client.table("article_sources")
        .select("id,url")
        .eq("article_id", article_id)
        .execute()
        .data
        or []
    )
    stale_ids = [
        str(row["id"])
        for row in existing_rows
        if row.get("id") is not None and row.get("url") not in desired_urls
    ]
    for source_id in stale_ids:
        client.table("article_sources").delete().eq("id", source_id).execute()
    return len(sources)


def _next_version(client, article_id):
    response = (
        client.table("article_versions")
        .select("version_no")
        .eq("article_id", article_id)
        .order("version_no", desc=True)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    return int(rows[0]["version_no"]) + 1 if rows else 1


def _topic_tags(record):
    """Return at most 30 unique normalized article tags in stable source order.

    Deduplication is by slug rather than ``(slug, label)`` because the database has
    one unique topic row per slug. Two display labels that normalize to the same slug
    must not cause repeated joins or make reconciliation depend on capitalization.
    """
    tags = []
    seen_slugs = set()
    for value in record.get("tags") or []:
        label = str(value).strip()
        slug = _slugify(label)
        if not slug or slug in seen_slugs:
            continue
        seen_slugs.add(slug)
        tags.append((slug, label))
        if len(tags) >= 30:
            break
    return tags


def _sync_topics(client, record, dry_run=False):
    """Converge article-topic links without a delete-before-insert outage window.

    The previous implementation deleted every existing link before resolving and
    inserting the desired topics. A transient failure after that delete could leave a
    published article with no topic relationships until a later reconciliation run.

    This implementation resolves and upserts *all* desired topics/joins first. Only
    after every desired link has been accepted do we read the current join set and
    remove stale links. If topic resolution or an upsert fails, the exception bubbles
    up while the previous good links remain available. This mirrors the evidence/source
    reconciliation safety rule and makes retry behavior naturally convergent.
    """
    tags = _topic_tags(record)
    if dry_run:
        return len(tags)

    article_id = str(record["id"])
    desired_topic_ids = set()

    for slug, label in tags:
        client.table("topics").upsert(
            {"slug": slug, "label": label},
            on_conflict="slug",
        ).execute()
        topic_rows = (
            client.table("topics")
            .select("id")
            .eq("slug", slug)
            .limit(1)
            .execute()
            .data
            or []
        )
        if not topic_rows or not topic_rows[0].get("id"):
            # Failing closed is important here. Treating an unresolved desired topic
            # as optional and continuing to cleanup could erase the previous join even
            # though Supabase never confirmed its replacement.
            raise RuntimeError(f"Supabase did not return an id for ALAM topic slug {slug!r}")

        topic_id = str(topic_rows[0]["id"])
        desired_topic_ids.add(topic_id)
        client.table("article_topics").upsert(
            {
                "article_id": article_id,
                "topic_id": topic_id,
                "weight": 1,
            },
            on_conflict="article_id,topic_id",
        ).execute()

    existing_rows = (
        client.table("article_topics")
        .select("topic_id")
        .eq("article_id", article_id)
        .execute()
        .data
        or []
    )
    stale_topic_ids = [
        str(row["topic_id"])
        for row in existing_rows
        if row.get("topic_id") is not None and str(row["topic_id"]) not in desired_topic_ids
    ]
    for topic_id in stale_topic_ids:
        client.table("article_topics").delete().eq("article_id", article_id).eq(
            "topic_id", topic_id
        ).execute()
    return len(tags)


def _prediction_status(value):
    raw = str(value or "OPEN").upper()
    if raw == "CONFIRMED":
        return "correct"
    if raw == "PARTLY_CONFIRMED":
        return "partially_correct"
    if raw == "WRONG":
        return "incorrect"
    if raw == "EXPIRED":
        return "unresolved"
    return "open"


def _sync_prediction(client, record, category, dry_run=False):
    content = record.get("content") if isinstance(record.get("content"), dict) else {}
    record_type = str(record.get("type") or "").lower()
    is_prediction = category == "trend" and (
        record_type in {"prediction", "correction"}
        or content.get("current_probability") is not None
        or content.get("initial_probability") is not None
    )
    if not is_prediction:
        return False

    article_id = str(record["id"])
    claim = content.get("statement") or record.get("title")
    row = {
        "article_id": article_id,
        "agent_id": str(record.get("agent") or category),
        "claim": str(claim or "").strip(),
        "horizon": content.get("horizon") or content.get("forecast_horizon"),
        "confidence": _probability(content.get("current_probability", content.get("initial_probability"))),
        "status": _prediction_status(content.get("status")),
        "resolution_notes": content.get("resolution_notes"),
        "created_at": record.get("created_at"),
        "resolved_at": record.get("created_at") if _prediction_status(content.get("status")) != "open" else None,
    }
    if dry_run:
        return True

    existing = client.table("predictions").select("id").eq("article_id", article_id).limit(1).execute().data or []
    if existing:
        client.table("predictions").update(row).eq("id", existing[0]["id"]).execute()
    else:
        client.table("predictions").insert(row).execute()
    return True


def sync_article(client, record, category, dry_run=False):
    if not isinstance(record, dict) or not record.get("id") or not record.get("title"):
        return "invalid"

    article_id = str(record["id"])
    incoming_dt = _parse_dt(record.get("created_at"))
    existing_rows = (
        client.table("articles")
        .select("id,created_at,record")
        .eq("id", article_id)
        .limit(1)
        .execute()
        .data
        or []
    ) if not dry_run else []

    if existing_rows:
        existing_dt = _parse_dt(existing_rows[0].get("created_at"))
        if incoming_dt <= existing_dt:
            return "unchanged"

    if dry_run:
        _sync_sources(client, record, dry_run=True)
        _sync_topics(client, record, dry_run=True)
        _sync_prediction(client, record, category, dry_run=True)
        return "would_publish"

    row = _article_row(record, category)
    client.table("articles").upsert(row, on_conflict="id").execute()

    version_no = _next_version(client, article_id)
    change = record.get("content") if isinstance(record.get("content"), dict) else {}
    change_summary = change.get("change_summary") if isinstance(change.get("change_summary"), dict) else None
    client.table("article_versions").insert({
        "article_id": article_id,
        "version_no": version_no,
        "lifecycle_status": row["lifecycle_status"],
        "change_summary": json.dumps(change_summary, ensure_ascii=False) if change_summary else None,
        "record": record,
        "created_at": record.get("created_at"),
    }).execute()

    _sync_sources(client, record)
    _sync_topics(client, record)
    _sync_prediction(client, record, category)
    return "published"


def sync_comment(client, record, dry_run=False):
    if not isinstance(record, dict):
        return "invalid"
    required = ("id", "story_id", "created_at", "agent", "persona_id", "body")
    if any(not record.get(key) for key in required):
        return "invalid"
    if dry_run:
        return "would_publish"
    client.table("agent_comments").upsert({
        "id": str(record["id"]),
        "article_id": str(record["story_id"]),
        "agent_id": str(record["agent"]).lower(),
        "persona_id": str(record["persona_id"]),
        "reply_to": str(record.get("reply_to")) if record.get("reply_to") else None,
        "stance": str(record.get("stance") or "").upper() or None,
        "comment": str(record["body"]),
        "status": "published",
        "record": record,
        "created_at": record["created_at"],
    }, on_conflict="id").execute()
    return "published"


def sync_wisdom(client, record, dry_run=False):
    if not isinstance(record, dict) or not record.get("date") or not record.get("question"):
        return "invalid"
    if dry_run:
        return "would_publish"
    client.table("wisdom_entries").upsert({
        "entry_date": str(record["date"]),
        "based_on": record.get("based_on"),
        "question": str(record["question"]),
        "verses": record.get("verses") or [],
        "record": record,
    }, on_conflict="entry_date").execute()
    return "published"


def _article_inputs():
    rows = []
    for category, folder in ARTICLE_DIRS.items():
        if not folder.exists():
            continue
        for path in sorted(folder.rglob("*.json")):
            if path.name.startswith("_"):
                continue
            for record in _load_json(path):
                if isinstance(record, dict):
                    rows.append((category, path, record))
    rows.sort(key=lambda item: _parse_dt(item[2].get("created_at")))
    return rows


def _comment_inputs():
    rows = []
    if COMMENTS_DIR.exists():
        for path in sorted(COMMENTS_DIR.rglob("*.json")):
            if path.name.startswith("_"):
                continue
            for record in _load_json(path):
                if isinstance(record, dict):
                    rows.append((path, record))
    rows.sort(key=lambda item: _parse_dt(item[1].get("created_at")))
    return rows


def _wisdom_inputs():
    rows = []
    if WISDOM_DIR.exists():
        for path in sorted(WISDOM_DIR.glob("*.json")):
            if path.name.startswith("_"):
                continue
            for record in _load_json(path):
                if isinstance(record, dict):
                    rows.append((path, record))
    rows.sort(key=lambda item: str(item[1].get("date") or ""))
    return rows


def rebuild_shared_signal_relationships(client, dry_run=False):
    """Create non-causal Connect-the-Dots links from explicit connection tags."""
    if dry_run:
        return 0
    response = client.table("articles").select("id,record").eq("status", "published").execute()
    tag_to_articles = defaultdict(set)
    for row in response.data or []:
        record = row.get("record") if isinstance(row.get("record"), dict) else {}
        content = record.get("content") if isinstance(record.get("content"), dict) else {}
        for tag in content.get("connection_tags") or []:
            slug = _slugify(tag)
            if slug:
                tag_to_articles[slug].add(str(row["id"]))

    pairs = defaultdict(set)
    for tag, ids in tag_to_articles.items():
        ordered = sorted(ids)
        for i, left in enumerate(ordered):
            for right in ordered[i + 1:]:
                pairs[(left, right)].add(tag)

    client.table("article_relationships").delete().eq("relationship", "shared_signal").execute()
    rows = []
    for (left, right), tags in pairs.items():
        rows.append({
            "from_article_id": left,
            "to_article_id": right,
            "relationship": "shared_signal",
            "strength": min(1, len(tags) / 3),
            "explanation": "Shared ALAM connection tags: " + ", ".join(sorted(tags)[:6]),
        })
    if rows:
        for start in range(0, len(rows), 200):
            client.table("article_relationships").insert(rows[start:start + 200]).execute()
    return len(rows)


def run(dry_run=False):
    client = _client()
    stats = defaultdict(int)

    for category, path, record in _article_inputs():
        try:
            result = sync_article(client, record, category, dry_run=dry_run)
        except Exception as exc:
            print(f"ARTICLE ERROR {path}: {exc}", file=sys.stderr)
            stats["article_errors"] += 1
            continue
        stats[f"article_{result}"] += 1

    for path, record in _comment_inputs():
        try:
            result = sync_comment(client, record, dry_run=dry_run)
        except Exception as exc:
            print(f"COMMENT ERROR {path}: {exc}", file=sys.stderr)
            stats["comment_errors"] += 1
            continue
        stats[f"comment_{result}"] += 1

    for path, record in _wisdom_inputs():
        try:
            result = sync_wisdom(client, record, dry_run=dry_run)
        except Exception as exc:
            print(f"WISDOM ERROR {path}: {exc}", file=sys.stderr)
            stats["wisdom_errors"] += 1
            continue
        stats[f"wisdom_{result}"] += 1

    try:
        stats["relationships"] = rebuild_shared_signal_relationships(client, dry_run=dry_run)
    except Exception as exc:
        print(f"RELATIONSHIP ERROR: {exc}", file=sys.stderr)
        stats["relationship_errors"] += 1

    print(json.dumps(dict(sorted(stats.items())), indent=2, ensure_ascii=False))
    return 1 if any(key.endswith("_errors") and value for key, value in stats.items()) else 0


def main():
    parser = argparse.ArgumentParser(description="Sync ALAM GitHub JSON audit data into Supabase.")
    parser.add_argument("--dry-run", action="store_true", help="Validate/scan without writing database rows.")
    args = parser.parse_args()
    raise SystemExit(run(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
