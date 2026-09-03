from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "015_article_version_sync_and_nisa_daily_guard.sql"


def main() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    required = (
        "create or replace function internal.alam_capture_article_version()",
        "set search_path = public, pg_temp",
        "from public.article_versions",
        "insert into public.article_versions",
        "drop trigger if exists trg_alam_capture_article_version on public.articles",
        "create trigger trg_alam_capture_article_version",
        "after insert or update of record, lifecycle_status on public.articles",
        "create unique index if not exists uq_articles_nisa_daily_date",
        "record ->> 'nisa_date'",
        "record ->> 'type'",
        "= 'nisa_daily'",
        "revoke all on function internal.alam_capture_article_version() from public",
        "revoke all on function internal.alam_capture_article_version() from anon",
        "revoke all on function internal.alam_capture_article_version() from authenticated",
    )
    missing = [needle for needle in required if needle not in sql]
    assert not missing, f"Migration lost required recovery semantics: {missing}"

    destructive = (
        "drop table",
        "truncate ",
        "delete from",
        "drop schema",
        "alter table public.articles drop",
        "alter table public.article_versions drop",
    )
    found = [needle for needle in destructive if needle in sql]
    assert not found, f"Recovery migration must remain non-destructive: {found}"

    # A no-change UPDATE must not manufacture a duplicate historical version.
    assert "new.record is not distinct from old.record" in sql
    assert "new.lifecycle_status is not distinct from old.lifecycle_status" in sql
    assert "v.record = new.record" in sql

    print("ALAM article-version migration regression checks passed")


if __name__ == "__main__":
    main()
