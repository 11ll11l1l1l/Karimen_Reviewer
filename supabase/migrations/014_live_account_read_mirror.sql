-- Keep authenticated ALAM reading history current without requiring a manual Settings sync.
--
-- Anonymous/browser-first use remains authoritative: every article_open is still recorded
-- in app_events by the existing constrained RPC. When that visitor has explicitly linked
-- their browser identity to an Auth account, this AFTER INSERT trigger mirrors the exact
-- event into the RLS-protected article_reads table. source_event_id is already unique, so
-- retries/imports remain idempotent and the original anonymous audit event is never removed.

create or replace function public.alam_mirror_linked_article_read()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_user uuid;
begin
  if new.event_name <> 'article_open'
     or new.article_id is null
     or new.visitor_id is null then
    return new;
  end if;

  select l.user_id
    into v_user
  from public.account_visitor_links l
  where l.visitor_id = new.visitor_id
  limit 1;

  if v_user is null then
    return new;
  end if;

  -- Do not allow an event carrying a stale/unknown article ID to break the anonymous
  -- event write. The public article FK remains the source of truth for account history.
  if not exists (
    select 1
    from public.articles a
    where a.id = new.article_id
  ) then
    return new;
  end if;

  insert into public.article_reads (
    user_id,
    article_id,
    opened_at,
    source_event_id
  )
  values (
    v_user,
    new.article_id,
    new.created_at,
    new.id
  )
  on conflict do nothing;

  return new;
end;
$$;

-- This function is an internal trigger implementation, not a client API.
revoke all on function public.alam_mirror_linked_article_read() from public;
revoke all on function public.alam_mirror_linked_article_read() from anon;
revoke all on function public.alam_mirror_linked_article_read() from authenticated;

drop trigger if exists alam_mirror_linked_article_read_after_insert on public.app_events;

create trigger alam_mirror_linked_article_read_after_insert
after insert on public.app_events
for each row
execute function public.alam_mirror_linked_article_read();
