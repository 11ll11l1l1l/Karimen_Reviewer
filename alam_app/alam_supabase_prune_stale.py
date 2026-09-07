"""Prune Supabase article rows that are no longer represented by GitHub audit data.

This module is executed only inside the canonical ALAM Supabase sync workflow after
normal reconciliation succeeds. GitHub remains the publication source of truth.

Deletion is deliberately fail-closed around user-linked state. If an obsolete mirror
article still has saved/read/feedback/notification rows, nothing is deleted and the
workflow fails for operator review instead of silently destroying user data.
"""

from __future__ import annotations

import json

from alam_supabase_ingest import _client
from alam_supabase_reconcile import prepare_public_archive

USER_STATE_TABLES = (
    "saved_articles",
    "article_reads",
    "article_feedback",
    "notifications",
)


def _stale_ids(existing_ids, desired_ids):
    return sorted(set(existing_ids) - set(desired_ids))


def _has_reference(client, table_name, article_id):
    response = (
        client.table(table_name)
        .select("article_id")
        .eq("article_id", article_id)
        .limit(1)
        .execute()
    )
    return bool(response.data or [])


def prune_stale_articles(client, prepared_archive=None):
    archive = prepared_archive if prepared_archive is not None else prepare_public_archive()
    desired_ids = set(archive)

    response = client.table("articles").select("id").execute()
    existing_ids = [row.get("id") for row in (response.data or []) if row.get("id")]
    stale = _stale_ids(existing_ids, desired_ids)

    blockers = []
    for article_id in stale:
        for table_name in USER_STATE_TABLES:
            if _has_reference(client, table_name, article_id):
                blockers.append((article_id, table_name))

    if blockers:
        detail = ", ".join(f"{article_id}:{table_name}" for article_id, table_name in blockers)
        raise RuntimeError(
            "Refusing to prune stale ALAM mirror articles because user-linked state exists: "
            + detail
        )

    deleted_predictions = 0
    deleted_articles = 0
    for article_id in stale:
        # predictions.article_id uses SET NULL, so remove this derived public mirror
        # row explicitly before deleting the article. Other normalized public mirror
        # tables cascade from articles. app_events intentionally survives with NULL.
        pred = client.table("predictions").delete().eq("article_id", article_id).execute()
        deleted_predictions += len(pred.data or [])
        deleted = client.table("articles").delete().eq("id", article_id).execute()
        deleted_articles += len(deleted.data or [])

    return {
        "archive_article_ids": len(desired_ids),
        "existing_article_ids_before_prune": len(existing_ids),
        "stale_article_ids": len(stale),
        "stale_articles_deleted": deleted_articles,
        "stale_predictions_deleted": deleted_predictions,
    }


def main():
    stats = prune_stale_articles(_client())
    print("ALAM stale mirror pruning:")
    print(json.dumps(stats, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
