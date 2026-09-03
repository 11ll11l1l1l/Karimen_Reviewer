"""Static regression contract for automatic linked-account read-history mirroring."""

from pathlib import Path


def main():
    migration = (
        Path(__file__).resolve().parents[1]
        / "supabase"
        / "migrations"
        / "014_live_account_read_mirror.sql"
    ).read_text(encoding="utf-8")
    lowered = migration.lower()

    assert "after insert on public.app_events" in lowered
    assert "for each row" in lowered
    assert "new.event_name <> 'article_open'" in lowered
    assert "new.article_id is null" in lowered
    assert "new.visitor_id is null" in lowered
    assert "public.account_visitor_links" in lowered
    assert "public.article_reads" in lowered
    assert "source_event_id" in lowered
    assert "new.id" in lowered
    assert "new.created_at" in lowered
    assert "on conflict do nothing" in lowered
    assert "security definer" in lowered
    assert "set search_path = ''" in lowered
    assert "revoke all on function public.alam_mirror_linked_article_read() from public" in lowered
    assert "revoke all on function public.alam_mirror_linked_article_read() from anon" in lowered
    assert "revoke all on function public.alam_mirror_linked_article_read() from authenticated" in lowered
    assert "delete from public.app_events" not in lowered
    assert "delete from public.article_reads" not in lowered

    print("ALAM live linked-account read mirror contract checks passed")


if __name__ == "__main__":
    main()
