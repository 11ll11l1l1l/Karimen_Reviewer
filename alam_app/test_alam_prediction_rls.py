from pathlib import Path


MIGRATION = Path(__file__).resolve().parents[1] / "supabase" / "migrations" / "023_scope_public_predictions.sql"


def _sql():
    return " ".join(MIGRATION.read_text(encoding="utf-8").lower().split())


def test_public_predictions_follow_published_article_boundary():
    sql = _sql()
    assert 'drop policy if exists "public can read predictions"' in sql
    assert 'create policy "public can read predictions"' in sql
    assert "from public.articles as article" in sql
    assert "article.id = predictions.article_id" in sql
    assert "article.status = 'published'" in sql
    assert "using ( true )" not in sql


def test_public_prediction_updates_require_published_parent_article():
    sql = _sql()
    assert 'drop policy if exists "public can read prediction updates"' in sql
    assert 'create policy "public can read prediction updates"' in sql
    assert "from public.predictions as prediction" in sql
    assert "join public.articles as article" in sql
    assert "prediction.id = prediction_updates.prediction_id" in sql
    assert "article.id = prediction.article_id" in sql
    assert "article.status = 'published'" in sql


def test_prediction_rls_migration_is_replay_safe_and_non_destructive():
    sql = _sql()
    assert sql.count("drop policy if exists") == 2
    for destructive in ("drop table", "truncate table", "delete from"):
        assert destructive not in sql
