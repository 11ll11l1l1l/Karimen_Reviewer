from pathlib import Path


MIGRATION = Path(__file__).resolve().parents[1] / "supabase" / "migrations" / "022_scope_public_article_links.sql"


def _sql():
    return " ".join(MIGRATION.read_text(encoding="utf-8").lower().split())


def test_public_article_topic_links_follow_published_parent_boundary():
    sql = _sql()
    assert 'drop policy if exists "public can read article topics"' in sql
    assert 'create policy "public can read article topics"' in sql
    assert "from public.articles as article" in sql
    assert "article.id = article_topics.article_id" in sql
    assert "article.status = 'published'" in sql
    assert "using ( true )" not in sql


def test_public_relationships_require_both_published_endpoints():
    sql = _sql()
    assert 'drop policy if exists "public can read article relationships"' in sql
    assert 'create policy "public can read article relationships"' in sql
    assert "source_article.id = article_relationships.from_article_id" in sql
    assert "source_article.status = 'published'" in sql
    assert "target_article.id = article_relationships.to_article_id" in sql
    assert "target_article.status = 'published'" in sql


def test_link_rls_migration_is_replay_safe_and_non_destructive():
    sql = _sql()
    assert "drop policy if exists" in sql
    for destructive in ("drop table", "truncate table", "delete from"):
        assert destructive not in sql
