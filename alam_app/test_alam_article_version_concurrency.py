from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "016_serialize_article_version_capture.sql"


def main() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    required = (
        "create or replace function internal.alam_capture_article_version()",
        "perform pg_advisory_xact_lock(hashtextextended(new.id, 0))",
        "select coalesce(max(v.version_no), 0) + 1",
        "insert into public.article_versions",
        "revoke all on function internal.alam_capture_article_version() from public",
        "revoke all on function internal.alam_capture_article_version() from anon",
        "revoke all on function internal.alam_capture_article_version() from authenticated",
    )
    missing = [needle for needle in required if needle not in sql]
    assert not missing, f"Article-version concurrency guard is incomplete: {missing}"

    # The per-article lock must be acquired before dedupe/version allocation so two
    # concurrent writers cannot both observe the same MAX(version_no).
    lock_pos = sql.index("pg_advisory_xact_lock")
    exists_pos = sql.index("if exists")
    max_pos = sql.index("select coalesce(max(v.version_no), 0) + 1")
    assert lock_pos < exists_pos < max_pos

    destructive = (
        "drop table",
        "truncate ",
        "delete from",
        "drop schema",
        "alter table public.articles drop",
        "alter table public.article_versions drop",
    )
    found = [needle for needle in destructive if needle in sql]
    assert not found, f"Concurrency migration must remain non-destructive: {found}"

    print("ALAM article-version concurrency regression checks passed")


if __name__ == "__main__":
    main()
