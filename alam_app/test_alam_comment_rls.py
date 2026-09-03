from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "025_scope_public_agent_comments.sql"


def _migration_text() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_public_comments_require_published_comment_and_parent_article():
    text = _migration_text()
    assert "status = 'published'" in text
    assert "article.status = 'published'" in text
    assert "article.id = agent_comments.article_id" in text
    assert "to anon, authenticated" in text


def test_comment_policy_migration_is_replay_safe_and_non_destructive():
    text = _migration_text()
    assert 'drop policy if exists "public can read published comments"' in text
    assert "delete from" not in text
    assert "truncate" not in text
    assert "drop table" not in text
