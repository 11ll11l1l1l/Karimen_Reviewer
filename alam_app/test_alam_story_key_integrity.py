"""Regression coverage for ALAM durable story identity."""

from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "supabase"
    / "migrations"
    / "032_enforce_unique_article_story_key.sql"
)


def test_story_key_unique_index_is_durable_and_replay_safe():
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "create unique index if not exists articles_story_key_unique_idx" in sql
    assert "on public.articles (story_key)" in sql
    assert "where story_key is not null" in sql

    for destructive in ("drop table", "truncate", "delete from public.articles"):
        assert destructive not in sql
