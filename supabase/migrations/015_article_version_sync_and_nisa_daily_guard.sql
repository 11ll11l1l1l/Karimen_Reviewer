-- Repository backfill of the live article-version synchronization and NISA daily guard.
--
-- This migration intentionally mirrors the already-deployed production behavior so a fresh
-- environment, disaster-recovery restore, or branch database can reproduce the same schema.
-- It is idempotent and does not rewrite or delete historical article data.

create schema if not exists internal;

create or replace function internal.alam_capture_article_version()
returns trigger
language plpgsql
set search_path = public, pg_temp
as $$
declare
  v_next integer;
begin
  if tg_op = 'UPDATE'
     and new.record is not distinct from old.record
     and new.lifecycle_status is not distinct from old.lifecycle_status then
    return new;
  end if;

  if exists (
    select 1
    from public.article_versions v
    where v.article_id = new.id
      and v.record = new.record
      and v.lifecycle_status is not distinct from new.lifecycle_status
  ) then
    return new;
  end if;

  select coalesce(max(v.version_no), 0) + 1
    into v_next
  from public.article_versions v
  where v.article_id = new.id;

  insert into public.article_versions (
    article_id,
    version_no,
    lifecycle_status,
    change_summary,
    record,
    created_at
  )
  values (
    new.id,
    v_next,
    new.lifecycle_status,
    case
      when tg_op = 'INSERT' then 'Automatic initial snapshot'
      else 'Automatic synchronized snapshot'
    end,
    new.record,
    coalesce(new.updated_at, new.created_at, now())
  );

  return new;
end;
$$;

-- Trigger implementations are internal infrastructure, not browser-callable API functions.
revoke all on function internal.alam_capture_article_version() from public;
revoke all on function internal.alam_capture_article_version() from anon;
revoke all on function internal.alam_capture_article_version() from authenticated;

drop trigger if exists trg_alam_capture_article_version on public.articles;

create trigger trg_alam_capture_article_version
after insert or update of record, lifecycle_status on public.articles
for each row
execute function internal.alam_capture_article_version();

-- Exactly one published nisa_daily record per nisa_date. The partial index leaves all other
-- article types unaffected and preserves the JSON audit record as the canonical value source.
create unique index if not exists uq_articles_nisa_daily_date
  on public.articles ((record ->> 'nisa_date'))
  where (record ->> 'type') = 'nisa_daily';
